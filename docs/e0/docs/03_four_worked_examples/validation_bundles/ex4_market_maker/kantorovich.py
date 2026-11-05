"""Exact Kantorovich behavioral distances for small stochastic machines.

d = max(d0, gamma * max_a W_d(M_a x, M_a y)), with d0 from the observation tolerances.
Float iteration finds the structure; an exact linear solve gives a candidate D; exact transport
LPs (a small rational simplex) then certify D = Psi(D): couplings bound every term from above
(Proposition certs (2)), and dual potentials show that the binding term attains D.  For
gamma < 1 the operator is a contraction, so the verified fixed point is the distance.
"""
from fractions import Fraction as F
import numpy as np
from scipy.optimize import linprog


def simplex_min(c, A, b):
    """min c.x  s.t. A x = b, x >= 0, exact (two-phase, Bland's rule).
    Returns (value, x, y) with y the duals of the equality rows (c - A^T y >= 0)."""
    m, n = len(A), len(c)
    A = [[F(v) for v in row] for row in A]
    b = [F(v) for v in b]
    for i in range(m):
        if b[i] < 0:
            A[i] = [-v for v in A[i]]
            b[i] = -b[i]
    # phase 1: artificials n..n+m-1
    T = [A[i] + [F(int(i == j)) for j in range(m)] + [b[i]] for i in range(m)]
    basis = [n + i for i in range(m)]

    def pivot(r, col):
        piv = T[r][col]
        T[r] = [v / piv for v in T[r]]
        for i in range(m):
            if i != r and T[i][col] != 0:
                f = T[i][col]
                T[i] = [vi - f * vr for vi, vr in zip(T[i], T[r])]
        basis[r] = col

    def run(cost, allowed):
        while True:
            # reduced costs
            cb = [cost[j] for j in basis]
            enter = None
            for j in allowed:
                if j in basis:
                    continue
                rc = cost[j] - sum(cb[i] * T[i][j] for i in range(m))
                if rc < 0:
                    enter = j
                    break
            if enter is None:
                return
            rows = [(T[i][-1] / T[i][enter], basis[i], i) for i in range(m) if T[i][enter] > 0]
            if not rows:
                raise ValueError("unbounded")
            _, _, r = min(rows)
            pivot(r, enter)

    cost1 = [F(0)] * n + [F(1)] * m
    run(cost1, list(range(n + m)))
    if sum(T[i][-1] for i in range(m) if basis[i] >= n) != 0:
        raise ValueError("infeasible")
    # drive artificials out of the basis where possible
    for i in range(m):
        if basis[i] >= n:
            j = next((j for j in range(n) if T[i][j] != 0), None)
            if j is not None:
                pivot(i, j)
    cost2 = [F(v) for v in c] + [F(10 ** 9)] * m
    run(cost2, list(range(n)))
    x = [F(0)] * n
    for i in range(m):
        if basis[i] < n:
            x[basis[i]] = T[i][-1]
    val = sum(F(c[j]) * x[j] for j in range(n))
    # duals: solve y^T B = c_B using the original A on the final basis (pad redundant rows)
    return val, x


def transport(mu, nu, D):
    """Exact optimal coupling of two finite laws (dicts) for the cost D(u, v); returns
    (value, coupling dict, potential f) with f 1-Lipschitz for D on the given points."""
    U, V = sorted(mu), sorted(nu)
    cells = [(u, v) for u in U for v in V]
    c = [D(u, v) for u, v in cells]
    A, b = [], []
    for u in U:
        A.append([1 if cu == u else 0 for cu, _ in cells]); b.append(mu[u])
    for v in V[:-1]:                       # one marginal row is redundant
        A.append([1 if cv == v else 0 for _, cv in cells]); b.append(nu[v])
    val, x = simplex_min(c, A, b)
    theta = {cell: x[k] for k, cell in enumerate(cells) if x[k] != 0}
    return val, theta


def kr_potential(mu, nu, D, points, W):
    """A 1-Lipschitz potential f on points (for D) with E_mu f - E_nu f = W, found by an exact
    LP (maximize the difference subject to f(u) - f(v) <= D(u, v)); the potential is shifted so
    that its smallest value is 0."""
    P = sorted(points)
    k = len(P)
    # variables f = fp - fm (free) -> 2k nonnegative variables; constraints with slacks
    idx = {p: i for i, p in enumerate(P)}
    rows, rhs = [], []
    for u in P:
        for v in P:
            if u != v:
                r = [F(0)] * (2 * k)
                r[idx[u]] += 1; r[k + idx[u]] -= 1
                r[idx[v]] -= 1; r[k + idx[v]] += 1
                rows.append(r); rhs.append(D(u, v))
    m = len(rows)
    A = [r + [F(int(i == j)) for j in range(m)] for i, r in enumerate(rows)]
    obj = [F(0)] * (2 * k + m)
    for p in P:
        w = mu.get(p, F(0)) - nu.get(p, F(0))
        obj[idx[p]] -= w; obj[k + idx[p]] += w           # minimize -(E_mu f - E_nu f)
    val, x = simplex_min(obj, A, rhs)
    f = {p: x[idx[p]] - x[k + idx[p]] for p in P}
    lo = min(f.values())
    f = {p: v - lo for p, v in f.items()}
    assert -val == W, (val, W)
    return f


