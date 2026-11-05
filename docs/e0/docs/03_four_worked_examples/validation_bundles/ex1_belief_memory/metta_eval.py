"""A small reference evaluator for the map fragment used by the worked examples' modules.

It reads the modules with its own small reader, resolves imports, and evaluates Cases, Body and
Table maps, parameterized maps (Families), the Core arithmetic, NatArith (Lt, Le, Max, Min, Quot,
Rem), the bit-vector primitives on integers (SetBit, Slice, PopCount, BitOr, BitAnd, BitXor,
IsZero), and the proposed Laws primitives (Coin, Point, Indep, Image, LawOf, Expect).  Laws are
dicts from values to exact masses, evaluated on their support.  If evaluates only the branch it
selects.  The oracles of Examples 1 and 4 use it to check that the module defines the same
machines, processes, kernels and laws as the Python model, cell by cell.
"""
import os
import re
from fractions import Fraction as F
from itertools import product

TOKEN = re.compile(r'\s*(?:(;[^\n]*)|("(?:[^"\\]|\\.)*")|([()])|(!)|([^\s()";!]+))')


def read_forms(text):
    """Top-level forms of a MeTTaDinC file: ("form", sexpr) or ("run", sexpr)."""
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
    return x if isinstance(x, str) else "(" + " ".join(show(y) for y in x) + ")"


def is_num(a):
    return isinstance(a, str) and re.fullmatch(r"-?\d+", a) is not None


def num(a):
    return is_num(a)


class Module:
    def __init__(self, form):
        self.name = form[1]
        self.items = form[2:]
        self.decls = {}
        self.imports = []
        for it in self.items:
            if not isinstance(it, list) or not it:
                continue
            if it[0] == "Import":
                only = next(x for x in it[2:] if isinstance(x, list) and x[0] == "Only")
                self.imports.append((it[1], only[1:]))
            elif it[0] not in ("Profile", "Use") and len(it) > 1 and isinstance(it[1], str):
                self.decls[it[1]] = it


