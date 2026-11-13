#!/usr/bin/env python3
"""Independent replay of M6 Contracts answers (t-2026-11-13-mettadinc-m6).

usage: replay_m6.py fixture.metta dcalc.out
Own s-expression reader and own rational evaluator (no dcalc code).  Every Checked/Refuted
CheckImplementation or ThenContracts row that claims (Replayed True) is recomputed from the
fixture: the affine bound E(f-hat(xh), f(x)) <= L*D(xh, x) + eta over every ordered audited pair
(spec section 9, OneMinusAbsoluteDifference distances = |a - b|), and Proposition 9.1 for
compositions.  Exit 0 iff every such row is ACCEPTed."""
import sys
from fractions import Fraction as Q

def toks(t):
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c.isspace(): i += 1
        elif c == ';':
            while i < n and t[i] != '\n': i += 1
        elif c in '()': yield c; i += 1
        elif c == '"':
            j = i + 1
            while j < n and t[j] != '"': j += 2 if t[j] == '\\' else 1
            yield t[i:j + 1]; i = j + 1
        else:
            j = i
            while j < n and not t[j].isspace() and t[j] not in '()"': j += 1
            yield t[i:j]; i = j
def read_all(text):
    st = [[]]
    for k in toks(text):
        if k == '(': st.append([])
        elif k == ')': x = st.pop(); st[-1].append(x)
        else: st[-1].append(k)
    return st[0]
def head(t): return t[0] if isinstance(t, list) and t and isinstance(t[0], str) else None
def field(t, h):
    for x in (t[1:] if isinstance(t, list) else []):
        if head(x) == h: return x
    return None
def val(x):
    """own value reading: integers and (Rat p q) -> Fraction, (Tuple ...) -> tuple, other symbols -> str"""
    if isinstance(x, str):
        try: return Q(int(x))
        except ValueError: return x
    if head(x) == 'Rat' and len(x) == 3: return Q(int(x[1]), int(x[2]))
    if head(x) == 'Tuple': return tuple(val(e) for e in x[1:])
    raise ValueError('not a value: %r' % (x,))
rat = val
# FiniteSets packet symbols as receipt sets (spec Example 4.3): Empty {}, UOnly {u}, VOnly {v}, Both {u, v}
RSET = {'Empty': frozenset(), 'UOnly': frozenset('u'), 'VOnly': frozenset('v'), 'Both': frozenset('uv')}
RSYM = {v: k for k, v in RSET.items()}

