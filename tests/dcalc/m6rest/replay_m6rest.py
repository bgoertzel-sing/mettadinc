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

# ---- CompleteHive (M6-rest; hive decision 2, our reading of spec l.2896-2906) ----
def hive_partial(M, name):
    """Like replay_m6.hive but unmeasured / undeclared correspondences are left out of H (not zero-filled)."""
    if isinstance(name, list): return hive_output(M, name)   # M7: (Output D Hive), possibly nested
    d = M.raw[('KernelHive', name)]; mem = [x for x in d[2:] if head(x) == 'Member']; names = [x[1] for x in mem]
    W = field(d, 'Weights'); w = {e[0]: R.val(e[1]) for e in W[1:]} if W else {n: Q(1, len(mem)) for n in names}
    need(set(w) == set(names) and sum(w.values()) == 1, 'member weights')
    car, nodes, wt, H = {}, [], {}, {}
    for x in mem:
        nm, c, t, ms = x[1:5]; tk = head(M.raw[('Tolerance', t)][3])
        need(head(M.raw[('Measure', ms)][3]) == 'Uniform', 'measure %s not replayable' % ms)
        need(tk in ('Discrete', 'Trivial'), 'member tolerance %s not replayable' % t)
        car[nm] = M.dom(c)
        for v in car[nm]: nodes.append((nm, v)); wt[(nm, v)] = w[nm] / len(car[nm])
        for a in car[nm]:
            for b in car[nm]: H[((nm, a), (nm, b))] = Q(1) if a == b or tk == 'Trivial' else Q(0)
    for x in d[2:]:
        if head(x) == 'Correspondence' and x[4] == 'Measured':
            for e in field(M.raw[('CrossKernel', x[3])], 'Entries')[1:]:
                a, b, v = R.val(e[0]), R.val(e[1]), R.val(e[2]); H[((x[1], a), (x[2], b))] = H[((x[2], b), (x[1], a))] = v
    return names, car, nodes, wt, H

# ---- (Output D Hive) after CompleteHive (M7 order; m6-graded review F4).  Own recomputation, not the C code:
# completion = (max, Lukasiewicz) path closure F of the measured entries (crisp: reachability over measured 1s).
# A measured entry below F has no completion.  Unmeasured entries of a member pair joined by some positive path
# get F (crisp: 1 if joined, else 0); every entry of a NoPath member pair stays unmeasured (never zero-filled).
def _lk(a, b): return max(Q(0), a + b - 1)
def complete_h(names, car, nodes, wt, H):
    F = {(a, b): H.get((a, b), Q(0)) for a in nodes for b in nodes}
    for k in nodes:
        for a in nodes:
            fak = F[(a, k)]
            if fak == 0: continue
            for b in nodes:
                v = _lk(fak, F[(k, b)])
                if v > F[(a, b)]: F[(a, b)] = v
    need(all(H[k] >= F[k] for k in H), 'a measured entry is below its path closure: no completion (should be Unsupported)')
    H2 = dict(H)
    for I in names:
        for J in names:
            if not any(F[((I, x), (J, y))] > 0 for x in car[I] for y in car[J]): continue   # NoPath pair
            for x in car[I]:
                for y in car[J]:
                    if ((I, x), (J, y)) not in H2: H2[((I, x), (J, y))] = F[((I, x), (J, y))]
    return names, car, nodes, wt, H2
_depth = [0]
def hive_output(M, name):
    need(isinstance(name, list) and len(name) == 3 and name[0] == 'Output' and name[2] == 'Hive', 'expected (Output D Hive)')
    d = getattr(M, 'derive', {}).get(name[1]); need(isinstance(d, list) and len(d) > 0, '%s names no declared Derive' % name[1])
    if d[0] == 'KernelOf': return R.kernel_of(M, d)
    need(d[0] == 'CompleteHive' and len(d) == 2, 'Derive %s is not a KernelOf or CompleteHive' % name[1])
    need(_depth[0] < 4, 'CompleteHive: completions nested more than 4 deep')
    _depth[0] += 1
    try: names, car, nodes, wt, H = hive_partial(M, d[1])
    finally: _depth[0] -= 1
    return complete_h(names, car, nodes, wt, H)
_hive0 = R.hive
def hive_any(M, name):
    if isinstance(name, list) and len(name) == 3 and name[0] == 'Output':
        d = getattr(M, 'derive', {}).get(name[1])
        if isinstance(d, list) and d and d[0] == 'CompleteHive': return hive_output(M, name)
    return _hive0(M, name)
