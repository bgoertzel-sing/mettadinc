#!/usr/bin/env python3
"""Independent exact-rational oracle for MeTTaDinC M4/M6 requests (t-2026-11-18-mettadinc-m4m6-differential).

Written from the specification text only (docs/e0/docs/01_language_specification/mettadinc_language_spec.txt,
Sections 3.8/3.9, 4.3, 7.1-7.3). It imports nothing from the repo (no C, no generated tables, no replayers) and
works on a plain Python model produced by gen.py, never on dcalc output.

Model: {'states': [names], 'obs': {state: report}, 'actions': {a: {s: {t: Fraction}}}}
"""
from fractions import Fraction as F


def obs_classes(m):
    by = {}
    for s in m['states']:
        by.setdefault(m['obs'][s], []).append(s)
    return [by[k] for k in sorted(by, key=str)]


def bisim_partition(m):
    """Coarsest probabilistic bisimulation (spec 7.1: strong lumpability, refinement by the signature
    (sum_{y in C} M_a(x,y))_{a,C})."""
    blocks = obs_classes(m)
    while True:
        cls = {s: i for i, b in enumerate(blocks) for s in b}
        new = []
        for b in blocks:
            sig = {}
            for s in b:
                key = []
                for a in sorted(m['actions']):
                    row = m['actions'][a].get(s, {})
                    acc = {}
                    for t, p in row.items():
                        if p:
                            acc[cls[t]] = acc.get(cls[t], F(0)) + p
                    key.append((a, tuple(sorted(acc.items()))))
                sig.setdefault(tuple(key), []).append(s)
            new.extend(sig.values())
        if len(new) == len(blocks):
            return canon(new, m)
        blocks = new


def canon(blocks, m):
    order = {s: i for i, s in enumerate(m['states'])}
    bs = [sorted(b, key=order.get) for b in blocks]
    return sorted(bs, key=lambda b: order[b[0]])


def _reduce_add(basis, v):
    """Gaussian elimination over Q; basis is a list of (pivot, vec). Returns True if v was independent."""
    v = list(v)
    for p, b in basis:
        if v[p]:
            c = v[p] / b[p]
            v = [x - c * y for x, y in zip(v, b)]
    for i, x in enumerate(v):
        if x:
            basis.append((i, v))
            return True
    return False


def test_space(m):
    """Span of x -> P_x(y0 a1 y1 ... ak yk) (spec 7.2 'Deciding trace equivalence': Krylov iteration).
    f_{y w}(x) = [o(x)=y] * sum_z M_a(x,z) f_w(z); start from the length-1 indicators [o(x)=y]."""
    S = m['states']
    ys = sorted({m['obs'][s] for s in S}, key=str)
    basis, kept, frontier = [], [], []
    for y in ys:
        v = [F(1) if m['obs'][s] == y else F(0) for s in S]
        if _reduce_add(basis, v):
            kept.append(v); frontier.append(v)
    while frontier:
        nxt = []
        for t in frontier:
            for a in sorted(m['actions']):
                Mt = [sum((p * t[S.index(z)] for z, p in m['actions'][a].get(s, {}).items()), F(0)) for s in S]
                for y in ys:
                    v = [Mt[i] if m['obs'][s] == y else F(0) for i, s in enumerate(S)]
                    if _reduce_add(basis, v):
                        kept.append(v); nxt.append(v)
        frontier = nxt
    return kept


def minimal_linear_dim(m):
    return len(test_space(m))


def trace_partition(m):
    S = m['states']
    T = test_space(m)
    sig = {}
    for i, s in enumerate(S):
        sig.setdefault(tuple(t[i] for t in T), []).append(s)
    return canon(list(sig.values()), m)


def trace_equivalent(m, s, t):
    S = m['states']
    i, j = S.index(s), S.index(t)
    return all(v[i] == v[j] for v in test_space(m))


# ---------------------------------------------------------------- Kantorovich (spec 4.3, 7.1, 7.2)
INF = None


