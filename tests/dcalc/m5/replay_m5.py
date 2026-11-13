#!/usr/bin/env python3
"""Independent replayer for M5 nondeterministic results (review 1 F1, t-2026-11-12-mettadinc-m5).

Shares no code with dcalc: its own s-expression reader, its own reading of the
fixture module, exact Fractions.  For each result line of a dcalc .out file it
recomputes the evidence from the module source and accepts or rejects it:
  Simulation certificate  -- Pairs = graph of the Relation map; observers agree on
                             every pair; one Match per (pair, action, source step),
                             each a real target move into a related pair; Coverage of
                             every initial source state.
  SafetyTransfer          -- nested Simulation certificate (with Init coverage);
                             Reachable = closure of the related initial targets
                             under the target actions; the Never property on it.
  UnmatchedMove witness   -- the source move exists and no target move matches it.
  ExactnessFailure        -- the two states share a code and their successor codes
                             are the listed, different sets.
  Probability             -- uniform-scheduler distribution after the word, and the
                             event mass, recomputed with Fractions.
Every row whose Assurance claims (Replayed True) under the M5 policy must be
accepted here; a claim the replayer cannot check is reported, never silently passed.
Usage: replay_m5.py MODULE.metta RESULTS.out [...pairs]   exit 1 on any rejection.
"""
import re, sys
from fractions import Fraction

TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')
def read_all(text):
    toks = TOK.findall(text); pos = 0; out = []
    def one():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            l = []
            while toks[pos] != ')': l.append(one())
            pos += 1; return l
        if t == ')': raise ValueError('unbalanced )')
        return t
    while pos < len(toks): out.append(one())
    return out
def head(t): return t[0] if isinstance(t, list) and t and isinstance(t[0], str) else None
def field(t, h):
    for x in t[1:] if isinstance(t, list) else []:
        if head(x) == h: return x
    return None
def fields(t, h): return [x for x in (t[1:] if isinstance(t, list) else []) if head(x) == h]
def find_all(t, h, acc=None):
    acc = [] if acc is None else acc
    if isinstance(t, list):
        if head(t) == h: acc.append(t)
        for x in t: find_all(x, h, acc)
    return acc

class Module:
    def __init__(self, term):
        self.name = term[1]; self.car = {}; self.map = {}; self.mach = {}; self.sim = {}; self.rep = {}; self.relp = {}
        for d in term[2:]:
            h = head(d)
            if h == 'Carrier':
                en = field(d, 'Enum')
                self.car[d[1]] = list(en[1:]) if en else None   # non-enumerated carrier: not replayable here
            elif h == 'Map':
                img = {}
                for c in (field(d, 'Cases') or [None])[1:]: img[c[0]] = {c[1]}
                for c in (field(d, 'Choice') or [None])[1:]: img[c[0]] = set(c[1:])
                self.map[d[1]] = img
            elif h == 'Machine':
                self.mach[d[1]] = {'states': field(d, 'States')[1], 'obs': {o[1]: o[2] for o in fields(d, 'Observe')},
                                   'act': {a[1]: a[2] for a in fields(d, 'Action')}}
            elif h == 'Relation': self.relp[d[1]] = {(c[0], c[1]) for c in (field(d, 'Pairs') or ['Pairs'])[1:]}
            elif h == 'Simulation': self.sim[d[1]] = (field(d, 'Source')[1], field(d, 'Target')[1], field(d, 'Relation')[1])
            elif h == 'Representation': self.rep[d[1]] = (field(d, 'Of')[1], field(d, 'Encode')[1])
    def states(self, m): return self.car[self.mach[m]['states']]
    def img(self, m, a, x): return self.map[self.mach[m]['act'][a]].get(x, set())
    def obs(self, m, o, x):
        v = self.map[self.mach[m]['obs'][o]].get(x, set()); return next(iter(v)) if len(v) == 1 else None
    def rel(self, s):
        src, tgt, r = self.sim[s]
        if r in self.relp: return set(self.relp[r])
        return {(x, y) for x, ys in self.map[r].items() for y in ys}

def fail(msg): raise AssertionError(msg)
def need(c, msg):
    if not c: fail(msg)

