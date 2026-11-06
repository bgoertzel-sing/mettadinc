"""Example 2: the access-policy module, read from its source into a typed intermediate form.

This file is the only route from access_policy.metta to the obligations, reachable sets and
witnesses of the oracle.  The module is read with a small reader; imports are resolved (Only
lists; a name is looked up in the module that declares the map being elaborated); the Families
forms (Parameters, For, Switch, Exists, ForAll) are expanded and constants folded; and every map
into Bool or Word is elaborated into a typed term over the bits of one word variable, with its
declared From and To types checked.  The intermediate form (IR) has three consumers:

  IR.eval / Policy.step     evaluation on numpy arrays of words and on single words
  CNF.lit                   the Tseitin encoding, which records the definition of every gate
  Policy.guarded            the normal form "if g then set these bits" used by the BDD images

SourceInterpreter evaluates the source terms directly, without the IR, on numpy arrays of words.
The oracle compares the interpreter, the IR and the CNF point by point on a two-user instance of
the same source.  An instance is chosen by restricting the User carrier; the Word width is then
ten bits per user.
"""
import hashlib
import re

import numpy as np

TOKEN = re.compile(r'\s*(?:(;[^\n]*)|("(?:[^"\\]|\\.)*")|([()])|(!)|([^\s()";!]+))')
INT = re.compile(r"-?\d+")


class ElabError(Exception):
    """A declaration or term outside the admitted fragment (the checker's InvalidInput)."""


# ------------------------------------------------------------------------------------ reader
def read_forms(text):
    """Top-level forms of a module file: ("form", sexpr) or ("run", sexpr)."""
    pos, stack = 0, [[]]
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ElabError(f"cannot read the source at offset {pos}")
        pos = m.end()
        comment, string, paren, bang, atom = m.groups()
        if comment is not None:
            continue
        if paren == "(":
            stack.append([])
        elif paren == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif bang:
            stack[-1].append("!")
        elif string is not None:
            stack[-1].append(string)
        elif atom is not None:
            stack[-1].append(atom)
    if len(stack) != 1:
        raise ElabError("unbalanced parentheses")
    items, forms, i = stack[0], [], 0
    while i < len(items):
        if items[i] == "!":
            forms.append(("run", items[i + 1]))
            i += 2
        else:
            forms.append(("form", items[i]))
            i += 1
    return forms


def show(x):
    return x if isinstance(x, str) else "(" + " ".join(show(y) for y in x) + ")"


class Module:
    def __init__(self, form):
        if form[0] != "DC.Module":
            raise ElabError(f"not a module: {show(form)[:60]}")
        self.name, self.items = form[1], form[2:]
        self.decls, self.imports = {}, []
        for it in self.items:
            if not isinstance(it, list) or not it or it == ["..."]:
                continue
            if it[0] == "Import":
                only = next(x for x in it[2:] if isinstance(x, list) and x[0] == "Only")
                self.imports.append((it[1], only[1:]))
            elif it[0] not in ("Profile", "Use") and len(it) > 1 and isinstance(it[1], str):
                self.decls[it[1]] = it


class Source:
    """The parsed file: modules by name, run requests, and the digest of the exact text."""

    def __init__(self, text, name="access_policy.metta"):
        self.text, self.name = text, name
        self.digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        self.modules, self.runs = {}, []
        for kind, form in read_forms(text):
            if kind == "form":
                m = Module(form)
                self.modules[m.name] = m
            else:
                self.runs.append(form)

    def lookup(self, mod, name):
        m = self.modules[mod]
        if name in m.decls:
            return mod, m.decls[name]
        for src, names in m.imports:
            if name in names:
                return self.lookup(src, name)
        return None

    @staticmethod
    def field(decl, key):
        for x in decl[2:]:
            if isinstance(x, list) and x and x[0] == key:
                return x
        return None

    @staticmethod
    def fields(decl, key):
        return [x for x in decl[2:] if isinstance(x, list) and x and x[0] == key]