class Mod:
    def __init__(self, form, forms):
        self.name = form[1]; self.cdecl = {}; self.maps = {}; self.impl = {}; self.derive = {}; self.tol = {}
        decls = []
        for d in form[2:]:
            only = field(d, 'Only') if head(d) == 'Import' else None
            if only and d[1] in forms and d[1] != form[1]:
                names = set(only[1:])
                decls += [e for e in forms[d[1]][2:] if isinstance(e, list) and len(e) > 1 and isinstance(e[1], str) and head(e) != 'Import' and e[1] in names]
            else: decls.append(d)
        self.raw = {(head(d), d[1]): d for d in decls if isinstance(d, list) and len(d) > 1 and isinstance(d[1], str)}
        for d in decls:
            h = head(d)
            if h == 'Carrier': self.cdecl[d[1]] = d[3]
            elif h == 'Map' and len(d) == 5:
                if head(d[4]) == 'Body': self.maps[d[1]] = (field(d, 'From')[1], 'body', d[4][1][0], d[4][2])
                elif head(d[4]) in ('Cases', 'Table'): self.maps[d[1]] = (field(d, 'From')[1], 'cases', {val(c[0]): val(c[1]) for c in d[4][1:]}, None)   # Table rows are (key value) like Cases
            elif h == 'Implementation': self.impl[d[1]] = {k: field(d, k)[1] for k in ('Ideal', 'Actual', 'Audit', 'InputDistance', 'OutputDistance')}
            elif h == 'Derive': self.derive[d[1]] = d[2]
            elif h == 'Tolerance': self.tol[d[1]] = head(d[3])
    def dom(self, c):
        if isinstance(c, str):
            b = self.cdecl[c]
            if head(b) == 'Enum': return [val(e) for e in b[1:]]
            if head(b) == 'Product' and len(b) == 3: return [(x, y) for x in self.dom(b[1]) for y in self.dom(b[2])]
            raise ValueError('carrier %s not replayable' % c)
        if head(c) == 'Product' and len(c) == 3: return [(x, y) for x in self.dom(c[1]) for y in self.dom(c[2])]
        raise ValueError('carrier %r not replayable' % (c,))
    def ev(self, b, var, v):
        if b == var: return v
        if isinstance(b, str) or head(b) == 'Rat': return val(b)
        op = head(b)
        if op in ('Add', 'Sub', 'Mul', 'Div') and len(b) == 3:
            x, y = self.ev(b[1], var, v), self.ev(b[2], var, v)
            if not (isinstance(x, Q) and isinstance(y, Q)): raise ValueError('%s on non-rationals' % op)
            return x + y if op == 'Add' else x - y if op == 'Sub' else x * y if op == 'Mul' else x / y
        if op == 'GetTuple' and len(b) == 3: return self.ev(b[1], var, v)[int(b[2])]
        if op == 'ReceiptUnion' and len(b) == 3: return RSYM[RSET[self.ev(b[1], var, v)] | RSET[self.ev(b[2], var, v)]]
        if op in self.maps and len(b) == 2: return self.app(op, self.ev(b[1], var, v))
        raise ValueError('Body operator %r' % (op,))
    def app(self, f, v):
        frm, kind, a, body = self.maps[f]
        if v not in self.dom(frm): raise ValueError('%s applied outside its From carrier' % f)
        return self.ev(body, a, v) if kind == 'body' else a[v]
    def dist(self, t, a, b):
        k = self.tol.get(t)
        if k == 'Trivial': return Q(0)
        if k == 'Discrete': return Q(0) if a == b else Q(1)
        if k == 'OneMinusAbsoluteDifference' and isinstance(a, Q) and isinstance(b, Q): return abs(a - b)
        raise ValueError('distance %s not replayable' % t)
    def worst(self, name, L, eta):
        """(holds, first violating (xh, x, gap, bound) or None)"""
        I = self.impl[name]; X = self.dom(I['Audit'])
        for a in X:
            for b in X:
                gap = self.dist(I['OutputDistance'], self.app(I['Actual'], a), self.app(I['Ideal'], b)); bound = L * self.dist(I['InputDistance'], a, b) + eta
                if gap > bound: return False, (a, b, gap, bound)
        return True, None

def need(c, msg):
    if not c: raise AssertionError(msg)

# ---- M6 Hives (crisp kernel hives), own semantics ----
HIVE_OPS = ('CheckKernelCoherence', 'Holonomy', 'ConsensusCost', 'LeastCoherentRefinement')
def hive(M, name):
    if isinstance(name, list):
        need(head(name) == 'Output' and name[2] == 'Hive' and head(M.derive[name[1]]) == 'KernelOf', 'not a derived kernel hive'); return kernel_of(M, M.derive[name[1]])
    d = M.raw[('KernelHive', name)]; mem = [x for x in d[2:] if head(x) == 'Member']; names = [x[1] for x in mem]
    W = field(d, 'Weights'); w = {e[0]: val(e[1]) for e in W[1:]} if W else {n: Q(1, len(mem)) for n in names}
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
                a, b, v = val(e[0]), val(e[1]), val(e[2]); H[((x[1], a), (x[2], b))] = H[((x[2], b), (x[1], a))] = v
    need(all((a, b) in H for a in nodes for b in nodes), 'kernel not fully measured')
    return names, car, nodes, wt, H
def holo(car, H, cyc):
    s = u = cyc[0]; R = {(a, b): a == b for a in car[s] for b in car[s]}
    for v in cyc[1:] + [s]:
        R = {(a, c): any(R[(a, b)] and H[((u, b), (v, c))] == 1 for b in car[u]) for a in car[s] for c in car[v]}; u = v
    return R
