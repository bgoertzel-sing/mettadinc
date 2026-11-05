"""Exact reachable sets with binary decision diagrams (dd).

reach_ir computes the reachable set of a machine elaborated from the source (policy_ir.Policy): each
action is taken in its guarded-update normal form "if g then set these bits", read off the IR, and
the image of a set R is (R and not g) or ((exists written bits. R and g) and the written values).
The formula needs the guard not to read the bits it writes; the elaborator checks that condition
(Policy.writes_ok) and reach_ir refuses an action that fails it.

reach is the same computation from the hand-written guards of the independent model (rbac.py); the
oracle compares the two sets in one manager as a differential check.
"""
import time, json, sys
from dd.autoref import BDD
from rbac import *


def build(nu=NU):
    bdd = BDD()
    names = [f"x{i}" for i in range(10 * nu)]
    bdd.declare(*names)
    X = [bdd.var(n) for n in names]
    return bdd, names, X


def OR(bdd, items):
    out = bdd.false
    for it in items:
        out = out | it
    return out


def AND(bdd, items):
    out = bdd.true
    for it in items:
        out = out & it
    return out


def guards(bdd, X, a, written, nu):
    k, u, r = a
    oa = OR(bdd, [X[S(v, 4)] for v in range(nu) if v != u])
    if k == "assign":
        pre = {0: bdd.true, 1: X[A(u, 0)],
               2: X[A(u, 1)] & ~(X[S(u, 3)] if written else X[A(u, 3)]),
               3: X[A(u, 0)] & ~X[A(u, 2)], 4: X[A(u, 0)]}[r]
        return oa & pre
    if k == "revoke":
        return oa
    if k == "activate":
        g = X[A(u, r)]
        if r == 2:
            g = g & ~X[S(u, 3)]
        if r == 3:
            g = g & ~X[S(u, 2)]
        return g
    return bdd.true


def image(bdd, names, X, R, a, written, nu):
    """Image of R under a deterministic guarded update that sets or clears a few bits."""
    k, u, r = a
    g = guards(bdd, X, a, written, nu)
    close = CLOSE_WRITTEN if written else CLOSE
    if k == "assign":
        bits, val = [A(u, r)], True
    elif k == "revoke":
        bits = [A(u, q) for q in close[r]] + [S(u, q) for q in close[r]]
        val = False
    elif k == "activate":
        bits, val = [S(u, r)], True
    else:
        bits, val = [S(u, r)], False
    moved = R & g
    rest = R & ~g
    ex = bdd.exist([names[i] for i in bits], moved)
    lit = AND(bdd, [X[i] if val else ~X[i] for i in bits])
    return rest | (ex & lit)


def node_bdd(bdd, X, ir, n, memo):
    """The BDD of an IR node over the variables X."""
    if n in memo:
        return memo[n]
    k = ir.nodes[n]
    if k[0] == "true":
        r = bdd.true
    elif k[0] == "false":
        r = bdd.false
    elif k[0] == "bit":
        r = X[k[1]]
    elif k[0] == "not":
        r = ~node_bdd(bdd, X, ir, k[1], memo)
    elif k[0] == "and":
        r = AND(bdd, [node_bdd(bdd, X, ir, a, memo) for a in k[1]])
    elif k[0] == "or":
        r = OR(bdd, [node_bdd(bdd, X, ir, a, memo) for a in k[1]])
    else:
        c, t, e = (node_bdd(bdd, X, ir, a, memo) for a in k[1:])
        r = (c & t) | (~c & e)
    memo[n] = r
    return r


def reach_ir(pol, init, manager=None):
    """Reachable set of an elaborated machine from init, by chaotic iteration of its images."""
    bdd, names, X = manager if manager is not None else build(pol.el.width // 10)
    memo = {}
    acts = []
    for a, g in enumerate(pol.guarded):
        if g is None or not pol.writes_ok[a]:
            raise ValueError(f"{pol.labels[a]}: not a guarded update whose guard avoids its writes")
        guard, writes = g
        lit = AND(bdd, [X[i] if v else ~X[i] for i, v in sorted(writes.items())])
        acts.append((node_bdd(bdd, X, pol.ir, guard, memo), [names[i] for i in sorted(writes)], lit))
    R = AND(bdd, [X[i] if (init >> i) & 1 else ~X[i] for i in range(pol.el.width)])
    rounds = 0
    while True:
        old = R
        for g, w, lit in acts:
            moved = R & g
            R = R | ((R & ~g) | (bdd.exist(w, moved) & lit))
        rounds += 1
        if R == old:
            break
    return bdd, names, X, R, rounds


def reach(written, nu=NU, init=INIT, manager=None):
    bdd, names, X = manager if manager is not None else build(nu)
    P = Policy(written=written, nu=nu)
    R = AND(bdd, [X[i] if (init >> i) & 1 else ~X[i] for i in range(10 * nu)])
    rounds = 0
    while True:
        old = R
        for a in P.actions:          # chaotic iteration: apply each image in turn
            R = R | image(bdd, names, X, R, a, written, nu)
        rounds += 1
        if R == old:
            break
    return bdd, names, X, R, rounds


def consistent_bdd(bdd, X, nu):
    parts = []
    for u in range(nu):
        for r in range(NR):
            parts.append(~X[S(u, r)] | X[A(u, r)])
        parts += [~X[A(u, 1)] | X[A(u, 0)], ~X[A(u, 2)] | X[A(u, 1)], ~X[A(u, 3)] | X[A(u, 0)],
                  ~X[A(u, 4)] | X[A(u, 0)], ~X[A(u, 2)] | ~X[A(u, 3)]]
    return AND(bdd, parts)


if __name__ == "__main__":
    res = {}
    for written in (False, True):
        t0 = time.time()
        bdd, names, X, R, rounds = reach(written)
        n = R.count(nvars=40)
        cons = consistent_bdd(bdd, X, NU)
        some_admin = OR(bdd, [X[A(u, 4)] for u in range(NU)])
        star = cons & some_admin
        key = "written" if written else "fixed"
        res[key] = {"reachable": int(n), "rounds": rounds, "bdd_nodes": len(R), "seconds": round(time.time() - t0, 1),
                    "equals_consistent_and_some_admin": R == star,
                    "count_consistent_and_some_admin": int(star.count(nvars=40)),
                    "reach_minus_consistent": int((R & ~cons).count(nvars=40)),
                    "consistent_minus_reach": int((cons & ~R).count(nvars=40))}
        print(key, res[key], flush=True)
    json.dump(res, open("bdd_summary.json", "w"), indent=1)