# ------------------------------------------------------------------------------------ the IR
class IR:
    """Hash-consed Boolean terms over the bits of one word.  Node 0 is True, node 1 is False.
    Kinds: ("bit", i), ("not", a), ("and", (a, ...)), ("or", (a, ...)), ("ite", c, t, e).
    The constructors fold constants, flatten nested and/or, and drop duplicates."""
    TRUE, FALSE = 0, 1

    def __init__(self):
        self.nodes = [("true",), ("false",)]
        self.table = {("true",): 0, ("false",): 1}

    def mk(self, key):
        n = self.table.get(key)
        if n is None:
            n = len(self.nodes)
            self.nodes.append(key)
            self.table[key] = n
        return n

    def BIT(self, i):
        return self.mk(("bit", i))

    def NOT(self, a):
        if a == self.TRUE:
            return self.FALSE
        if a == self.FALSE:
            return self.TRUE
        k = self.nodes[a]
        if k[0] == "not":
            return k[1]
        return self.mk(("not", a))

    def _nary(self, kind, args, unit, zero):
        flat = []
        for a in args:
            k = self.nodes[a]
            flat.extend(k[1] if k[0] == kind else (a,))
        out, seen = [], set()
        for a in flat:
            if a == zero:
                return zero
            if a == unit or a in seen:
                continue
            seen.add(a)
            out.append(a)
        if any(self.NOT(a) in seen for a in out):
            return zero
        if not out:
            return unit
        if len(out) == 1:
            return out[0]
        return self.mk((kind, tuple(out)))

    def AND(self, args):
        return self._nary("and", args, self.TRUE, self.FALSE)

    def OR(self, args):
        return self._nary("or", args, self.FALSE, self.TRUE)

    def ITE(self, c, t, e):
        T, Fa = self.TRUE, self.FALSE
        if c == T or t == e:
            return t
        if c == Fa:
            return e
        if t == T and e == Fa:
            return c
        if t == Fa and e == T:
            return self.NOT(c)
        if t == T:
            return self.OR([c, e])
        if t == Fa:
            return self.AND([self.NOT(c), e])
        if e == T:
            return self.OR([self.NOT(c), t])
        if e == Fa:
            return self.AND([c, t])
        return self.mk(("ite", c, t, e))

    def support(self, n, memo=None):
        memo = {} if memo is None else memo
        if n in memo:
            return memo[n]
        k = self.nodes[n]
        if k[0] == "bit":
            s = frozenset([k[1]])
        elif k[0] in ("true", "false"):
            s = frozenset()
        elif k[0] == "not":
            s = self.support(k[1], memo)
        elif k[0] in ("and", "or"):
            s = frozenset().union(*[self.support(a, memo) for a in k[1]])
        else:
            s = self.support(k[1], memo) | self.support(k[2], memo) | self.support(k[3], memo)
        memo[n] = s
        return s

    def eval(self, n, X, memo=None):
        """Value of node n on a numpy array X of words (uint64): a boolean array."""
        memo = {} if memo is None else memo
        stack = [n]
        while stack:
            m = stack[-1]
            if m in memo:
                stack.pop()
                continue
            k = self.nodes[m]
            kids = [] if k[0] in ("true", "false", "bit") else (
                [k[1]] if k[0] == "not" else list(k[1]) if k[0] in ("and", "or") else [k[1], k[2], k[3]])
            todo = [c for c in kids if c not in memo]
            if todo:
                stack.extend(todo)
                continue
            stack.pop()
            if k[0] == "true":
                v = np.ones(X.shape, dtype=bool)
            elif k[0] == "false":
                v = np.zeros(X.shape, dtype=bool)
            elif k[0] == "bit":
                v = ((X >> np.uint64(k[1])) & np.uint64(1)).astype(bool)
            elif k[0] == "not":
                v = ~memo[k[1]]
            elif k[0] == "and":
                v = np.logical_and.reduce([memo[c] for c in k[1]])
            elif k[0] == "or":
                v = np.logical_or.reduce([memo[c] for c in k[1]])
            else:
                v = np.where(memo[k[1]], memo[k[2]], memo[k[3]])
            memo[m] = v
        return memo[n]

    def pyexpr(self, n):
        """Python source of node n over an integer variable x (used to compile guards)."""
        k = self.nodes[n]
        if k[0] == "true":
            return "True"
        if k[0] == "false":
            return "False"
        if k[0] == "bit":
            return f"(x >> {k[1]} & 1 == 1)"
        if k[0] == "not":
            return f"(not {self.pyexpr(k[1])})"
        if k[0] == "and":
            return "(" + " and ".join(self.pyexpr(a) for a in k[1]) + ")"
        if k[0] == "or":
            return "(" + " or ".join(self.pyexpr(a) for a in k[1]) + ")"
        return f"({self.pyexpr(k[2])} if {self.pyexpr(k[1])} else {self.pyexpr(k[3])})"


