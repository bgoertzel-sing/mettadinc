"""A small reference evaluator for the modules of memory_goals.metta.

It reads the file with its own reader, evaluates carriers (Enum, Product, Subset, Reach), constants,
maps (Cases, Body and Table bodies, parameterized maps with Switch), the Core and NatArith
arithmetic used in the file, Coin from the proposed Laws library, and builds deterministic machines
(Observe and Action entries, compound labels with For, Like and ActionsOf), representations,
abstraction maps, block partitions, implementations and tolerances (Pullback, Meet,
OneMinusAbsoluteDifference).  The oracle uses it to rebuild every machine from the module text and
to rerun the checks, so that the module and the Python models are compared result by result.

It also reads the proposed Consumer declarations (Of, Accepts with its Conditional clause, Custody,
Decode), answers the proposed CheckInterpretation request, records the binding of a result (the
module digest and subject declarations, the machine with its states, queries, actions and merges and
the maps they apply, the scope, the assumptions and the assurance), and applies the gate's rule:
a result covers a touched consumer only when its binding names the consumer's machine and
interface, or a machine with the same states and actions whose queries include the consumer's, and
only when the consumer's Accepts declaration admits its status and assumptions.  It is a test aid
for this guide, not an implementation of MeTTaDinC.
"""
import hashlib
import json
import re
from fractions import Fraction as F
from itertools import product


class InvalidInput(ValueError):
    """A declaration or request that violates the admitted language; the message names the mismatch."""


def parse_accepts(vals):
    """(Accepts Checked [Estimated] [(Conditional entry+)]) with entries (TrustedBackend solver+)
    or (Assumption name+), as in the specification's registry, returned as
    {"statuses": [...], "backends": [{"solver": ...}, ...], "assumptions": [name, ...]}."""
    text = show(["Accepts"] + list(vals))
    if not vals or vals[0] != "Checked":
        raise InvalidInput(f"{text}: Accepts begins with Checked")
    statuses = ["Checked"]
    rest = list(vals[1:])
    if rest and rest[0] == "Estimated":
        statuses.append("Estimated")
        rest = rest[1:]
    if len(rest) > 1:
        raise InvalidInput(f"{text}: Accepts takes at most one Conditional clause")
    backends, assumptions = [], []
    for clause in rest:
        if not (isinstance(clause, list) and len(clause) > 1 and clause[0] == "Conditional"):
            raise InvalidInput(f"{text}: expected Estimated or (Conditional (TrustedBackend solver) ...)")
        for entry in clause[1:]:
            if not (isinstance(entry, list) and len(entry) >= 2 and entry[0] in ("TrustedBackend", "Assumption")
                    and all(isinstance(t, str) for t in entry[1:])):
                raise InvalidInput(f"{text}: expected (TrustedBackend solver+) or (Assumption name+)")
            if entry[0] == "TrustedBackend":
                backends += [{"solver": t.strip('"')} for t in entry[1:]]
            else:
                assumptions += [t.strip('"') for t in entry[1:]]
        statuses.append("Conditional")
    return {"statuses": statuses, "backends": backends, "assumptions": assumptions}

def admits(acc, result):
    """(accepted, reason): whether a parsed Accepts declaration admits a result's status and assumptions.
    A Conditional result is admitted only when every undischarged assumption is covered: a
    (TrustedBackend solver ...) assumption by a TrustedBackend entry naming the solver, an
    (Assumption name digest) by an Assumption entry naming the declaration, and an
    (EstimatedPremise result-digest delta) by Estimated in the declaration."""
    st = result["status"]
    asm = result.get("binding", {}).get("assumptions", [])
    if st == "Checked":
        return (True, None) if not asm else (False, "a Checked result carries no assumptions")
    if st == "Estimated":
        ok = "Estimated" in acc["statuses"]
        return ok, None if ok else "the consumer does not accept Estimated results"
    if st == "Conditional":
        if not asm:
            return False, "a Conditional result names its assumptions"
        for a in asm:
            kind, body = next(iter(a.items())) if isinstance(a, dict) and len(a) == 1 else (None, None)
            if kind == "TrustedBackend":
                if not any(all(body.get(k) == v for k, v in b.items()) for b in acc["backends"]):
                    return False, f"the consumer does not accept results that rest on {body.get('solver')}"
            elif kind == "Assumption":
                if body.get("name") not in acc["assumptions"]:
                    return False, f"the consumer does not accept results that rest on the assumption {body.get('name')}"
            elif kind == "EstimatedPremise":
                if "Estimated" not in acc["statuses"]:
                    return False, "the consumer does not accept results derived from estimates"
            else:
                return False, f"the assumption {json.dumps(a)} has no registered form"
        return True, None
    return False, f"a result with status {st} is not coverage"


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
    return x if isinstance(x, str) else "(" + " ".join(show(y) for y in x) + ")"


