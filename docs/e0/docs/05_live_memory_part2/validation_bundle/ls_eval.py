"""A reference evaluator for the modules of live_memory.metta, with the cvc5 solver as back end.

It reads the module files with its own reader and rebuilds, from the module text, the carriers
(Enum, All, Subset, Product, Reach), constants, maps (Cases, Body and Table bodies, parameterized
maps, Switch), the arithmetic of Core, NatArith and the proposed RationalArith, the finite and
identity-bounded sets of the proposed BoundedSets library, Coin, machines (Observe, Action and
Merge entries, For families over any carrier, Like and ActionsOf, imports), statistics,
representations, simulations, block partitions with invariants, tolerances, implementation
contracts, streams and monitors.  Values are Python values (Fraction, bool, symbol strings, tuples,
frozensets) or cvc5 terms; a request on symbolic carriers becomes a list of obligations, each
decided by asking cvc5 for a counterexample.  "unsat" proves an obligation for every state and
parameter; "sat" gives a model, which is a witness.  The oracle compares every verdict with the
Z3 encodings of models/smt_live.py, written separately.  This is a test aid for the guide, not an
implementation of MeTTaDinC.
"""
import hashlib
import json
import math
import os
import re
from fractions import Fraction as F

import cvc5
from cvc5 import Kind

TOKEN = re.compile(r'\s*(?:(;[^\n]*)|("(?:[^"\\]|\\.)*")|([()])|(!)|([^\s()";!]+))')


def read_forms(text):
    pos, stack = 0, [[]]
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"cannot tokenize at {pos}")
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
    if isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)):
        return "(" + " ".join(show(y) for y in x) + ")"
    return str(x)


def is_num(a):
    return isinstance(a, str) and re.fullmatch(r"-?\d+", a) is not None


class Capped:
    """An identity-bounded set: many is true when the set has reached the cap; the set is then
    empty, so that equal values have equal components."""
    __slots__ = ("many", "set")

    def __init__(self, many, st):
        self.many, self.set = many, st

    def __eq__(self, other):
        return isinstance(other, Capped) and self.many == other.many and self.set == other.set

    def __hash__(self):
        return hash((self.many, self.set))

    def __repr__(self):
        return "Many" if self.many is True else f"Capped({self.many}, {self.set})"


class Module:
    def __init__(self, form, path):
        self.name, self.path = form[1], path
        self.decls, self.imports, self.uses = {}, {}, set()
        for it in form[2:]:
            if not (isinstance(it, list) and it):
                continue
            if it[0] == "Use":
                self.uses |= set(it[1:])
            elif it[0] == "Import":
                for nm in it[2][1:]:
                    self.imports[nm] = it[1]
            elif it[0] != "Profile" and len(it) > 1 and isinstance(it[1], str):
                self.decls[it[1]] = it