def kern_ok(K, R): return {(val(e[0]), val(e[1])): val(e[2]) == 1 for e in field(K, 'Entries')[1:]} == R
def node(n): need(head(n) == 'Node', 'not a Node'); return (n[1], val(n[2]))
def replay_hive(M, req, res, st):
    h = head(req); names, car, nodes, wt, H = hive(M, req[1]); ev = field(res, 'Evidence')
    if h != 'CheckKernelCoherence': need(st == 'Checked', '%s replays Checked rows only' % h)
    if h == 'CheckKernelCoherence':
        bad = [(a, b, c) for a in nodes for b in nodes for c in nodes if H[(a, c)] < H[(a, b)] + H[(b, c)] - 1]
        if st == 'Checked': need(not bad, 'Checked but %s is not transitive' % (bad[:1],)); return 'transitive over %d triples' % len(nodes) ** 3
        need(bad, 'Refuted but the kernel is transitive'); a, b, c = map(node, field(field(ev, 'Witness'), 'Triple')[1:4])
        need(H[(a, c)] < H[(a, b)] + H[(b, c)] - 1, 'witness triple is transitive')
        hk = field(ev, 'Holonomy')
        if hk: need(kern_ok(field(hk, 'Kernel'), holo(car, H, names)), 'evidence holonomy differs')
        return 'intransitive triple replayed'
    if h == 'Holonomy':
        need(st == 'Checked', 'Holonomy replays Checked rows only')
        need(kern_ok(field(field(res, 'Value'), 'Kernel'), holo(car, H, list(req[2][1:]))), 'holonomy kernel differs'); return 'holonomy recomposed'
    if h == 'ConsensusCost':
        C = {k: v == 1 for k, v in H.items()}
        for k in nodes:
            for a in nodes:
                if C[(a, k)]:
                    for b in nodes:
                        if C[(k, b)]: C[(a, b)] = True
        cost = sum(wt[a] * wt[b] for a in nodes for b in nodes if C[(a, b)] and H[(a, b)] == 0)
        need(rat(field(res, 'Value')[1]) == cost, 'closure cost is %s' % cost); return 'closure cost recomputed'
    if h == 'LeastCoherentRefinement':
        cert = field(ev, 'Certificate'); X = {(a, b): Q(1 if a == b else 0) for a in nodes for b in nodes}
        for p in field(cert, 'Kept')[1:]: a, b = node(p[1]), node(p[2]); X[(a, b)] = X[(b, a)] = rat(p[3])
        need(all(0 <= X[k] <= H[k] for k in X), 'kept pair outside [0, H]')
        need(all(X[(a, c)] >= X[(a, b)] + X[(b, c)] - 1 for a in nodes for b in nodes for c in nodes), 'refinement not transitive')
        E = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:] if H[(a, b)] == 1]
        cov = {frozenset(e): Q(0) for e in E}; Dv = Q(0)
        for t in field(cert, 'Dual')[1:]:
            y = rat(t[-1]); need(y >= 0, 'negative dual'); Dv += y
            if head(t) == 'Edge': ks = [frozenset((node(t[1]), node(t[2])))]
            else:
                a, b, c = node(t[1]), node(t[2]), node(t[3]); need(H[(a, c)] == 0, 'dual triple closes on an identified pair'); ks = [frozenset((a, b)), frozenset((b, c))]
            for k in ks:
                if k in cov: cov[k] += y
        need(all(cov[frozenset((a, b))] >= wt[a] * wt[b] for a, b in E), 'dual infeasible')
        P = sum(wt[a] * wt[b] * X[(a, b)] for a, b in E); T = sum(wt[a] * wt[b] for a, b in E)
        need(P == Dv, 'primal %s != dual %s' % (P, Dv)); need(rat(field(cert, 'PrimalValue')[1]) == P and rat(field(cert, 'DualValue')[1]) == Dv, 'certificate values differ')
        need(rat(field(res, 'Value')[1]) == 2 * (T - P), 'cost is not 2(EdgeMass - kept)'); return 'optimality certificate replayed (primal = dual)'
    raise AssertionError('no hive rule for %s' % h)

