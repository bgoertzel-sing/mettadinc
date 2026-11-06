"""Translation validation on small instances of the same policy.

Source against encoding (the obligations the oracle discharges come from this route).  On the
two-user (20-bit) instance of access_policy.metta, for every word, every action, every observer and
every alarm, the direct interpreter of the source terms, the intermediate form (IR) and the CNF
generated from the IR agree; and every closure obligation's CNF is satisfiable with a given start
word exactly when the interpreter says that word violates the obligation.  The CNF side is
evaluated by propagating the inputs through the recorded gates, after a structural check that the
gate clauses admit exactly one extension of every input assignment.

Independent model against source (differential).  The hand-written Python model of rbac.py
(vectorized below as vec_step) and the hand-written encoder of circuits.py are compared with the
source: point by point at 20 bits, and obligation by obligation (enumeration against CNF) as before:
closure obligations at 20 bits and two-copy miters at 10 bits.
"""
import itertools
import numpy as np
from pysat.solvers import Solver
from circuits import *
from sat_obligations import closure_obligations
import policy_ir as pir
import obligations as ob

def vec_bit(x, i): return (x >> np.uint64(i)) & np.uint64(1)
def vec_step(x, a, written, nu):
    k, u, r = a
    one = np.uint64(1)
    oa = np.zeros_like(x, dtype=bool)
    for v in range(nu):
        if v != u: oa |= vec_bit(x, S(v, 4)).astype(bool)
    b = lambda i: vec_bit(x, i).astype(bool)
    if k == "assign":
        pre = {0: np.ones_like(oa), 1: b(A(u, 0)), 2: b(A(u, 1)) & ~(b(S(u, 3)) if written else b(A(u, 3))),
               3: b(A(u, 0)) & ~b(A(u, 2)), 4: b(A(u, 0))}[r]
        g = oa & pre
        return np.where(g, x | (one << np.uint64(A(u, r))), x)
    if k == "revoke":
        close = CLOSE_WRITTEN if written else CLOSE
        m = np.uint64(0)
        for q in close[r]: m |= (one << np.uint64(A(u, q))) | (one << np.uint64(S(u, q)))
        return np.where(oa, x & ~m, x)
    if k == "activate":
        g = b(A(u, r))
        if r == 2: g &= ~b(S(u, 3))
        if r == 3: g &= ~b(S(u, 2))
        return np.where(g, x | (one << np.uint64(S(u, r))), x)
    return x & ~(one << np.uint64(S(u, r)))

def vec_consistent(x, nu):
    ok = np.ones(x.shape, dtype=bool)
    b = lambda i: vec_bit(x, i).astype(bool)
    for u in range(nu):
        for r in range(NR): ok &= ~b(S(u, r)) | b(A(u, r))
        ok &= (~b(A(u, 1)) | b(A(u, 0))) & (~b(A(u, 2)) | b(A(u, 1))) & (~b(A(u, 3)) | b(A(u, 0)))
        ok &= (~b(A(u, 4)) | b(A(u, 0))) & (~b(A(u, 2)) | ~b(A(u, 3)))
    return ok
def vec_nosod(x, nu):
    b = lambda i: vec_bit(x, i).astype(bool)
    return np.logical_and.reduce([~(b(A(u, 2)) & b(A(u, 3))) for u in range(nu)])
def vec_noclerkless(x, nu):
    b = lambda i: vec_bit(x, i).astype(bool)
    return np.logical_and.reduce([~b(S(u, 2)) | b(A(u, 1)) for u in range(nu)])


def closure_agreement():
    nu = 2
    X = np.arange(1 << (10 * nu), dtype=np.uint64)
    agree, total = 0, 0
    for written in (False, True):
        for inv_name, venc, cenc in (("consistent", vec_consistent, enc_consistent), ("nosod", vec_nosod, enc_no_sod),
                                     ("noclerkless", vec_noclerkless, enc_no_clerkless)):
            for a, c, tag in closure_obligations(written, inv_name, cenc, nu=nu):
                enum_sat = bool((venc(X, nu) & ~venc(vec_step(X, a, written, nu), nu)).any())
                s = Solver(name="cadical153", bootstrap_with=c.clauses); sat = s.solve(); s.delete()
                total += 1; agree += (sat == enum_sat)
    return agree, total


def miter_agreement():
    import itertools
    X = np.arange(1 << 10, dtype=np.uint64)
    P = Policy(written=False, nu=1)
    agree, total = 0, 0
    for keep in itertools.combinations(range(10), 3):
        mask = np.uint64(sum(1 << i for i in keep))
        for a in P.actions:
            Y = vec_step(X, a, False, 1)
            cx = X & mask; cy = Y & mask
            enum_sat = any(len(np.unique(cy[cx == code])) > 1 for code in np.unique(cx))
            c = CNF(); x = c.inputs(10); xp = c.inputs(10)
            for i in keep:
                c.clauses.append([-c.XOR(x[i], xp[i])])
            y = enc_step(c, x, a, False, 1); yp = enc_step(c, xp, a, False, 1)
            c.clauses.append([c.OR([c.XOR(y[i], yp[i]) for i in keep])])
            s = Solver(name="cadical153", bootstrap_with=c.clauses); sat = s.solve(); s.delete()
            total += 1; agree += (sat == enum_sat)
    return agree, total


# ------------------------------------------------------------------------------------ source route
SMALL = ("alice", "bob")


