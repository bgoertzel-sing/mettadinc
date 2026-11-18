"""Seeded generator of random linear arrows between small stochastic machines (M4).

Each case: machines A -> B -> C (2-4 states each, one shared Report carrier, 1-2 actions),
arrows L : A -> B and K : B -> C, each Positive (rows are laws) or Signed (rows sum to one,
negative entries allowed), plus CheckLinearArrow on both and Then(L, K).
Families: 'random' (random targets, residual usually > 0) and 'exact' (target is a relabelled
copy of the source and the arrow its permutation, so rho = 0; optionally mixed with random).
Standard library only.
"""
import random
from fractions import Fraction as F
from gen_stoch import rand_row, rat


def rand_mach(rng, prefix, n, acts, nobs):
    S = ['%s%d' % (prefix, i) for i in range(n)]
    report = {s: rng.randrange(nobs) for s in S}
    return dict(states=S, report=report, actions={a: {s: rand_row(rng, S) for s in S} for a in acts})


def relabel(M, prefix, rng):
    S = M['states']
    perm = S[:]
    rng.shuffle(perm)
    new = {s: '%s%d' % (prefix, perm.index(s)) for s in S}
    T = sorted(new.values(), key=lambda t: int(t[len(prefix):]))
    acts = {a: {new[x]: {new[y]: m for y, m in K[x].items()} for x in S} for a, K in M['actions'].items()}
    return dict(states=T, report={new[s]: M['report'][s] for s in S}, actions=acts), new


def rand_arrow(rng, src, tgt, kind, obs=False):
    """obs=True: L(x,z) != 0 only when report(z) == report(x) (so every S_y = 0)."""
    L = []
    for x in src['states']:
        cols = [t for t in tgt['states'] if not obs or tgt['report'][t] == src['report'][x]]
        if kind == 'Positive':
            r = rand_row(rng, cols)
            L.append([r.get(t, F(0)) for t in tgt['states']])
        else:
            vals = {t: F(rng.randint(-2, 2), rng.choice([1, 2, 3])) for t in cols}
            j = rng.choice(cols)
            vals[j] += 1 - sum(vals.values())
            L.append([vals.get(t, F(0)) for t in tgt['states']])
    return L


def cover_reports(rng, M, values):
    """Relabel reports of M so every value in `values` occurs (M must be large enough)."""
    S = M['states'][:]
    rng.shuffle(S)
    for s, v in zip(S, sorted(values)):
        M['report'][s] = v
    return M


def rand_case(rng, family):
    acts = ['a', 'b'][:rng.choice([1, 1, 2])]
    nobs = rng.choice([1, 2, 2, 3])
    A = rand_mach(rng, 'A', rng.randint(2, 4), acts, nobs)
    if family == 'obs':
        n = max(2, nobs)
        B = cover_reports(rng, rand_mach(rng, 'B', rng.randint(n, 4), acts, nobs), set(A['report'].values()))
        kL = rng.choice(['Positive', 'Signed'])
        L = rand_arrow(rng, A, B, kL, obs=True)
        C = cover_reports(rng, rand_mach(rng, 'C', rng.randint(n, 4), acts, nobs), set(B['report'].values()))
        kK = rng.choice(['Positive', 'Signed'])
        K = rand_arrow(rng, B, C, kK, obs=True)
        return dict(A=A, B=B, C=C, L=L, K=K, kL=kL, kK=kK, acts=acts, nobs=nobs)
    if family == 'exact':
        B, perm = relabel(A, 'B', rng)
        L = [[F(int(perm[x] == t)) for t in B['states']] for x in A['states']]
        kL = 'Positive'
    else:
        B = rand_mach(rng, 'B', rng.randint(2, 4), acts, nobs)
        kL = rng.choice(['Positive', 'Signed'])
        L = rand_arrow(rng, A, B, kL)
    C = rand_mach(rng, 'C', rng.randint(2, 4), acts, nobs)
    kK = rng.choice(['Positive', 'Signed'])
    K = rand_arrow(rng, B, C, kK)
    return dict(A=A, B=B, C=C, L=L, K=K, kL=kL, kK=kK, acts=acts, nobs=nobs)


def matrix_text(src, tgt, L):
    rows = []
    for x, r in zip(src['states'], L):
        ents = ' '.join('(%s %s)' % (t, rat(m)) for t, m in zip(tgt['states'], r) if m != 0)
        rows.append('(%s %s)' % (x, ents))
    return '(Matrix (Rows %s))' % ' '.join(rows)


def module_text(name, c):
    L = ['(DC.Module %s' % name, '  (Profile Stochastic)', '  (Use Linear)',
         '  (Carrier Report (Of Nat) (Enum %s))' % ' '.join(map(str, range(c['nobs'])))]
    for key in 'ABC':
        M = c[key]
        L.append('  (Carrier S%s (Of Symbol) (Enum %s))' % (key, ' '.join(M['states'])))
        L.append('  (Map rep%s (From S%s) (To Report) (Cases %s))' % (key, key, ' '.join('(%s %d)' % (s, M['report'][s]) for s in M['states'])))
        for a in c['acts']:
            K = M['actions'][a]
            rows = ' '.join('(Row %s %s)' % (s, ' '.join('(Mass %s %s)' % (y, rat(m)) for y, m in K[s].items())) for s in M['states'])
            L.append('  (TransitionKernel K%s%s (From S%s) (To S%s) %s)' % (key, a, key, key, rows))
        L.append('  (Machine M%s (States S%s) (Observe report rep%s) %s)' % (key, key, key, ' '.join('(Action %s K%s%s)' % (a, key, a) for a in c['acts'])))
    L.append('  (LinearArrow L (Source MA) (Target MB) (Kind %s) %s)' % (c['kL'], matrix_text(c['A'], c['B'], c['L'])))
    L.append('  (LinearArrow K (Source MB) (Target MC) (Kind %s) %s)' % (c['kK'], matrix_text(c['B'], c['C'], c['K'])))
    L.append('  (Derive LChecked (CheckLinearArrow L))')
    L.append('  (Derive KChecked (CheckLinearArrow K))')
    L.append('  (Derive LK (Then (Output LChecked Value) (Output KChecked Value))))')
    return '\n'.join(L) + '\n' + ''.join('!(dc.run %s %s)\n' % (name, d) for d in ['LChecked', 'KChecked', 'LK'])