def check_simulation(M, cert, init):
    sname = field(cert, 'Relation')[1]; src, tgt, _ = M.sim[sname]
    need(field(cert, 'Source')[1] == src and field(cert, 'Target')[1] == tgt, 'Source/Target names differ from the module')
    pairs = {(p[0], p[1]) for p in field(cert, 'Pairs')[1:]}
    need(pairs == M.rel(sname), 'Pairs is not the graph of the relation map')
    for (x, y) in pairs:
        for o in M.mach[src]['obs']:
            need(o in M.mach[tgt]['obs'], 'observer %s missing in target' % o)
            need(M.obs(src, o, x) is not None and M.obs(src, o, x) == M.obs(tgt, o, y), 'observer %s differs on (%s,%s)' % (o, x, y))
    match = {}
    for m in fields(field(cert, 'Matches') or ['Matches'], 'Match'):
        match[(field(m, 'Pair')[1], field(m, 'Pair')[2], field(m, 'Action')[1], field(m, 'Step')[1])] = field(m, 'To')[1]
    used = 0
    for (x, y) in pairs:
        for a in M.mach[src]['act']:
            need(a in M.mach[tgt]['act'], 'action %s missing in target' % a)
            for x2 in M.img(src, a, x):
                k = (x, y, a, x2); need(k in match, 'no Match for %s -%s-> %s from %s' % (x, a, x2, y)); used += 1
                y2 = match[k]
                need(y2 in M.img(tgt, a, y), 'Match %s -%s-> %s is not a target move' % (y, a, y2))
                need((x2, y2) in pairs, 'Match leads to unrelated pair (%s,%s)' % (x2, y2))
    need(used == len(match), 'certificate lists Matches for moves that do not exist')
    cov = {(c[1], c[2]) for c in fields(field(cert, 'Coverage') or ['Coverage'], 'Covers')}
    need(cov <= pairs, 'Coverage uses unrelated pairs')
    # A simulation relation needs no coverage (the empty relation is a simulation:
    # fixture excerpt simulation-scope).  Coverage of the initial states is a
    # premise of SafetyTransfer only, so it is enforced only when Init is given.
    if init is not None:
        for x in init:
            need(any(c[0] == x for c in cov), 'initial state %s not covered' % x)
    return pairs, src, tgt

def check_safety(M, req, cert):
    init = [s for s in field(req, 'Init')[1:]]
    need(field(cert, 'Via')[1] == field(req, 'Via')[1], 'Via differs from the request')
    need(field(field(cert, 'Certificate'), 'Relation')[1] == field(req, 'Via')[1], 'certificate Relation is not the Via simulation')   # review 2 F7
    pairs, src, tgt = check_simulation(M, field(cert, 'Certificate'), init)
    need(req[1] == tgt, 'CheckSafety subject is not the simulation target')
    reach = {y for (x, y) in pairs if x in init}; todo = list(reach)
    while todo:
        y = todo.pop()
        for a in M.mach[tgt]['act']:
            for y2 in M.img(tgt, a, y):
                if y2 not in reach: reach.add(y2); todo.append(y2)
    need(reach == set(field(cert, 'Reachable')[1:]), 'Reachable differs from the recomputed closure')
    p = field(req, 'Never')[1]
    if head(p) == 'Shows':
        need(all(M.obs(tgt, p[1], y) != p[2] for y in reach), 'a reachable target state shows %s %s' % (p[1], p[2]))
        return 'Never Shows replayed'
    if head(p) == 'EnterFrom':   # never enter state p[1] from a state outside p[2]
        # (EnterFrom T X): a move into T from a state y != T satisfying X is forbidden.
        X = p[2]
        sat = lambda y: (y not in X[1:]) if head(X) == 'Not' else (y in (X if isinstance(X, list) else [X]))
        for y in reach:
            if y == p[1]: continue   # staying in T is not entering it
            for a in M.mach[tgt]['act']:
                if p[1] in M.img(tgt, a, y): need(not sat(y), 'reachable %s -%s-> %s violates EnterFrom' % (y, a, p[1]))
        return 'Never EnterFrom replayed'
    if head(p) == 'ReachWithin':   # never reach state p[1] within p[2] steps of a related initial state
        k = int(p[2]); need(k >= 0, 'ReachWithin bound is not a natural number')
        dep = {y: 0 for (x, y) in pairs if x in init}; fr = list(dep)
        while fr:
            nx = []
            for y in fr:
                for a in M.mach[tgt]['act']:
                    for y2 in M.img(tgt, a, y):
                        if y2 not in dep: dep[y2] = dep[y] + 1; nx.append(y2)
            fr = nx
        need(not (p[1] in dep and dep[p[1]] <= k), 'target state %s is reached in %s steps, within %d' % (p[1], dep.get(p[1]), k))
        return 'Never ReachWithin replayed'
    fail('property %s has no replay rule; it must not claim Replayed True (listed open)' % head(p))