class World:
    def __init__(self, path):
        forms = read_forms(open(path).read())
        self.modules = {}
        for kind, form in forms:
            if kind == "form":
                m = Module(form)
                self.modules[m.name] = m
        self.elements = {}
        for m in self.modules.values():
            for it in m.decls.values():
                if it[0] == "Carrier":
                    for x in it[3:]:
                        if isinstance(x, list) and x and x[0] == "Enum":
                            for e in x[1:]:
                                if isinstance(e, str):
                                    self.elements[e] = True

    def lookup(self, mod, name):
        m = self.modules[mod]
        if name in m.decls:
            return mod, m.decls[name]
        for src, names in m.imports:
            if name in names:
                return self.lookup(src, name)
        return None

    def field(self, decl, key):
        for x in decl[2:]:
            if isinstance(x, list) and x and x[0] == key:
                return x
        return None

    # ------------------------------------------------------------ carriers
    def carrier(self, mod, name):
        _, d = self.lookup(mod, name)
        body = d[3] if not (isinstance(d[2], list) and d[2][0] == "Of") else d[3]
        for x in d[2:]:
            if isinstance(x, list) and x and x[0] == "Enum":
                return [self.atom(e) for e in x[1:]]
            if isinstance(x, list) and x and x[0] == "Product":
                return list(product(*[self.carrier(mod, c) for c in x[1:]]))
            if isinstance(x, list) and x and x[0] == "All":
                of = self.field(d, "Of")
                if isinstance(of[1], list) and of[1][0] == "BitVector":
                    return list(range(1 << int(of[1][1])))
        raise ValueError(f"carrier {name}")

    def atom(self, a):
        if num(a):
            return int(a)
        return a

    # ------------------------------------------------------------ evaluation
    def ev(self, mod, x, env, params):
        if isinstance(x, str):
            if x.startswith("$"):
                if x in env:
                    return env[x]
                if x in params:
                    return params[x]
                raise KeyError(x)
            if num(x):
                return int(x)
            if x.startswith('"'):
                return x
            if x in ("True", "False"):
                return x == "True"
            hit = self.lookup(mod, x)
            if hit and hit[1][0] == "Measure":
                return self.measure(hit[0], x)
            return x                                  # a symbol element
        h = x[0]
        E = lambda y: self.ev(mod, y, env, params)
        if h == "Rat":
            return F(int(x[1]), int(x[2]))
        if h == "Tuple":
            return tuple(E(y) for y in x[1:])
        if h == "GetTuple":
            return E(x[1])[int(x[2])]
        if h == "If":
            return E(x[2]) if E(x[1]) else E(x[3])
        if h == "Eq":
            return E(x[1]) == E(x[2])
        if h == "Lt":
            return E(x[1]) < E(x[2])
        if h == "Le":
            return E(x[1]) <= E(x[2])
        if h == "And":
            return all(E(y) for y in x[1:])
        if h == "Or":
            return any(E(y) for y in x[1:])
        if h == "Not":
            return not E(x[1])
        if h == "Add":
            return sum((E(y) for y in x[1:]), 0)
        if h == "Sub":
            return E(x[1]) - E(x[2])
        if h == "Mul":
            r = 1
            for y in x[1:]:
                r = r * E(y)
            return r
        if h == "Div":
            return F(E(x[1])) / E(x[2])
        if h == "Quot":
            b = E(x[2])
            if b <= 0:
                raise ValueError("Quot needs a positive divisor")
            return E(x[1]) // b
        if h == "Rem":
            b = E(x[2])
            if b <= 0:
                raise ValueError("Rem needs a positive divisor")
            return E(x[1]) % b
        if h == "SetBit":
            w, i, v = E(x[1]), E(x[2]), E(x[3])
            return (w & ~(1 << i)) | (v << i)
        if h == "Slice":
            w, lo, hi = E(x[1]), E(x[2]), E(x[3])
            return (w >> lo) & ((1 << (hi - lo + 1)) - 1)
        if h == "PopCount":
            return bin(E(x[1])).count("1")
        if h == "BitOr":
            return E(x[1]) | E(x[2])
        if h == "BitAnd":
            return E(x[1]) & E(x[2])
        if h == "BitXor":
            return E(x[1]) ^ E(x[2])
        if h == "IsZero":
            return E(x[1]) == 0
        if h == "Max":
            return max(E(x[1]), E(x[2]))
        if h == "Min":
            return min(E(x[1]), E(x[2]))
        if h == "Switch":
            v = params[x[1]] if x[1] in params else env[x[1]]
            for case in x[2:]:
                if case[0] == v:
                    return E(case[1])
            raise ValueError(f"Switch: no case {v}")
        if h == "Coin":
            p = F(E(x[1]))
            return {k: m for k, m in ((1, p), (0, 1 - p)) if m}
        if h == "Point":
            return {E(x[1]): F(1)}
        if h == "Indep":
            laws = [E(y) for y in x[1:]]
            out = {}
            for combo in product(*[list(L.items()) for L in laws]):
                v = tuple(c[0] for c in combo)
                m = F(1)
                for c in combo:
                    m *= c[1]
                out[v] = out.get(v, F(0)) + m
            return out
        if h == "Image":
            var, body, L = x[1], x[2], E(x[3])
            out = {}
            for v, m in L.items():
                w = self.ev(mod, body, dict(env, **{var: v}), params)
                out[w] = out.get(w, F(0)) + m
            return out
        if h == "LawOf":
            return E(x[1])
        if h == "Expect":
            return sum(v * m for v, m in E(x[1]).items())
        # map application, possibly with parameters
        hit = self.lookup(mod, h)
        if hit and hit[1][0] == "Map":
            return self.apply(hit[0], hit[1], [E(y) for y in x[1:]])
        raise ValueError(f"cannot evaluate {show(x)[:80]}")

    def measure(self, mod, name):
        _, d = self.lookup(mod, name)
        body = next(x for x in d[2:] if isinstance(x, list) and x[0] == "Masses")
        return {self.ev(mod, e[0], {}, {}): F(self.ev(mod, e[1], {}, {})) for e in body[1:]}

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
            var = body[1][0]
            return self.ev(mod, body[2], {var: arg}, params)
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
                raise ValueError(f"Cases {d[1]} at {arg}: {len(hits)} matches")
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
        return self.ev(mod, pat, {}, params) == v

    # ------------------------------------------------------------ declared objects
    def instance(self, mod, x):
        """A map or an instance (f p1 ... pk) of a parameterized map: returns a function."""
        if isinstance(x, str):
            m, d = self.lookup(mod, x)
            return lambda arg: self.call(m, d, {}, arg)
        m, d = self.lookup(mod, x[0])
        par = self.field(d, "Parameters")
        params = {pv: self.ev(mod, a, {}, {}) for (pv, _), a in zip(par[1:], x[1:])}
        return lambda arg: self.call(m, d, params, arg)

    def process(self, mod, name):
        m, d = self.lookup(mod, name)
        states = self.carrier(m, self.field(d, "States")[1])
        actions = self.carrier(m, self.field(d, "Actions")[1])
        k = self.instance(m, self.field(d, "Kernel")[1])
        r = self.instance(m, self.field(d, "RewardLaw")[1])
        g = self.ev(m, self.field(d, "Discount")[1], {}, {})
        return states, actions, (lambda x, a: k((x, a))), (lambda x, a: r((x, a))), g

    def kernel_rows(self, mod, name):
        m, d = self.lookup(mod, name)
        rows = {}
        for x in d[2:]:
            if isinstance(x, list) and x and x[0] == "Row":
                rows[x[1]] = {e[1]: F(self.ev(m, e[2], {}, {})) for e in x[2:]}
        return rows

    def machine(self, mod, name):
        m, d = self.lookup(mod, name)
        like = self.field(d, "Like")
        src = self.lookup(m, like[1])[1] if like else d
        obs = [(o[1], self.instance(m, o[2])) for o in src[2:] if isinstance(o, list) and o[0] == "Observe"]
        acts = [(a[1], self.kernel_rows(m, a[2])) for a in src[2:] if isinstance(a, list) and a[0] == "Action"]
        st = self.field(d, "States")[1]
        _, cd = self.lookup(m, st)
        reach = next((x for x in cd[2:] if isinstance(x, list) and x[0] == "Reach"), None)
        if reach:
            _, _, inner_acts, _ = self.machine(m, reach[1])
            todo = list(reach[2][1:])
            seen = list(todo)
            while todo:
                z = todo.pop(0)
                for _, rows in inner_acts:
                    for y in rows[z]:
                        if y not in seen:
                            seen.append(y)
                            todo.append(y)
            order = self.carrier(m, self.field(self.lookup(m, reach[1])[1], "States")[1])
            states = [s for s in order if s in seen]
        else:
            states = self.carrier(m, st)
        return states, obs, acts, d