def is_num(a):
    return isinstance(a, str) and re.fullmatch(r"-?\d+", a) is not None


class Module:
    def __init__(self, form):
        self.name = form[1]
        self.form = form
        self.decls = {}
        self.order = []
        for it in form[2:]:
            if isinstance(it, list) and it and it[0] not in ("Profile", "Use") and len(it) > 1 \
                    and isinstance(it[1], str):
                self.decls[it[1]] = it
                self.order.append(it[1])


class World:
    def __init__(self, path):
        forms = read_forms(open(path).read())
        self.modules = {}
        self.runs = []
        for kind, form in forms:
            if kind == "form":
                m = Module(form)
                self.modules[m.name] = m
            else:
                self.runs.append(form)
        self._carriers = {}

    def decl(self, mod, name):
        return self.modules[mod].decls[name]

    def field(self, d, key):
        for x in d[2:]:
            if isinstance(x, list) and x and x[0] == key:
                return x
        return None

    def fields(self, d, key):
        return [x for x in d[2:] if isinstance(x, list) and x and x[0] == key]

    # ------------------------------------------------------------ values
    def atom(self, a):
        if is_num(a):
            return int(a)
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
                raise KeyError(x)
            if is_num(x) or x in ("True", "False"):
                return self.atom(x)
            d = self.modules[mod].decls.get(x)
            if d is not None and d[0] == "Const":
                return self.ev(mod, d[3], {}, {})
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
            a, b = E(x[1]), E(x[2])
            assert b > 0 and a >= 0
            return a // b
        if h == "Max":
            return max(E(x[1]), E(x[2]))
        if h == "Min":
            return min(E(x[1]), E(x[2]))
        if h == "Switch":
            v = params[x[1]] if x[1] in params else env[x[1]]
            for case in x[2:]:
                if self.atom(case[0]) == v:
                    return E(case[1])
            raise ValueError(f"Switch: no case {v}")
        if h == "Coin":
            p = F(E(x[1]))
            return {k: m for k, m in ((1, p), (0, 1 - p)) if m}
        d = self.modules[mod].decls.get(h)
        if d is not None and d[0] == "Map":
            return self.apply(mod, d, [E(y) for y in x[1:]])
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

    def fn(self, mod, x):
        """A map name or an instance (f p1 ... pk) of a parameterized map, as a Python function.
        Values are memoized: maps are pure."""
        if isinstance(x, str):
            d = self.decl(mod, x)
            params = {}
        else:
            d = self.decl(mod, x[0])
            par = self.field(d, "Parameters")
            params = {pv: self.ev(mod, a, {}, {}) for (pv, _), a in zip(par[1:], x[1:])}
        memo = {}

        def f(arg):
            if arg not in memo:
                memo[arg] = self.call(mod, d, params, arg)
            return memo[arg]
        return f

    # ------------------------------------------------------------ carriers
    def carrier(self, mod, name):
        key = (mod, name)
        if key in self._carriers:
            return self._carriers[key]
        d = self.decl(mod, name)
        body = d[-1]
        if body[0] == "Enum":
            out = [self.atom(e) for e in body[1:]]
        elif body[0] == "Product":
            out = list(product(*[self.carrier(mod, c) for c in body[1:]]))
        elif body[0] == "Subset":
            base = self.carrier(mod, body[1])
            pred = self.fn(mod, body[2])
            out = [s for s in base if pred(s)]
        elif body[0] == "Reach":
            mname = body[1]
            states, acts = self.raw_machine(mod, mname)
            starts = [self.ev(mod, e, {}, {}) for e in body[2][1:]]
            seen = set(starts)
            todo = list(starts)
            while todo:
                z = todo.pop(0)
                for _, f in acts:
                    y = f(z)
                    if y not in seen:
                        seen.add(y)
                        todo.append(y)
            out = [s for s in states if s in seen]
        else:
            raise ValueError(f"carrier {name}: {body[0]}")
        self._carriers[key] = out
        return out

    # ------------------------------------------------------------ machines
    def entry_exprs(self, mod, d, kind):
        """Observe, Action or Merge entries of a machine as (label, map expression, tolerance name or
        None), with Like and ActionsOf resolved and For families expanded in declaration order."""
        out = []
        like = self.field(d, "Like")
        if like is not None:
            return self.entry_exprs(mod, self.decl(mod, like[1]), kind)
        if kind == "Action":
            acts_of = self.field(d, "ActionsOf")
            if acts_of is not None:
                return self.entry_exprs(mod, self.decl(mod, acts_of[1]), "Action")
        for x in self.fields(d, kind):
            rest = x[1:]
            fors = [y for y in rest if isinstance(y, list) and y and y[0] == "For"]
            vals = [y for y in rest if isinstance(y, list) and y and y[0] == "Values"]
            core = [y for y in rest if not (isinstance(y, list) and y and y[0] in ("For", "Values"))]
            label, mp = core
            tol = vals[0][1] if vals else None
            if not fors:
                out.append((show(label), mp, tol))
                continue
            names = [f[1] for f in fors]
            for combo in product(*[self.carrier(mod, f[2]) for f in fors]):
                env = {n: str(v) for n, v in zip(names, combo)}
                sub = lambda t: env.get(t, t) if isinstance(t, str) else [sub(u) for u in t]
                out.append((show(sub(label)), sub(mp), tol))
        return out

    def entries(self, mod, d, kind):
        """Observe or Action entries of a machine as (label, function), in declaration order."""
        return [(lab, self.fn(mod, e)) for lab, e, _ in self.entry_exprs(mod, d, kind)]

    def raw_machine(self, mod, name):
        d = self.decl(mod, name)
        states = self.carrier(mod, self.field(d, "States")[1])
        return states, self.entries(mod, d, "Action")

    def machine(self, mod, name):
        """(states, actions, observers): lists of (label, function) in declaration order."""
        d = self.decl(mod, name)
        states = self.carrier(mod, self.field(d, "States")[1])
        return states, self.entries(mod, d, "Action"), self.entries(mod, d, "Observe")

    def representation(self, mod, name):
        d = self.decl(mod, name)
        return self.field(d, "Of")[1], self.fn(mod, self.field(d, "Encode")[1])

    def abstraction_map(self, mod, name):
        d = self.decl(mod, name)
        return self.field(d, "Source")[1], self.field(d, "Target")[1], self.fn(mod, self.field(d, "Map")[1])

    def block_predicate(self, mod, name):
        d = self.decl(mod, name)
        blk = self.field(d, "Block")
        pred = blk[2]
        var = pred[1][0]
        return lambda s: self.ev(mod, pred[2], {var: s}, {})

    def tolerance(self, mod, name):
        d = self.decl(mod, name)
        return self.tol_body(mod, d[-1])

    def tol_body(self, mod, b):
        if b[0] == "OneMinusAbsoluteDifference":
            return lambda x, y: 1 - abs(F(x) - F(y))
        if b[0] == "Pullback":
            f = self.fn(mod, b[1])
            t = self.tolerance(mod, b[2])
            return lambda x, y: t(f(x), f(y))
        if b[0] == "Meet":
            parts = [self.tol_body(mod, c) for c in b[1:]]
            return lambda x, y: min(p(x, y) for p in parts)
        raise ValueError(f"tolerance {b[0]}")

    def implementation(self, mod, name):
        d = self.decl(mod, name)
        ideal = self.fn(mod, self.field(d, "Ideal")[1])
        actual = self.fn(mod, self.field(d, "Actual")[1])
        audit = self.carrier(mod, self.field(d, "Audit")[1])
        tin = self.tolerance(mod, self.field(d, "InputDistance")[1])
        tout = self.tolerance(mod, self.field(d, "OutputDistance")[1])
        pairs = self.field(d, "Pairs")
        ok = None
        if pairs is not None:
            pf = self.fn(mod, pairs[1])
            ok = lambda a, b: pf((a, b))
        return ideal, actual, audit, (lambda x, y: 1 - tin(x, y)), (lambda x, y: 1 - tout(x, y)), ok

    # ------------------------------------------------------------ identities and bindings
    def module_digest(self, mod):
        """SHA-256 of the module's normalized text: the printed form, without comments."""
        return "sha256:" + hashlib.sha256(show(self.modules[mod].form).encode()).hexdigest()

    def interface(self, mod, mname):
        """A machine's interface: its state carrier, each query, action and merge label with the map
        it applies, and the value tolerances of the queries ("exact" when none is declared)."""
        d = self.decl(mod, mname)
        if d[0] != "Machine":
            raise InvalidInput(f"{mname} is a {d[0]}, not a Machine")
        table = lambda kind: {lab: show(e) for lab, e, _ in self.entry_exprs(mod, d, kind)}
        tols = {lab: t or "exact" for lab, _, t in self.entry_exprs(mod, d, "Observe")}
        return {"machine": mname, "states": self.field(d, "States")[1], "queries": table("Observe"),
                "actions": table("Action"), "merges": table("Merge"),
                "tolerance": "exact" if all(t == "exact" for t in tols.values()) else tols}

    def binding(self, mod, subject, scope, assumptions=(), assurance="Exact"):
        """The binding of a result about a representation or a machine: the module and its digest,
        the subject declarations, the machine's interface, the scope, the assumptions and the
        assurance."""
        d = self.decl(mod, subject)
        if d[0] == "Representation":
            mname, names = self.field(d, "Of")[1], [subject, show(self.field(d, "Encode")[1])]
        elif d[0] == "Machine":
            mname, names = subject, [subject]
        else:
            raise InvalidInput(f"no binding for the {d[0]} {subject}")
        b = {"module": mod, "module_digest": self.module_digest(mod), "subject": names}
        b.update(self.interface(mod, mname))
        b.update({"scope": dict(scope), "assumptions": list(assumptions), "assurance": assurance})
        return b

    # ------------------------------------------------------------ consumers and goal meaning
    def consumer(self, mod, name):
        """A Consumer declaration: its machine, what it accepts, its custody and its decoder."""
        d = self.modules[mod].decls.get(name)
        if d is None or d[0] != "Consumer":
            raise InvalidInput(f"{name} is not a Consumer of {mod}")
        dec = self.field(d, "Decode")
        return {"name": name, "module": mod, "of": self.field(d, "Of")[1],
                "accepts": parse_accepts(self.field(d, "Accepts")[1:]),
                "custody": self.field(d, "Custody")[1], "decode": None if dec is None else dec[1]}

    def goal_answer(self, mod, mname):
        """A machine's goal answer: the value of its observer, or the tuple of its observers' values
        in declaration order."""
        obs = self.entries(mod, self.decl(mod, mname), "Observe")
        if len(obs) == 1:
            return obs[0][1]
        return lambda s: tuple(f(s) for _, f in obs)

    def check_interpretation(self, mod, old, new, via=None):
        """The interpretation obligation: d_new(g_new(h x)) = d_old(g_old(x)) for every valid record x
        of the old consumer's machine, h the Via map or the identity.  Checked by enumeration, Refuted
        with the least record whose decisions differ, InvalidInput naming a mismatch."""
        def invalid(why):
            return {"status": "InvalidInput", "reason": why}
        try:
            co, cn = self.consumer(mod, old), self.consumer(mod, new)
        except InvalidInput as e:
            return invalid(str(e))
        for c in (co, cn):
            if c["decode"] is None:
                return invalid(f"{c['name']} declares no decoder (Decode)")
        mo, mn = co["of"], cn["of"]
        io, inew = self.interface(mod, mo), self.interface(mod, mn)
        if via is None:
            if io["states"] != inew["states"]:
                return invalid(f"{mo} has states {io['states']} and {mn} has states {inew['states']}; "
                               "a change of record schema needs (Via map)")
            h = lambda x: x
        else:
            d = self.modules[mod].decls.get(via)
            if d is None or d[0] != "AbstractionMap":
                return invalid(f"{via} is not an AbstractionMap of {mod}")
            src, tgt, h = self.abstraction_map(mod, via)
            if src != mo:
                return invalid(f"{via} starts from {src}, not from {mo}, the machine of {old}")
            if tgt != mn:
                return invalid(f"{via} ends at {tgt}, not at {mn}, the machine of {new}")
        records = self.carrier(mod, io["states"])
        targets = set(self.carrier(mod, inew["states"]))
        g_old, g_new = self.goal_answer(mod, mo), self.goal_answer(mod, mn)
        d_old, d_new = self.fn(mod, co["decode"]), self.fn(mod, cn["decode"])
        side = lambda c, i: {"consumer": c["name"], "machine": c["of"], "queries": i["queries"],
                             "decoder": c["decode"], "custody": c["custody"]}
        binding = {"module": mod, "module_digest": self.module_digest(mod),
                   "subject": [old, new] + ([via] if via else []),
                   "old": side(co, io), "new": side(cn, inew), "via": via,
                   "scope": {"records": io["states"], "count": len(records)}, "assumptions": []}
        for x in records:
            y = h(x)
            if y not in targets:
                return invalid(f"{via} maps {x} outside the states {inew['states']} of {mn}")
            a_old, a_new = g_old(x), g_new(y)
            try:
                e_old, e_new = d_old(a_old), d_new(a_new)
            except ValueError as e:
                return invalid(f"a decoder has no value for an answer: {e}")
            if e_old != e_new:
                binding["assurance"] = "Witness"
                return {"status": "Refuted", "binding": binding,
                        "witness": {"record": x, "old_answer": a_old, "new_answer": a_new,
                                    "old_decision": e_old, "new_decision": e_new}}
        binding["assurance"] = "Exact"
        return {"status": "Checked", "binding": binding}

    def run_request(self, mod, rq):
        """Answers a CheckInterpretation request of the module text; the oracle reruns the other
        requests on the rebuilt objects."""
        if not (isinstance(rq, list) and rq and rq[0] == "CheckInterpretation"):
            raise ValueError(f"run_request answers CheckInterpretation only: {show(rq)}")
        via = [a[1] for a in rq[3:] if isinstance(a, list) and a and a[0] == "Via"]
        return self.check_interpretation(mod, rq[1], rq[2], via[0] if via else None)

    # ------------------------------------------------------------ the gate
    def accepts(self, mod, consumer, result):
        """(accepted, reason): whether the consumer's Accepts declaration admits the result's status
        and assumptions (the function admits)."""
        acc = self.consumer(mod, consumer)["accepts"]
        if result["status"] == "Conditional" and "Conditional" not in acc["statuses"] and not any(
                "EstimatedPremise" in a for a in result.get("binding", {}).get("assumptions", [])
                if isinstance(a, dict)):
            return False, f"{consumer} accepts no Conditional result"
        ok, why = admits(acc, result)
        return ok, None if ok else why.replace("the consumer", consumer)

    def covers(self, mod, consumer, b):
        """(covers, how or why): whether a result's binding names the consumer's machine and interface,
        either exactly or through a machine with the same states, actions, merges and tolerances
        whose queries include the consumer's queries with the same maps (the transport rule for
        removed queries)."""
        c = self.consumer(mod, consumer)
        want = self.interface(mod, c["of"])
        where = f"bound to {b.get('machine')}"
        if b.get("module") != mod or b.get("module_digest") != self.module_digest(mod):
            return False, f"{where} in module {b.get('module')} with another digest, not in {mod}"
        for key in ("states", "actions", "merges"):
            if b.get(key) != want[key]:
                return False, f"{where}, whose {key} differ from those of {c['of']}, which {consumer} reads"
        tol = lambda t, q: t if isinstance(t, str) else t.get(q, "exact")
        missing = [q for q, m in want["queries"].items()
                   if b.get("queries", {}).get(q) != m or tol(b.get("tolerance"), q) != tol(want["tolerance"], q)]
        if missing:
            return False, (f"{where}, checked without the query {', '.join(missing)} that {consumer} "
                           f"reads through {c['of']}")
        return True, "exact" if b.get("machine") == c["of"] else "removed queries"

    def gate(self, bundle):
        """For each touched consumer: "blocked" when a result bound to it is Refuted; "covered" when
        results are bound to it and it accepts every one of them; "inadequate" otherwise.  A result
        bound elsewhere is recorded as InvalidInput for that consumer with the mismatch named."""
        out = {}
        for t in bundle["touched"]:
            mod, name = t["module"], t["consumer"]
            notes, bound, flawed = [], [], False
            if t.get("custody") not in (None, self.consumer(mod, name)["custody"]):
                notes.append({"status": "InvalidInput", "mismatch": f"{name} is not of custody {t['custody']}"})
                flawed = True
            for r in bundle["results"]:
                ok, why = self.covers(mod, name, r["binding"])
                if ok:
                    bound.append(r)
                else:
                    notes.append({"request": r["request"], "status": "InvalidInput", "mismatch": why})
            if any(r["status"] == "Refuted" for r in bound):
                verdict = "blocked"
            else:
                for r in bound:
                    ok, why = self.accepts(mod, name, r)
                    if not ok:
                        notes.append({"request": r["request"], "status": r["status"], "not_accepted": why})
                        flawed = True
                verdict = "covered" if bound and not flawed else "inadequate"
            out[name] = {"verdict": verdict, "notes": notes}
        return out