def check_unmatched(M, sname, w):
    src, tgt, _ = M.sim[sname]; pairs = M.rel(sname)
    x, y = field(w, 'Pair')[1:3]; a = field(w, 'Action')[1]; x2 = field(w, 'Step')[1]
    need((x, y) in pairs, 'witness pair is not related'); need(x2 in M.img(src, a, x), 'witness move is not a source move')
    need(not any((x2, y2) in pairs for y2 in M.img(tgt, a, y)), 'witness move does have a match')

def check_exactness(M, rname, w):
    of, enc = M.rep[rname]; e = lambda s: next(iter(M.map[enc][s]))
    s1, s2 = field(w, 'States')[1:3]; a = field(w, 'Action')[1]; cs = fields(w, 'Codes')
    need(e(s1) == e(s2), 'states do not share a code')
    c1 = {e(t) for t in M.img(of, a, s1)}; c2 = {e(t) for t in M.img(of, a, s2)}
    need(c1 == set(cs[0][1:]) and c2 == set(cs[1][1:]) and c1 != c2, 'successor codes do not match the witness')

def rat(t): return Fraction(int(t[1]), int(t[2]))
def check_probability(M, req, res):
    m = req[1]; d = {field(req, 'From')[1]: Fraction(1)}
    for a in field(req, 'After')[1][1:]:
        nd = {}
        for s, p in d.items():
            im = sorted(M.img(m, a, s)); need(im, 'blocked move')
            for t in im: nd[t] = nd.get(t, 0) + p / len(im)
        d = nd
    ev = field(res, 'Evidence'); dist = {x[0]: rat(x[1]) for x in field(ev, 'Distribution')[1:]}
    need(dist == d, 'Distribution differs from the uniform-scheduler recomputation')
    e = field(req, 'Event')[1]; need(head(e) == 'Shows', 'event form not replayable')
    pv = sum((p for s, p in d.items() if M.obs(m, e[1], s) == e[2]), Fraction(0))
    need(rat(field(field(res, 'Value'), 'Probability')[1]) == pv, 'Probability value differs (%s)' % pv)

def check_outcomes(M, req, res):
    m = req[1]; cur = {field(req, 'From')[1]}
    for a in field(req, 'After')[1][1:]:
        nxt = set()
        for x in cur: nxt |= M.img(m, a, x)
        cur = nxt
    ev = field(res, 'Evidence')
    need(field(ev, 'Word')[1:] == field(req, 'After')[1][1:], 'Word differs from the request')
    need(set(field(ev, 'Reached')[1:]) == cur, 'Reached differs from the recomputed successor set')
    o = field(req, 'Observe')[1]
    need({M.obs(m, o, x) for x in cur} == set(field(field(res, 'Value'), 'OutcomeSet')[1:]), 'OutcomeSet differs')

def check_obsmismatch(M, sname, w):
    # (ObserverMismatch (Pair x y) (Observer o)): x, y related and o does not show one equal value on both
    src, tgt, _ = M.sim[sname]
    x, y = field(w, 'Pair')[1:3]; o = field(w, 'Observer')[1]
    need((x, y) in M.rel(sname), 'witness pair is not related')
    need(o in M.mach[src]['obs'] and o in M.mach[tgt]['obs'], 'witness observer is not shared by source and target')
    vx, vy = M.obs(src, o, x), M.obs(tgt, o, y)
    need(vx is None or vy is None or vx != vy, 'observer %s agrees on (%s,%s)' % (o, x, y))

