#!/usr/bin/env python3
"""Independent replay for (Carriers Symbolic) modules (M3, t-2026-11-11-mettadinc-m3).

Shares no code with src/dcalc.  It re-reads the module, evaluates Body terms on
plain integers, and replays from each envelope's own data:
  - refutation witnesses (pairs with a continuation word, partition obligations);
  - reach scopes: the reach set is recomputed by breadth-first search, the
    Invariant and every reachability word are replayed, and every obligation is
    rechecked on the (finite) scope;
  - splitting trees: every Split is evaluated on the representatives;
  - linear certificates: matrices are rebuilt from unit vectors and the identities
    B_j A_a = sum K_a[j][l] B_l are replayed by multiplication;
  - Proof forms: checker cake_lpr, LRAT, and the pinned generator version.
Called from replay.py for modules whose Profile has (Carriers Symbolic)."""
import re
from replay import find, show, Fail, need

GEN_PIN = 'm3.1'   # obligation generator version this replay accepts (spec 15.3)

def is_symbolic(form):
    pf = find(form, 'Profile')
    return bool(pf) and any(isinstance(x, list) and x == ['Carriers', 'Symbolic'] for x in pf[1:])

def lit(t):
    return int(t) if isinstance(t, str) and re.fullmatch(r'[0-9]+', t) else None

class SymM:
    def __init__(self, form):
        self.car, self.map, self.mach, self.decl = {}, {}, {}, {}
        for d in form[2:]:
            if not isinstance(d, list) or len(d) < 2: continue
            h = d[0]
            if h in ('Profile', 'Use', 'Derive'): continue
            if h == 'Carrier':
                of = find(d, 'Of'); en = find(d, 'Enum'); rc = find(d, 'Reach')
                if of and isinstance(of[1], list) and of[1][0] == 'BitVector': w = int(of[1][1])
                else:
                    n = len(en) - 1; w = max(1, (n - 1).bit_length())
                    need([lit(x) for x in en[1:]] == list(range(n)) and n == 1 << w, 'Enum carrier must be 0..2^k-1')
                self.car[d[1]] = {'w': w, 'reach': (rc[1], int(rc[2][1])) if rc else None}
            elif h == 'Map':
                b = find(d, 'Body')
                self.map[d[1]] = {'from': find(d, 'From')[1], 'to': find(d, 'To')[1], 'var': b[1][0], 'body': b[2]}
            elif h == 'Machine':
                self.mach[d[1]] = {'states': find(d, 'States')[1],
                                   'obs': [(x[1], x[2]) for x in d[2:] if x[0] == 'Observe'],
                                   'act': [(x[1], x[2]) for x in d[2:] if x[0] == 'Action']}
            else: self.decl[d[1]] = d

    def W(self, mach): return self.car[self.mach[mach]['states']]['w']

    def ev(self, t, var, x, W):
        """(value, width); width None for an untyped literal."""
        if isinstance(t, str):
            if t == var: return x & ((1 << W) - 1), W
            v = lit(t); need(v is not None, 'unknown symbol %s' % t); return v, None
        h = t[0]; a = lambda k: self.ev(t[k], var, x, W)
        if h == 'BitAt': v, w = a(1); i = int(t[2]); need(w and i < w, 'BitAt range'); return (v >> i) & 1, 1
        if h == 'Slice': v, w = a(1); i, j = int(t[2]), int(t[3]); need(w and i <= j < w, 'Slice range'); return (v >> i) & ((1 << (j - i + 1)) - 1), j - i + 1
        if h == 'SwapBits':
            v, w = a(1); i, j = int(t[2]), int(t[3]); bi, bj = (v >> i) & 1, (v >> j) & 1
            v &= ~((1 << i) | (1 << j)); return v | (bj << i) | (bi << j), w
        if h == 'RotateRange':   # up by one: bit k <- bit k-1, bit i <- bit j
            v, w = a(1); i, j = int(t[2]), int(t[3]); n = j - i + 1; m = (1 << n) - 1; f = (v >> i) & m
            r = ((f << 1) | (f >> (n - 1))) & m; return (v & ~(m << i)) | (r << i), w
        if h == 'SetBit': v, w = a(1); b, _ = a(3); i = int(t[2]); need(b in (0, 1), 'SetBit value'); return (v & ~(1 << i)) | (b << i), w
        if h == 'Parity': v, w = a(1); return bin(v).count('1') & 1, 1
        if h == 'IsZero': v, w = a(1); return int(v == 0), 1
        if h == 'Not': v, w = a(1); need(v in (0, 1), 'Not of a non-bit'); return 1 - v, 1
        if h in ('And', 'Or', 'Xor'):
            (p, wp), (q, wq) = a(1), a(2); w = wp if wp is not None else wq
            r = p & q if h == 'And' else p | q if h == 'Or' else p ^ q; return r & ((1 << w) - 1), w
        if h == 'Eq': (p, _), (q, _) = a(1), a(2); return int(p == q), 1
        raise Fail('Body operator %s outside the BitVectors fragment' % h)

    def apply(self, mname, x):
        m = self.map[mname]; v, _ = self.ev(m['body'], m['var'], x, self.car[m['from']]['w'])
        need(v < (1 << self.car[m['to']]['w']), 'map %s leaves its carrier' % mname); return v

    def act(self, mach, label):
        for l, mp in self.mach[mach]['act']:
            if l == label: return mp
        raise Fail('machine %s has no action %s' % (mach, label))

    def obs(self, mach, x): return tuple(self.apply(mp, x) for _, mp in self.mach[mach]['obs'])

    def run(self, mach, x, word):
        for l in word: x = self.apply(self.act(mach, l), x)
        return x

    def reach(self, mach, start, limit=65536):
        seen, order = {start: []}, [start]
        for x in order:
            for l, mp in self.mach[mach]['act']:
                y = self.apply(mp, x)
                if y not in seen:
                    need(len(order) < limit, 'reach set too large to replay'); seen[y] = seen[x] + [l]; order.append(y)
        return seen

    def block_has(self, blk, x, W):
        b = find(blk, 'Body'); v, _ = self.ev(b[2], b[1][0], x, W); return v == 1

