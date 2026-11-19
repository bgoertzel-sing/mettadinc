"""Independent exact-rational oracle for M4 stochastic requests (spec Section 4.1, 7.1-7.3).

Independence: imports only the Python standard library and oracle_lp.py from this directory.
It reads no repo C code, no generated tables and no replayer output; inputs are the Python
data the generator also prints as a MeTTaDinC module.

Model: states (list), report (dict state -> value, discrete), actions (dict name -> kernel),
kernel = dict x -> dict y -> Fraction (rows sum to one; zero masses allowed and ignored).
"""
from fractions import Fraction as F
from itertools import product
from oracle_lp import kantorovich, lp_min


def row(K, x):
    return {y: m for y, m in K[x].items() if m != 0}


# ---- probabilistic bisimulation (spec 7.1: signature refinement; Thm 4.2(3)) ----
def bisim_partition(M):
    cls = {x: M['report'][x] for x in M['states']}
    while True:
        sig = {}
        for x in M['states']:
            s = [cls[x]]
            for a in sorted(M['actions']):
                acc = {}
                for y, m in row(M['actions'][a], x).items():
                    acc[cls[y]] = acc.get(cls[y], F(0)) + m
                s.append(tuple(sorted((repr(k), v) for k, v in acc.items())))
            sig[x] = tuple(map(repr, s))
        ids, new = {}, {}
        for x in M['states']:
            new[x] = ids.setdefault(sig[x], len(ids))
        if len(set(new.values())) == len(set(cls.values())):
            return blocks(M['states'], new)
        cls = new


def blocks(states, cls):
    out = {}
    for x in states:
        out.setdefault(cls[x], []).append(x)
    return sorted(out.values(), key=lambda b: states.index(b[0]))


# ---- behavioral pseudometric (Def 4.1): d = max(d0, g * max_a W_d(Ma x, Ma y)) ----
def d0(M):
    S = M['states']
    return {(x, y): F(int(M['report'][x] != M['report'][y])) for x in S for y in S}


def phi(M, d, g):
    S, base = M['states'], d0(M)
    out = {}
    for x, y in product(S, S):
        if x == y:
            out[x, y] = F(0); continue
        if (y, x) in out:
            out[x, y] = out[y, x]; continue
        w = max((kantorovich(row(K, x), row(K, y), d) for K in M['actions'].values()), default=F(0))
        out[x, y] = max(base[x, y], g * w)
    return out


def horizon_distance(M, g, h):
    """d^{g,h}_beh = 1 - Phi^h(alpha0): h applications of Phi starting from d0."""
    d = d0(M)
    for _ in range(h):
        d = phi(M, d, g)
    return d


# ---- exact unbounded distance for discount g < 1 (Thm 4.2(2): unique fixed point) ----
def coupling(mu, nu, d):
    """Optimal coupling (dict (x,y) -> mass) for W_d(mu, nu)."""
    xs = [x for x in sorted(mu) if mu[x] != 0]
    ys = [y for y in sorted(nu) if nu[y] != 0]
    var = [(x, y) for x in xs for y in ys]
    A, b = [], []
    for x in xs:
        A.append([F(int(v[0] == x)) for v in var]); b.append(mu[x])
    for y in ys:
        A.append([F(int(v[1] == y)) for v in var]); b.append(nu[y])
    val, sol = lp_min([d[v] for v in var], A, b)
    return {v: m for v, m in zip(var, sol) if m != 0}


def solve(A, b):
    """Exact Gaussian elimination, A square and nonsingular."""
    n = len(A)
    M = [list(map(F, A[i])) + [F(b[i])] for i in range(n)]
    for c in range(n):
        p = next(r for r in range(c, n) if M[r][c] != 0)
        M[c], M[p] = M[p], M[c]
        M[c] = [v / M[c][c] for v in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def exact_distance(M, g, warm=40, rounds=30):
    """Strategy improvement: fix (action, coupling) per pair, solve d = g*Theta d, then
    accept only a candidate that is an exact fixed point of Phi_g (unique for g < 1).
    Returns the distance dict, or None if no certified fixed point was found."""
    assert g < 1
    S, base = M['states'], d0(M)
    d = horizon_distance(M, g, min(warm, 4 * len(S)))
    pairs = [(x, y) for i, x in enumerate(S) for y in S[i + 1:]]
    idx = {p: i for i, p in enumerate(pairs)}
    for _ in range(rounds):
        nxt = phi(M, d, g)
        if all(nxt[p] == d[p] for p in pairs):
            return d
        A = [[F(0)] * len(pairs) for _ in pairs]
        b = [F(0)] * len(pairs)
        for (x, y), i in idx.items():
            A[i][i] = F(1)
            if base[x, y] == 1 or not M['actions']:
                b[i] = base[x, y]; continue
            best = max(M['actions'], key=lambda a: kantorovich(row(M['actions'][a], x), row(M['actions'][a], y), nxt))
            K = M['actions'][best]
            for (u, v), m in coupling(row(K, x), row(K, y), nxt).items():
                if u == v:
                    continue
                j = idx[(u, v)] if (u, v) in idx else idx[(v, u)]
                A[i][j] -= g * m
        sol = solve(A, b)
        d = {}
        for (x, y), i in idx.items():
            d[x, y] = d[y, x] = sol[i]
        for x in S:
            d[x, x] = F(0)
    return None


# ---- trace equivalence and minimal linear dimension (spec 7.2 "Deciding trace equivalence") ----
# Test functions f_w(x) = P_x(y0 a1 y1 ... ak yk).  f_{y} = [o(x)=y] and
# f_{y a w} = Pi_y K_a f_w, so the span is the Krylov closure of the indicators under
# the maps f -> Pi_y K_a f.  Dimension = rank of that span; trace classes = states on
# which every basis test agrees.
def _reduce(basis, v):
    """basis: list of (pivot, vector) in echelon form; returns v reduced against it."""
    v = list(v)
    for p, b in basis:
        if v[p] != 0:
            f = v[p] / b[p]
            v = [a - f * c for a, c in zip(v, b)]
    return v


def krylov_tests(M):
    S = M['states']
    n = len(S)
    vals = sorted(set(M['report'].values()), key=repr)
    proj = lambda y, f: [f[i] if M['report'][S[i]] == y else F(0) for i in range(n)]
    def apply(K, f):
        return [sum((m * f[S.index(t)] for t, m in row(K, S[i]).items()), F(0)) for i in range(n)]
    basis, tests, queue = [], [], []
    def add(f):
        r = _reduce(basis, f)
        nz = next((i for i in range(n) if r[i] != 0), None)
        if nz is None:
            return
        basis.append((nz, r)); tests.append(f); queue.append(f)
    for y in vals:
        add([F(int(M['report'][s] == y)) for s in S])
    while queue:
        f = queue.pop(0)
        for a in sorted(M['actions']):
            g = apply(M['actions'][a], f)
            for y in vals:
                add(proj(y, g))
    return tests


def linear_dimension(M):
    return len(krylov_tests(M))


def trace_partition(M):
    S, T = M['states'], krylov_tests(M)
    key = {x: tuple(t[i] for t in T) for i, x in enumerate(S)}
    ids = {}
    cls = {x: ids.setdefault(key[x], len(ids)) for x in S}
    return blocks(S, cls)
