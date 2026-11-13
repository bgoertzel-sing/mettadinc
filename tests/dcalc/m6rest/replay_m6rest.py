#!/usr/bin/env python3
"""M6-rest replayer (Fractions, independent of the C code).  Extends tests/dcalc/m6/replay_m6.py, which stays
unchanged: LeastCoherentRefinement certificates may now carry Chord dual rows (ours, M6-rest registry patch):
(Chord a b c y) is the row x_ab + x_bc - x_ac <= 1 for an identified pair (a, c); it covers ab and bc by +y and
ac by -y.  Everything else is delegated to replay_m6."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'm6'))
import replay_m6 as R
from replay_m6 import field, head, need, node, rat, Q

_orig = R.replay_hive
def replay_hive(M, req, res, st):
    if head(req) != 'LeastCoherentRefinement': return _orig(M, req, res, st)
    names, car, nodes, wt, H = R.hive(M, req[1]); ev = field(res, 'Evidence')
    need(st == 'Checked', 'LeastCoherentRefinement replays Checked rows only')
    cert = field(ev, 'Certificate'); X = {(a, b): Q(1 if a == b else 0) for a in nodes for b in nodes}
    for p in field(cert, 'Kept')[1:]:
        a, b = node(p[1]), node(p[2]); need(a != b, 'kept pair on the diagonal'); X[(a, b)] = X[(b, a)] = rat(p[3])
    need(all(0 <= X[k] <= H[k] for k in X), 'kept pair outside [0, H]')
    need(all(X[(a, c)] >= X[(a, b)] + X[(b, c)] - 1 for a in nodes for b in nodes for c in nodes), 'refinement not transitive')
    E = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:] if H[(a, b)] == 1]
    cov = {frozenset(e): Q(0) for e in E}; Dv = Q(0)
    for t in field(cert, 'Dual')[1:]:
        y = rat(t[-1]); need(y >= 0, 'negative dual'); Dv += y; k = head(t)
        if k == 'Edge': adds = [(frozenset((node(t[1]), node(t[2]))), y)]
        elif k in ('Triple', 'Chord'):
            a, b, c = node(t[1]), node(t[2]), node(t[3]); need(len({a, b, c}) == 3, 'degenerate triple')
            need(H[(a, b)] == 1 and H[(b, c)] == 1, '%s row on a pair H does not identify' % k)
            adds = [(frozenset((a, b)), y), (frozenset((b, c)), y)]
            if k == 'Triple': need(H[(a, c)] == 0, 'dual Triple closes on an identified pair (use Chord)')
            else: need(H[(a, c)] == 1, 'dual Chord on an unidentified pair'); adds.append((frozenset((a, c)), -y))
        else: raise AssertionError('unknown dual row %s' % k)
        for kk, v in adds: cov[kk] += v
    need(all(cov[frozenset((a, b))] >= wt[a] * wt[b] for a, b in E), 'dual infeasible')
    P = sum(wt[a] * wt[b] * X[(a, b)] for a, b in E); T = sum(wt[a] * wt[b] for a, b in E)
    need(P == Dv, 'primal %s != dual %s' % (P, Dv))
    need(rat(field(cert, 'PrimalValue')[1]) == P and rat(field(cert, 'DualValue')[1]) == Dv, 'certificate values differ')
    em = field(cert, 'EdgeMass'); need(em is None or rat(em[1]) == T, 'EdgeMass differs')
    need(rat(field(res, 'Value')[1]) == 2 * (T - P), 'cost is not 2(EdgeMass - kept)')
    return 'optimality certificate replayed (primal = dual%s)' % (', chords' if any(head(t) == 'Chord' for t in field(cert, 'Dual')[1:]) else '')
R.replay_hive = replay_hive

if __name__ == '__main__': sys.exit(R.main(sys.argv[1], sys.argv[2]))