# ---- M6 Transfers (spec 10.2/10.4), own semantics ----
TRANSFER_OPS = ('CheckTransfer', 'CheckValuePullback', 'LibraryGap', 'ComposeTransfers', 'CheckTransferHive')
def cases(M, name): mp = M.maps[name]; need(mp[1] == 'cases', 'map %s not replayable' % name); return mp[2]
def msys(M, name):
    d = M.raw[('MethodSystem', name)]
    return dict(d=d, X=M.dom(field(d, 'States')[1]), A=M.dom(field(d, 'Methods')[1]), r=cases(M, field(d, 'Response')[1]))
def tload(M, name):
    d = M.raw[('Transfer', name)]
    return dict(name=name, a=msys(M, field(d, 'Source')[1]), b=msys(M, field(d, 'Target')[1]), an=field(d, 'Source')[1], bn=field(d, 'Target')[1],
                phi=cases(M, field(d, 'StatePullback')[1]), iota=cases(M, field(d, 'MethodPushforward')[1]))
def tdist(met, u, v): return (Q(0) if u == v else Q(1)) if met == 'RewardLawTV' else abs(u - v)
def tcheck(M, T, met):
    """(observer failure or None, defect, worst (b, a))"""
    A, B = T['a'], T['b']
    for o in B['d'][2:]:
        if head(o) != 'Observe': continue
        oa = [x for x in A['d'][2:] if head(x) == 'Observe' and x[1] == o[1]]; need(oa, 'observer %s missing on source' % o[1])
        fb, fa = cases(M, o[2]), cases(M, oa[0][2])
        for b in B['X']:
            if fa[T['phi'][b]] != fb[b]: return (o[1], b), None, None
    best, w = Q(0), None
    for b in B['X']:
        for a in A['A']:
            d = tdist(met, A['r'][(T['phi'][b], a)], B['r'][(b, T['iota'][a])])
            if d > best: best, w = d, (b, a)
    return None, best, w
def metric(req):
    ms = [o[1] for o in req[2:] if head(o) == 'Metric']; return ms[-1] if ms else 'RewardLawTV'
def gauge(M, th, nm, S):
    gens = []
    for x in th[2:]:
        if head(x) == 'Gauge' and x[1] == nm:
            sy = M.raw[('Symmetry', x[2])]; need(field(sy, 'Of')[1] == nm, 'symmetry of another system')
            s, a = cases(M, field(sy, 'States')[1]), cases(M, field(sy, 'Methods')[1])
            if not all(S['r'][(s[x_], a[m])] == S['r'][(x_, m)] for x_ in S['X'] for m in S['A']): return None
            gens.append((s, a))
    G = {(tuple(S['X']), tuple(S['A']))}; grow = True
    while grow:
        grow = False
        for gs, ga in list(G):
            for s, a in gens:
                p = (tuple(s[dict(zip(S['X'], gs))[x_]] for x_ in S['X']), tuple(a[dict(zip(S['A'], ga))[m]] for m in S['A']))
                if p not in G: G.add(p); grow = True
    return [(dict(zip(S['X'], gs)), dict(zip(S['A'], ga))) for gs, ga in G]
