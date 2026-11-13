#!/usr/bin/env python3
"""m6-graded replayer (Fractions, independent of the C code).  Extends tests/dcalc/m6rest/replay_m6rest.py (which
stays unchanged) to GRADED kernel hives: some measured degree outside {0, 1} (spec Def 10.1 l.2821, c_ij in [0, 1]).
Own semantics: Lukasiewicz product a (x) b = max(0, a + b - 1) and max-(x) composition (spec l.288-289, l.736-742);
the path closure is recomputed by Floyd-Warshall over (max, (x)) (dcalc uses Dijkstra on d = 1 - c).
Crisp hives are delegated unchanged to replay_m6rest / replay_m6."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'm6')); sys.path.insert(0, os.path.join(HERE, '..', 'm6rest'))
import replay_m6 as R
import replay_m6rest as RR
from replay_m6 import field, head, need, node, rat, Q

def lk(a, b): return max(Q(0), a + b - 1)
def graded(H): return any(v not in (0, 1) for v in H.values())
def closure(nodes, H):
    F = {(a, b): (Q(1) if a == b else H.get((a, b), Q(0))) for a in nodes for b in nodes}
    for k in nodes:
        for a in nodes:
            for b in nodes:
                t = lk(F[(a, k)], F[(k, b)])
                if t > F[(a, b)]: F[(a, b)] = t
    return F
def path_deg(H, pth, a, b):
    need(pth and pth[0] == a and pth[-1] == b, 'path does not join the pair')
    s = Q(1)
    for u, v in zip(pth, pth[1:]):
        need(H.get((u, v), Q(0)) > 0, 'path step %s-%s is not a measured positive entry' % (u, v)); s = lk(s, H[(u, v)])
    return s
def gholo(car, H, cyc):
    s = u = cyc[0]; Rk = {(a, b): Q(1 if a == b else 0) for a in car[s] for b in car[s]}
    for v in cyc[1:] + [s]:
        need(all(((u, b), (v, c)) in H for b in car[u] for c in car[v]), 'holonomy through an unmeasured correspondence')
        Rk = {(a, c): max([lk(Rk[(a, b)], H[((u, b), (v, c))]) for b in car[u]] + [Q(0)]) for a in car[s] for c in car[v]}; u = v
    return Rk
def kern_eq(K, Rk): return {(R.val(e[0]), R.val(e[1])): rat(e[2]) for e in field(K, 'Entries')[1:]} == Rk

def replay_graded(M, req, res, st, names, car, nodes, wt, H):
    h = head(req); ev = field(res, 'Evidence'); full = all((a, b) in H for a in nodes for b in nodes)
    need(all(0 <= v <= 1 for v in H.values()), 'degree outside [0, 1]')
    if h == 'CheckKernelCoherence':
        need(full, 'coherence verdict on an unmeasured hive (must be Unknown)')
        bad = [(a, b, c) for a in nodes for b in nodes for c in nodes if H[(a, c)] < lk(H[(a, b)], H[(b, c)])]
        if st == 'Checked': need(not bad, 'Checked but %s is not transitive' % (bad[:1],)); return 'graded: transitive over %d triples' % len(nodes) ** 3
        need(bad, 'Refuted but the kernel is transitive'); w = field(ev, 'Witness'); a, b, c = map(node, field(w, 'Triple')[1:4])
        need(H[(a, c)] < lk(H[(a, b)], H[(b, c)]), 'witness triple is transitive')
        need([rat(x) for x in field(w, 'Degrees')[1:]] == [H[(a, b)], H[(b, c)], H[(a, c)]], 'witness degrees differ')
        hk = field(ev, 'Holonomy')
        if hk: need(kern_eq(field(hk, 'Kernel'), gholo(car, H, names)), 'evidence holonomy differs')
        return 'graded: intransitive triple replayed'
    need(st == 'Checked', '%s replays Checked rows only' % h)
    if h == 'Holonomy':
        need(kern_eq(field(field(res, 'Value'), 'Kernel'), gholo(car, H, list(req[2][1:]))), 'graded holonomy kernel differs'); return 'graded: holonomy recomposed'
    if h == 'Associator':
        I, J, K = req[2], req[3], req[4]; zero = True; pos = neg = 0; want = {}
        for a in car[I]:
            for c in car[K]:
                d = H[((I, a), (K, c))]; cp = max([lk(H[((I, a), (J, b))], H[((J, b), (K, c))]) for b in car[J]] + [Q(0)])
                want[(a, c)] = (d, cp, d - cp)
                if d != cp: zero = False; pos += d > cp; neg += d < cp
        A = field(field(res, 'Value'), 'Associator')
        got = {(R.val(e[1]), R.val(e[2])): (rat(e[3]), rat(e[4]), rat(e[5])) for e in field(A, 'Entries')[1:]}
        need(got == want, 'graded associator entries differ from c_ik - c_ij o c_jk')
        need(field(A, 'Zero')[1] == ('True' if zero else 'False') and int(field(A, 'Positive')[1]) == pos and int(field(A, 'Negative')[1]) == neg, 'associator counts differ')
        return 'graded: associator recomposed'
    if h == 'ConsensusCost':
        need(full, 'ConsensusCost on an unmeasured hive')
        F = closure(nodes, H); cost = sum(wt[a] * wt[b] * (F[(a, b)] - H[(a, b)]) for a in nodes for b in nodes if a != b)
        need(rat(field(res, 'Value')[1]) == cost, 'graded closure cost is %s' % cost)
        raised = {frozenset((a, b)) for a in nodes for b in nodes if a != b and F[(a, b)] > H[(a, b)]}; seen = set()
        for r in field(field(ev, 'Closure'), 'Raised')[1:]:
            a, b = node(r[1]), node(r[2]); seen.add(frozenset((a, b)))
            need(rat(field(r, 'Measured')[1]) == H[(a, b)] and rat(field(r, 'Closure')[1]) == F[(a, b)], 'Raise row degrees differ')
            need(path_deg(H, [node(x) for x in field(r, 'Path')[1:]], a, b) == F[(a, b)], 'Raise path does not attain the closure')
        need(seen == raised, 'Raise rows do not list exactly the raised pairs')
        return 'graded: closure cost recomputed (%d raised pairs, paths attain)' % len(raised)
    if h == 'LeastCoherentRefinement':
        need(full, 'LCR on an unmeasured hive')
        cert = field(ev, 'Certificate'); X = {(a, b): Q(1 if a == b else 0) for a in nodes for b in nodes}
        for p in field(cert, 'Kept')[1:]:
            a, b = node(p[1]), node(p[2]); need(a != b, 'kept pair on the diagonal'); X[(a, b)] = X[(b, a)] = rat(p[3])
        need(all(0 <= X[k] <= H[k] for k in X), 'kept pair outside [0, c]')
        need(all(X[(a, c)] >= X[(a, b)] + X[(b, c)] - 1 for a in nodes for b in nodes for c in nodes), 'refinement not transitive')
        E = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:] if H[(a, b)] > 0]
        cov = {frozenset(e): Q(0) for e in E}; Dv = Q(0)
        for t in field(cert, 'Dual')[1:]:
            y = rat(t[-1]); need(y >= 0, 'negative dual'); k = head(t)
            if k == 'Edge':
                a, b = node(t[1]), node(t[2]); need(H[(a, b)] > 0, 'Edge row on a zero pair'); Dv += H[(a, b)] * y; adds = [(frozenset((a, b)), y)]
            elif k in ('Triple', 'Chord'):
                a, b, c = node(t[1]), node(t[2]), node(t[3]); need(len({a, b, c}) == 3, 'degenerate triple')
                need(H[(a, b)] > 0 and H[(b, c)] > 0, '%s row on a zero pair' % k); Dv += y
                adds = [(frozenset((a, b)), y), (frozenset((b, c)), y)]
                if k == 'Triple': need(H[(a, c)] == 0, 'dual Triple closes on a positive pair (use Chord)')
                else: need(H[(a, c)] > 0, 'dual Chord on a zero pair'); adds.append((frozenset((a, c)), -y))
            else: raise AssertionError('unknown dual row %s' % k)
            for kk, v in adds: cov[kk] += v
        need(all(cov[frozenset((a, b))] >= wt[a] * wt[b] for a, b in E), 'dual infeasible')
        P = sum(wt[a] * wt[b] * X[(a, b)] for a, b in E); T = sum(wt[a] * wt[b] * H[(a, b)] for a, b in E)
        need(P == Dv, 'primal %s != dual %s' % (P, Dv))
        need(rat(field(cert, 'PrimalValue')[1]) == P and rat(field(cert, 'DualValue')[1]) == Dv, 'certificate values differ')
        em = field(cert, 'EdgeMass'); need(em is None or rat(em[1]) == T, 'EdgeMass differs')
        need(rat(field(res, 'Value')[1]) == 2 * (T - P), 'cost is not 2(EdgeMass - kept)')
        return 'graded: LP optimality certificate replayed (primal = dual)'
    if h == 'CompleteHive':
        F = closure(nodes, H)
        need(all(H[k] >= F[k] for k in H), 'a measured entry is below its path closure: no completion (should be Unsupported)')
        unm = [(a, b) for a in nodes for b in nodes if (a, b) not in H]
        cert = field(ev, 'Certificate')
        need(field(cert, 'Method')[1] == 'LukasiewiczPathClosure' and field(cert, 'Optimality')[1] == 'Checked', 'certificate method/optimality')
        need(int(field(cert, 'UnmeasuredEntries')[1]) == len(unm), 'UnmeasuredEntries count differs')
        idx = {n: i for i, n in enumerate(nodes)}
        want = {(a, b) for a, b in unm if F[(a, b)] > 0 and idx[a] < idx[b]}; got = set()
        for f in field(cert, 'Filled')[1:]:
            need(head(f) == 'Fill', 'malformed Fill row'); a, b = node(f[1]), node(f[2]); got.add((a, b))
            need((a, b) in want, 'Fill on a measured pair or a pair with no positive path')
            need(rat(field(f, 'Degree')[1]) == F[(a, b)], 'Fill degree is not the closure')
            need(path_deg(H, [node(x) for x in field(f, 'Path')[1:]], a, b) == F[(a, b)], 'Fill path does not attain the closure')
        need(got == want, 'Filled rows miss pairs')
        nop = set()
        for i, I in enumerate(names):
            for J in names[i + 1:]:
                if ((I, car[I][0]), (J, car[J][0])) in H: continue
                if all(F[((I, x), (J, y))] == 0 for x in car[I] for y in car[J]): nop.add((I, J))
        need({(x[1], x[2]) for x in field(cert, 'NoPaths')[1:]} == nop, 'NoPath rows differ')
        cost = sum(wt[a] * wt[b] * F[(a, b)] for a, b in unm)
        need(rat(field(res, 'Value')[1]) == cost, 'completion cost is %s' % cost)
        return 'graded: Lukasiewicz path closure completion replayed (%d fills)' % len(got)
    raise AssertionError('graded %s not replayable' % h)

_prev = R.replay_hive
def replay_hive_g(M, req, res, st):
    nm = req[1] if len(req) > 1 else None
    if isinstance(nm, str) and ('KernelHive', nm) in M.raw:
        names, car, nodes, wt, H = RR.hive_partial(M, nm)
        if graded(H): return replay_graded(M, req, res, st, names, car, nodes, wt, H)
    return _prev(M, req, res, st)
R.replay_hive = replay_hive_g

if __name__ == '__main__': sys.exit(R.main(sys.argv[1], sys.argv[2]))
