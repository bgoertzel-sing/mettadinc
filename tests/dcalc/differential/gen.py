#!/usr/bin/env python3
"""Seeded generators for the M4/M6 differential test. Each generator returns (model, module_text, requests).
The model is the plain-Python input the oracle reads; module_text is a MeTTaDinC module for the real CLI."""
import random
from fractions import Fraction as F

DENOMS = (1, 2, 3, 4, 6)


def rat(q):
    q = F(q)
    return str(q.numerator) if q.denominator == 1 else '(Rat %d %d)' % (q.numerator, q.denominator)


def rand_law(rng, targets, zero_mass=True):
    """Random rational law over a random non-empty support; sometimes adds explicit zero-mass entries."""
    k = rng.randint(1, min(3, len(targets)))
    sup = rng.sample(targets, k)
    den = rng.choice(DENOMS)
    while den < k:
        den = rng.choice(DENOMS + (6,))
    cuts = sorted(rng.sample(range(1, den), k - 1)) if k > 1 else []
    parts = [b - a for a, b in zip([0] + cuts, cuts + [den])]
    law = {t: F(p, den) for t, p in zip(sup, parts)}
    if zero_mass and rng.random() < 0.25:
        rest = [t for t in targets if t not in law]
        if rest:
            law[rng.choice(rest)] = F(0)
    return law


def rand_chain(rng, nmin=2, nmax=6, amax=2):
    n = rng.randint(nmin, nmax)
    S = ['s%d' % i for i in range(n)]
    nobs = rng.randint(1, min(3, n))
    obs = {s: rng.randrange(nobs) for s in S}
    acts = {}
    for ai in range(rng.randint(1, amax)):
        rows = {}
        for s in S:
            if rows and rng.random() < 0.2:          # ties: copy an earlier row exactly
                rows[s] = dict(rows[rng.choice(list(rows))])
            elif rng.random() < 0.15:                 # absorbing point mass
                rows[s] = {s: F(1)}
            else:
                rows[s] = rand_law(rng, S)
        acts['a%d' % ai] = rows
    return {'states': S, 'obs': obs, 'actions': acts}


def rand_encode(rng, m):
    """Crisp representation merging random states (often an observation-respecting pair)."""
    S = m['states']
    enc = {s: s for s in S}
    same = [(s, t) for s in S for t in S if s < t and m['obs'][s] == m['obs'][t]]
    if same:                                      # always merge one observation-respecting pair (non-trivial defect)
        s, t = rng.choice(same); enc[t] = enc[s]
    k = rng.randint(0, max(1, len(S) // 2))
    for _ in range(k):
        s, t = rng.sample(S, 2)
        if rng.random() < 0.8 and m['obs'][s] != m['obs'][t]:
            continue
        enc[t] = enc[s]
    return {s: enc[enc[s]] for s in S}


def chain_module(name, m, enc=None):
    S = m['states']
    nobs = sorted({m['obs'][s] for s in S})
    L = ['(DC.Module %s' % name, '  (Profile Stochastic)', '  (Use Linear)',
         '  (Carrier S (Of Symbol) (Enum %s))' % ' '.join(S),
         '  (Carrier Report (Of Nat) (Enum %s))' % ' '.join(str(i) for i in range(max(nobs) + 1)),
         '  (Map report (From S) (To Report) (Cases %s))' % ' '.join('(%s %d)' % (s, m['obs'][s]) for s in S)]
    for a, rows in sorted(m['actions'].items()):
        L.append('  (TransitionKernel K%s (From S) (To S)' % a)
        for s in S:
            L.append('    (Row %s %s)' % (s, ' '.join('(Mass %s %s)' % (t, rat(p)) for t, p in rows[s].items())))
        L[-1] += ')'
    L.append('  (Machine Chain (States S) (Observe report report) %s)'
             % ' '.join('(Action %s K%s)' % (a, a) for a in sorted(m['actions'])))
    if enc:
        L.append('  (Map enc (From S) (To S) (Cases %s))' % ' '.join('(%s %s)' % (s, enc[s]) for s in S))
        L.append('  (Representation Rep (Of Chain) (Encode enc))')
    L[-1] += ')'
    return '\n'.join(L) + '\n'