def thive(M, name):
    """own verdict for a transfer hive: (coherent, {cycle tuple: (state map, method map)})"""
    th = M.raw[('TransferHive', name)]; mem = [x[1] for x in th[2:] if head(x) == 'Member']; S = {n: msys(M, n) for n in mem}
    G = {n: gauge(M, th, n, S[n]) for n in mem}
    if any(g is None for g in G.values()): return False, {}
    E = [tload(M, x[1]) for x in th[2:] if head(x) == 'Edge']
    for T in E:
        need(T['an'] in S and T['bn'] in S, 'edge joins a non-member')
        if tcheck(M, T, 'RewardLawTV')[1] != 0: return False, {}
        GA, GB = G[T['an']], G[T['bn']]
        inter = lambda ga, gb: all(T['phi'][gb[0][b]] == ga[0][T['phi'][b]] for b in S[T['bn']]['X']) and all(T['iota'][ga[1][a]] == gb[1][T['iota'][a]] for a in S[T['an']]['A'])
        if not all(any(inter(ga, gb) for gb in GB) for ga in GA) or not all(any(inter(ga, gb) for ga in GA) for gb in GB): return False, {}
    hol = {}
    for x in th[2:]:
        if head(x) != 'Cycle': continue
        cyc = x[1:]; es = [next(T for T in E if T['an'] == cyc[j] and T['bn'] == cyc[(j + 1) % len(cyc)]) for j in range(len(cyc))]
        U = S[cyc[0]]; hs, ha = {}, {}
        for s in U['X']:
            y = s
            for T in reversed(es): y = T['phi'][y]
            hs[s] = y
        for a in U['A']:
            y = a
            for T in es: y = T['iota'][y]
            ha[a] = y
        if (hs, ha) not in G[cyc[0]]: return False, {}
        hol[tuple(cyc)] = (hs, ha)
    return True, hol
def ents(e): return {val(x[1]): val(x[2]) for x in e[1:]}
def kernel_of(M, kreq):
    th = M.raw[('TransferHive', kreq[1])]; sat = any(head(o) == 'Saturate' for o in kreq[2:])
    mem = [x[1] for x in th[2:] if head(x) == 'Member']; S = {n: msys(M, n) for n in mem}
    G = {n: (gauge(M, th, n, S[n]) if sat else [({x: x for x in S[n]['X']}, {m: m for m in S[n]['A']})]) for n in mem}
    need(all(g is not None for g in G.values()), 'declared gauge is not a symmetry')
    al = {n: {(x, y): max(1 - max(abs(S[n]['r'][(x, m)] - S[n]['r'][(y, g[1][m])]) for m in S[n]['A']) for g in G[n]) for x in S[n]['X'] for y in S[n]['X']} for n in mem}
    H = {((n, x), (n, y)): v for n in mem for (x, y), v in al[n].items()}
    for x in th[2:]:
        if head(x) != 'Edge': continue
        T = tload(M, x[1]); i, j = T['an'], T['bn']
        c = {(u, v): 1 - max(abs(S[i]['r'][(u, m)] - S[j]['r'][(v, T['iota'][m])]) for m in S[i]['A']) for u in S[i]['X'] for v in S[j]['X']}
        for u in S[i]['X']:
            for v in S[j]['X']:
                k = max(min(al[i][(u, p)], c[(p, q)], al[j][(q, v)]) for p in S[i]['X'] for q in S[j]['X']) if sat else c[(u, v)]
                H[((i, u), (j, v))] = H[((j, v), (i, u))] = k
    car = {n: S[n]['X'] for n in mem}; nodes = [(n, x) for n in mem for x in car[n]]; wt = {(n, x): Q(1, len(mem)) / len(car[n]) for n, x in nodes}
    need(all((a, b) in H for a in nodes for b in nodes), 'derived kernel not fully measured')
    return mem, car, nodes, wt, H