def _cnf_word(c, lits, val):
    out = np.zeros(next(iter(val.values())).shape, dtype=np.uint64)
    for i, l in enumerate(lits):
        v = val[l] if l > 0 else ~val[-l]
        out |= v.astype(np.uint64) << np.uint64(i)
    return out


def _inputs(xvars, X):
    return {v: ((X >> np.uint64(i)) & np.uint64(1)).astype(bool) for i, v in enumerate(xvars)}


def source_pointwise(src, users=SMALL):
    """Interpreter, IR and CNF on every word of the small instance: actions, observers, alarms."""
    el = pir.Elaborator(src, users)
    I = pir.SourceInterpreter(src, users)
    X = np.arange(1 << el.width, dtype=np.uint64)
    out = {"words": int(X.size), "actions": [0, 0], "queries": [0, 0], "structure": [0, 0]}
    for mod in ("AccessPolicy", "AccessPolicyFixed"):
        pol = pir.Policy(el, mod)
        ents = I.machine_entries(mod, "Policy")
        acts = [e for e in ents if e[0] == "Action"]
        for i, (_, lab, m, term) in enumerate(acts):
            ys = I.apply(m, term, X)
            yi = pol.step_array(X, i)
            c = pir.CNF(el.ir)
            x = c.inputs(el.width)
            y = ob.step_lits(c, pol, i, x)
            val, sat = c.evaluate(_inputs(x, X))
            yc = _cnf_word(c, y, val)
            out["actions"][1] += 1
            out["actions"][0] += bool(lab == pol.labels[i] and np.array_equal(ys, yi) and np.array_equal(ys, yc)
                                      and sat.all())
            out["structure"][1] += 1
            out["structure"][0] += c.structure_ok()
        queries = [(lab, ("map", m, term)) for k, lab, m, term in ents if k == "Observe"]
        queries += [(name, ("pred", mod, name)) for name in ("sod-breach", "clerkless-approval", "consistent")]
        for (lab, node), (qlab, how) in zip(pol.obs + [(n, el.predicate(mod, n)) for n in
                                                      ("sod-breach", "clerkless-approval", "consistent")], queries):
            vs = I.apply(how[1], how[2], X) if how[0] == "map" else I.predicate(mod, how[2], X)
            vs = np.broadcast_to(np.asarray(vs, dtype=bool), X.shape)
            vi = el.ir.eval(node, X)
            c = pir.CNF(el.ir)
            x = c.inputs(el.width)
            l = c.lit(node, x, {})
            val, sat = c.evaluate(_inputs(x, X))
            vc = val[l] if l > 0 else ~val[-l]
            out["queries"][1] += 1
            out["queries"][0] += bool(lab == qlab and np.array_equal(vs, vi) and np.array_equal(vs, vc) and sat.all())
            out["structure"][1] += 1
            out["structure"][0] += c.structure_ok()
    return out


def source_obligations_pointwise(src, users=SMALL):
    """Every closure obligation of the small instance, from the IR: its CNF is satisfiable with
    start word x exactly when the interpreter finds inv(x) and not inv(T_a x); and the solver's
    answer is that of enumeration."""
    el = pir.Elaborator(src, users)
    I = pir.SourceInterpreter(src, users)
    X = np.arange(1 << el.width, dtype=np.uint64)
    pointwise, solver, total = 0, 0, 0
    for mod in ("AccessPolicy", "AccessPolicyFixed"):
        pol = pir.Policy(el, mod)
        acts = [e for e in I.machine_entries(mod, "Policy") if e[0] == "Action"]
        for name in ("consistent", "sod-breach", "clerkless-approval"):
            node = el.predicate(mod, name)
            inv = node if name == "consistent" else el.ir.NOT(node)
            vx = I.predicate(mod, name, X)
            vx = vx if name == "consistent" else ~vx
            for i, (_, lab, m, term) in enumerate(acts):
                ys = I.apply(m, term, X)
                vy = I.predicate(mod, name, ys)
                vy = vy if name == "consistent" else ~vy
                want = vx & ~vy
                c, x = ob.closure(pol, inv, i)
                _, sat = c.evaluate(_inputs(x, X))
                s = Solver(name="cadical153", bootstrap_with=c.clauses)
                ans = s.solve()
                s.delete()
                total += 1
                pointwise += bool(c.structure_ok() and np.array_equal(sat, want))
                solver += bool(ans == bool(want.any()))
    return pointwise, solver, total


def model_against_source(src, users=SMALL):
    """The independent Python model (vec_step) against the interpreter, every word and action."""
    el = pir.Elaborator(src, users)
    I = pir.SourceInterpreter(src, users)
    X = np.arange(1 << el.width, dtype=np.uint64)
    agree, total, first = 0, 0, None
    for mod, written in (("AccessPolicy", True), ("AccessPolicyFixed", False)):
        acts = [e for e in I.machine_entries(mod, "Policy") if e[0] == "Action"]
        model = Policy(written=written, nu=len(users))
        for (_, lab, m, term), a in zip(acts, model.actions):
            ys = I.apply(m, term, X)
            ym = vec_step(X, a, written, len(users))
            same = lab == label(a) and np.array_equal(ys, ym)
            if not same and first is None:
                w = int(np.nonzero(ys != ym)[0][0])
                first = (mod, lab, w)
            total += 1
            agree += same
    return agree, total, first