# word terms: ("var",), ("set", w, i, b) with b a node, ("if", c, w1, w2)
VAR = ("var",)


class Elaborator:
    """Elaborates the maps, machines and partitions of one module into the IR.

    Typed values: ("word", wterm), ("bool", node), ("bitval", node) for the Nat 0/1 that BitAt
    returns, ("nat", int), ("sym", element), ("bits", [node, ...]) for BitVector results."""

    def __init__(self, source, users=None):
        self.src = source
        self.ir = IR()
        self.carriers = {}
        for m in source.modules.values():
            for d in m.decls.values():
                if d[0] == "Carrier":
                    en = next((x for x in d[2:] if isinstance(x, list) and x and x[0] == "Enum"), None)
                    if en is not None:
                        self.carriers.setdefault(d[1], [e for e in en[1:]])
        if users is not None:
            self.carriers["User"] = list(users)
        self.width = 10 * len(self.carriers["User"])
        self.elements = {e for es in self.carriers.values() for e in es}
        self._bits, self._apply = {}, {}

    # ---------------------------------------------------------------- word terms to bits
    def bits(self, w):
        key = id(w)
        hit = self._bits.get(key)
        if hit is not None and hit[0] is w:
            return hit[1]
        ir = self.ir
        if w == VAR:
            out = [ir.BIT(i) for i in range(self.width)]
        elif w[0] == "set":
            out = list(self.bits(w[1]))
            if not 0 <= w[2] < self.width:
                raise ElabError(f"SetBit index {w[2]} outside the word")
            out[w[2]] = w[3]
        else:
            a, b = self.bits(w[2]), self.bits(w[3])
            out = [ir.ITE(w[1], x, y) for x, y in zip(a, b)]
        self._bits[key] = (w, out)
        return out

    def guarded(self, w):
        """(guard, {bit: 0|1}) when w is "if g then set these bits", else None."""
        def sets(t):
            writes = {}
            while t != VAR:
                if t[0] != "set" or t[3] not in (IR.TRUE, IR.FALSE):
                    return None
                writes.setdefault(t[2], 1 if t[3] == IR.TRUE else 0)
                t = t[1]
            return writes
        s = sets(w)
        if s is not None:
            return IR.TRUE, s
        if w[0] == "if":
            if w[3] == VAR and sets(w[2]) is not None:
                return w[1], sets(w[2])
            if w[2] == VAR and sets(w[3]) is not None:
                return self.ir.NOT(w[1]), sets(w[3])
        return None

    # ---------------------------------------------------------------- types
    def type_of(self, mod, t):
        if t == "Bool":
            return "bool"
        if t == "Nat":
            return "nat"
        if isinstance(t, list) and t[0] == "BitVector":
            return "bits"
        hit = self.src.lookup(mod, t)
        if hit and hit[1][0] == "Carrier":
            of = self.src.field(hit[1], "Of")
            if of and isinstance(of[1], list) and of[1][0] == "BitVector":
                return "word"
            if of and of[1] == "Symbol":
                return "sym"
        raise ElabError(f"unknown type {show(t)}")

    def static(self, v, kind):
        if v[0] != kind:
            raise ElabError(f"expected a static {kind}, found {v[0]}")
        return v[1]

    def boolof(self, v):
        if v[0] != "bool":
            raise ElabError(f"expected Bool, found {v[0]}")
        return v[1]

    # ---------------------------------------------------------------- terms
    def elab(self, mod, t, env, params):
        ir = self.ir
        if isinstance(t, str):
            if t.startswith("$"):
                if t in env:
                    return env[t]
                if t in params:
                    return params[t]
                raise ElabError(f"unbound variable {t}")
            if INT.fullmatch(t):
                return ("nat", int(t))
            if t == "True":
                return ("bool", IR.TRUE)
            if t == "False":
                return ("bool", IR.FALSE)
            if t in self.elements:
                return ("sym", t)
            hit = self.src.lookup(mod, t)
            if hit and hit[1][0] == "Const":
                return ("nat", int(hit[1][3]))
            raise ElabError(f"unknown name {t}")
        h = t[0]
        E = lambda y: self.elab(mod, y, env, params)  # noqa: E731
        if h == "Eq":
            return self.eq(E(t[1]), E(t[2]))
        if h == "BitAt":
            w = E(t[1])
            if w[0] != "word":
                raise ElabError("BitAt needs a word")
            i = self.static(E(t[2]), "nat")
            if not 0 <= i < self.width:
                raise ElabError(f"BitAt index {i} outside the word")
            return ("bitval", self.bits(w[1])[i])
        if h == "SetBit":
            w = E(t[1])
            if w[0] != "word":
                raise ElabError("SetBit needs a word")
            i, v = self.static(E(t[2]), "nat"), self.static(E(t[3]), "nat")
            if v not in (0, 1):
                raise ElabError("SetBit value must be 0 or 1")
            return ("word", ("set", w[1], i, IR.TRUE if v else IR.FALSE))
        if h == "Add":
            return ("nat", sum(self.static(E(a), "nat") for a in t[1:]))
        if h == "Not":
            return ("bool", ir.NOT(self.boolof(E(t[1]))))
        if h == "And":
            return ("bool", ir.AND([self.boolof(E(a)) for a in t[1:]]))
        if h == "Or":
            return ("bool", ir.OR([self.boolof(E(a)) for a in t[1:]]))
        if h == "If":
            c = self.boolof(E(t[1]))
            if c == IR.TRUE:
                return E(t[2])
            if c == IR.FALSE:
                return E(t[3])
            a, b = E(t[2]), E(t[3])
            if a[0] == b[0] == "word":
                return ("word", ("if", c, a[1], b[1]))
            if a[0] == b[0] == "bool":
                return ("bool", ir.ITE(c, a[1], b[1]))
            raise ElabError("If branches of different types")
        if h == "Switch":
            v = E(t[1])
            if v[0] != "sym":
                raise ElabError("Switch needs a parameter over an enumerated carrier")
            carrier = next(c for c, es in self.carriers.items() if v[1] in es)
            keys = [case[0] for case in t[2:]]
            full = self.src_carrier(carrier)
            if sorted(keys) != sorted(full) or len(set(keys)) != len(keys):
                raise ElabError(f"Switch on {carrier} is not total and exclusive")
            return E(next(case[1] for case in t[2:] if case[0] == v[1]))
        if h in ("Exists", "ForAll"):
            var, carrier, body = t[1], t[2], t[3]
            parts = [self.boolof(self.elab(mod, body, dict(env, **{var: ("sym", e)}), params))
                     for e in self.carriers[carrier]]
            return ("bool", ir.OR(parts) if h == "Exists" else ir.AND(parts))
        if h == "Gather":
            w = E(t[1])
            idx = [self.static(E(a), "nat") for a in t[2:]]
            return ("bits", [self.bits(w[1])[i] for i in idx])
        if h == "Slice":
            w = E(t[1])
            lo, hi = self.static(E(t[2]), "nat"), self.static(E(t[3]), "nat")
            return ("bits", self.bits(w[1])[lo:hi + 1])
        hit = self.src.lookup(mod, h)
        if hit and hit[1][0] == "Map":
            return self.apply(hit[0], hit[1], [E(a) for a in t[1:]])
        raise ElabError(f"cannot elaborate {show(t)[:80]}")

    def src_carrier(self, name):
        """The carrier as declared in the source (Switch totality is checked against it)."""
        for m in self.src.modules.values():
            d = m.decls.get(name)
            if d is not None and d[0] == "Carrier":
                en = next(x for x in d[2:] if isinstance(x, list) and x and x[0] == "Enum")
                return list(en[1:])
        raise ElabError(f"unknown carrier {name}")

    def eq(self, a, b):
        ir = self.ir
        static = ("nat", "sym")
        if a[0] in static and b[0] in static:
            return ("bool", IR.TRUE if a == b else IR.FALSE)
        if b[0] == "bitval":
            a, b = b, a
        if a[0] == "bitval" and b[0] == "nat":
            return ("bool", a[1] if b[1] == 1 else ir.NOT(a[1]) if b[1] == 0 else IR.FALSE)
        if a[0] in ("bool", "bitval") and b[0] in ("bool", "bitval") and a[0] == b[0]:
            p, q = a[1], b[1]
            return ("bool", ir.OR([ir.AND([p, q]), ir.AND([ir.NOT(p), ir.NOT(q)])]))
        raise ElabError(f"Eq of {a[0]} and {b[0]}")

    def apply(self, mod, decl, args):
        name = decl[1]
        par = self.src.field(decl, "Parameters")
        npar = len(par) - 1 if par else 0
        params = {}
        for (pv, pc), a in zip(par[1:] if par else [], args[:npar]):
            if a[0] != "sym" or a[1] not in self.carriers[pc]:
                raise ElabError(f"{name}: parameter {pv} must be an element of {pc}")
            params[pv] = a
        rest = args[npar:]
        if len(rest) != 1:
            raise ElabError(f"{name} is unary after its parameters, given {len(rest)} arguments")
        arg = rest[0]
        frm = self.type_of(mod, self.src.field(decl, "From")[1])
        to = self.type_of(mod, self.src.field(decl, "To")[1])
        if arg[0] != frm and not (frm == "nat" and arg[0] == "nat"):
            raise ElabError(f"{name}: argument of type {arg[0]}, declared From {frm}")
        key = None
        if arg[0] == "word" and arg[1] == VAR or arg[0] in ("sym", "nat"):
            key = (mod, name, tuple(sorted((k, v[1]) for k, v in params.items())), arg[0], arg[1] if arg[0] != "word" else "var")
            if key in self._apply:
                return self._apply[key]
        body = decl[-1]
        if body[0] == "Body":
            out = self.elab(mod, body[2], {body[1][0]: arg}, params)
        elif body[0] == "Table":
            v = arg[1]
            row = next((r for r in body[1:] if self.elab(mod, r[0], {}, params)[1] == v), None)
            if row is None:
                raise ElabError(f"Table {name}: no row for {v}")
            out = self.elab(mod, row[1], {}, params)
        else:
            raise ElabError(f"{name}: unsupported body {body[0]}")
        if out[0] != to:
            raise ElabError(f"{name}: value of type {out[0]}, declared To {to}")
        if key is not None:
            self._apply[key] = out
        return out

    def map_on_var(self, mod, term):
        """A map term (f p ...) or a bare map name, applied to the state variable."""
        t = (term if isinstance(term, list) else [term]) + ["$__state"]
        return self.elab(mod, t, {"$__state": ("word", VAR)}, {})

    # ---------------------------------------------------------------- declarations
    def expand(self, entry, start):
        """Entries with (For $v C) clauses, expanded in clause order and carrier order."""
        fors = [x for x in entry[start:] if isinstance(x, list) and x and x[0] == "For"]
        binds = [{}]
        for f in fors:
            binds = [dict(b, **{f[1]: e}) for b in binds for e in self.carriers[f[2]]]
        return binds

    @staticmethod
    def inst(t, b):
        if isinstance(t, str):
            return b.get(t, t)
        return [Elaborator.inst(x, b) for x in t]

    def machine(self, mod, name):
        """(labels and word terms of the actions, labels and nodes of the observers, states)."""
        hit = self.src.lookup(mod, name)
        if hit is None or hit[1][0] != "Machine":
            raise ElabError(f"unknown machine {name}")
        m, d = hit
        acts, obs = [], []
        like = self.src.field(d, "Like")
        if like:
            a2, o2, _ = self.machine(m, like[1])
            acts, obs = list(a2), list(o2)
        borrow = self.src.field(d, "ActionsOf")
        if borrow:
            acts = list(self.machine(m, borrow[1])[0])
        for e in d[2:]:
            if not isinstance(e, list) or e[0] not in ("Observe", "Action"):
                continue
            for b in self.expand(e, 3):
                label = show(self.inst(e[1], b))
                v = self.map_on_var(m, self.inst(e[2], b))
                if e[0] == "Action":
                    if v[0] != "word":
                        raise ElabError(f"action {label} is not a map into the state carrier")
                    acts.append((label, v[1]))
                else:
                    if v[0] != "bool":
                        raise ElabError(f"observer {label} is not Bool-valued")
                    obs.append((label, v[1]))
        return acts, obs, self.src.field(d, "States")[1]

    def predicate(self, mod, name_or_body):
        """A Bool map name, or a (Body ($x) e) term, on the state variable."""
        if isinstance(name_or_body, list) and name_or_body[0] == "Body":
            v = self.elab(mod, name_or_body[2], {name_or_body[1][0]: ("word", VAR)}, {})
        else:
            v = self.map_on_var(mod, name_or_body)
        return self.boolof(v)

    def encoding(self, mod, name):
        v = self.map_on_var(mod, name)
        if v[0] != "bits":
            raise ElabError(f"{name} is not a bit-vector encoding")
        return v[1]

    def const(self, mod, name):
        hit = self.src.lookup(mod, name)
        if hit is None or hit[1][0] != "Const":
            raise ElabError(f"unknown constant {name}")
        return int(hit[1][3])

    def partition(self, mod, name):
        """A one-block BlockPartition on a reachability scope."""
        m, d = self.src.lookup(mod, name)
        blocks = self.src.fields(d, "Block")
        if len(blocks) != 1:
            raise ElabError(f"{name}: one block expected")
        blk = blocks[0]
        succ = self.src.fields(d, "Successor")
        if [s[1:] for s in succ] != [["Any", blk[1], blk[1]]]:
            raise ElabError(f"{name}: expected (Successor Any {blk[1]} {blk[1]})")
        inv = self.src.field(d, "Invariant")
        scope = self.src.lookup(m, self.src.field(d, "On")[1])[1]
        reach = self.src.field(scope, "Reach")
        return {"name": name, "module": m, "block": self.predicate(m, blk[2]),
                "members": [self.const(m, s) for s in blk[3:]],
                "invariant": self.predicate(m, inv[1]) if inv else None,
                "invariant_name": inv[1] if inv else None,
                "scope_machine": reach[1], "scope_from": [self.const(m, s) for s in reach[2][1:]]}