def replay_transfer(M, req, res, st):
    h = head(req); ev = field(res, 'Evidence')
    if h == 'CheckTransfer':
        T = tload(M, req[1]); met = metric(req); obs, d, w = tcheck(M, T, met)
        if st == 'Checked':
            need(obs is None and d == 0, 'Checked but defect %s / observer %s' % (d, obs)); need(rat(field(field(res, 'Value'), 'Defect')[1]) == 0, 'Value defect is not 0'); return 'exact transfer (%s)' % met
        need(obs is not None or d > 0, 'Refuted but the transfer is exact'); W = field(ev, 'Witness')
        if field(W, 'Observer'):
            b = val(field(W, 'State')[1]); o = field(W, 'Observer')[1]; need(obs is not None and o == obs[0], 'observer witness differs')
            oa = [x for x in T['a']['d'][2:] if head(x) == 'Observe' and x[1] == o][0]; ob = [x for x in T['b']['d'][2:] if head(x) == 'Observe' and x[1] == o][0]
            need(cases(M, oa[2])[T['phi'][b]] != cases(M, ob[2])[b], 'observer witness is preserved'); return 'observer witness replayed'
        need(obs is None, 'observer failure not reported'); b, a = val(field(W, 'State')[1]), val(field(W, 'Method')[1])
        dd = tdist(met, T['a']['r'][(T['phi'][b], a)], T['b']['r'][(b, T['iota'][a])])
        need(dd == d and rat(field(W, 'Defect')[1]) == d, 'witness defect is not the maximum %s' % d); return 'defect witness replayed (%s)' % d
    if h == 'CheckValuePullback':
        T = tload(M, req[1]); bad = [b for b in T['b']['X'] if max(T['b']['r'][(b, m)] for m in T['b']['A']) != max(T['a']['r'][(T['phi'][b], a)] for a in T['a']['A'])]
        need((st == 'Checked') == (not bad), 'value pullback verdict differs'); return 'optimal values compared'
    if h == 'LibraryGap':
        need(st == 'Checked', 'LibraryGap replays Checked rows only'); T = tload(M, req[1]); B = T['b']
        g = max(max(B['r'][(b, m)] for m in B['A']) - max(B['r'][(b, T['iota'][a])] for a in T['a']['A']) for b in B['X'])
        need(rat(field(res, 'Value')[1]) == g, 'gap is %s' % g); return 'library gap recomputed'
    if h == 'ComposeTransfers':
        need(st == 'Checked', 'ComposeTransfers replays Checked rows only'); Ts, tot = [], Q(0)
        for o in req[1:]:
            need(head(o) == 'Output' and o[2] == 'Transfer' and head(M.derive[o[1]]) == 'CheckTransfer', 'premise is not a CheckTransfer Derive')
            p = M.derive[o[1]]; T = tload(M, p[1]); obs, d, w = tcheck(M, T, metric(p)); need(obs is None and d == 0, 'premise %s is not exact' % p[1]); Ts.append(T); tot += d
        need(all(Ts[k]['bn'] == Ts[k + 1]['an'] for k in range(len(Ts) - 1)), 'transfers do not chain')
        V = field(field(res, 'Value'), 'Transfer'); ph, io = {}, {}
        for x in Ts[-1]['b']['X']:
            y = x
            for T in reversed(Ts): y = T['phi'][y]
            ph[x] = y
        for a in Ts[0]['a']['A']:
            y = a
            for T in Ts: y = T['iota'][y]
            io[a] = y
        need(ents(field(field(V, 'StatePullback'), 'Entries')) == ph and ents(field(field(V, 'MethodPushforward'), 'Entries')) == io, 'composite maps differ')
        need(rat(field(V, 'Defect')[1]) == tot, 'composite defect is not the sum'); return 'Poly composition recomputed'
    if h == 'CheckTransferHive':
        ok, hol = thive(M, req[1]); need((st == 'Checked') == ok, 'transfer hive verdict differs (own: %s)' % ok)
        if ok:
            got = {tuple(x[1][1:]): (ents(field(field(x, 'States'), 'Entries')), ents(field(field(x, 'Methods'), 'Entries'))) for x in field(res, 'Value')[1:]}
            need(got == hol, 'holonomies differ')
        return 'transfer hive recomputed'
    raise AssertionError('no transfer rule for %s' % h)

