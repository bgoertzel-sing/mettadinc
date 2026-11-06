"""Pattern 7: checking MetaMo properties on a finite instance of the OpenPsi/MAGUS equations.

State (integers; the real values are in brackets):
  gi   individuation overgoal weight      1..4    [gi/4]
  g1   exploration goal weight            0..4    [g1/4]
  a    arousal modulator                  0..2    [a/2]
  c    securing modulator                 0..2    [c/2]
  nu   stimulus novelty                   0..1
  rho  stimulus risk                      0..1
Appraisal Psi updates the modulators only; decision D updates the goal weights only.  The cycle is
F = D o Psi.  The safe region is gi >= 2 [individuation at least 1/2].  These choices instantiate the
equations of the MetaMo paper on OpenPsi; the functions the paper leaves open (f, MIC, the snapping
to a grid) are our own.
"""
from fractions import Fraction as F
from itertools import product

from dclib import Machine, least_violation, check_implementation

CARRIER = list(product([1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2], [0, 1, 2], [0, 1], [0, 1]))
THETA = 2


def psi(s):
    gi, g1, a, c, nu, rho = s
    a2 = (4 * nu + g1) // 4          # arousal ~ (novelty + exploration)/2, floored to halves
    c2 = (4 * rho + gi) // 4         # securing ~ (risk + individuation)/2, floored to halves
    return (gi, g1, a2, c2, nu, rho)


def decide(floor_at_theta):
    def d(s):
        gi, g1, a, c, nu, rho = s
        g1n = max(0, min(4, g1 + a - c))                # step toward approach minus caution
        if a == 2 and g1 >= 3:                         # high arousal on a strong exploration goal
            gin = gi - 1
            if floor_at_theta and gi >= THETA:
                gin = max(THETA, gin)
            gin = max(1, gin)
        elif c == 2:                                   # strong caution raises individuation
            gin = min(4, gi + 1)
        else:
            gin = gi
        return (gin, g1n, a, c, nu, rho)
    return d


def decide_damped(s):
    """Damped decision: the goal weight moves at most one quarter per cycle, and individuation
    relaxes only to the threshold."""
    gi, g1, a, c, nu, rho = s
    step = (a - c > 0) - (a - c < 0)
    g1n = max(0, min(4, g1 + step))
    d = decide(True)(s)
    return (d[0], g1n, a, c, nu, rho)


D_PLAIN = decide(False)
D_FLOOR = decide(True)


def cycle(d):
    return lambda s: d(psi(s))


def setters():
    return [("novel", lambda s: s[:4] + (1, s[5])), ("familiar", lambda s: s[:4] + (0, s[5])),
            ("risky", lambda s: s[:5] + (1,)), ("safe", lambda s: s[:5] + (0,))]


def machine(d):
    return Machine(CARRIER, [("cycle", cycle(d))] + setters(), [])


def safe(s):
    return s[0] >= THETA


def closure_violation(d):
    """Least state of the safe region and action that leave it (the block is checked for closure
    over the whole carrier, so any failure is a genuine counterexample)."""
    m = machine(d)
    for s in m.states:
        if not safe(s):
            continue
        for a in m.alabels:
            t = m.T[a][s]
            if not safe(t):
                return {"state": s, "action": a, "successor": t}
    return None


def real(s):
    gi, g1, a, c, nu, rho = s
    return (F(gi, 4), F(g1, 4), F(a, 2), F(c, 2), F(nu), F(rho))


QUARTERS = (1, 1, 2, 2, 4, 4)          # each coordinate in units of one quarter
_DIST = {}


def dist(x, y):
    """The largest coordinate difference in real units (exact; computed in quarters)."""
    q = max(abs(p - r) * w for p, r, w in zip(x, y, QUARTERS))
    v = _DIST.get(q)
    if v is None:
        v = _DIST[q] = F(q, 4)
    return v


def same_stimulus(x, y):
    return x[4:] == y[4:]


def in_band(s):
    return s[0] == THETA


def order_swap(d):
    """Affine contract between the two orders: ideal D o Psi, actual Psi o D."""
    ideal = lambda s: d(psi(s))
    actual = lambda s: psi(d(s))
    pure = max(dist(actual(x), ideal(x)) for x in CARRIER)
    worst = {}
    for eta in (F(1, 4), F(1, 2)):
        w, wit = check_implementation(CARRIER, ideal, actual, dist, dist, 1, eta, same_stimulus)
        worst[str(eta)] = wit
    least_eta, _ = check_implementation(CARRIER, ideal, actual, dist, dist, 1, F(1), same_stimulus)
    return {"pure": pure, "least_eta_L1": least_eta, "witness": worst}


def contraction(d, c=F(1, 2)):
    """d(F x, F y) <= c d(x, y) + eta on pairs with equal stimulus and one member on the boundary
    layer of the safe region; returns the least eta for this c and the witness at eta = 1/4."""
    f = cycle(d)
    ok = lambda x, y: same_stimulus(x, y) and (in_band(x) or in_band(y))
    least, _ = check_implementation(CARRIER, f, f, dist, dist, c, F(1), ok)
    _, wit = check_implementation(CARRIER, f, f, dist, dist, c, F(1, 4), ok)
    return {"least_eta": least, "witness_quarter": wit}


if __name__ == "__main__":
    print("states", len(CARRIER))
    for name, d in (("plain", D_PLAIN), ("floor", D_FLOOR), ("damped", decide_damped)):
        print(name, "closure:", closure_violation(d))
        print("   order swap:", order_swap(d))
        print("   contraction:", contraction(d))