class Policy:
    """A machine of the module, elaborated: actions as bit functions and guarded updates, compiled
    to Python for single words."""

    def __init__(self, el, mod, machine="Policy"):
        self.el, self.ir, self.mod, self.name = el, el.ir, mod, machine
        acts, obs, self.states = el.machine(mod, machine)
        self.labels = [a for a, _ in acts]
        self.wterms = [w for _, w in acts]
        self.bits = [el.bits(w) for w in self.wterms]
        self.obs = obs
        self.guarded = [el.guarded(w) for w in self.wterms]
        self.writes_ok = []
        self._fns = []
        for (lab, w), g in zip(acts, self.guarded):
            if g is None:
                self.writes_ok.append(False)
                self._fns.append(self._bitwise(self.bits[len(self._fns)]))
                continue
            guard, writes = g
            # admission: the guard of a guarded update must not read the bits it writes
            self.writes_ok.append(not (self.ir.support(guard) & set(writes)))
            setm = sum(1 << i for i, v in writes.items() if v)
            clr = sum(1 << i for i, v in writes.items() if not v)
            gfun = eval("lambda x: " + self.ir.pyexpr(guard))  # noqa: S307 -- generated from the IR
            self._fns.append(self._guarded_fn(gfun, setm, clr))

    @staticmethod
    def _guarded_fn(g, setm, clr):
        keep = ~clr
        return lambda x: ((x | setm) & keep) if g(x) else x

    def _bitwise(self, bits):
        exprs = [eval("lambda x: " + self.ir.pyexpr(b)) for b in bits]  # noqa: S307
        return lambda x: sum(1 << i for i, f in enumerate(exprs) if f(x))

    def step(self, x, a):
        return self._fns[a](x)

    def step_array(self, X, a):
        memo = {}
        out = np.zeros(X.shape, dtype=np.uint64)
        for i, b in enumerate(self.bits[a]):
            out |= self.ir.eval(b, X, memo).astype(np.uint64) << np.uint64(i)
        return out

    def index(self, label):
        return self.labels.index(label)


