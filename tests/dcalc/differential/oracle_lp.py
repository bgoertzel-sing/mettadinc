"""Exact rational LP for the differential oracle (two-phase dense simplex, Bland's rule).

Independence: Python standard library only (fractions). Reads no repo C code, no generated
tables and no replayer output.  Written from the spec text (Section 4.1, Definition 4.1).
"""
from fractions import Fraction as F


def lp_min(c, A_eq, b_eq):
    """Minimise c.x subject to A_eq x = b_eq, x >= 0, with b_eq >= 0.
    Returns (value, x), or None when infeasible.  Raises ValueError when unbounded."""
    m, n = len(A_eq), len(c)
    T = [[F(v) for v in row] + [F(int(i == j)) for j in range(m)] + [F(b)]
         for i, (row, b) in enumerate(zip(A_eq, b_eq))]
    basis = [n + i for i in range(m)]

    def pivot(r, col):
        pv = T[r][col]
        T[r] = [v / pv for v in T[r]]
        for i in range(m):
            if i != r and T[i][col] != 0:
                f = T[i][col]
                T[i] = [a - f * b for a, b in zip(T[i], T[r])]
        basis[r] = col

    def run(cost, ncols):
        while True:
            cb = [cost[b] for b in basis]
            enter = None
            for j in range(ncols):          # Bland: smallest improving index
                if j in basis:
                    continue
                if cost[j] - sum(cb[i] * T[i][j] for i in range(m)) < 0:
                    enter = j
                    break
            if enter is None:
                return
            best = None
            for i in range(m):
                if T[i][enter] > 0:
                    ratio = T[i][-1] / T[i][enter]
                    if best is None or ratio < best[0] or (ratio == best[0] and basis[i] < basis[best[1]]):
                        best = (ratio, i)
            if best is None:
                raise ValueError("unbounded LP")
            pivot(best[1], enter)

    run([F(0)] * n + [F(1)] * m, n + m)                     # phase 1
    if any(basis[i] >= n and T[i][-1] != 0 for i in range(m)):
        return None
    for i in range(m):                                      # drive artificials out
        if basis[i] >= n:
            for j in range(n):
                if T[i][j] != 0:
                    pivot(i, j)
                    break
    cost = [F(v) for v in c] + [F(0)] * m
    run(cost, n)                                            # phase 2
    x = [F(0)] * n
    for i in range(m):
        if basis[i] < n:
            x[basis[i]] = T[i][-1]
    return sum(cost[j] * x[j] for j in range(n)), x


def kantorovich(mu, nu, d):
    """W_d(mu, nu) = min over couplings theta of sum theta(x,y) d(x,y) (spec 4.1, coupling lift).
    mu, nu: dict state -> Fraction (each sums to 1); d: dict (x, y) -> Fraction."""
    xs = [x for x in sorted(mu) if mu[x] != 0]
    ys = [y for y in sorted(nu) if nu[y] != 0]
    var = [(x, y) for x in xs for y in ys]
    A, b = [], []
    for x in xs:
        A.append([F(int(v[0] == x)) for v in var]); b.append(mu[x])
    for y in ys:
        A.append([F(int(v[1] == y)) for v in var]); b.append(nu[y])
    res = lp_min([d[v] for v in var], A, b)
    assert res is not None, "marginals must have equal mass"
    return res[0]