R.hive = hive_any
def replay_complete(M, req, res, st):
    need(st == 'Checked', 'CompleteHive replays Checked rows only')
    names, car, nodes, wt, H = hive_partial(M, req[1])
    reach = {}
    for s0 in nodes:
        seen, todo = {s0}, [s0]
        while todo:
            a = todo.pop()
            for b in nodes:
                if b not in seen and H.get((a, b)) == 1: seen.add(b); todo.append(b)
        reach[s0] = seen
    need(all(H.get((a, b)) != 0 for a in nodes for b in reach[a]), 'a measured 0 entry is joined by a measured path: no coherent completion (should be Unsupported)')
    unm = [(a, b) for a in nodes for b in nodes if (a, b) not in H]
    filled = {(a, b) for a, b in unm if b in reach[a]}
    cert = field(field(res, 'Evidence'), 'Certificate')
    need(field(cert, 'Method')[1] == 'PathComposition' and field(cert, 'Optimality')[1] == 'Checked', 'certificate method/optimality')
    need(int(field(cert, 'UnmeasuredEntries')[1]) == len(unm), 'UnmeasuredEntries count differs')
    got = set()
    for f in field(cert, 'Filled')[1:]:
        need(head(f) == 'Fill' and head(f[3]) == 'Path', 'malformed Fill row')
        a, b = node(f[1]), node(f[2]); pth = [node(x) for x in f[3][1:]]
        need((a, b) not in H, 'Fill on a measured entry')
        need(len(pth) >= 2 and pth[0] == a and pth[-1] == b, 'Path does not join the filled pair')
        need(all(H.get((pth[i], pth[i + 1])) == 1 for i in range(len(pth) - 1)), 'Path step is not a measured identification')
        got.add(frozenset((a, b)))
    need(got == {frozenset(e) for e in filled}, 'Fill rows differ from the fills transitivity forces')
    exp = set()
    for i, mi in enumerate(names):
        for mj in names[i + 1:]:
            pairs = [((mi, u), (mj, v)) for u in car[mi] for v in car[mj]]
            if all(pp not in H for pp in pairs) and not any(pp[1] in reach[pp[0]] for pp in pairs): exp.add((mi, mj))
    need({(r[1], r[2]) for r in field(cert, 'NoPaths')[1:]} == exp, 'NoPath rows differ')
    K = {(a, b): H[(a, b)] if (a, b) in H else Q(1 if (a, b) in filled else 0) for a in nodes for b in nodes}
    need(all(K[(a, c)] >= K[(a, b)] + K[(b, c)] - 1 for a in nodes for b in nodes for c in nodes), 'completion not transitive')
    cost = sum((wt[a] * wt[b] for a, b in filled), Q(0))
    need(rat(field(res, 'Value')[1]) == cost, 'alignment cost %s differs from %s' % (rat(field(res, 'Value')[1]), cost))
    return 'completion replayed (%d fills, %d no-path pairs, transitive)' % (len(got), len(exp))
R.HIVE_OPS = tuple(R.HIVE_OPS) + ('CompleteHive',)
_lcr = replay_hive
def replay_hive2(M, req, res, st):
    return replay_complete(M, req, res, st) if head(req) == 'CompleteHive' else _lcr(M, req, res, st)
R.replay_hive = replay_hive2

# ---- Associator (M6-rest; request shape ours, definition spec Def 10.1 l.2827) ----
def replay_assoc(M, req, res, st):
    need(st == 'Checked', 'Associator replays Checked rows only')
    names, car, nodes, wt, H = R.hive(M, req[1]); i, j, k = req[2], req[3], req[4]
    need(len({i, j, k}) == 3 and all(x in names for x in (i, j, k)), 'members')
    v = field(res, 'Value'); A = field(v, 'Associator')
    need(list(field(A, 'Members')[1:]) == [i, j, k], 'Members differ')
    exp = {}
    for a in car[i]:
        for c in car[k]:
            d = H[((i, a), (k, c))]; comp = Q(1) if any(H[((i, a), (j, b))] == 1 and H[((j, b), (k, c))] == 1 for b in car[j]) else Q(0)
            exp[(a, c)] = (d, comp, d - comp)
    got = {}
    for e in field(A, 'Entries')[1:]:
        need(head(e) == 'Entry', 'malformed Entry'); got[(R.val(e[1]), R.val(e[2]))] = tuple(Q(R.val(x)) for x in e[3:6])
    need(got == exp, 'associator entries differ from c_ik - c_ij o c_jk')
    zero = all(t[2] == 0 for t in exp.values())
    need(field(A, 'Zero')[1] == ('True' if zero else 'False'), 'Zero flag differs')
    need(int(field(A, 'Positive')[1]) == sum(1 for t in exp.values() if t[2] > 0) and int(field(A, 'Negative')[1]) == sum(1 for t in exp.values() if t[2] < 0), 'counts differ')
    return 'associator recomputed (%d entries, zero=%s)' % (len(exp), zero)
R.HIVE_OPS = tuple(R.HIVE_OPS) + ('Associator',)
_prev = R.replay_hive
def replay_hive3(M, req, res, st):
    return replay_assoc(M, req, res, st) if head(req) == 'Associator' else _prev(M, req, res, st)
R.replay_hive = replay_hive3

if __name__ == '__main__': sys.exit(R.main(sys.argv[1], sys.argv[2]))