def transport(mu, nu, cost):
    """Exact optimal transport between finite rational laws mu, nu (dicts) under cost(i, j).
    Successive shortest paths with Bellman-Ford on a residual graph; all arithmetic in Fraction."""
    L = [i for i in mu if mu[i]]
    R = [j for j in nu if nu[j]]
    if not L:
        return F(0)
    n = 2 + len(L) + len(R)
    src, snk = 0, n - 1
    g = [[] for _ in range(n)]          # edge: [to, cap(None=inf), cost, rev_index]

    def add(u, v, cap, c):
        g[u].append([v, cap, c, len(g[v])])
        g[v].append([u, F(0), -c, len(g[u]) - 1])
    for a, i in enumerate(L):
        add(src, 1 + a, mu[i], F(0))
        for b, j in enumerate(R):
            add(1 + a, 1 + len(L) + b, INF, F(cost(i, j)))
    for b, j in enumerate(R):
        add(1 + len(L) + b, snk, nu[j], F(0))
    total, flow = F(0), F(0)
    while flow < 1:
        dist = [None] * n; dist[src] = F(0); prev = [None] * n
        for _ in range(n):
            ch = False
            for u in range(n):
                if dist[u] is None:
                    continue
                for k, (v, cap, c, _r) in enumerate(g[u]):
                    if (cap is None or cap > 0) and (dist[v] is None or dist[u] + c < dist[v]):
                        dist[v] = dist[u] + c; prev[v] = (u, k); ch = True
            if not ch:
                break
        if dist[snk] is None:
            raise ValueError('transport: laws have different mass')
        f, v = 1 - flow, snk
        while v != src:
            u, k = prev[v]; cap = g[u][k][1]
            if cap is not None and cap < f:
                f = cap
            v = u
        v = snk
        while v != src:
            u, k = prev[v]; e = g[u][k]
            if e[1] is not None:
                e[1] -= f
            r = g[v][e[3]]
            if r[1] is not None:
                r[1] += f
            v = u
        flow += f; total += f * dist[snk]
    return total


def _obs_dist(m, s, t):
    return F(0) if m['obs'][s] == m['obs'][t] else F(1)


def horizon_distances(m, steps, gamma=F(1)):
    """d_0 = observation distance; d_{k+1}(s,t) = 1 if o(s)!=o(t) else gamma * max_a K(d_k)(M_a s, M_a t).
    (spec 7.1: value iteration; certificate_limits U02: horizon 3 gives 7/8)."""
    S = m['states']
    d = {(s, t): _obs_dist(m, s, t) for s in S for t in S}
    for _ in range(steps):
        nd = {}
        for s in S:
            for t in S:
                if m['obs'][s] != m['obs'][t]:
                    nd[(s, t)] = F(1)
                elif s == t:
                    nd[(s, t)] = F(0)
                else:
                    best = F(0)
                    for a in m['actions']:
                        k = transport(m['actions'][a].get(s, {}), m['actions'][a].get(t, {}), lambda i, j: d[(i, j)])
                        best = max(best, k)
                    nd[(s, t)] = gamma * best
        d = nd
    return d


def defect(m, d, encode):
    """Behavioral defect of a crisp representation: largest distance between two states it merges."""
    S = m['states']
    return max([d[(s, t)] for s in S for t in S if encode[s] == encode[t]] + [F(0)])


# ---------------------------------------------------------------- linear arrows (spec Def 3.8, Prop 3.9)
def _mat(m, a):
    S = m['states']
    return [[m['actions'][a].get(s, {}).get(t, F(0)) for t in S] for s in S]


def _obsmat(m, y):
    S = m['states']
    return [[F(1) if (i == j and m['obs'][s] == y) else F(0) for j, _ in enumerate(S)] for i, s in enumerate(S)]


def _mul(A, B):
    return [[sum((A[i][k] * B[k][j] for k in range(len(B))), F(0)) for j in range(len(B[0]))] for i in range(len(A))]


def _sub(A, B):
    return [[x - y for x, y in zip(r, s)] for r, s in zip(A, B)]


def inf_norm(A):
    return max([sum((abs(x) for x in r), F(0)) for r in A] + [F(0)])


