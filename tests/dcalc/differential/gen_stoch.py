"""Seeded generator of small random stochastic machines (M4 differential tests).

Emits (a) Python data for the oracle and (b) a MeTTaDinC module text for the real CLI.
Hard paths covered on purpose: explicit zero-mass edges, ties (equal masses / equal
reports), non-full support (rows with 1-2 successors), absorbing states, 1-3 actions.
Standard library only.
"""
import random
from fractions import Fraction as F

DENOMS = [1, 2, 3, 4, 6]


def rat(q):
    q = F(q)
    if q.denominator == 1:
        return str(q.numerator)
    return '(Rat %d %d)' % (q.numerator, q.denominator)


def rand_row(rng, states):
    k = rng.choice([1, 1, 2, 2, 3])
    k = min(k, len(states))
    supp = rng.sample(states, k)
    den = rng.choice(DENOMS)
    if rng.random() < 0.3:                      # tie: uniform masses
        masses = [F(1, k)] * k
    else:
        cuts = sorted(rng.randint(0, den) for _ in range(k - 1))
        parts = [b - a for a, b in zip([0] + cuts, cuts + [den])]
        masses = [F(p, den) for p in parts]
        if sum(masses) != 1:
            masses = [F(1, k)] * k
    r = {}
    for y, m in zip(supp, masses):
        r[y] = r.get(y, F(0)) + m
    if rng.random() < 0.25:                     # explicit zero-mass edge
        z = rng.choice(states)
        r.setdefault(z, F(0))
    return r


def rand_machine(rng, nmin=2, nmax=6):
    n = rng.randint(nmin, nmax)
    S = ['s%d' % i for i in range(n)]
    nobs = rng.choice([1, 2, 2, 3])
    report = {s: rng.randrange(nobs) for s in S}
    acts = {}
    for a in ['a', 'b', 'c'][:rng.choice([1, 1, 2, 3])]:
        acts[a] = {s: rand_row(rng, S) for s in S}
    merge = {s: s for s in S}
    x, y = rng.sample(S, 2)
    merge[y] = x                                 # MergeXY-style representation
    return dict(states=S, report=report, actions=acts, merge=merge, pair=(x, y))


def module_text(name, M):
    S = M['states']
    obs = sorted(set(M['report'].values()))
    L = ['(DC.Module %s' % name, '  (Profile Stochastic)', '  (Use Linear)',
         '  (Carrier S (Of Symbol) (Enum %s))' % ' '.join(S),
         '  (Carrier Report (Of Nat) (Enum %s))' % ' '.join(map(str, range(max(obs) + 1))),
         '  (Map report (From S) (To Report) (Cases %s))' % ' '.join('(%s %d)' % (s, M['report'][s]) for s in S)]
    for a, K in sorted(M['actions'].items()):
        rows = ' '.join('(Row %s %s)' % (s, ' '.join('(Mass %s %s)' % (y, rat(m)) for y, m in K[s].items())) for s in S)
        L.append('  (TransitionKernel K%s (From S) (To S) %s)' % (a, rows))
    L.append('  (Machine Chain (States S) (Observe report report) %s)' %
             ' '.join('(Action %s K%s)' % (a, a) for a in sorted(M['actions'])))
    L.append('  (Map merge (From S) (To S) (Cases %s))' % ' '.join('(%s %s)' % (s, M['merge'][s]) for s in S))
    L.append('  (Representation Merge (Of Chain) (Encode merge)))')
    return '\n'.join(L) + '\n'


def rand_mixture_machine(rng):
    """Mixture family (spec 7.2 seven-state pattern, randomised): states x, y, u, v, w share
    one report; w's row is the lam-mixture of u's and v's rows, x -> lam u + (1-lam) v,
    y -> w.  So x, y are trace equivalent but in general not bisimilar, and w's predictive
    vector is a mixture (linear dimension < trace classes).  Base states b0.. carry the rest."""
    nb = rng.randint(1, 2)
    B = ['b%d' % i for i in range(nb)]
    S = ['x', 'y', 'u', 'v', 'w'] + B
    r = rng.randrange(2)
    report = {s: r for s in ['x', 'y', 'u', 'v', 'w']}
    for b in B:
        report[b] = rng.randrange(3)
    lam = rng.choice([F(1, 2), F(1, 3), F(2, 3), F(1, 4)])
    acts = {}
    for a in ['a', 'b'][:rng.choice([1, 1, 2])]:
        K = {}
        K['u'] = rand_row(rng, B + ['u', 'v'])
        K['v'] = rand_row(rng, B + ['u', 'v'])
        mix = {}
        for t, m in K['u'].items():
            mix[t] = mix.get(t, F(0)) + lam * m
        for t, m in K['v'].items():
            mix[t] = mix.get(t, F(0)) + (1 - lam) * m
        K['w'] = mix
        if a == 'a':
            K['x'] = {'u': lam, 'v': 1 - lam}
            K['y'] = {'w': F(1)}
        else:
            K['x'] = {'x': F(1)}
            K['y'] = {'y': F(1)}
        for b in B:
            K[b] = rand_row(rng, S)
        acts[a] = K
    merge = {s: s for s in S}
    merge['y'] = 'x'
    return dict(states=S, report=report, actions=acts, merge=merge, pair=('x', 'y'))