def check_concrete(M, req, w):
    # (ConcreteCounterexample (Path s0 (Step a s1) ..)): a run of the Via source from Init that
    # violates the property pulled back along the relation (target sets X become the source
    # states all of whose related target states lie in X)
    sname = field(req, 'Via')[1]; src, tgt, _ = M.sim[sname]; R = M.rel(sname)
    need(req[1] == tgt, 'CheckSafety subject is not the simulation target')
    init = set(field(req, 'Init')[1:]); path = field(w, 'Path')
    st = [path[1]] + [s[2] for s in path[2:]]; ac = [None] + [s[1] for s in path[2:]]
    need(all(head(s) == 'Step' and len(s) == 3 for s in path[2:]), 'path steps are not (Step a s)')
    need(st[0] in init, 'path does not start in Init')
    for i in range(1, len(st)):
        need(ac[i] in M.mach[src]['act'] and st[i] in M.img(src, ac[i], st[i - 1]), 'path step %s -%s-> %s is not a source move' % (st[i - 1], ac[i], st[i]))
    def down(T):
        T = set(T); xs = {x for (x, y) in R}
        return {x for x in xs if {y for (x1, y) in R if x1 == x} <= T}
    p = field(req, 'Never')[1]
    if head(p) == 'Shows':
        need(M.obs(src, p[1], st[-1]) == p[2], 'last state does not show %s %s' % (p[1], p[2]))
    elif head(p) == 'EnterFrom':
        X = down([p[1]]); Y = down(p[2][1:]) if head(p[2]) == 'Not' else None
        need(Y is not None and len(st) >= 2, 'EnterFrom form not replayable')
        need(st[-1] in X and st[-2] not in X and st[-2] not in Y, 'last step does not enter the pulled-back set from outside')
    elif head(p) == 'ReachWithin':
        need(st[-1] in down([p[1]]) and len(st) - 1 <= int(p[2]), 'path does not reach the pulled-back set within %s steps' % p[2])
    else: fail('property %s has no concrete replay rule' % head(p))


# ---- m5-rest: bisimulation rows (BehavioralTolerance / CheckBehavioral on Profile Nondeterministic) ----
def coarsest_bisim(M, m):
    """Independent naive refinement: start from observer image sets, split by action block-sets."""
    S = M.states(m); ob = M.mach[m]['obs']; ac = M.mach[m]['act']
    key = {x: tuple(tuple(sorted(M.map[ob[o]].get(x, set()))) for o in sorted(ob)) for x in S}
    while True:
        ids = {k: i for i, k in enumerate(sorted(set(key.values()), key=repr))}; blk = {x: ids[key[x]] for x in S}
        nk = {x: (blk[x],) + tuple(tuple(sorted({blk[y] for y in M.map[ac[a]].get(x, set())})) for a in sorted(ac)) for x in S}
        if len(set(nk.values())) == len(set(key.values())): return blk
        key = nk

def check_partition(M, m, part, exact):
    S = M.states(m); seen = [x for b in part[1:] for x in b[1:]]
    need(sorted(seen) == sorted(S) and len(seen) == len(set(seen)), 'Partition does not cover the states of %s exactly once' % m)
    blk = {x: i for i, b in enumerate(part[1:]) for x in b[1:]}; ob = M.mach[m]['obs']; ac = M.mach[m]['act']
    for x in S:
        for y in S:
            if blk[x] != blk[y]: continue
            for o in ob: need(M.map[ob[o]].get(x, set()) == M.map[ob[o]].get(y, set()), 'block {%s,%s} differs on observer %s' % (x, y, o))
            for a in ac: need({blk[z] for z in M.map[ac[a]].get(x, set())} == {blk[z] for z in M.map[ac[a]].get(y, set())}, 'block {%s,%s} is not stable under %s' % (x, y, a))
    if exact:
        ref = coarsest_bisim(M, m)
        for x in S:
            for y in S: need((blk[x] == blk[y]) == (ref[x] == ref[y]), 'Partition is not the coarsest bisimulation (%s,%s)' % (x, y))
    return blk

def rat(t):
    from fractions import Fraction
    if isinstance(t, list) and head(t) == 'Rat': return Fraction(int(str(t[1])), int(str(t[2])))
    if t == 'True': return Fraction(1)
    if t == 'False': return Fraction(0)
    return Fraction(str(t))

def req_disc(req):
    from fractions import Fraction
    d = field(req, 'Discount'); return rat(d[1]) if d else Fraction(1)