def linear_arrow(src, tgt, L):
    """Grade of a linear arrow between two stochastic machines (Def 3.8): returns dict with
    valid (L 1 = 1), positive (L >= 0), lam = ||L||, rho = max(max_a ||R_a||, max_y ||S_y||)."""
    valid = all(sum(r, F(0)) == 1 for r in L)
    positive = all(x >= 0 for r in L for x in r)
    res = []
    for a in sorted(src['actions']):
        res.append(inf_norm(_sub(_mul(_mat(src, a), L), _mul(L, _mat(tgt, a)))))
    ys = sorted({src['obs'][s] for s in src['states']} | {tgt['obs'][t] for t in tgt['states']}, key=str)
    obs_res = [inf_norm(_sub(_mul(_obsmat(src, y), L), _mul(L, _obsmat(tgt, y)))) for y in ys]
    return {'valid': valid, 'positive': positive, 'lam': inf_norm(L),
            'rho_act': max(res + [F(0)]), 'rho_obs': max(obs_res + [F(0)]),
            'rho': max(res + obs_res + [F(0)])}


def compose_grade(g1, g2):
    """Prop 3.9: grade (lL*lK, rL*lK + lL*rK)."""
    return g1['lam'] * g2['lam'], g1['rho'] * g2['lam'] + g1['lam'] * g2['rho']


def check_linear_arrow(src, tgt, L, kind):
    """Expected answer of CheckLinearArrow (spec 7.3 l.2465 + Def 3.8): replay the normalization L eta' = eta
    (both ends are stochastic machines, so eta = eta' = 1: every row of L sums to 1) and, when declared,
    positivity; return the Def 3.8 grade with rho over action AND observation residuals.
    Status Checked when the replayed conditions hold, Refuted otherwise."""
    g = linear_arrow(src, tgt, L)
    ok = g['valid'] and (kind != 'Positive' or g['positive'])
    return ('Checked' if ok else 'Refuted'), g


# ---------------------------------------------------------------- affine contracts (spec 9.3, Prop 9.1)
def gap(p, q):
    """Distance of the OneMinusAbsoluteDifference tolerance: 1 - max(0, 1 - |p - q|) = min(1, |p - q|) (spec l.686-694)."""
    return min(F(1), abs(F(p) - F(q)))


def affine(ab):
    a, b = ab
    return lambda x: a * x + b


def tight_eta(ideal, actual, audit, L):
    """Smallest eta with d(actual(xh), ideal(x)) <= L d(xh, x) + eta over all ordered audited pairs."""
    return max([gap(actual(xh), ideal(x)) - L * gap(xh, x) for xh in audit for x in audit] + [F(0)])


def check_implementation(ideal, actual, audit, L, eta):
    ok = all(gap(actual(xh), ideal(x)) <= L * gap(xh, x) + eta for xh in audit for x in audit)
    return ('Checked' if ok else 'Refuted'), (F(L), F(eta))


def then_contracts(gf, gg):
    """Prop 9.1: (Lg Lf, Lg eta_f + eta_g)."""
    (Lf, ef), (Lg, eg) = gf, gg
    return Lg * Lf, Lg * ef + eg


# ---------------------------------------------------------------- positive realization (spec l.2469-2486)
def positive_realization(src, tgt, L):
    """PositiveRealization M (Candidate L): the candidate must be an exact positive arrow
    (valid, L >= 0, rho = 0) into a stochastic machine of dimension k; then the positive
    dimension lies in [signed minimum, k].  Otherwise the candidate is not replayed -> Refuted."""
    # The bisimulation quotient (lumping) is itself an exact positive realization, so it is
    # always an upper bound; a replayed exact candidate can only tighten it (min).  A rejected
    # candidate therefore does not make the claim fail (spec gap noted in disagreements/README.md N1).
    g = linear_arrow(src, tgt, L)
    up = len(bisim_partition(src))
    if g['valid'] and g['positive'] and g['rho'] == 0:
        up = min(up, len(tgt['states']))
    return 'Checked', (minimal_linear_dim(src), up)
