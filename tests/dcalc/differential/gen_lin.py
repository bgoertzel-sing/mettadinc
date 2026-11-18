#!/usr/bin/env python3
"""Seeded generator for linear arrows and their composition (spec Def 3.8, Prop 3.9).
Three stochastic machines MS -> MT -> MU over one Report carrier and one action set, two arrows L, K
(Positive: rows are laws; Signed: rows sum to 1 with negative entries), and the requests
CheckLinearArrow L, CheckLinearArrow K, Then(L, K)."""
import random
from fractions import Fraction as F
import gen


def rand_machine(rng, prefix, n, nobs, acts):
    S = ['%s%d' % (prefix, i) for i in range(n)]
    obs = {s: rng.randrange(nobs) for s in S}
    A = {}
    for a in acts:
        rows = {}
        for s in S:
            if rows and rng.random() < 0.2:
                rows[s] = dict(rows[rng.choice(list(rows))])
            elif rng.random() < 0.15:
                rows[s] = {s: F(1)}
            else:
                rows[s] = gen.rand_law(rng, S)
        A[a] = rows
    return {'states': S, 'obs': obs, 'actions': A}


def permuted(rng, m, prefix):
    """Copy of m under a random renaming; returns (copy, point-mass arrow matrix) -> exact arrow (rho 0)."""
    S = m['states']; T = ['%s%d' % (prefix, i) for i in range(len(S))]
    pi = dict(zip(S, rng.sample(T, len(T))))
    t = {'states': T, 'obs': {pi[s]: m['obs'][s] for s in S},
         'actions': {a: {pi[s]: {pi[z]: p for z, p in r[s].items()} for s in S} for a, r in m['actions'].items()}}
    L = [[F(1) if pi[s] == tt else F(0) for tt in T] for s in S]
    return t, L


def rand_arrow(rng, srcm, tgtm, signed, respect=True, nonnorm=False):
    """Random arrow matrix. respect: nonzero entries only where o(x) = o(z) (falls back to all targets when the
    target has no state with that observation); nonnorm (Signed only): one row deliberately not summing to 1."""
    T = tgtm['states']; k = len(T)
    L = []
    for s in srcm['states']:
        cols = [j for j, t in enumerate(T) if tgtm['obs'][t] == srcm['obs'][s]] if respect else []
        cols = cols or list(range(k))
        if signed:
            row = [F(0)] * k
            for j in cols:
                row[j] = F(rng.randint(-2, 2), rng.choice((1, 2, 3)))
            j = rng.choice(cols); row[j] += 1 - sum(row, F(0))
        else:
            law = gen.rand_law(rng, cols, zero_mass=False)
            row = [law.get(j, F(0)) for j in range(k)]
        L.append(row)
    if signed and nonnorm:
        r = rng.randrange(len(L)); j = rng.randrange(k); L[r][j] += rng.choice((F(1, 2), F(-1, 3), F(1)))
    return L


def arrow_text(name, src, tgt, srcm, tgtm, L, signed):
    rows = []
    for s, r in zip(srcm['states'], L):
        ent = ' '.join('(%s %s)' % (t, gen.rat(x)) for t, x in zip(tgtm['states'], r) if x)
        rows.append('(%s %s)' % (s, ent))
    return '  (LinearArrow %s (Source %s) (Target %s) (Kind %s)\n    (Matrix (Rows %s)))' % (
        name, src, tgt, 'Signed' if signed else 'Positive', ' '.join(rows))


def machine_text(car, mach, m, nobs):
    L = ['  (Carrier %s (Of Symbol) (Enum %s))' % (car, ' '.join(m['states'])),
         '  (Map rep%s (From %s) (To Report) (Cases %s))' % (car, car, ' '.join('(%s %d)' % (s, m['obs'][s]) for s in m['states']))]
    for a in sorted(m['actions']):
        L.append('  (TransitionKernel K%s%s (From %s) (To %s)' % (car, a, car, car))
        for s in m['states']:
            L.append('    (Row %s %s)' % (s, ' '.join('(Mass %s %s)' % (t, gen.rat(p)) for t, p in m['actions'][a][s].items())))
        L[-1] += ')'
    L.append('  (Machine %s (States %s) (Observe report rep%s) %s)' % (mach, car, car,
             ' '.join('(Action %s K%s%s)' % (a, car, a) for a in sorted(m['actions']))))
    return '\n'.join(L)


def rand_case(rng, name):
    acts = ['a%d' % i for i in range(rng.randint(1, 2))]
    nobs = rng.randint(1, 3)
    ms = rand_machine(rng, 's', rng.randint(2, 5), nobs, acts)
    if rng.random() < 0.3:
        mt, L = permuted(rng, ms, 't'); sL = False
    else:
        mt = rand_machine(rng, 't', rng.randint(2, 5), nobs, acts); sL = rng.random() < 0.4
        L = rand_arrow(rng, ms, mt, sL, respect=rng.random() < 0.8, nonnorm=sL and rng.random() < 0.25)
    if rng.random() < 0.3:
        mu, K = permuted(rng, mt, 'u'); sK = False
    else:
        mu = rand_machine(rng, 'u', rng.randint(2, 5), nobs, acts); sK = rng.random() < 0.4
        K = rand_arrow(rng, mt, mu, sK, respect=rng.random() < 0.8, nonnorm=sK and rng.random() < 0.25)
    txt = '\n'.join(['(DC.Module %s' % name, '  (Profile Stochastic)', '  (Use Linear)',
                     '  (Carrier Report (Of Nat) (Enum %s))' % ' '.join(str(i) for i in range(nobs)),
                     machine_text('S', 'MS', ms, nobs), machine_text('T', 'MT', mt, nobs), machine_text('U', 'MU', mu, nobs),
                     arrow_text('L', 'MS', 'MT', ms, mt, L, sL), arrow_text('K', 'MT', 'MU', mt, mu, K, sK),
                     '  (Derive LC (CheckLinearArrow L))', '  (Derive KC (CheckLinearArrow K))',
                     '  (Derive LK (Then (Output LC Value) (Output KC Value))))']) + '\n'
    txt += ''.join('!(dc.run %s %s)\n' % (name, r) for r in ('LC', 'KC', 'LK'))
    return (ms, mt, mu, L, K, sL, sK), txt