def eval_formula(M, m, fg, g):
    """Exact evaluation of a test graph: Indicator 0/1, Not 1-v, And/Min (empty = 1), Sub max(0, v-r),
    Diamond a k [g'] = g' * max over a-successors (0 if none); g' must equal the request discount."""
    from fractions import Fraction
    import sys; sys.setrecursionlimit(100000)
    S = M.states(m); nodes = {str(n[1]): n[2] for n in fields(fg, 'Node')}; memo = {}
    def val(k):
        k = str(k)
        if k in memo: return memo[k]
        need(k in nodes, 'Formula node %s missing' % k); b = nodes[k]; h = head(b)
        kids = b[1:] if h in ('And', 'Min', 'Not') else [b[1]] if h == 'Sub' else [b[2]] if h == 'Diamond' else []
        for c in kids: need(int(str(c)) < int(k), 'Formula node %s refers forward to %s' % (k, c))
        if h == 'Indicator': r = {y: Fraction(int(b[2] in M.map[M.mach[m]['obs'][b[1]]].get(y, set()))) for y in S}
        elif h == 'Not': c = val(b[1]); r = {y: 1 - c[y] for y in S}
        elif h in ('And', 'Min'):
            cs = [val(c) for c in b[1:]]; r = {y: min([c[y] for c in cs], default=Fraction(1)) for y in S}
        elif h == 'Sub': c = val(b[1]); t = rat(b[2]); r = {y: max(Fraction(0), c[y] - t) for y in S}
        elif h == 'Diamond':
            gg = rat(b[3]) if len(b) > 3 else Fraction(1)
            need(gg == g, 'Diamond discount %s differs from the request discount %s' % (gg, g))
            c = val(b[2]); r = {y: gg * max([c[z] for z in M.img(m, b[1], y)], default=Fraction(0)) for y in S}
        else: raise AssertionError('unknown formula node %s' % h)
        memo[k] = r; return r
    return val(field(fg, 'Root')[1])

def check_modal(M, req, w, g=None):
    from fractions import Fraction
    g = Fraction(1) if g is None else g
    m, enc = M.rep[req[1]]; pr = field(w, 'Pair'); x, z = pr[1], pr[2]
    need(M.map[enc].get(x) == M.map[enc].get(z), 'Pair %s %s does not share a code' % (x, z))
    v = eval_formula(M, m, field(w, 'Formula'), g)
    need(v[x] == rat(field(w, 'Left')[1]) and v[z] == rat(field(w, 'Right')[1]), 'Formula does not evaluate to Left/Right at %s, %s' % (x, z))
    need(v[x] != v[z], 'Formula does not distinguish %s and %s' % (x, z))
    return abs(v[x] - v[z])

