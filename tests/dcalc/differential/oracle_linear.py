"""Independent exact-rational oracle for linear arrows (spec Definition 3.8, Proposition 3.9).

Independence: Python standard library only.  Reads no repo C code, generated tables or
replayer output.  Machines are the same Python data as oracle_stoch (states, report, actions).
A machine is the realization (M_a, E_y, 1) on its own carrier (Def 3.8).
"""
from fractions import Fraction as F


def mat(M, a):
    S = M['states']
    K = M['actions'][a]
    return [[F(K[x].get(y, 0)) for y in S] for x in S]


def proj(M, y):
    S = M['states']
    return [[F(int(i == j and M['report'][S[i]] == y)) for j in range(len(S))] for i in range(len(S))]


def mul(A, B):
    return [[sum((A[i][k] * B[k][j] for k in range(len(B))), F(0)) for j in range(len(B[0]))] for i in range(len(A))]


def sub(A, B):
    return [[a - b for a, b in zip(r, s)] for r, s in zip(A, B)]


def norm(A):
    """Induced infinity-norm: largest absolute row sum."""
    return max((sum(abs(v) for v in r) for r in A), default=F(0))


def arrow_grade(src, tgt, L, with_projectors=True):
    """L: list of rows (len |src|) of length |tgt|.  Returns dict valid, lam, rho, rho_actions,
    rho_projectors.  valid = (L 1 = 1), since eta = eta' = 1 for machines."""
    valid = all(sum(r) == 1 for r in L)
    lam = norm(L)
    ra = max((norm(sub(mul(mat(src, a), L), mul(L, mat(tgt, a)))) for a in src['actions']), default=F(0))
    ys = sorted(set(src['report'].values()) | set(tgt['report'].values()))
    rs = max((norm(sub(mul(proj(src, y), L), mul(L, proj(tgt, y)))) for y in ys), default=F(0))
    return dict(valid=valid, lam=lam, rho=max(ra, rs) if with_projectors else ra,
                rho_actions=ra, rho_projectors=rs)


def compose_grade(gL, gK):
    """Prop 3.9: (lamL*lamK, rhoL*lamK + lamL*rhoK)."""
    return gL[0] * gK[0], gL[1] * gK[0] + gL[0] * gK[1]