# ------------------------------------------------------------------------------------ CNF
class CNF:
    """Tseitin encoding of IR nodes.  Variable 1 is the constant True.  Every gate is an AND of
    literals, recorded in self.gates with its definitional clauses, so that for each assignment
    of the input variables exactly one extension satisfies the gate clauses."""

    def __init__(self, ir):
        self.ir = ir
        self.n = 1
        self.clauses = [[1]]
        self.gates = []          # (var, literals, index of its first clause)
        self.inputs_vars = []
        self.cache = {}
        self.extra = []          # indices of clauses that are not gate definitions

    def inputs(self, w):
        out = []
        for _ in range(w):
            self.n += 1
            out.append(self.n)
        self.inputs_vars.extend(out)
        return out

    def AND(self, lits):
        lits = [l for l in lits if l != 1]
        if any(l == -1 for l in lits):
            return -1
        if not lits:
            return 1
        if len(lits) == 1:
            return lits[0]
        if any(-l in lits for l in lits):
            return -1
        key = tuple(sorted(set(lits)))
        if key in self.cache:
            return self.cache[key]
        self.n += 1
        g = self.n
        self.gates.append((g, tuple(lits), len(self.clauses)))
        for l in lits:
            self.clauses.append([-g, l])
        self.clauses.append([g] + [-l for l in lits])
        self.cache[key] = g
        return g

    def lit(self, node, xin, memo):
        """Literal of IR node over the input literal vector xin (memo is per input vector)."""
        if node in memo:
            return memo[node]
        k = self.ir.nodes[node]
        if k[0] == "true":
            r = 1
        elif k[0] == "false":
            r = -1
        elif k[0] == "bit":
            r = xin[k[1]]
        elif k[0] == "not":
            r = -self.lit(k[1], xin, memo)
        elif k[0] == "and":
            r = self.AND([self.lit(a, xin, memo) for a in k[1]])
        elif k[0] == "or":
            r = -self.AND([-self.lit(a, xin, memo) for a in k[1]])
        else:
            c, t, e = (self.lit(a, xin, memo) for a in k[1:])
            r = -self.AND([-self.AND([c, t]), -self.AND([-c, e])])
        memo[node] = r
        return r

    def assert_lit(self, l):
        self.extra.append(len(self.clauses))
        self.clauses.append([l])

    def assert_clause(self, lits):
        self.extra.append(len(self.clauses))
        self.clauses.append(list(lits))

    def dimacs(self):
        return f"p cnf {self.n} {len(self.clauses)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in self.clauses)

    def digest(self):
        return "sha256:" + hashlib.sha256(self.dimacs().encode()).hexdigest()

    # ---------------------------------------------------------------- validation
    def structure_ok(self):
        """The clause list is [1], then the definitional clauses of each gate in creation order,
        interleaved with the asserted clauses; each gate reads only the inputs, the constant and
        earlier gates; every variable is an input or a gate.  Then, for every assignment of the
        inputs, exactly one extension satisfies the gate clauses."""
        if not self.clauses or self.clauses[0] != [1]:
            return False
        defined = {1} | set(self.inputs_vars)
        if len(defined) != len(self.inputs_vars) + 1:
            return False
        extra = set(self.extra)
        ci, gi = 1, 0
        while ci < len(self.clauses):
            if ci in extra:
                ci += 1
                continue
            if gi >= len(self.gates):
                return False
            g, key, first = self.gates[gi]
            if first != ci or g in defined or any(abs(l) not in defined for l in key):
                return False
            want = [[-g, l] for l in key] + [[g] + [-l for l in key]]
            if self.clauses[ci:ci + len(want)] != want:
                return False
            defined.add(g)
            ci += len(want)
            gi += 1
        return gi == len(self.gates) and defined == set(range(1, self.n + 1)) and \
            all(abs(l) in defined for i in extra for l in self.clauses[i])

    def evaluate(self, inputs):
        """inputs: {var: boolean array}.  Returns (value of every variable, satisfied mask): the
        unique extension of the inputs through the gates, and where it satisfies every clause."""
        shape = next(iter(inputs.values())).shape
        val = {1: np.ones(shape, dtype=bool)}
        val.update(inputs)
        get = lambda l: val[l] if l > 0 else ~val[-l]  # noqa: E731
        for g, key, _ in self.gates:
            val[g] = np.logical_and.reduce([get(l) for l in key])
        sat = np.ones(shape, dtype=bool)
        for c in self.clauses:
            sat &= np.logical_or.reduce([get(l) for l in c])
        return val, sat