def check_haus(M, req, ev):
    """Upper certificate (Prop 4.10(3)): kernel layers, observer rule, one-side-empty rule (K >= g),
    forward/backward matchings per pair and action. Returns (lower from tests, upper or None)."""
    from fractions import Fraction
    m, enc = M.rep[req[1]]; S = M.states(m); ob = M.mach[m]['obs']; ac = M.mach[m]['act']; g = req_disc(req)
    hz = field(req, 'Horizon'); h = int(str(hz[1][1])) if hz and isinstance(hz[1], list) else None
    same = [(x, z) for i, x in enumerate(S) for z in S[i + 1:] if M.map[enc].get(x) == M.map[enc].get(z)]
    lo = max([check_modal(M, req, w, g) for w in find_all(ev, 'ModalTestWitness')], default=Fraction(0)); up = None
    def kern(layer):
        K = {}
        for p in fields(field(layer, 'Kernel'), 'P'): v = rat(p[3]); K[(p[1], p[2])] = v; K[(p[2], p[1])] = v
        return lambda x, y: Fraction(0) if x == y else K.get((x, y), Fraction(0))
    for c in [c for c in fields(ev, 'Certificate') if field(c, 'Kind')[1] in ('HausdorffPrefixpoint', 'HausdorffLayers')]:
        need(rat(field(c, 'Discount')[1]) == g, 'certificate Discount differs from the request')
        ch = field(c, 'Horizon')[1]; kd = field(c, 'Kind')[1]
        need((h is None and ch == 'AllFiniteWords' and kd == 'HausdorffPrefixpoint') or (h is not None and isinstance(ch, list) and int(str(ch[1])) == h and kd == 'HausdorffLayers'), 'certificate Horizon/Kind differs from the request')
        layers = fields(c, 'Layer'); need(len(layers) == (1 if h is None else h + 1), 'wrong number of kernel layers')
        prev = None
        for li, L in enumerate(layers):
            need(int(str(L[1])) == li, 'layer index %s out of order' % L[1])
            K = kern(L); Kp = K if h is None else prev
            mt = {(e[1], e[2], e[3]): e for e in fields(field(L, 'Matchings'), 'Match')}
            for x in S:
                for y in S:
                    if x == y: continue
                    k = K(x, y)
                    if any(M.map[ob[o]].get(x) != M.map[ob[o]].get(y) for o in ob): need(k >= 1, 'K(%s,%s) < 1 but observers differ' % (x, y)); continue
                    if Kp is None or k >= 1: continue
                    for a in ac:
                        X2, Y2 = M.img(m, a, x), M.img(m, a, y)
                        if not X2 and not Y2: continue
                        if not X2 or not Y2: need(k >= g, 'one side of (%s,%s) has no %s-successor but K < g' % (x, y, a)); continue
                        e = mt.get((x, y, a)) or mt.get((y, x, a)); need(e is not None, 'no matching for (%s,%s,%s)' % (x, y, a))
                        f = {r[0]: r[1] for r in field(e, 'Fwd')[1:]}; bw = {r[0]: r[1] for r in field(e, 'Bwd')[1:]}
                        if e[1] != x: f, bw = bw, f
                        need(set(f) == X2 and all(f[u] in Y2 for u in f), 'Fwd matching of (%s,%s,%s) is not a map succ->succ' % (x, y, a))
                        need(set(bw) == Y2 and all(bw[v] in X2 for v in bw), 'Bwd matching of (%s,%s,%s) is not a map succ->succ' % (x, y, a))
                        need(k >= g * max([Kp(u, f[u]) for u in f] + [Kp(bw[v], v) for v in bw]), 'kernel is not a prefixpoint at (%s,%s,%s)' % (x, y, a))
            prev = K
        up = max([prev(x, z) for x, z in same], default=Fraction(0))
    return lo, up

# ---- m5-rest: may-trace rows (CheckTrace on Profile Nondeterministic) ----
def obs_vectors(M, m):
    import itertools
    ob = M.mach[m]['obs']; names = sorted(ob); vs = set()
    for x in M.states(m):
        for v in itertools.product(*[sorted(M.map[ob[o]].get(x, set())) for o in names]): vs.add(tuple(zip(names, v)))
    return sorted(vs)

def obs_filter(M, m, X, vec):
    ob = M.mach[m]['obs']
    return {x for x in X if all(v in M.map[ob[o]].get(x, set()) for o, v in vec)}

def post(M, m, a, X):
    r = set()
    for x in X: r |= M.img(m, a, x)
    return r

def check_maytrace(M, req, w):
    m, enc = M.rep[req[1]]; pr = field(w, 'Pair'); x, z = pr[1], pr[2]
    need(M.map[enc].get(x) == M.map[enc].get(z), 'Pair %s %s does not share a code' % (x, z))
    tr = field(w, 'Trace')[1:]; word = field(w, 'Word')[1:]
    need(len(tr) % 2 == 1 and [t for t in tr[1::2]] == list(word), 'Trace does not alternate Shows/action along Word')
    ob = M.mach[m]['obs']; X, Z = {x}, {z}
    for i, t in enumerate(tr):
        if i % 2:
            need(t in M.mach[m]['act'], 'unknown action %s' % t); X, Z = post(M, m, t, X), post(M, m, t, Z); continue
        need(head(t) == 'Shows', 'Trace entry %d is not (Shows ..)' % i)
        vec = [(o[0], o[1]) for o in t[1:]]
        need(sorted(o for o, _ in vec) == sorted(ob), 'Shows does not name every observer exactly once')
        X, Z = obs_filter(M, m, X, vec), obs_filter(M, m, Z, vec)
    need(bool(X) == (field(w, 'Left')[1] == 'True') and bool(Z) == (field(w, 'Right')[1] == 'True'), 'Trace possibility does not match Left/Right')
    need(bool(X) != bool(Z), 'Trace does not distinguish %s and %s' % (x, z))