class Behavioral:
    """Behavioral pseudometric of a stochastic machine with graded observations.
    states: list; actions: list; kernel(x, a) -> {y: p}; d0(x, y) -> rational in [0, 1]."""

    def __init__(self, states, actions, kernel, d0, gamma):
        self.S, self.A, self.k, self.d0, self.g = list(states), list(actions), kernel, d0, gamma
        self.idx = {x: i for i, x in enumerate(self.S)}

    def float_iterate(self, iters=400):
        n = len(self.S)
        D0 = np.array([[float(self.d0(x, y)) for y in self.S] for x in self.S])
        D = D0.copy()
        for _ in range(iters):
            Dn = D0.copy()
            for i, x in enumerate(self.S):
                for j, y in enumerate(self.S):
                    if j <= i:
                        continue
                    best = 0.0
                    for a in self.A:
                        best = max(best, self._wfloat(self.k(x, a), self.k(y, a), D))
                    Dn[i, j] = Dn[j, i] = max(D0[i, j], float(self.g) * best)
            if np.max(np.abs(Dn - D)) < 1e-15:
                D = Dn
                break
            D = Dn
        self.Dfloat = D
        return D

    def _wfloat(self, mu, nu, D):
        U, V = sorted(mu), sorted(nu)
        c = [D[self.idx[u], self.idx[v]] for u in U for v in V]
        A_eq, b_eq = [], []
        for u in U:
            A_eq.append([1.0 if uu == u else 0.0 for uu in U for _ in V]); b_eq.append(float(mu[u]))
        for v in V:
            A_eq.append([1.0 if vv == v else 0.0 for _ in U for vv in V]); b_eq.append(float(nu[v]))
        r = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=(0, None), method="highs")
        return r.fun

    def exact(self, tol=1e-9):
        """Exact fixed point from the float structure, then verification."""
        D = self.Dfloat if hasattr(self, "Dfloat") else self.float_iterate()
        S, g = self.S, self.g
        prs = [(x, y) for i, x in enumerate(S) for y in S[i + 1:]]
        pid = {p: k for k, p in enumerate(prs)}
        # binding term per pair: d0 or an action with its optimal float coupling
        structure = {}
        for x, y in prs:
            i, j = self.idx[x], self.idx[y]
            d0 = float(self.d0(x, y))
            if abs(D[i, j] - d0) < tol:
                structure[(x, y)] = ("d0", None)
                continue
            best = None
            for a in self.A:
                w = float(g) * self._wfloat(self.k(x, a), self.k(y, a), D)
                if abs(w - D[i, j]) < tol:
                    best = a
                    break
            structure[(x, y)] = ("act", best)
        # exact solve: iterate the exact couplings until they are stable
        Dex = {p: F(0) for p in prs}

        def dist(u, v, Dd):
            if u == v:
                return F(0)
            p = (u, v) if self.idx[u] < self.idx[v] else (v, u)
            return Dd[p]

        # initial couplings from float D
        def fD(u, v):
            return F(D[self.idx[u], self.idx[v]]).limit_denominator(10 ** 6) if u != v else F(0)

        couplings = {}
        for (x, y), (kind, a) in structure.items():
            if kind == "act":
                _, th = transport(self.k(x, a), self.k(y, a), fD)
                couplings[(x, y)] = th
        for _ in range(20):
            n = len(prs)
            Am = [[F(int(r == c)) for c in range(n)] for r in range(n)]
            bm = [F(0)] * n
            for (x, y), (kind, a) in structure.items():
                r = pid[(x, y)]
                if kind == "d0":
                    bm[r] = self.d0(x, y)
                else:
                    for (u, v), p in couplings[(x, y)].items():
                        if u != v:
                            pu = (u, v) if self.idx[u] < self.idx[v] else (v, u)
                            Am[r][pid[pu]] -= g * p
            from mm import solve
            sol = solve(Am, bm)
            Dex = {p: sol[k] for k, p in enumerate(prs)}
            # re-optimize couplings exactly under Dex
            changed = False
            for (x, y), (kind, a) in structure.items():
                if kind == "act":
                    val, th = transport(self.k(x, a), self.k(y, a), lambda u, v: dist(u, v, Dex))
                    cur = sum(p * dist(u, v, Dex) for (u, v), p in couplings[(x, y)].items())
                    if val < cur:
                        couplings[(x, y)] = th
                        changed = True
            if not changed:
                break
        self.D = Dex
        self.structure = structure
        self.couplings = couplings
        return Dex

    def dist(self, u, v):
        if u == v:
            return F(0)
        p = (u, v) if self.idx[u] < self.idx[v] else (v, u)
        return self.D[p]

    def verify(self):
        """Exact check that D = max(d0, gamma max_a W_D); returns the certificate."""
        cert = {"couplings": {}, "potentials": {}}
        for (x, y) in self.D:
            Dxy = self.D[(x, y)]
            d0 = self.d0(x, y)
            assert d0 <= Dxy, ("d0 exceeds", x, y)
            attained = d0 == Dxy
            for a in self.A:
                mu, nu = self.k(x, a), self.k(y, a)
                W, th = transport(mu, nu, self.dist)
                assert self.g * W <= Dxy, ("upper fails", x, y, a, self.g * W, Dxy)
                cert["couplings"][(x, y, a)] = th
                if self.g * W == Dxy and not attained:
                    pts = set(mu) | set(nu)
                    f = kr_potential(mu, nu, self.dist, pts, W)
                    cert["potentials"][(x, y)] = (a, f)
                    attained = True
            assert attained, ("lower fails", x, y)
            if d0 == Dxy:
                cert["potentials"].setdefault((x, y), ("d0", None))
        return cert