# ------------------------------------------------------------------------------------ interpreter
class SourceInterpreter:
    """Direct evaluation of the source terms on numpy arrays of words, without the IR.  Words are
    uint64 arrays, Booleans are bool arrays or Python bools, parameters are element names."""

    def __init__(self, source, users=None):
        self.src = source
        self.carriers = Elaborator(source, users).carriers

    def ev(self, mod, t, env, params):
        if isinstance(t, str):
            if t.startswith("$"):
                return env[t] if t in env else params[t]
            if INT.fullmatch(t):
                return int(t)
            if t in ("True", "False"):
                return t == "True"
            if any(t in es for es in self.carriers.values()):
                return t
            hit = self.src.lookup(mod, t)
            if hit and hit[1][0] == "Const":
                return int(hit[1][3])
            raise ElabError(f"unknown name {t}")
        h = t[0]
        E = lambda y: self.ev(mod, y, env, params)  # noqa: E731
        if h == "Eq":
            a, b = E(t[1]), E(t[2])
            return a == b
        if h == "BitAt":
            return (E(t[1]) >> np.uint64(E(t[2]))) & np.uint64(1)
        if h == "SetBit":
            w, i, v = E(t[1]), np.uint64(E(t[2])), np.uint64(E(t[3]))
            return (w & ~(np.uint64(1) << i)) | (v << i)
        if h == "Add":
            return sum(E(a) for a in t[1:])
        if h == "Not":
            return np.logical_not(E(t[1]))
        if h == "And":
            out = True
            for a in t[1:]:
                out = np.logical_and(out, E(a))
            return out
        if h == "Or":
            out = False
            for a in t[1:]:
                out = np.logical_or(out, E(a))
            return out
        if h == "If":
            c = E(t[1])
            if isinstance(c, (bool, np.bool_)) and np.ndim(c) == 0:
                return E(t[2]) if c else E(t[3])
            return np.where(c, E(t[2]), E(t[3]))
        if h == "Switch":
            v = E(t[1])
            return E(next(case[1] for case in t[2:] if case[0] == v))
        if h in ("Exists", "ForAll"):
            out = h == "ForAll"
            for e in self.carriers[t[2]]:
                v = self.ev(mod, t[3], dict(env, **{t[1]: e}), params)
                out = np.logical_or(out, v) if h == "Exists" else np.logical_and(out, v)
            return out
        hit = self.src.lookup(mod, h)
        if hit and hit[1][0] == "Map":
            m, d = hit
            args = [E(a) for a in t[1:]]
            par = self.src.field(d, "Parameters")
            npar = len(par) - 1 if par else 0
            p2 = {pv: a for (pv, _), a in zip(par[1:] if par else [], args[:npar])}
            body = d[-1]
            if body[0] == "Body":
                return self.ev(m, body[2], {body[1][0]: args[npar]}, p2)
            if body[0] == "Table":
                return next(self.ev(m, r[1], {}, p2) for r in body[1:] if r[0] == args[npar])
        raise ElabError(f"cannot interpret {show(t)[:80]}")

    def machine_entries(self, mod, name):
        """[(kind, label, module, map term)] of a machine, Like and ActionsOf resolved."""
        m, d = self.src.lookup(mod, name)
        out = []
        like = Source.field(d, "Like")
        if like:
            out = self.machine_entries(m, like[1])
        borrow = Source.field(d, "ActionsOf")
        if borrow:
            out = [e for e in self.machine_entries(m, borrow[1]) if e[0] == "Action"]
        for e in d[2:]:
            if not isinstance(e, list) or e[0] not in ("Observe", "Action"):
                continue
            fors = [x for x in e[3:] if isinstance(x, list) and x and x[0] == "For"]
            binds = [{}]
            for f in fors:
                binds = [dict(b, **{f[1]: v}) for b in binds for v in self.carriers[f[2]]]
            for b in binds:
                out.append((e[0], show(Elaborator.inst(e[1], b)), m, Elaborator.inst(e[2], b)))
        return out

    def apply(self, mod, term, X):
        t = (term if isinstance(term, list) else [term]) + ["$__state"]
        return self.ev(mod, t, {"$__state": X}, {})

    def predicate(self, mod, name_or_body, X):
        if isinstance(name_or_body, list) and name_or_body[0] == "Body":
            v = self.ev(mod, name_or_body[2], {name_or_body[1][0]: X}, {})
        else:
            v = self.apply(mod, name_or_body, X)
        return np.broadcast_to(np.asarray(v, dtype=bool), X.shape)