def check_maytrace_cert(M, req, c):
    m, enc = M.rep[req[1]]; S = M.states(m)
    hz = field(req, 'Horizon'); h = int(str(hz[1][1])) if hz and isinstance(hz[1], list) else None
    ch = field(c, 'Horizon')[1]
    need((h is None and ch == 'AllFiniteWords') or (h is not None and isinstance(ch, list) and int(str(ch[1])) == h), 'certificate Horizon differs from the request')
    P = {}
    for e in fields(field(c, 'Pairs'), 'P'):
        k = (frozenset(field(e, 'Left')[1:]), frozenset(field(e, 'Right')[1:])); P[k] = min(P.get(k, 10 ** 9), int(str(e[1])))
    def has(X, Z, d):
        for k in ((frozenset(X), frozenset(Z)), (frozenset(Z), frozenset(X))):
            if k in P and (h is None or P[k] <= d): return True
        return False
    for i, x in enumerate(S):
        for zz in S[i + 1:]:
            if M.map[enc].get(x) == M.map[enc].get(zz): need(has({x}, {zz}, 0), 'same-code pair %s %s missing from certificate' % (x, zz))
    V = obs_vectors(M, m)
    for (X, Z), d in P.items():
        for vec in V:
            X1, Z1 = obs_filter(M, m, X, vec), obs_filter(M, m, Z, vec)
            if not X1 and not Z1: continue
            need(X1 and Z1, 'certificate pair %s/%s splits on observation %s' % (sorted(X), sorted(Z), vec))
            if h is not None and d >= h: continue
            for a in M.mach[m]['act']:
                X2, Z2 = post(M, m, a, X1), post(M, m, a, Z1)
                if X2 or Z2: need(has(X2, Z2, d + 1), 'certificate not closed: %s/%s missing' % (sorted(X2), sorted(Z2)))