class World:
    def __init__(self, paths, timeout_ms=60000):
        self.modules, self.runs = {}, []
        for path in paths:
            for kind, form in read_forms(open(path).read()):
                if kind == "form":
                    m = Module(form, path)
                    self.modules[m.name] = m
                else:
                    self.runs.append((path, form))
        self.tm = cvc5.TermManager()
        self.src = self.tm.mkUninterpretedSort("Src")
        self.setsort = self.tm.mkSetSort(self.src)
        self.codes, self.n, self.symvars = {}, 0, set()
        self.timeout = timeout_ms
        self.req_backend, self.req_text = False, hashlib.sha256()

    # ------------------------------------------------------------ declarations
    def find(self, mod, name):
        """(module, declaration) of a name visible in mod, following imports."""
        m = self.modules[mod]
        if name in m.decls:
            return mod, m.decls[name]
        if name in m.imports:
            return self.find(m.imports[name], name)
        raise KeyError(f"{mod}: no declaration {name}")

    @staticmethod
    def field(d, key):
        for x in d[2:]:
            if isinstance(x, list) and x and x[0] == key:
                return x
        return None

    @staticmethod
    def fields(d, key):
        return [x for x in d[2:] if isinstance(x, list) and x and x[0] == key]

    # ------------------------------------------------------------ terms
    def code(self, sym):
        return self.codes.setdefault(sym, len(self.codes))

    def fresh(self, sort, hint):
        self.n += 1
        return self.tm.mkConst(sort, f"{hint}_{self.n}")

    def term(self, v, like=None):
        tm = self.tm
        if isinstance(v, cvc5.Term):
            return v
        if isinstance(v, bool):
            return tm.mkBoolean(v)
        if isinstance(v, (int, F)):
            q = F(v)
            if like is not None and isinstance(like, cvc5.Term) and like.getSort().isInteger() \
                    and q.denominator == 1:
                return tm.mkInteger(int(q))
            return tm.mkReal(str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}")
        if isinstance(v, str):
            return tm.mkInteger(self.code(v))
        if isinstance(v, frozenset):
            out = tm.mkEmptySet(self.setsort)
            for e in v:
                out = tm.mkTerm(Kind.SET_INSERT, self.term(e), out)
            return out
        raise TypeError(f"no term for {v!r}")

    @staticmethod
    def concrete(v):
        if isinstance(v, tuple):
            return all(World.concrete(u) for u in v)
        if isinstance(v, Capped):
            return World.concrete(v.many) and World.concrete(v.set)
        return not isinstance(v, cvc5.Term)

    def mk(self, kind, *args):
        return self.tm.mkTerm(kind, *args)

    # ------------------------------------------------------------ operations
    def ite(self, c, a, b):
        if isinstance(c, bool):
            return a if c else b
        if isinstance(a, tuple):
            return tuple(self.ite(c, x, y) for x, y in zip(a, b))
        if isinstance(a, Capped):
            return Capped(self.ite(c, a.many, b.many), self.ite(c, a.set, b.set))
        if self.concrete(a) and self.concrete(b) and type(a) is type(b) and a == b:
            return a
        if isinstance(a, bool) and isinstance(b, bool):
            return c if a else self.NOT(c)
        if isinstance(a, frozenset) and not a and isinstance(b, cvc5.Term):
            return self.mk(Kind.ITE, c, self.tm.mkEmptySet(self.setsort), b)
        return self.mk(Kind.ITE, c, self.term(a, like=b), self.term(b, like=a))

    def AND(self, *vs):
        terms = []
        for v in vs:
            if v is False:
                return False
            if v is not True:
                terms.append(v)
        if not terms:
            return True
        return terms[0] if len(terms) == 1 else self.mk(Kind.AND, *terms)

    def OR(self, *vs):
        terms = []
        for v in vs:
            if v is True:
                return True
            if v is not False:
                terms.append(v)
        if not terms:
            return False
        return terms[0] if len(terms) == 1 else self.mk(Kind.OR, *terms)

    def NOT(self, v):
        return (not v) if isinstance(v, bool) else self.mk(Kind.NOT, v)

    def eq(self, a, b):
        if isinstance(a, tuple):
            return self.AND(*[self.eq(x, y) for x, y in zip(a, b)])
        if isinstance(a, Capped):
            return self.AND(self.eq(a.many, b.many), self.eq(a.set, b.set))
        if self.concrete(a) and self.concrete(b):
            return a == b
        return self.mk(Kind.EQUAL, self.term(a, like=b), self.term(b, like=a))

    def neq(self, a, b):
        return self.NOT(self.eq(a, b))

    def arith(self, kind, pyop, a, b):
        if self.concrete(a) and self.concrete(b):
            return pyop(a, b)
        return self.mk(kind, self.term(a, like=b), self.term(b, like=a))

    def add(self, a, b):
        return self.arith(Kind.ADD, lambda x, y: x + y, a, b)

    def sub(self, a, b):
        return self.arith(Kind.SUB, lambda x, y: x - y, a, b)

    def mul(self, a, b):
        return self.arith(Kind.MULT, lambda x, y: x * y, a, b)

    def div(self, a, b):
        if self.concrete(a) and self.concrete(b):
            return F(a) / F(b)
        return self.mk(Kind.DIVISION, self.term(a, like=b), self.term(b, like=a))

    def le(self, a, b):
        return self.arith(Kind.LEQ, lambda x, y: x <= y, a, b)

    def lt(self, a, b):
        return self.arith(Kind.LT, lambda x, y: x < y, a, b)

    def vmin(self, a, b):
        return self.ite(self.le(a, b), a, b)

    def vmax(self, a, b):
        return self.ite(self.le(a, b), b, a)

    def vabs(self, a):
        return self.ite(self.le(0, a), a, self.sub(0, a))

    # finite and identity-bounded sets
    def insert(self, x, s):
        if self.concrete(x) and self.concrete(s):
            return s | {x}
        return self.mk(Kind.SET_INSERT, self.term(x), self.term(s))

    def union(self, s, t):
        if self.concrete(s) and self.concrete(t):
            return s | t
        return self.mk(Kind.SET_UNION, self.term(s), self.term(t))

    def size(self, s):
        if self.concrete(s):
            return len(s)
        return self.mk(Kind.SET_CARD, self.term(s))

    def cap(self, k, s):
        many = self.le(k, self.size(s))
        return Capped(many, self.ite(many, frozenset(), s))

    def cap_insert(self, k, x, c):
        s = self.insert(x, c.set)
        many = self.OR(c.many, self.le(k, self.size(s)))
        return Capped(many, self.ite(many, frozenset(), s))

    def cap_union(self, k, c, d):
        s = self.union(c.set, d.set)
        many = self.OR(c.many, d.many, self.le(k, self.size(s)))
        return Capped(many, self.ite(many, frozenset(), s))

    def cap_size(self, k, c):
        return self.ite(c.many, k, self.size(c.set))

    # ------------------------------------------------------------ evaluation
    def atom(self, a):
        if is_num(a):
            return F(int(a))
        if a in ("True", "False"):
            return a == "True"
        return a

    def ev(self, mod, x, env, params):
        if isinstance(x, str):
            if x.startswith("$"):
                if x in env:
                    return env[x]
                if x in params:
                    return params[x]
                raise KeyError(f"{mod}: unbound {x}")
            if is_num(x) or x in ("True", "False"):
                return self.atom(x)
            m = self.modules[mod]
            if x in m.decls and m.decls[x][0] == "Const":
                return self.ev(mod, m.decls[x][3], {}, {})
            return x
        h = x[0]
        E = lambda y: self.ev(mod, y, env, params)
        if h == "Rat":
            return F(int(x[1]), int(x[2]))
        if h == "Tuple":
            return tuple(E(y) for y in x[1:])
        if h == "GetTuple":
            return E(x[1])[int(x[2])]
        if h == "If":
            c = E(x[1])
            if isinstance(c, bool):
                return E(x[2]) if c else E(x[3])
            return self.ite(c, E(x[2]), E(x[3]))
        if h == "Eq":
            return self.eq(E(x[1]), E(x[2]))
        if h == "Lt":
            return self.lt(E(x[1]), E(x[2]))
        if h == "Le":
            return self.le(E(x[1]), E(x[2]))
        if h == "And":
            return self.AND(*[E(y) for y in x[1:]])
        if h == "Or":
            return self.OR(*[E(y) for y in x[1:]])
        if h == "Not":
            return self.NOT(E(x[1]))
        if h == "Add":
            out = E(x[1])
            for y in x[2:]:
                out = self.add(out, E(y))
            return out
        if h == "Sub":
            return self.sub(E(x[1]), E(x[2]))
        if h == "Mul":
            out = E(x[1])
            for y in x[2:]:
                out = self.mul(out, E(y))
            return out
        if h == "Div":
            return self.div(E(x[1]), E(x[2]))
        if h == "Min":
            return self.vmin(E(x[1]), E(x[2]))
        if h == "Max":
            return self.vmax(E(x[1]), E(x[2]))
        if h == "Insert":
            return self.insert(E(x[1]), E(x[2]))
        if h == "Union":
            return self.union(E(x[1]), E(x[2]))
        if h == "Size":
            return self.size(E(x[1]))
        if h == "Cap":
            return self.cap(int(x[1]), E(x[2]))
        if h == "CapInsert":
            return self.cap_insert(int(x[1]), E(x[2]), E(x[3]))
        if h == "CapUnion":
            return self.cap_union(int(x[1]), E(x[2]), E(x[3]))
        if h == "CapSize":
            return self.cap_size(int(x[1]), E(x[2]))
        if h == "Switch":
            v = params[x[1]] if x[1] in params else env[x[1]]
            for case in x[2:]:
                if self.atom(case[0]) == v:
                    return E(case[1])
            raise ValueError(f"Switch: no case {v}")
        if h == "Coin":
            p = F(E(x[1]))
            return {k: m for k, m in ((1, p), (0, 1 - p)) if m}
        dm, d = self.find(mod, h)
        if d[0] == "Map":
            return self.apply(dm, d, [E(y) for y in x[1:]])
        raise ValueError(f"cannot evaluate {show(x)[:80]}")

    def apply(self, mod, d, args):
        par = self.field(d, "Parameters")
        params = {}
        if par:
            for (pv, _), a in zip(par[1:], args):
                params[pv] = a
            args = args[len(par) - 1:]
        assert len(args) == 1, (d[1], args)
        return self.call(mod, d, params, args[0])

    def call(self, mod, d, params, arg):
        body = d[-1]
        if body[0] == "Body":
            return self.ev(mod, body[2], {body[1][0]: arg}, params)
        if body[0] == "Table":
            for k, v in body[1:]:
                if self.ev(mod, k, {}, params) == arg:
                    return self.ev(mod, v, {}, params)
            raise ValueError(f"Table {d[1]}: no row for {arg}")
        if body[0] == "Cases":
            hits = []
            for pat, out in body[1:]:
                env = {}
                if self.match(mod, pat, arg, env, params):
                    hits.append((out, env))
            if len(hits) != 1:
                raise ValueError(f"Cases {d[1]}: {len(hits)} matches")
            out, env = hits[0]
            return self.ev(mod, out, env, params)
        raise ValueError(f"map body {body[0]}")

    def match(self, mod, pat, v, env, params):
        if isinstance(pat, str):
            if pat.startswith("$"):
                env[pat] = v
                return True
            return self.ev(mod, pat, {}, params) == v
        if pat[0] == "Tuple":
            if not isinstance(v, tuple) or len(v) != len(pat) - 1:
                return False
            return all(self.match(mod, p, w, env, params) for p, w in zip(pat[1:], v))
        raise ValueError(f"pattern {show(pat)}")

    def fn(self, mod, x, env=None):
        """A map name, or an instance (f a1 ... ak) of a parameterized map, as a function."""
        env = env or {}
        if isinstance(x, str):
            dm, d = self.find(mod, x)
            return lambda v: self.call(dm, d, {}, v)
        dm, d = self.find(mod, x[0])
        par = self.field(d, "Parameters")
        params = {pv: self.ev(mod, a, env, {}) for (pv, _), a in zip(par[1:], x[1:])}
        return lambda v: self.call(dm, d, params, v)

    # ------------------------------------------------------------ carriers
    def carrier_type(self, mod, cname):
        dm, d = self.find(mod, cname)
        return dm, d, self.field(d, "Of")[1], d[-1]

    def var(self, mod, cname, hint="x"):
        """A fresh value of the carrier's shape."""
        dm, d, of, body = self.carrier_type(mod, cname)
        if body[0] == "Product":
            return tuple(self.var(dm, c, f"{hint}{i}") for i, c in enumerate(body[1:]))
        if body[0] == "Subset":
            return self.var(dm, body[1], hint)
        if body[0] == "Reach":
            mm, md = self.find(dm, body[1])
            return self.var(mm, self.field(md, "States")[1], hint)
        return self.leaf(of, body, hint)

    def leaf(self, of, body, hint):
        tm = self.tm
        if of == "Bool":
            return self.fresh(tm.getBooleanSort(), hint)
        if of in ("Rational", "Rational01"):
            return self.fresh(tm.getRealSort(), hint)
        if of in ("Nat", "Int"):
            return self.fresh(tm.getIntegerSort(), hint)
        if of == "Symbol":
            if body[0] == "All":
                return self.fresh(self.src, hint)
            t = self.fresh(tm.getIntegerSort(), hint)
            self.symvars.add(t.getId())
            return t
        if isinstance(of, list) and of[0] == "FiniteSet":
            return self.fresh(self.setsort, hint)
        raise ValueError(f"no variables of type {show(of)}")

    def member(self, mod, cname, v):
        dm, d, of, body = self.carrier_type(mod, cname)
        if body[0] == "Product":
            return self.AND(*[self.member(dm, c, u) for c, u in zip(body[1:], v)])
        if body[0] == "Subset":
            return self.AND(self.member(dm, body[1], v), self.fn(dm, body[2])(v))
        if body[0] == "Reach":
            mm, md = self.find(dm, body[1])
            return self.member(mm, self.field(md, "States")[1], v)
        if body[0] == "Enum":
            vals = [self.atom(e) for e in body[1:]]
            if of == "Bool" and set(vals) == {True, False}:
                return True
            return self.OR(*[self.eq(v, e) for e in vals])
        if body[0] == "All":
            return self.le(0, v) if of == "Nat" else True
        raise ValueError(f"carrier {cname}: {body[0]}")

    def enumerate_carrier(self, mod, cname, cap=64):
        """The elements of a finite carrier, by model enumeration; None if there are more than cap."""
        dm, d, of, body = self.carrier_type(mod, cname)
        if body[0] == "Enum":
            return [self.atom(e) for e in body[1:]]
        v = self.var(mod, cname, "e")
        found = []
        cons = [self.member(mod, cname, v)]
        while len(found) <= cap:
            st, model = self.solve(cons, {"v": v})
            if st != "sat":
                return found
            found.append(model["v"])
            cons.append(self.neq(v, model["v"]))
        return None

    # ------------------------------------------------------------ machines
    def entries(self, mod, name, kind):
        """[(module, label expr, head, fors, map expr)] with Like and ActionsOf resolved."""
        dm, d = self.find(mod, name)
        like = self.field(d, "Like")
        if like is not None:
            return self.entries(dm, like[1], kind)
        if kind == "Action":
            ao = self.field(d, "ActionsOf")
            if ao is not None:
                return self.entries(dm, ao[1], "Action")
        out = []
        for x in self.fields(d, kind):
            rest = x[1:]
            fors = [(y[1], y[2]) for y in rest if isinstance(y, list) and y and y[0] == "For"]
            core = [y for y in rest if not (isinstance(y, list) and y and y[0] in ("For", "Values"))]
            label, mp = core
            head = label if isinstance(label, str) else label[0]
            out.append((dm, label, head, fors, mp))
        return out

    def states(self, mod, name):
        dm, d = self.find(mod, name)
        return dm, self.field(d, "States")[1]

    def instance(self, entry, hint="p"):
        """Fresh parameters for a family entry: (env, parameter domain, update function)."""
        dm, label, head, fors, mp = entry
        env = {v: self.var(dm, c, hint) for v, c in fors}
        pdom = self.AND(*[self.member(dm, c, env[v]) for v, c in fors])
        return env, pdom, self.fn(dm, mp, env)

    # ------------------------------------------------------------ solving
    def solve(self, constraints, extract=None):
        """Decides one obligation.  Constraints that fold to constants are decided by evaluation;
        anything else goes to cvc5, and the request then rests on that backend's answer, which is
        recorded (with a digest of the asserted formulas) so that run() can report the assumption."""
        live = []
        for c in constraints:
            if c is False:
                return "unsat", None
            if c is True:
                continue
            live.append(c)
        s = cvc5.Solver(self.tm)
        s.setLogic("ALL")
        s.setOption("produce-models", "true")
        s.setOption("tlimit-per", str(self.timeout))
        self.req_backend = True
        for c in live:
            self.req_text.update(str(c).encode())
            s.assertFormula(c)
        r = s.checkSat()
        if r.isUnsat():
            return "unsat", None
        if not r.isSat():
            return "unknown", None
        return "sat", {k: self.value(s, v) for k, v in (extract or {}).items()}

    def value(self, s, v):
        if isinstance(v, tuple):
            return tuple(self.value(s, u) for u in v)
        if isinstance(v, Capped):
            return Capped(self.value(s, v.many), self.value(s, v.set))
        if not isinstance(v, cvc5.Term):
            return v
        w = s.getValue(v)
        srt = v.getSort()
        if srt.isBoolean():
            return w.getBooleanValue()
        if srt.isInteger():
            n = w.getIntegerValue()
            if v.getId() in self.symvars:
                inv = {c: sym for sym, c in self.codes.items()}
                return inv.get(n, f"#{n}")
            return F(n)
        if srt.isReal():
            if not w.isRealValue():
                return f"irrational {w}"
            return F(w.getRealValue())
        if srt.isSet():
            return frozenset(str(e) for e in w.getSetValue())
        return str(w)

    def obligations(self, items):
        """items: [(name, [constraints], extract)].  Returns (status, table, witness)."""
        table, witness, status = {}, None, "Checked"
        for name, cons, extract in items:
            st, model = self.solve(cons, extract)
            table[name] = st
            if st == "sat" and witness is None:
                witness, status = {"obligation": name, "values": model}, "Refuted"
            elif st == "unknown" and status == "Checked":
                status = "Unknown"
        return status, table, witness

    # ------------------------------------------------------------ requests
    def check_statistic(self, mod, name, method="Symbolic"):
        sm, d = self.find(mod, name)
        if d[0] == "Keyed":
            return self.check_lift(sm, name, d)
        mach = self.field(d, "Of")[1]
        enc = self.fn(sm, self.field(d, "Encode")[1])
        steps = {}
        for st in self.fields(d, "Step"):
            label = st[1]
            head = label if isinstance(label, str) else label[0]
            steps[head] = st
        reads = {r[1]: self.fn(sm, r[2]) for r in self.fields(d, "Read")}
        msteps = {r[1]: self.fn(sm, r[2]) for r in self.fields(d, "MergeStep")}
        cm, cname = self.states(sm, mach)
        items = []
        missing = []
        for entry in self.entries(sm, mach, "Action"):
            dm, label, head, fors, mp = entry
            if head not in steps:
                missing.append(f"Step {head}")
                continue
            x = self.var(cm, cname)
            env, pdom, T = self.instance(entry)
            st = steps[head]
            slabel = st[1]
            senv = {}
            if not isinstance(slabel, str):
                for sv, lv in zip(slabel[1:], label[1:]):
                    senv[sv] = env[lv]
            smap = [y for y in st[2:] if not (isinstance(y, list) and y and y[0] == "For")][0]
            step = self.fn(sm, smap, senv)
            dom = self.member(cm, cname, x)
            y = T(x)
            ext = {"state": x, **{v: env[v] for v in env}}
            items.append((f"closed {head}", [dom, pdom, self.NOT(self.member(cm, cname, y))], ext))
            items.append((f"step {head}", [dom, pdom, self.neq(enc(y), step(enc(x)))], ext))
        for entry in self.entries(sm, mach, "Observe"):
            dm, label, head, fors, mp = entry
            if head not in reads:
                missing.append(f"Read {head}")
                continue
            x = self.var(cm, cname)
            q = self.fn(dm, mp)
            items.append((f"read {head}", [self.member(cm, cname, x), self.neq(q(x), reads[head](enc(x)))],
                          {"state": x}))
        for entry in self.entries(sm, mach, "Merge"):
            dm, label, head, fors, mp = entry
            if head not in msteps:
                missing.append(f"MergeStep {head}")
                continue
            x, y = self.var(cm, cname), self.var(cm, cname)
            mg = self.fn(dm, mp)
            dom = self.AND(self.member(cm, cname, x), self.member(cm, cname, y))
            z = mg((x, y))
            items.append((f"closed {head}", [dom, self.NOT(self.member(cm, cname, z))], {"x": x, "y": y}))
            items.append((f"merge {head}", [dom, self.neq(enc(z), msteps[head]((enc(x), enc(y))))],
                          {"x": x, "y": y}))
        if missing:
            return {"status": "InvalidInput", "missing": missing}
        status, table, wit = self.obligations(items)
        return {"status": status, "obligations": table, "witness": wit, "method": method,
                "binding": {"subject": [sm, name], "machine": list(self.find(sm, mach)[:1]) + [mach],
                            "queries": sorted(reads), "actions": sorted(steps)}}

    def resolve(self, mod, name):
        """The (module, name) that a name visible in mod refers to."""
        return (self.find(mod, name)[0], name)

    def is_view(self, vmod, view, mmod, mach):
        """A view of machine M: the same state carrier, and its actions declared as (ActionsOf M)."""
        vm, vd = self.find(vmod, view)
        ao = self.field(vd, "ActionsOf")
        same_states = self.resolve(vm, self.field(vd, "States")[1]) == \
            self.resolve(self.find(mmod, mach)[0], self.field(self.find(mmod, mach)[1], "States")[1])
        return ao is not None and self.resolve(vm, ao[1]) == self.resolve(mmod, mach) and same_states

    def check_lift(self, sm, name, d):
        """Lifting a statistic to a keyed store (Part II, Proposition 4.3).  The premise checked here
        is that the item statistic is a statistic of the store's item machine M; to index a view of
        the items, the declaration names it with (View V), V must be a view of M, the statistic must
        be a statistic of V, and the lifted result is bound to V's queries only."""
        store = self.field(d, "Of")[1]
        stm, sd = self.find(sm, store)
        mach = self.field(sd, "Of")[1]
        M = self.resolve(stm, mach)
        item = self.field(d, "Item")[1]
        xm, xd = self.find(sm, item)
        S_of = self.resolve(xm, self.field(xd, "Of")[1])
        view = self.field(d, "View")
        if view is None:
            if S_of != M:
                return {"status": "InvalidInput", "method": "Lift",
                        "mismatch": f"{item} is a statistic of {S_of[1]}, not of the store's item machine {M[1]}; "
                                    f"declare (View {S_of[1]}) to index that view"}
            bound = M
        else:
            V = self.resolve(sm, view[1])
            if not self.is_view(sm, view[1], stm, mach):
                return {"status": "InvalidInput", "method": "Lift",
                        "mismatch": f"{view[1]} is not a view of {M[1]} (same states, ActionsOf {M[1]})"}
            if S_of != V:
                return {"status": "InvalidInput", "method": "Lift",
                        "mismatch": f"{item} is a statistic of {S_of[1]}, not of the declared view {V[1]}"}
            bound = V
        res = self.check_statistic(xm, item)
        res["method"] = "Lift"
        queries = sorted(e[2] for e in self.entries(bound[0], bound[1], "Observe"))
        res["binding"] = {"subject": [sm, name], "store": [stm, store], "item_machine": list(M),
                          "bound_to": list(bound), "queries": queries,
                          "premise": res.get("binding", {}).get("subject")}
        return res

    def check_now(self, mod, rep):
        rm, d = self.find(mod, rep)
        mach = self.field(d, "Of")[1]
        enc = self.fn(rm, self.field(d, "Encode")[1])
        cm, cname = self.states(rm, mach)
        x, y = self.var(cm, cname), self.var(cm, cname)
        diffs = [self.neq(self.fn(dm, mp)(x), self.fn(dm, mp)(y)) for dm, _, _, _, mp in self.entries(rm, mach, "Observe")]
        cons = [self.member(cm, cname, x), self.member(cm, cname, y), self.eq(enc(x), enc(y)), self.OR(*diffs)]
        status, table, wit = self.obligations([("now", cons, {"x": x, "y": y})])
        return {"status": status, "witness": wit}

    def check_updates(self, mod, rep):
        rm, d = self.find(mod, rep)
        mach = self.field(d, "Of")[1]
        enc = self.fn(rm, self.field(d, "Encode")[1])
        cm, cname = self.states(rm, mach)
        items = []
        for entry in self.entries(rm, mach, "Action"):
            x, y = self.var(cm, cname), self.var(cm, cname)
            env, pdom, T = self.instance(entry)
            cons = [self.member(cm, cname, x), self.member(cm, cname, y), pdom, self.eq(enc(x), enc(y)),
                    self.neq(enc(T(x)), enc(T(y)))]
            items.append((f"updates {entry[2]}", cons, {"x": x, "y": y, **env}))
        status, table, wit = self.obligations(items)
        return {"status": status, "obligations": table, "witness": wit}

    def check_simulation(self, mod, name):
        sm, d = self.find(mod, name)
        src, tgt = self.field(d, "Source")[1], self.field(d, "Target")[1]
        h = self.fn(sm, self.field(d, "Relation")[1])
        matching = (self.field(d, "Matching") or [None, "Lockstep"])[1]
        scm, scn = self.states(sm, src)
        tcm, tcn = self.states(sm, tgt)
        tgt_actions = {e[2]: e for e in self.entries(sm, tgt, "Action")}
        tgt_obs = {e[2]: e for e in self.entries(sm, tgt, "Observe")}
        items = []
        x = self.var(scm, scn)
        items.append(("into target", [self.member(scm, scn, x), self.NOT(self.member(tcm, tcn, h(x)))], {"x": x}))
        for dm, label, head, fors, mp in self.entries(sm, src, "Observe"):
            if head not in tgt_obs:
                return {"status": "InvalidInput", "missing": [f"target query {head}"]}
            x = self.var(scm, scn)
            tq = self.fn(tgt_obs[head][0], tgt_obs[head][4])
            items.append((f"query {head}", [self.member(scm, scn, x), self.neq(self.fn(dm, mp)(x), tq(h(x)))],
                          {"x": x}))
        for entry in self.entries(sm, src, "Action"):
            head = entry[2]
            if head not in tgt_actions:
                return {"status": "InvalidInput", "missing": [f"target action {head}"]}
            x = self.var(scm, scn)
            env, pdom, T = self.instance(entry)
            te = tgt_actions[head]
            TT = self.fn(te[0], te[4])
            dom = self.member(scm, scn, x)
            y = T(x)
            items.append((f"closed {head}", [dom, pdom, self.NOT(self.member(scm, scn, y))], {"x": x, **env}))
            moved = self.neq(h(y), TT(h(x)))
            if matching == "Stutter":
                cons = [dom, pdom, self.neq(h(y), h(x)), moved]
            else:
                cons = [dom, pdom, moved]
            items.append((f"match {head}", cons, {"x": x, **env}))
        status, table, wit = self.obligations(items)
        return {"status": status, "obligations": table, "witness": wit, "matching": matching}

    def concrete_actions(self, mod, mach):
        """[(label, function)] with every family instantiated over its enumerable parameters."""
        acts = []
        for entry in self.entries(mod, mach, "Action"):
            dm, label, head, fors, mp = entry
            choices = [[]]
            for v, c in fors:
                vals = self.enumerate_carrier(dm, c)
                if vals is None:
                    return None
                choices = [ch + [(v, val)] for ch in choices for val in vals]
            for ch in choices:
                env = dict(ch)
                lab = head if not fors else f"({head} {' '.join(str(env[v]) for v, _ in fors)})"
                acts.append((lab, self.fn(dm, mp, env)))
        return acts

    def bfs(self, mod, mach, start, depth=None, visit=None):
        """Breadth-first search; visit(state, word, previous, label) may stop it by returning a
        value.  Returns (seen, stop value)."""
        acts = self.concrete_actions(mod, mach)
        if acts is None:
            return None, None
        seen = {start: []}
        if visit:
            r = visit(start, [], None, None)
            if r is not None:
                return seen, r
        frontier, k = [start], 0
        while frontier and (depth is None or k < depth):
            nxt = []
            for s in frontier:
                for lab, f in acts:
                    t = f(s)
                    if visit:
                        r = visit(t, seen[s] + [lab], s, lab)
                        if r is not None:
                            seen.setdefault(t, seen[s] + [lab])
                            return seen, r
                    if t not in seen:
                        seen[t] = seen[s] + [lab]
                        nxt.append(t)
            frontier = nxt
            k += 1
        return seen, None

    def check_safety(self, mod, target, prop, via, init):
        sm, sd = self.find(mod, via)
        src = self.field(sd, "Source")[1]
        sim_target = self.field(sd, "Target")[1]
        if self.resolve(sm, sim_target) != self.resolve(mod, target):
            return {"status": "InvalidInput",
                    "mismatch": f"the simulation {via} relates {src} to {sim_target}, not to {target}; "
                                f"safety of {target} does not transfer along it"}
        sim = self.check_simulation(mod, via)
        if sim["status"] != "Checked":
            return {"status": "Unknown", "reason": "the simulation is not checked", "simulation": sim}
        h = self.fn(sm, self.field(sd, "Relation")[1])
        scm, scn = self.states(sm, src)
        o, v = prop[1], self.atom(prop[2])
        x0 = self.ev(mod, init, {}, {})
        if self.member(scm, scn, x0) is not True:
            return {"status": "InvalidInput", "reason": "Init outside the source carrier"}
        tm_, td = self.find(mod, target)
        reach, _ = self.bfs(tm_, target, h(x0))
        tq = [e for e in self.entries(mod, target, "Observe") if e[2] == o][0]
        q = self.fn(tq[0], tq[4])
        bad = [(s, w) for s, w in reach.items() if q(s) == v]
        if not bad:
            return {"status": "Checked", "reachable_target_states": len(reach),
                    "binding": {"about": [sm, src], "target": [sm, sim_target], "via": [sm, via],
                                "init": show(init), "property": show(prop)}}
        s_bad, word = min(bad, key=lambda sw: len(sw[1]))
        # concretize the abstract run one step at a time
        src_actions = {}
        for e in self.entries(sm, src, "Action"):
            src_actions.setdefault(e[2], e)
        x, run, a = x0, [], h(x0)
        tgt_actions = {e[2]: e for e in self.entries(mod, target, "Action")}
        for lab in word:
            te = tgt_actions[lab]
            a_next = self.fn(te[0], te[4])(a)
            entry = src_actions[lab]
            env, pdom, T = self.instance(entry, "c")
            st, model = self.solve([pdom, self.eq(h(T(x)), a_next)], env)
            if st != "sat":
                return {"status": "Unknown", "reason": f"abstract step {lab} not realized"}
            x = self.fn(entry[0], entry[4], model)(x)
            run.append(lab if not env else f"({lab} {' '.join(str(model[k]) for k in env)})")
            a = a_next
        sq = [e for e in self.entries(sm, src, "Observe") if e[2] == o][0]
        if self.fn(sq[0], sq[4])(x) == v:
            return {"status": "Refuted", "run": run, "state": x, "abstract_word": word}
        return {"status": "Unknown", "reason": "concrete run does not show the value"}

    def check_block_partition(self, mod, name, of, unrollings=None):
        pm, d = self.find(mod, name)
        on = self.field(d, "On")[1]
        blocks = []
        for b in self.fields(d, "Block"):
            pred = b[2]
            var = pred[1][0]
            blocks.append((b[1], (lambda pr, vv: (lambda s: self.ev(pm, pr, {vv: s}, {})))(pred[2], var),
                           self.ev(pm, b[3], {}, {})))
        succ = [(s[1], s[2], s[3]) for s in self.fields(d, "Successor")]
        inv_f = self.field(d, "Invariant")
        cm, cname = self.states(pm, of)
        _, cd, _, cbody = self.carrier_type(cm, cname)
        if cbody[0] != "Reach":
            raise ValueError("this evaluator checks block partitions on reachable carriers only")
        rm, rmach = self.find(cm, cbody[1])[0], cbody[1]
        bm, bname = self.states(rm, rmach)
        start = self.ev(cm, cbody[2][1], {}, {})
        actions = self.entries(pm, of, "Action")
        queries = self.entries(pm, of, "Observe")
        bpred = {lab: f for lab, f, _ in blocks}
        items, inductive = [], None
        if inv_f is not None:
            inv = self.fn(pm, inv_f[1])
            ok_start = self.AND(self.member(bm, bname, start), inv(start))
            items.append(("invariant holds at the start", [self.NOT(ok_start)], {}))
            for entry in actions:
                x = self.var(bm, bname)
                env, pdom, T = self.instance(entry)
                y = T(x)
                cons = [self.member(bm, bname, x), inv(x), pdom,
                        self.NOT(self.AND(self.member(bm, bname, y), inv(y)))]
                items.append((f"invariant closed under {entry[2]}", cons, {"x": x, **env}))
            st, table, wit = self.obligations(items)
            inductive = st == "Checked"
            if inductive:
                more = []
                x = self.var(bm, bname)
                dom = self.AND(self.member(bm, bname, x), inv(x))
                more.append(("cover", [dom, self.NOT(self.OR(*[f(x) for _, f, _ in blocks]))], {"x": x}))
                for i, (li, fi, ri) in enumerate(blocks):
                    more.append((f"representative {li}", [self.NOT(fi(ri))], {}))
                    for lj, fj, _ in blocks[i + 1:]:
                        more.append((f"disjoint {li} {lj}", [dom, fi(x), fj(x)], {"x": x}))
                    for qm, _, qh, _, qmp in queries:
                        y = self.var(bm, bname)
                        q = self.fn(qm, qmp)
                        more.append((f"query {qh} constant on {li}",
                                     [dom, self.member(bm, bname, y), inv(y), fi(x), fi(y), self.neq(q(x), q(y))],
                                     {"x": x, "y": y}))
                for a, frm, to in succ:
                    for entry in actions:
                        if a != "Any" and entry[2] != a:
                            continue
                        x = self.var(bm, bname)
                        env, pdom, T = self.instance(entry)
                        cons = [self.member(bm, bname, x), inv(x), bpred[frm](x), pdom, self.NOT(bpred[to](T(x)))]
                        more.append((f"successor {entry[2]} {frm} {to}", cons, {"x": x, **env}))
                st2, table2, wit2 = self.obligations(more)
                table.update(table2)
                return {"status": st2, "inductive": True, "obligations": table, "witness": wit2}
            noninductive = {"obligations": table, "witness": wit}
        else:
            noninductive = {}
        # bounded search for a reachable violation
        if unrollings is None:
            return {"status": "Unknown", "inductive": inductive, **noninductive}
        rep_q = {lab: {qh: self.fn(qm, qmp)(r) for qm, _, qh, _, qmp in queries} for lab, _, r in blocks}

        def visit(t, word, prev, lab):
            inside = [b for b, f, _ in blocks if f(t) is True]
            if len(inside) != 1:
                return {"violation": "cover", "word": word, "state": t}
            for qm, _, qh, _, qmp in queries:
                if self.fn(qm, qmp)(t) != rep_q[inside[0]][qh]:
                    return {"violation": f"query {qh}", "word": word, "state": t}
            if prev is not None:
                frm = [b for b, f, _ in blocks if f(prev) is True][0]
                head = lab.strip("(").split()[0]
                for a, bf, bt in succ:
                    if bf == frm and (a == "Any" or a == head) and bt != inside[0]:
                        return {"violation": f"successor {head} {bf} {bt}", "word": word, "state": t}
            return None
        seen, hit = self.bfs(rm, rmach, start, depth=unrollings, visit=visit)
        if seen is None:
            return {"status": "Unknown", "reason": "parameters not enumerable"}
        if hit is not None:
            return {"status": "Refuted", "inductive": inductive, **hit, **noninductive}
        return {"status": "Unknown", "inductive": inductive, "searched": len(seen), **noninductive}

    def tolerance(self, mod, name):
        tm_, d = self.find(mod, name)
        return self.tol_body(tm_, d[-1])

    def tol_body(self, mod, b):
        if b[0] == "OneMinusAbsoluteDifference":
            return lambda p, q: self.vmax(0, self.sub(1, self.vabs(self.sub(p, q))))
        if b[0] == "Pullback":
            f, t = self.fn(mod, b[1]), self.tolerance(mod, b[2])
            return lambda x, y: t(f(x), f(y))
        if b[0] == "Meet":
            parts = [self.tol_body(mod, c) for c in b[1:]]

            def meet(x, y):
                out = parts[0](x, y)
                for p in parts[1:]:
                    out = self.vmin(out, p(x, y))
                return out
            return meet
        raise ValueError(f"tolerance {b[0]}")

    def check_implementation(self, mod, name, L, eta):
        im, d = self.find(mod, name)
        ideal = self.fn(im, self.field(d, "Ideal")[1])
        actual = self.fn(im, self.field(d, "Actual")[1])
        audit = self.field(d, "Audit")[1]
        tin = self.tolerance(im, self.field(d, "InputDistance")[1])
        tout = self.tolerance(im, self.field(d, "OutputDistance")[1])
        pairs = self.field(d, "Pairs")
        xh, x = self.var(im, audit, "xh"), self.var(im, audit, "x")
        din = self.sub(1, tin(xh, x))
        dout = self.sub(1, tout(actual(xh), ideal(x)))
        cons = [self.member(im, audit, xh), self.member(im, audit, x),
                self.fn(im, pairs[1])((xh, x)) if pairs else True,
                self.lt(self.add(self.mul(L, din), eta), dout)]
        status, table, wit = self.obligations([("contract", cons, {"xh": xh, "x": x})])
        if wit is not None:
            vh, vx = wit["values"]["xh"], wit["values"]["x"]
            wit["out"] = 1 - self.tolerance(im, self.field(d, "OutputDistance")[1])(
                self.fn(im, self.field(d, "Actual")[1])(vh), self.fn(im, self.field(d, "Ideal")[1])(vx))
        return {"status": status, "witness": wit}

    # ------------------------------------------------------------ streams and monitors
    def stream(self, mod, name):
        """(rows, binding) of a frozen stream, or (None, InvalidInput result) when the file's digest
        differs from the declared one: nothing is computed from a stream that is not the one
        declared."""
        sm, d = self.find(mod, name)
        src = json.loads(self.field(d, "Source")[1])
        path = os.path.join(os.path.dirname(os.path.abspath(self.modules[sm].path)), src)
        digest = "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()
        declared = json.loads(self.field(d, "Digest")[1])
        if digest != declared:
            return None, {"status": "InvalidInput", "stream": name,
                          "mismatch": f"stream {name}: declared digest {declared}, file digest {digest}"}
        data = json.load(open(path))
        binding = {"stream": [sm, name], "digest": digest}
        for key in ("Population", "Selection", "Policy"):
            f = self.field(d, key)
            if f is not None:
                binding[key.lower()] = json.loads(f[1])
        return data, binding

    @staticmethod
    def log_mix(S, n, p):
        if p <= 0:
            return 0.0 if S == 0 else math.inf
        if p >= 1:
            return 0.0 if S == n else math.inf
        lbeta = math.lgamma(S + 1) + math.lgamma(n - S + 1) - math.lgamma(n + 2)
        return lbeta - S * math.log(p) - (n - S) * math.log(1 - p)

    def cs(self, S, n, level):
        thr = math.log(1 / level)
        phat = S / n

        def edge(a, b, inside_at_b):
            for _ in range(200):
                m = (a + b) / 2
                if (self.log_mix(S, n, m) < thr) == inside_at_b:
                    b = m
                else:
                    a = m
            return a, b
        lo = 0.0 if S == 0 else edge(0.0, phat, True)[0]
        hi = 1.0 if S == n else edge(1.0, phat, True)[0]
        return lo, hi

    def estimate_rate(self, mod, rq):
        args = {a[0]: a[1:] for a in rq[1:]}
        data, bind = self.stream(mod, args["On"][0])
        if data is None:
            return bind
        col = data["schema"].index(json.loads(args["Column"][0]))
        val = int(self.atom(args["Equals"][0]))
        level = float(self.ev(mod, args["Level"][0], {}, {}))
        rows = [r[col] for r in data["rows"]]
        S, n = sum(1 for v in rows if v == val), len(rows)
        lo, hi = self.cs(S, n, level)
        return {"status": "Estimated", "count": S, "observations": n, "lower": lo, "upper": hi,
                "level": level, "binding": bind}

    def compare_rates(self, mod, rq):
        args = {a[0]: a[1:] for a in rq[1:]}
        data, bind = self.stream(mod, args["On"][0])
        if data is None:
            return bind
        c1 = data["schema"].index(json.loads(args["First"][0]))
        c2 = data["schema"].index(json.loads(args["Second"][0]))
        val = int(self.atom(args["Equals"][0]))
        level = float(self.ev(mod, args["Level"][0], {}, {}))
        b = sum(1 for r in data["rows"] if r[c1] == val and r[c2] != val)
        c = sum(1 for r in data["rows"] if r[c1] != val and r[c2] == val)
        lo, hi = self.cs(b, b + c, level) if b + c else (0.0, 1.0)
        return {"status": "Estimated", "first_only": b, "second_only": c, "lower": lo, "upper": hi,
                "level": level, "binding": bind}

    def monitor_laws(self, mod, name):
        mm, d = self.find(mod, name)
        ctx = self.field(d, "Context")[1]
        contexts = self.enumerate_carrier(mm, ctx)
        null = {c: self.fn(mm, self.field(d, "Null")[1])(c) for c in contexts}
        alt = {c: self.fn(mm, self.field(d, "Alternative")[1])(c) for c in contexts}
        return null, alt

    def check_monitor(self, mod, name):
        null, alt = self.monitor_laws(mod, name)
        expect = {c: sum((alt[c].get(o, 0) for o in null[c]), F(0)) for c in null}
        valid = all(e <= 1 for e in expect.values())
        blind = all(null[c] == alt[c] for c in null)
        return {"status": "Checked", "valid": valid, "exactly_one": all(e == 1 for e in expect.values()),
                "blind": blind}

    def detect(self, mod, rq):
        names = [a for a in rq[1:] if isinstance(a, str)]
        args = {a[0]: a[1:] for a in rq[1:] if isinstance(a, list)}
        data, bind = self.stream(mod, args["On"][0])
        if data is None:
            return bind
        level = self.ev(mod, args["Level"][0], {}, {})
        combine = args.get("Combine", ["Union"])[0]
        laws = [self.monitor_laws(mod, nm) for nm in names]
        col = data["schema"].index("stale")
        e = [F(1)] * len(names)
        k = len(names)
        for t, row in enumerate(data["rows"], 1):
            o = row[col]
            for i, (null, alt) in enumerate(laws):
                c = next(iter(null))
                e[i] *= F(alt[c].get(o, 0)) / null[c][o]
            if combine == "Mixture":
                if sum(e) / k >= 1 / level:
                    return {"status": "Estimated", "binding": bind, "fired": "Mixture", "step": t,
                            "evalue": float(sum(e) / k)}
            else:
                for i in range(k):
                    if e[i] >= k / level:
                        return {"status": "Estimated", "binding": bind, "fired": names[i], "step": t,
                                "evalue": float(e[i])}
        return {"status": "Estimated", "binding": bind, "fired": None, "step": None,
                "evalue": float(sum(e) / k if combine == "Mixture" else max(e))}

    # ------------------------------------------------------------ dispatch
    def run(self, mod, rq):
        """Answers one request and records its assurance.  A Checked verdict whose obligations
        went to cvc5 rests on that backend's answer, which this evaluator does not replay, so it is
        reported as Conditional on (TrustedBackend cvc5 ...); verdicts decided by evaluation alone
        stay Checked (assurance Exact).  Derived results (lifts, safety along a simulation) inherit
        the backend use of their premises, since those are decided within the same request."""
        self.req_backend, self.req_text = False, hashlib.sha256()
        res = self.answer(mod, rq)
        if res.get("status") == "Checked":
            if self.req_backend:
                res["status"] = "Conditional"
                res["assumptions"] = [{"TrustedBackend": {
                    "solver": "cvc5", "version": cvc5.__version__, "logic": "ALL",
                    "obligations": "sha256:" + self.req_text.hexdigest()}}]
                res["assurance"] = "TrustedBackend"
            else:
                res["assurance"] = "Exact"
        elif res.get("status") == "Refuted":
            res["assurance"] = "Witness"
        elif res.get("status") == "Estimated":
            res["assurance"] = "Statistical"
        return res

    def answer(self, mod, rq):
        h = rq[0]
        args = {a[0]: a[1:] for a in rq[1:] if isinstance(a, list)}
        if h == "CheckStatistic":
            return self.check_statistic(mod, rq[1], args.get("Method", ["Symbolic"])[0])
        if h == "CheckNow":
            return self.check_now(mod, rq[1])
        if h == "CheckUpdates":
            return self.check_updates(mod, rq[1])
        if h == "CheckSimulation":
            return self.check_simulation(mod, rq[1])
        if h == "CheckSafety":
            return self.check_safety(mod, rq[1], args["Never"][0], args["Via"][0], args["Init"][0])
        if h == "CheckBlockPartition":
            b = args.get("Budget")
            return self.check_block_partition(mod, rq[1], args["Of"][0], int(b[0][1]) if b else None)
        if h == "CheckImplementation":
            g = args["Grade"]
            return self.check_implementation(mod, rq[1], self.ev(mod, g[0], {}, {}), self.ev(mod, g[1], {}, {}))
        if h == "EstimateRate":
            return self.estimate_rate(mod, rq)
        if h == "CompareRates":
            return self.compare_rates(mod, rq)
        if h == "CheckMonitor":
            return self.check_monitor(mod, rq[1])
        if h == "Detect":
            return self.detect(mod, rq)
        raise ValueError(f"no evaluator for {h}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    part1 = os.path.join(here, "memory_goals.metta")
    if not os.path.exists(part1):
        part1 = os.path.join(here, "..", "memgoals", "memory_goals.metta")
    W = World([part1, os.path.join(here, "live_memory.metta")])
    for path, (_, mod, rq) in [(p, f) for p, f in W.runs if p.endswith("live_memory.metta")]:
        res = W.run(mod, rq)
        print(mod, show(rq)[:70], "->", res.get("status"), {k: v for k, v in res.items() if k != "status"})