# ---- part 2: replay of one symbolic result ----
def sval(x): return x[1] if isinstance(x, tuple) else x

def proofs_ok(cert):
    p = find(cert, 'Proof'); need(p is not None, 'Checked symbolic result without a Proof form')
    need(find(p, 'Format') == ['Format', 'LRAT'], 'proof format is not LRAT')
    need(find(p, 'Checker') == ['Checker', 'cake_lpr-033aad5'], 'proof checker is not the pinned cake_lpr')
    g = find(p, 'Generator'); need(g == ['Generator', 'dcalc-symgen', GEN_PIN], 'obligation generator version %s is not the pinned %s' % (show(g), GEN_PIN))
    shas = [find(p, 'CnfSha256')] if find(p, 'CnfSha256') else [find(x, 'CnfSha256') for x in (find(p, 'Proofs') or ['Proofs'])[1:]]
    need(shas and all(s and re.fullmatch(r'[0-9a-f]{64}', sval(s[1])) for s in shas), 'every proof must name the sha256 of its CNF')

def scope_of(S, bp):
    c = S.car[find(bp, 'On')[1]]
    if not c['reach']: return None
    return S.reach(c['reach'][0], c['reach'][1])

def blocks_of(bp): return [b for b in bp[2:] if isinstance(b, list) and b and b[0] == 'Block']

def succ_of(bp): return {(s[1], s[2]): s[3] for s in bp[2:] if isinstance(s, list) and s and s[0] == 'Successor'}

def failing(S, mach, bp, x, W, insc):
    """Obligations that fail at word x (Membership is checked on the representatives)."""
    bl = blocks_of(bp); hit = [b for b in bl if S.block_has(b, x, W)]; out = []
    if not insc: return out
    if not hit: out.append('Coverage')
    if len(hit) >= 2: out.append('Disjointness')
    if len(hit) == 1:
        b = hit[0]; r = int(b[3])
        if S.obs(mach, x) != S.obs(mach, r): out.append('Constancy')
        sm = succ_of(bp)
        for l, mp in S.mach[mach]['act']:
            tgt = [c for c in bl if c[1] == sm.get((l, b[1]))]
            if not tgt or not S.block_has(tgt[0], S.apply(mp, x), W): out.append('Stability')
    return out

def replay_partition(S, req, env, st):
    bp = S.decl[req[1]]; mach = find(req, 'Of')[1]; W = S.W(mach); sc = scope_of(S, bp)
    insc = (lambda x: x in sc) if sc is not None else (lambda x: x < (1 << W))
    if st == 'Refuted':
        r = find(find(env, 'Value'), 'Refuted'); ob = find(r, 'Obligation')[1]; x = int(find(r, 'Witness')[1])
        if ob == 'Membership':
            need(any(int(b[3]) == x and (not insc(x) or not S.block_has(b, x, W)) for b in blocks_of(bp)), 'membership witness does not fail')
        else: need(ob in failing(S, mach, bp, x, W, insc(x)), '%s witness %d does not fail' % (ob, x))
        return 'ok'
    cert = find(find(env, 'Evidence'), 'Certificate'); proofs_ok(cert)
    if sc is not None:   # finite scope: recheck every obligation on every word, and the reach words
        inv = find(cert, 'Invariant'); need(inv and sorted(int(w) for w in find(inv, 'Words')[1:]) == sorted(sc), 'Invariant is not the reach set')
        for w in find(cert, 'ReachWords')[1][1:]:
            x = int(w[1]); need(S.run(S.car[find(bp, 'On')[1]]['reach'][0], S.car[find(bp, 'On')[1]]['reach'][1], find(w, 'Path')[1:]) == x, 'reach word does not reach %d' % x)
        for x in sc: need(not failing(S, mach, bp, x, W, True), 'obligation fails at reachable word %d' % x)
        for b in blocks_of(bp): need(int(b[3]) in sc and S.block_has(b, int(b[3]), W), 'representative of %s not a reachable member' % b[1])
    return 'ok'