def replay_line(M, req, res):
    st = field(res, 'Status')[1]; ev = field(res, 'Evidence') or ['Evidence']; h = head(req)
    did = []
    for w in find_all(ev, 'UnmatchedMove'):
        check_unmatched(M, req[1] if h == 'CheckSimulation' else field(req, 'Via')[1], w); did.append('UnmatchedMove')
    for w in find_all(ev, 'ObserverMismatch'):
        check_obsmismatch(M, req[1] if h == 'CheckSimulation' else field(req, 'Via')[1], w); did.append('ObserverMismatch')
    for w in find_all(ev, 'ConcreteCounterexample'):
        need(h == 'CheckSafety', 'ConcreteCounterexample outside CheckSafety'); check_concrete(M, req, w); did.append('ConcreteCounterexample')
    for w in find_all(ev, 'ExactnessFailure'): check_exactness(M, req[1], w); did.append('ExactnessFailure')
    for c in [c for c in fields(ev, 'Certificate')]:
        k = field(c, 'Kind')[1]
        if k == 'Simulation' and h == 'CheckSimulation':
            need(field(c, 'Relation')[1] == req[1], 'certificate Relation %s is not the requested simulation %s' % (field(c, 'Relation')[1], req[1]))   # review 2 F7
            check_simulation(M, c, None); did.append('Simulation')
        elif k == 'SafetyTransfer' and h == 'CheckSafety': did.append('SafetyTransfer: ' + check_safety(M, req, c))
    if h == 'OutcomeProbability' and st == 'Checked': check_probability(M, req, res); did.append('Probability')
    if h == 'Outcomes' and st == 'Checked': check_outcomes(M, req, res); did.append('Outcomes')
    for w in find_all(ev, 'ModalTestWitness'):
        need(h in ('CheckBehavioral', 'MeasureBehavioral'), 'ModalTestWitness outside CheckBehavioral/MeasureBehavioral'); check_modal(M, req, w, req_disc(req)); did.append('ModalTestWitness')
    bd = field(field(res, 'Value') or ['Value'], 'BehavioralDefect')
    if h in ('CheckBehavioral', 'MeasureBehavioral') and bd and st in ('Checked', 'Refuted'):
        lo, up = check_haus(M, req, ev); dv = rat(bd[1])
        need(lo == dv, 'lower test gives %s, claimed BehavioralDefect %s' % (lo, dv))
        b = rat(field(req, 'Within')[1]) if field(req, 'Within') else 0
        if st == 'Checked': need(up is not None and up == dv, 'upper certificate gives %s, claimed %s' % (up, dv)); need(h == 'MeasureBehavioral' or dv <= b, 'Checked but defect exceeds Within')
        else: need(h == 'CheckBehavioral' and lo > b, 'Refuted but the lower test does not exceed Within')
        if h == 'CheckBehavioral': need((field(field(res, 'Value'), 'WithinBound')[1] == 'True') == (st == 'Checked'), 'WithinBound disagrees with status')
        did.append('Hausdorff')
    if h == 'BehavioralTolerance' and st == 'Checked':
        bs = field(field(res, 'Value'), 'Bisimulation'); check_partition(M, req[1], field(bs, 'Partition'), True)
        need(int(str(field(bs, 'Classes')[1])) == len(field(bs, 'Partition')) - 1, 'Classes count wrong'); did.append('Bisimulation')
    if h == 'CheckBehavioral' and st == 'Checked' and not bd:
        c = [c for c in fields(ev, 'Certificate') if field(c, 'Kind')[1] == 'Bisimulation'][0]; m, enc = M.rep[req[1]]
        blk = check_partition(M, m, field(c, 'Partition'), False)
        for x in M.states(m):
            for y in M.states(m): need(M.map[enc].get(x) != M.map[enc].get(y) or blk[x] == blk[y], 'same-code pair %s %s split by the certificate' % (x, y))
        did.append('BisimulationCertificate')
    for w in find_all(ev, 'MayTraceWitness'):
        need(h == 'CheckTrace', 'MayTraceWitness outside CheckTrace'); check_maytrace(M, req, w); did.append('MayTraceWitness')
    if h == 'CheckTrace' and st == 'Checked':
        c = [c for c in fields(ev, 'Certificate') if field(c, 'Kind')[1] == 'MayTraceSubsetPairs'][0]
        check_maytrace_cert(M, req, c); did.append('MayTraceSubsetPairs')
    return st, did

def main(argv):
    bad = 0; n = 0
    for mf, of in zip(argv[0::2], argv[1::2]):
        mods = {t[1]: Module(t) for t in read_all(re.sub(r'(?m)^\s*;.*$', '', open(mf, encoding='utf-8').read())) if head(t) == 'DC.Module'}
        for line in open(of, encoding='utf-8'):
            if ' => ' not in line: continue
            lhs, rhs = line.split(' => ', 1); lt = read_all(lhs); res = read_all(rhs)[0]
            bm = field(field(res, 'Binding') or ['Binding'], 'Module')
            M = mods.get(bm[1] if bm else lt[0]); req = lt[1] if len(lt) > 1 else None
            if not isinstance(req, list):   # named claim row: 'Mod Name => (Result .. (Claim REQ ..))'
                cl = field(res, 'Claim'); req = cl[1] if cl and len(cl) > 1 else None
            if M is None and len(mods) == 1: M = next(iter(mods.values()))
            asr = field(res, 'Assurance') or ['Assurance']
            claimed = (field(asr, 'Policy') or [0, 0])[1] == 'M5-NondeterministicReplay' and (field(asr, 'Replayed') or [0, 0])[1] == 'True'
            if not claimed or M is None or not isinstance(req, list): continue
            n += 1; tag = '%s: %s' % (of.split('/')[-1], ' '.join(map(str, req[:2])))
            try:
                st, did = replay_line(M, req, res)
                if not did: bad += 1; print('UNCHECKED %s [%s] claims Replayed True; no evidence this replayer can check' % (tag, st))
                else: print('ACCEPT    %s [%s] %s' % (tag, st, '; '.join(did)))
            except (AssertionError, KeyError, IndexError, TypeError, StopIteration) as e:
                bad += 1; print('REJECT    %s: %s' % (tag, e or type(e).__name__))
    print('replay_m5: %d rows, %d not accepted -> %s' % (n, bad, 'PASS' if bad == 0 and n else 'FAIL'))
    return 1 if bad or not n else 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