def replay(M, req, res):
    st = field(res, 'Status')[1]; h = head(req)
    if h == 'CheckImplementation':
        L, eta = rat(req[2][1]), rat(req[2][2]); ok, w = M.worst(req[1], L, eta)
        if st == 'Checked':
            need(ok, 'Checked but pair %s violates the bound' % (w,))
            g = field(field(res, 'Value'), 'Grade'); need(g and (rat(g[1]), rat(g[2])) == (L, eta), 'Value Grade differs from the request')
            return 'affine bound over %d audited pairs' % len(M.dom(M.impl[req[1]]['Audit'])) ** 2
        need(st == 'Refuted' and not ok, 'Refuted but every audited pair meets the bound')
        wit = field(field(field(res, 'Evidence'), 'Witness'), 'Pair'); W = field(field(res, 'Evidence'), 'Witness')
        a, b = rat(field(wit, 'Audited')[1]), rat(field(wit, 'Reference')[1]); I = M.impl[req[1]]
        need(a in M.dom(I['Audit']) and b in M.dom(I['Audit']), 'witness pair is not audited')
        gap = M.dist(I['OutputDistance'], M.app(I['Actual'], a), M.app(I['Ideal'], b)); bound = L * M.dist(I['InputDistance'], a, b) + eta
        need(gap > bound, 'witness pair meets the bound'); need(rat(field(W, 'OutputGap')[1]) == gap and rat(field(W, 'Bound')[1]) == bound, 'witness numbers differ')
        return 'violating pair replayed'
    if h == 'ThenContracts':
        need(st == 'Checked', 'ThenContracts replays Checked rows only')
        prem = []
        for o in req[1:3]:
            need(head(o) == 'Output' and o[2] == 'Value' and o[1] in M.derive, 'premise is not (Output Derive Value)')
            p = M.derive[o[1]]; need(head(p) == 'CheckImplementation', 'premise is not CheckImplementation')
            L, eta = rat(p[2][1]), rat(p[2][2]); ok, w = M.worst(p[1], L, eta); need(ok, 'premise %s does not hold: %s' % (p[1], w)); prem.append((p[1], L, eta))
        (n1, L1, e1), (n2, L2, e2) = prem; I1, I2 = M.impl[n1], M.impl[n2]
        need(I1['OutputDistance'] == I2['InputDistance'], 'distances do not chain')
        for x in M.dom(I1['Audit']):
            for f in (I1['Ideal'], I1['Actual']): need(M.app(f, x) in M.dom(I2['Audit']), 'value of %s outside %s audit' % (f, n2))
        g = field(field(res, 'Value'), 'Grade'); need(g and (rat(g[1]), rat(g[2])) == (L2 * L1, L2 * e1 + e2), 'composite Grade is not Proposition 9.1')
        return 'Proposition 9.1 composite grade'
    if h in HIVE_OPS: return replay_hive(M, req, res, st)
    if h in TRANSFER_OPS: return replay_transfer(M, req, res, st)
    raise AssertionError('no replay rule for %s' % h)

def main(fx, out):
    forms = read_all(open(fx, encoding='utf-8').read()); fm = {f[1]: f for f in forms if head(f) == 'DC.Module'}; mods = {}
    bad = rows = 0
    for line in open(out, encoding='utf-8').read().splitlines():
        if ' => ' not in line: continue
        res = read_all(line.split(' => ', 1)[1])[0]; st = field(res, 'Status')[1]
        asr = field(res, 'Assurance'); rep = field(asr, 'Replayed') if asr else None
        if st not in ('Checked', 'Refuted') or not rep or rep[1] != 'True': continue
        mod = line.split(' ', 1)[0]; req = field(res, 'Claim')[1]
        if head(req) not in ('CheckImplementation', 'ThenContracts') + HIVE_OPS + TRANSFER_OPS: continue   # other milestones have their own replayers
        rows += 1
        try:
            if mod not in mods: mods[mod] = Mod(fm[mod], fm)
            print('ACCEPT    %s' % replay(mods[mod], req, res))
        except (AssertionError, ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as e:
            bad += 1; print('REJECT    %s: %s' % (line.split(' => ')[0][:80], e))
    print('replay_m6: %d rows, %d not accepted -> %s' % (rows, bad, 'PASS' if rows and not bad else 'FAIL'))
    return 1 if bad or not rows else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1], sys.argv[2]))