def test_val(S, mach, split, x):
    o = find(split, 'Observe'); port = [n for n, _ in S.mach[mach]['obs']].index(o[1])
    y = S.run(mach, x, find(split, 'Word')[1:]); return (S.apply(S.mach[mach]['obs'][port][1], y) >> int(o[2])) & 1

def tree_reps(S, mach, t):
    if t[0] == 'Leaf': return [int(find(t, 'Rep')[1])], 0
    z, nz = tree_reps(S, mach, find(t, 'Zero')[1]); o, no = tree_reps(S, mach, find(t, 'One')[1])
    need(all(test_val(S, mach, t, x) == 0 for x in z) and all(test_val(S, mach, t, x) == 1 for x in o), 'a Split does not separate its subtrees')
    return z + o, nz + no + 1

def lin_rows(S, mp, W):
    tw = S.car[S.map[mp]['to']]['w']; rows = [0] * tw
    for i in range(W):
        y = S.apply(mp, 1 << i)
        for j in range(tw):
            if (y >> j) & 1: rows[j] |= 1 << i
    need(S.apply(mp, 0) == 0, 'map %s is not linear' % mp)
    for a, b in ((5, 9), (3 << 20, 77), ((1 << W) - 1, 12345)):
        a &= (1 << W) - 1; b &= (1 << W) - 1
        need(S.apply(mp, a ^ b) == S.apply(mp, a) ^ S.apply(mp, b), 'map %s is not linear' % mp)
    return rows

def comp(r, rows):
    x = 0
    for j, row in enumerate(rows):
        if (r >> j) & 1: x ^= row
    return x

def replay_linear(S, mach, lin, ncl):
    W = S.W(mach); B = [int(sval(r[1]), 16) for r in find(lin, 'Basis')[1:]]; k = len(B)
    need(int(find(lin, 'ObservableDimension')[1]) == k and int(find(lin, 'UnobservableDimension')[1]) == W - k and 1 << k == ncl, 'dimensions disagree')
    piv = {}
    def red(v):
        while v and (v.bit_length() - 1) in piv: v ^= piv[v.bit_length() - 1]
        return v
    for b in B: r = red(b); need(r, 'basis rows are dependent'); piv[r.bit_length() - 1] = r
    for _, mp in S.mach[mach]['obs']:
        for row in lin_rows(S, mp, W): need(red(row) == 0, 'an observation row is outside the observable space')
    for t in find(lin, 'Transitions')[1:]:
        rows = lin_rows(S, S.act(mach, t[1]), W); K = [int(sval(c), 16) for c in find(t, 'K')[1:]]; need(len(K) == k, 'K has the wrong size')
        for j in range(k):
            x = 0
            for l in range(k):
                if (K[j] >> l) & 1: x ^= B[l]
            need(comp(B[j], rows) == x, 'identity B_%d A_%s fails' % (j, t[1]))

def replay(S, D, digest, req, env):
    st = find(env, 'Status')[1]
    if st not in ('Checked', 'Refuted'): return 'skip'
    need(find(find(env, 'Binding'), 'Digest')[1][1] == digest, 'digest mismatch')
    dname = req if isinstance(req, str) else None
    if dname: need(dname in D, 'unknown derive'); req = D[dname]
    h = req[0]
    if h == 'CheckBlockPartition': return replay_partition(S, req, env, st)
    if h in ('CheckNow', 'CheckBehavioral'):
        rd = S.decl[req[1]]; mach = find(rd, 'Of')[1]; enc = find(rd, 'Encode')[1]
        if st == 'Checked': proofs_ok(find(find(env, 'Evidence'), 'Certificate')); return 'ok'
        w = find(find(find(env, 'Value'), 'Refuted'), 'Witness'); x, y = (int(v) for v in find(w, 'Pair')[1:])
        port = [n for n, _ in S.mach[mach]['obs']].index(find(w, 'Observe')[1]); word = find(w, 'Word')[1:]
        need(x != y and S.apply(enc, x) == S.apply(enc, y), 'witness pair does not share a code')
        need(h == 'CheckBehavioral' or not word, 'CheckNow witness with a continuation')
        need(S.apply(S.mach[mach]['obs'][port][1], S.run(mach, x, word)) != S.apply(S.mach[mach]['obs'][port][1], S.run(mach, y, word)), 'continuation does not separate the pair')
        return 'ok'
    if h == 'MinimizeForQueries':
        mach = req[1]; cert = find(find(env, 'Evidence'), 'Certificate'); proofs_ok(cert)
        ncl = int(find(find(find(env, 'Value'), 'Refinement'), 'Classes')[1]); tr = find(cert, 'Tree')
        reps, nodes = tree_reps(S, mach, tr[3])
        need(len(reps) == ncl == len(set(reps)) and nodes == int(find(tr, 'Nodes')[1]) == ncl - 1, 'tree leaves/nodes disagree with the classes')
        need(sorted(reps) == sorted(int(r) for r in find(cert, 'Representatives')[1:]), 'representatives differ from the tree leaves')
        if find(cert, 'Linear'): replay_linear(S, mach, find(cert, 'Linear'), ncl)
        return 'ok'
    raise Fail('symbolic request %s has no replay' % h)
