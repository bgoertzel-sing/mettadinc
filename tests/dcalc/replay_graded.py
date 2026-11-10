#!/usr/bin/env python3
"""M2 graded replay (t-2026-11-10-mettadinc-m2-v2).

Recomputes every graded result from the module source alone, with exact
fractions, and checks the producer's envelope, value, witnesses and
certificates against that recomputation.  It shares only the s-expression
reader with replay.py; the graded semantics (spec Def 4.1, Thm 4.2(5),
Def 4.4) are written again here, independently of src/dcalc."""
import hashlib
from fractions import Fraction as Q
from replay import show, find, key, match, ev

class GFail(Exception): pass
def need(c, msg):
    if not c: raise GFail(msg)

VALUE_TYPES = ('Rational01', 'Rational')
GRADED_HEADS = ('Defects', 'MeasureUpdates', 'MeasureBehavioral', 'CheckBehavioral', 'MeasureTrace', 'CheckTrace')
REP_HEADS = ('MeasureNow', 'CheckNow', 'CheckUpdates')
KN = ('Current', 'Update', 'Behavioral')
HEADS = ['Status', 'Claim', 'Binding', 'Scope', 'Value', 'Evidence', 'Assumptions', 'Assurance']

def rat(x):
    if isinstance(x, list) and len(x) == 3 and x[0] == 'Rat': return Q(int(x[1]), int(x[2]))
    if isinstance(x, str): return Q(x)
    raise GFail('not a rational: %s' % show(x))

class GModule:
    def __init__(self, form):
        self.name = form[1]; self.digest = hashlib.sha256(show(form).encode()).hexdigest()
        pf = find(form, 'Profile'); self.profile = pf[1] if pf and len(pf) == 2 else 'Crisp'
        self.form = form
        self.car, self.map, self.tol, self.mach, self.rep = {}, {}, {}, {}, {}
        self.meas, self.der = {}, {}
        self.sub = {}          # Reach carrier -> parent carrier
        self.uses = set(x for d in form[2:] if isinstance(d, list) and d and d[0] == 'Use' for x in d[1:])
        decls = [d for d in form[2:] if isinstance(d, list) and d]
        for h, fn in (('Carrier', self.carrier), ('Tolerance', self.toldecl), ('Map', self.mapdecl),
                      ('Machine', self.machine), ('Representation', self.repdecl),
                      ('Measure', self.measdecl), ('Derive', self.derdecl)):
            for d in decls:
                if d[0] != h: continue
                try: fn(d)
                except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError, GFail): pass
        # M2: Reach carriers need their machine, so they come after the first machine pass;
        # machines and representations on them are admitted in a second pass.
        for h, fn in (('Carrier', self.reach), ('Machine', self.machine), ('Representation', self.repdecl)):
            for d in decls:
                if d[0] != h or (h == 'Machine' and d[1] in self.mach) or (h == 'Representation' and d[1] in self.rep): continue
                try: fn(d)
                except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError, GFail): pass

    def carrier(self, d):
        b = d[3]
        if b[0] == 'Enum': self.car[d[1]] = list(b[1:])
        elif b[0] == 'Product':
            els = [['Tuple']]
            for f in b[1:]: els = [e + [v] for e in els for v in self.car[f]]
            self.car[d[1]] = els

    def reach(self, d):
        b = d[3]
        if b[0] != 'Reach' or self.profile != 'Graded' or d[1] in self.car: return
        mc = self.mach[b[1]]; need(b[2][0] == 'From', 'Reach needs From')
        st = self.car[mc['states']]; keys = [key(x) for x in st]; seen = set(); todo = []
        for x in b[2][1:]: need(key(x) in keys, 'Reach start off the states'); seen.add(key(x)); todo.append(key(x))
        while todo:
            x = todo.pop()
            for _, mp in mc['act']:
                y = self.map[mp]['f'][x]
                if y not in seen: seen.add(y); todo.append(y)
        self.car[d[1]] = [x for x in st if key(x) in seen]; self.sub[d[1]] = mc['states']

    def on(self, mp, states):
        """A map usable on the states: declared on them, or on the parent of a Reach carrier (by restriction)."""
        return self.map[mp]['from'] == states or self.sub.get(states) == self.map[mp]['from']

    def toldecl(self, d):
        on, b = d[2][1], d[3]
        t = {'on': on, 'kind': b[0]}
        if b[0] == 'SymmetricTable':
            diag, k = Q(1), {}
            for e in b[1:]:
                if e[0] == 'Diagonal': diag = rat(e[1]); continue
                a, c, v = key(e[0]), key(e[1]), rat(e[2]); k[a, c] = k[c, a] = v
            els = [key(x) for x in self.car[on]]
            for a in els: k[a, a] = diag
            if any((a, c) not in k for a in els for c in els): return
            t['k'] = k
        elif b[0] not in ('Trivial', 'Discrete', 'OneMinusAbsoluteDifference') or len(b) != 1: return
        self.tol[d[1]] = t

    def mapdecl(self, d):
        fr, to, body = d[2][1], d[3][1], d[4]
        if isinstance(fr, list):                    # inline (Product A B): a carrier named by its printed form
            need(self.profile == 'Graded' and fr[0] == 'Product' and len(fr) == 3, 'inline source outside M2')
            k_ = show(fr)
            if k_ not in self.car: self.car[k_] = [['Tuple', a, b] for a in self.car[fr[1]] for b in self.car[fr[2]]]
            fr = k_
        src, val = self.car[fr], to in VALUE_TYPES
        f = {}
        if body[0] == 'Table':
            for k_, v in body[1:]: f[key(k_)] = v
        elif body[0] == 'Cases':
            for s in src:
                for pat, rhs in body[1:]:
                    env = {}
                    if match(pat, s, env): f[key(s)] = ev(rhs, env); break
        elif body[0] == 'Body' and len(body) == 3 and self.profile == 'Graded' and 'FiniteSets' in self.uses:
            var = body[1][0]
            for s_ in src: f[key(s_)] = set_eval(body[2], var, s_)
        else: return
        need(all(key(s) in f for s in src), 'map %s not total' % d[1])
        if val:
            f = {k_: rat(v) for k_, v in f.items()}
            need(all(v >= 0 and (to != 'Rational01' or v <= 1) for v in f.values()), 'value out of range')
        else:
            dst = set(key(x) for x in self.car[to]); f = {k_: key(v) for k_, v in f.items()}
            need(all(v in dst for v in f.values()), 'map %s leaves its carrier' % d[1])
        self.map[d[1]] = {'from': fr, 'to': to, 'f': f}

    def machine(self, d):
        m = {'states': find(d, 'States')[1], 'obs': [], 'act': []}
        for x in d[2:]:
            if x[0] == 'States': continue
            if x[0] == 'Observe':
                t = None
                if len(x) == 4: need(x[3][0] == 'Values' and x[3][1] in self.tol, 'bad Values'); t = x[3][1]
                else: need(len(x) == 3 and isinstance(x[2], str), 'bad Observe')
                need(self.on(x[2], m['states']), 'observation off the states')
                need(t is None or self.tol[t]['on'] == self.map[x[2]]['to'], 'tolerance off the observation')
                m['obs'].append((x[1], x[2], t))
            elif x[0] == 'Action':
                par = self.sub.get(m['states'])
                need(len(x) == 3 and self.on(x[2], m['states']) and self.map[x[2]]['to'] in (m['states'], par), 'bad Action')
                if par and self.map[x[2]]['to'] == par:
                    inside = set(key(s_) for s_ in self.car[m['states']])
                    need(all(self.map[x[2]]['f'][k_] in inside for k_ in inside), 'update leaves carrier %s' % m['states'])
                m['act'].append((x[1], x[2]))
            elif x[0] == 'Merge' and self.profile == 'Graded':
                mp = self.map[x[2]]; st = self.car[m['states']]
                need(self.car[mp['from']] == [['Tuple', a, b] for a in st for b in st] and mp['to'] == m['states'], 'Merge map off (Product S S) -> S')
                m.setdefault('merge', []).append((x[1], x[2]))
            else: return                              # Bag, ...: outside this checker
        self.mach[d[1]] = m

    def measdecl(self, d):
        if len(d) == 4 and d[3] == ['Uniform'] and d[2][0] == 'On' and d[2][1] in self.car: self.meas[d[1]] = d[2][1]

    def derdecl(self, d):
        if len(d) == 3: self.der[d[1]] = d[2]

    def repdecl(self, d):
        co, mach, e = find(d, 'Codes'), find(d, 'Of')[1], find(d, 'Encode')[1]
        need(mach in self.mach and self.on(e, self.mach[mach]['states']), 'bad representation')
        t = co[1] if co else None
        need(t is None or (t in self.tol and self.tol[t]['on'] == self.map[e]['to']), 'bad Codes')
        self.rep[d[1]] = {'machine': mach, 'encode': e, 'tol': t}

RECEIPTS = {'Empty': frozenset(), 'UOnly': frozenset('u'), 'VOnly': frozenset('v'), 'Both': frozenset('uv')}
def set_eval(b, var, val):
    """FiniteSets Body: the variable, literals, GetTuple, ReceiptUnion (union of receipt sets, spec Example 4.3)."""
    if isinstance(b, str): return val if b == var else b
    if b[0] == 'GetTuple': t = set_eval(b[1], var, val); need(t[0] == 'Tuple', 'GetTuple on a non-tuple'); return t[1 + int(b[2])]
    if b[0] == 'ReceiptUnion':
        u = RECEIPTS[set_eval(b[1], var, val)] | RECEIPTS[set_eval(b[2], var, val)]
        return next(k for k, v in RECEIPTS.items() if v == u)
    raise GFail('Body operator %s outside FiniteSets' % b[0])

def dist(M, t, a, b):
    if t is None: return Q(0) if a == b else Q(1)
    T = M.tol[t]; k = T['kind']
    if k == 'Trivial': return Q(0)
    if k == 'Discrete': return Q(0) if a == b else Q(1)
    if k == 'OneMinusAbsoluteDifference': return abs(a - b)
    return 1 - T['k'][a, b]

def separated(M, t):
    els = sorted(set(M.map[m]['f'][s] for m in M.map for s in M.map[m]['f'] if M.map[m]['to'] == M.tol[t]['on']), key=str) \
        if M.tol[t]['on'] in VALUE_TYPES else [key(x) for x in M.car[M.tol[t]['on']]]
    return all(a == b or dist(M, t, a, b) > 0 for a in els for b in els)

def graded_rep(M, rn):
    r = M.rep.get(rn) if isinstance(rn, str) else None
    if not r: return False
    return any(t for _, _, t in M.mach[r['machine']]['obs']) or bool(M.mach[r['machine']].get('merge')) or (r['tol'] is not None and M.tol[r['tol']]['kind'] != 'Trivial')

KERNEL_HEADS = ('PathClosure', 'Bracket', 'Delta', 'Threshold', 'CheckTransitive')
CRISP_M2_HEADS = ('Refine', 'SamePartition', 'WeakestWithin', 'InduceApprox') + KERNEL_HEADS
def is_graded(M, req):
    if isinstance(req, str) and req in M.der: req = M.der[req]
    if not isinstance(req, list) or not req: return False
    return req[0] in GRADED_HEADS + CRISP_M2_HEADS + ('BehavioralTolerance',) or (req[0] in REP_HEADS + ('InduceExact',) and len(req) >= 2 and graded_rep(M, req[1]))

# ---- part 2: independent recomputation and the replay of one graded result ----
class Ctx:
    def __init__(self, M, rn, g=Q(1), h=None):
        r = M.rep[rn]; mc = M.mach[r['machine']]
        self.M, self.r, self.g, self.h = M, r, g, h
        self.S = [key(s) for s in M.car[mc['states']]]
        self.obs = [(lab, M.map[mp]['f'], t) for lab, mp, t in mc['obs']]
        self.act = [(lab, M.map[mp]['f']) for lab, mp in mc['act']]
        self.raw = {key(s): s for s in M.car[mc['states']]}
        self.merge = [(lab, M.map[mp]['f']) for lab, mp in mc.get('merge', [])]
        e = M.map[r['encode']]['f']; self.e = e
        S = self.S
        self.d0 = {(x, y): max([dist(M, t, f[x], f[y]) for _, f, t in self.obs] or [Q(0)]) for x in S for y in S}
        self.dq = {(x, y): dist(M, r['tol'], e[x], e[y]) for x in S for y in S}
        self.beh = self.iterate(h)
        self.eq = 'Observer' if any(t and not separated(M, t) for _, _, t in self.obs) else 'Literal'

    def mg(self, f, a, b): return key(f[key(['Tuple', self.raw[a], self.raw[b]])])

    def step(self, D):
        return {(x, y): max([self.d0[x, y]] + [self.g * D[f[x], f[y]] for _, f in self.act]) for (x, y) in D}

    def iterate(self, h):
        D = dict(self.d0)                       # Phi(1) = alpha_0: horizon 0
        if h is not None:
            for _ in range(h): D = self.step(D)
            return D
        for _ in range(len(self.S) ** 2 + 2):
            N = self.step(D)
            if N == D: return D
            D = N
        raise GFail('behavioral iteration did not stabilise')

    def defect(self, k):
        S = self.S
        if k == 'Current': return max([max(Q(0), self.d0[x, y] - self.dq[x, y]) for x in S for y in S])
        if k == 'Update':
            act = max([Q(0)] + [max(Q(0), self.dq[f[x], f[y]] - self.dq[x, y]) for _, f in self.act for x in S for y in S])
            return max([act] + [max(Q(0), self.dq[self.mg(f, a, b), self.mg(f, a2, b2)] - max(self.dq[a, a2], self.dq[b, b2]))
                                for _, f in self.merge for a in S for b in S for a2 in S for b2 in S])
        if k == 'Trace':
            # Def 4.4(4), deterministic, discrete value tolerances: the largest undiscounted
            # horizon-h behavioral distance between two states with equal codes.
            return max([Q(0)] + [self.beh[x, y] for x in S for y in S if self.e[x] == self.e[y]])
        return max([max(Q(0), self.beh[x, y] - self.dq[x, y]) for x in S for y in S])

def rs(q): return str(q.numerator) if q.denominator == 1 else '%d/%d' % (q.numerator, q.denominator)
def IV(q): return ['Interval', rs(q), rs(q)]
def _num(x):
    if isinstance(x, Q): return x
    try: return rat(x)
    except (GFail, ValueError, ZeroDivisionError): return None
def same_val(a, b):
    """a: a printed value from the result; b: the recomputed value (a Fraction or a carrier key)."""
    na, nb = _num(a), _num(b)
    if isinstance(b, Q): return na is not None and na == nb
    return key(a) == b

def check_word(C, w, k, d, horizon):
    need(isinstance(w, list) and w[0] == 'WordWitness' and len(w) == 8, 'WordWitness expected')
    P, Cd, W, Qy, L, R, LB = w[1:]
    nK = sum(1 for i, x in enumerate(C.S) if not any(C.d0[y, x] == 0 for y in C.S[:i]))
    need(LB == ['LengthBound', str(len(C.S) - nK)], 'LengthBound differs from n - |X/K_O| = %d' % (len(C.S) - nK))
    need(len(W) - 1 <= len(C.S) - nK, 'witness word longer than n - |X/K_O|')
    need(P[0] == 'Pair' and Cd[0] == 'Codes' and W[0] == 'Word' and Qy[0] == 'Query' and L[0] == 'Left' and R[0] == 'Right', 'malformed WordWitness')
    x, y = key(P[1]), key(P[2]); need(x in C.S and y in C.S, 'witness pair not states')
    need(same_val(Cd[1], C.e[x]) and same_val(Cd[2], C.e[y]), 'witness codes differ from the encoding')
    acts = dict(C.act); a, b = x, y; n = 0
    for st in W[1:]:
        need(st[0] == 'Do' and st[1] in acts, 'witness word names no action'); a, b = acts[st[1]][a], acts[st[1]][b]; n += 1
    need(horizon is None or n <= horizon, 'witness word longer than the horizon')
    if k == 'Current': need(n == 0, 'a current witness has the empty word')
    ob = [o for o in C.obs if o[0] == Qy[1]]; need(ob, 'witness query names no observation')
    lab, f, t = ob[0]
    need(same_val(L[1], f[a]) and same_val(R[1], f[b]), 'witness answers differ from the recomputed answers')
    if k == 'Trace':
        need(C.e[x] == C.e[y], 'a trace witness pair must have equal codes')
        lower = dist(C.M, t, f[a], f[b])
    else: lower = C.g ** n * dist(C.M, t, f[a], f[b]) - C.dq[x, y]
    need(lower == d and d > 0, 'witness bound %s does not attain the defect %s' % (rs(lower), rs(d)))

def check_update_witness(C, w, d):
    if isinstance(w, list) and w and w[0] == 'MergeWitness':
        need(len(w) == 6 and [x[0] for x in w[1:]] == ['Merge', 'Left', 'Right', 'Results', 'Codes'], 'malformed MergeWitness')
        mg = dict(C.merge); need(w[1][1] in mg, 'merge witness names no Merge port'); f = mg[w[1][1]]
        a, b, a2, b2 = key(w[2][1]), key(w[2][2]), key(w[3][1]), key(w[3][2])
        need(all(x in C.S for x in (a, b, a2, b2)), 'merge witness off the states')
        u, v = C.mg(f, a, b), C.mg(f, a2, b2)
        need(key(w[4][1]) == u and key(w[4][2]) == v, 'merge witness results differ from the recomputed merge')
        need(same_val(w[5][1], C.e[u]) and same_val(w[5][2], C.e[v]), 'merge witness codes differ')
        need(C.dq[u, v] - max(C.dq[a, a2], C.dq[b, b2]) == d and d > 0, 'merge witness does not attain the defect')
        return
    need(isinstance(w, list) and w[0] == 'UpdateWitness' and len(w) == 5, 'UpdateWitness expected')
    x, y = key(w[1][1]), key(w[1][2]); acts = dict(C.act)
    need(w[2][0] == 'Do' and w[2][1] in acts, 'update witness names no action'); f = acts[w[2][1]]
    need(same_val(w[3][1], C.e[x]) and same_val(w[3][2], C.e[y]), 'update witness codes differ')
    need(same_val(w[4][1], C.e[f[x]]) and same_val(w[4][2], C.e[f[y]]), 'update witness successors differ')
    need(C.dq[f[x], f[y]] - C.dq[x, y] == d and d > 0, 'update witness does not attain the defect')

def check_kernel(C, c, horizon):
    need(c[0] == 'Certificate', 'certificate expected')
    kd = 'LayeredPrefixpoint' if horizon is not None else 'Prefixpoint'
    need(find(c, 'Kind') == ['Kind', kd], 'certificate kind is not %s' % kd)
    need(rat(find(c, 'Discount')[1]) == C.g, 'certificate discount differs from the request')
    hz = find(c, 'Horizon')[1]
    need((hz == 'Unbounded') if horizon is None else (hz == ['Steps', str(horizon)]), 'certificate horizon differs')
    D = {(x, y): Q(0) for x in C.S for y in C.S}
    for en in find(c, 'Kernel')[1:]:
        x, y, v = key(en[1]), key(en[2]), rat(en[3]); need(x in C.S and y in C.S and x != y, 'kernel entry off the states')
        D[x, y] = D[y, x] = v
    need(all(D[p] >= C.d0[p] for p in D), 'kernel below the seed')
    if horizon is None: need(all(D[p] >= v for p, v in C.step(D).items()), 'kernel is not a prefixpoint')
    need(D == C.beh, 'kernel differs from the recomputed behavioral distance')

# ---- part 3: the envelope and the replay of one graded result ----
def opts(req):
    w, h, g, pol = Q(0), None, Q(1), None
    for f in req[2:]:
        need(isinstance(f, list) and len(f) == 2, 'malformed request field')
        if f[0] == 'Within': w = rat(f[1])
        elif f[0] == 'Horizon': need(f[1][0] == 'Steps', 'Horizon needs Steps'); h = int(f[1][1]); need(h >= 0, 'negative horizon')
        elif f[0] == 'Discount': g = rat(f[1]); need(0 < g <= 1, 'discount outside (0,1]')
        elif f[0] == 'Policies': need(pol is None and f[1] in ('Words', 'ObservationBased'), 'Policies must be Words or ObservationBased'); pol = f[1]
        else: raise GFail('unknown request field %s' % show(f))
    return w, h, g, pol

def envelope_ok(M, req, env, st, C, h, g, pc='None'):
    heads = [x[0] if isinstance(x, list) and x else None for x in env[1:]]
    need(env[0] == 'Result' and heads == HEADS, 'envelope fields %s' % heads)
    need(show(find(env, 'Claim')) == show(['Claim', req, ['Equality', C.eq]]), 'Claim differs from the request and equality')
    r = C.r
    exp_b = ['Binding', ['Module', M.name], ['Digest', ('str', M.digest)],
             ['Subject', ['Representation', req[1]], ['Machine', r['machine']]],
             ['Source', r['machine']], ['Target', M.map[r['encode']]['to']],
             ['Interface', ['Tolerance', r['tol'] if r['tol'] is not None else 'Exact']]]
    need(show(find(env, 'Binding')) == show(exp_b), 'Binding differs from the recomputed binding %s' % show(exp_b))
    exp_s = ['Scope', ['Profile', M.profile], ['Fragment', 'M2-GradedDeterministic'], ['InitialStates', 'AllDeclared'],
             ['ReachableStates', 'AllDeclared'], ['Horizon', 'Unbounded' if h is None else ['Steps', str(h)]],
             ['Discount', rs(g)], ['PolicyClass', pc]]
    need(show(find(env, 'Scope')) == show(exp_s), 'Scope differs from the recomputed scope %s' % show(exp_s))
    need(find(env, 'Assumptions') == ['Assumptions'], 'graded table results carry no assumptions')
    ground = 'Witness' if st == 'Refuted' else 'Replayed'
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M2-ExactReplay'], ['Replayed', 'True'], ['Ground', ground]]),
         'Assurance differs from the recomputed assurance')

def evidence_ok(C, k, d, items, h):
    """items: the evidence entries for one defect kind."""
    if k in ('Behavioral', 'Trace'):
        if d > 0:
            need(len(items) == 2 and items[0][0] == 'Witness', 'a positive %s defect needs a witness and a kernel' % k.lower())
            check_word(C, items[0][1], k, d, h); items = items[1:]
        need(len(items) == 1, 'behavioral evidence must end in one kernel certificate'); check_kernel(C, items[0], h)
        return
    need(len(items) == 1, '%s evidence must be one item' % k)
    it = items[0]
    if d == 0:
        need(show(it) == show(['Certificate', ['Kind', 'Prefixpoint'], ['Checks', k]]), 'zero %s defect needs its certificate' % k)
    elif k == 'Current': need(it[0] == 'Witness', 'current witness expected'); check_word(C, it[1], k, d, 0)
    else: need(it[0] == 'Witness', 'update witness expected'); check_update_witness(C, it[1], d)

def refine(C):
    """P0 = ker q ∩ K_O, then the coarsest stable refinement; labels are block minima."""
    S = C.S; p0 = {}
    for i, x in enumerate(S): p0[x] = next((p0[y] for y in S[:i] if C.d0[y, x] == 0 and C.dq[y, x] == 0), x)
    cls, rounds = dict(p0), 0
    while True:
        sig = {x: (cls[x],) + tuple(cls[f[x]] for _, f in C.act)
                  + tuple(cls[C.mg(f, x, y)] for _, f in C.merge for y in S) + tuple(cls[C.mg(f, y, x)] for _, f in C.merge for y in S) for x in S}; nx = {}
        for i, x in enumerate(S): nx[x] = next((nx[y] for y in S[:i] if sig[y] == sig[x]), x)
        if nx == cls: return p0, cls, rounds
        cls, rounds = nx, rounds + 1

def blocks(raw, S, cls, head):
    return [head] + [['Block'] + [raw[i] for i, x in enumerate(S) if cls[x] == b] for b in S if cls[b] == b]
def weak(S, cls):
    return sum(Q(sum(1 for x in S if cls[x] == b)) ** 2 for b in S if cls[b] == b) / len(S) ** 2

def envelope_gen(M, req, env, st, rn, subj, eq):
    heads = [x[0] if isinstance(x, list) and x else None for x in env[1:]]
    need(env[0] == 'Result' and heads == HEADS, 'envelope fields %s' % heads)
    need(show(find(env, 'Claim')) == show(['Claim', req, ['Equality', eq]]), 'Claim differs from the request')
    r = M.rep[rn]
    exp_b = ['Binding', ['Module', M.name], ['Digest', ('str', M.digest)], subj, ['Source', r['machine']],
             ['Target', M.map[r['encode']]['to']], ['Interface', ['Tolerance', r['tol'] if r['tol'] is not None else 'Exact']]]
    need(show(find(env, 'Binding')) == show(exp_b), 'Binding differs from the recomputed binding %s' % show(exp_b))
    exp_s = ['Scope', ['Profile', M.profile], ['Fragment', 'M2-GradedDeterministic'], ['InitialStates', 'AllDeclared'],
             ['ReachableStates', 'AllDeclared'], ['Horizon', 'Unbounded'], ['Discount', '1'], ['PolicyClass', 'None']]
    need(show(find(env, 'Scope')) == show(exp_s), 'Scope differs from the recomputed scope')
    need(find(env, 'Assumptions') == ['Assumptions'], 'graded table results carry no assumptions')
    ground = 'Witness' if st == 'Refuted' else 'Replayed'
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M2-ExactReplay'], ['Replayed', 'True'], ['Ground', ground]]),
         'Assurance differs from the recomputed assurance')

def replay_refine(M, req, env, st, dname):
    need(st == 'Checked', 'a refinement is Checked'); rn = req[1]; need(rn in M.rep, 'Refine names no representation')
    law, pres, until = None, False, False
    for f in req[2:]:
        if f == ['Preserve', 'Encoding']: pres = True
        elif f == ['Until', 'Stable']: until = True
        elif isinstance(f, list) and len(f) == 2 and f[0] == 'Under': law = f[1]
        else: raise GFail('unknown Refine field %s' % show(f))
    need(pres and until, 'Refine needs (Preserve Encoding) (Until Stable)')
    C = Ctx(M, rn); st_car = M.mach[C.r['machine']]['states']; raw = M.car[st_car]
    if law is not None: need(M.meas.get(law) == st_car, 'law %s is not a uniform law on the states' % law)
    p0, cls, rounds = refine(C)
    exp = ['Refinement', ['Representation', dname or '?'], blocks(raw, C.S, cls, 'Partition')]
    if law is not None: exp.append(['Ledger', ['Under', law], ['Before', rs(weak(C.S, p0))], ['After', rs(weak(C.S, cls))]])
    envelope_gen(M, req, env, st, rn, ['Subject', ['Representation', rn], ['Machine', C.r['machine']]], 'Literal')
    need(show(find(env, 'Value')[1]) == show(exp), 'Value differs from the recomputed %s' % show(exp))
    exp_e = ['Evidence', ['Certificate', ['Kind', 'StablePartition'], blocks(raw, C.S, p0, 'Initial'), ['Rounds', str(rounds)]]]
    need(show(find(env, 'Evidence')) == show(exp_e), 'certificate differs from the recomputed stable partition')
    return 'ok'

def replay_same(M, req, env, st):
    need(len(req) == 3, 'SamePartition takes two fields'); o, rn = req[1], req[2]
    need(isinstance(o, list) and len(o) == 3 and o[0] == 'Output' and o[2] == 'Representation' and o[1] in M.der, 'bad Output')
    rq = M.der[o[1]]; need(rq[0] == 'Refine', 'Output names no refinement')
    Cr = Ctx(M, rq[1]); _, cls, _ = refine(Cr); need(rn in M.rep, 'SamePartition names no representation')
    r2 = M.rep[rn]; need(r2['machine'] == Cr.r['machine'], 'the two partitions are on different machines')
    e = M.map[r2['encode']]['f']; S = Cr.S; raw = M.car[M.mach[r2['machine']]['states']]; k = {}
    for i, x in enumerate(S): k[x] = next((k[y] for y in S[:i] if e[y] == e[x]), x)
    same = all((cls[x] == cls[y]) == (k[x] == k[y]) for x in S for y in S)
    need(st == ('Checked' if same else 'Refuted'), 'status disagrees with the recomputed partitions')
    envelope_gen(M, req, env, st, rn, ['Subject', ['Partition', o[1]], ['Representation', rn], ['Machine', r2['machine']]], 'Literal')
    need(show(find(env, 'Value')[1]) == show(['Verdict', ['Holds', 'True' if same else 'False']]), 'Value differs')
    evd = find(env, 'Evidence')
    if same:
        need(show(evd) == show(['Evidence', ['Certificate', ['Kind', 'rule'], ['Rule', 'SamePartition'], blocks(raw, S, k, 'Blocks')]]), 'certificate differs')
    else:
        w = find(evd, 'Witness')[1]; need(w[0] == 'PartitionWitness', 'PartitionWitness expected')
        x, y = key(w[1][1]), key(w[1][2]); sd = lambda b: 'Same' if b else 'Different'
        need(w[2] == ['Left', sd(cls[x] == cls[y])] and w[3] == ['Right', sd(k[x] == k[y])] and (cls[x] == cls[y]) != (k[x] == k[y]), 'witness pair does not separate the partitions')
    return 'ok'

class MCtx(Ctx):
    """Behavioral distance of a machine (no representation): seed and Kleene iteration only."""
    def __init__(self, M, mn, g):
        mc = M.mach[mn]; self.M, self.g, self.h = M, g, None
        self.S = [key(s) for s in M.car[mc['states']]]
        self.obs = [(lab, M.map[mp]['f'], t) for lab, mp, t in mc['obs']]
        self.act = [(lab, M.map[mp]['f']) for lab, mp in mc['act']]
        S = self.S
        self.d0 = {(x, y): max([dist(M, t, f[x], f[y]) for _, f, t in self.obs] or [Q(0)]) for x in S for y in S}
        self.beh = self.iterate(None)

def all_partitions(s):
    if not s: yield []; return
    for p in all_partitions(s[1:]):
        for i in range(len(p)): yield p[:i] + [[s[0]] + p[i]] + p[i + 1:]
        yield [[s[0]]] + p

def replay_weakest(M, req, env, st, dname):
    need(st == 'Checked', 'WeakestWithin is Checked'); mn = req[1]; need(mn in M.mach, 'WeakestWithin names no machine')
    f = {x[0]: x for x in req[2:] if isinstance(x, list) and len(x) == 2}
    need(len(f) == len(req) - 2 and set(f) <= {'Within', 'Kind', 'Discount', 'Under', 'Search'}, 'bad WeakestWithin fields')
    need(f['Kind'][1] == 'Behavioral' and f['Search'][1] == 'Exhaustive', 'only Behavioral / Exhaustive replay')
    bound, g, law = rat(f['Within'][1]), rat(f['Discount'][1]) if 'Discount' in f else Q(1), f['Under'][1]
    st_car = M.mach[mn]['states']; need(M.meas.get(law) == st_car, 'law is not a uniform law on the states')
    C = MCtx(M, mn, g); S = C.S; n = len(S); raw = M.car[st_car]
    diam = lambda P: max([C.beh[x, y] for B in P for x in B for y in B] or [Q(0)])
    wk = lambda P: sum(Q(len(B), n) ** 2 for B in P)
    parts = list(all_partitions(S)); best = max(wk(P) for P in parts if diam(P) <= bound)
    heads = [x[0] if isinstance(x, list) and x else None for x in env[1:]]
    need(env[0] == 'Result' and heads == HEADS, 'envelope fields %s' % heads)
    need(show(find(env, 'Claim')) == show(['Claim', req, ['Equality', 'Literal']]), 'Claim differs')
    need(show(find(env, 'Binding')) == show(['Binding', ['Module', M.name], ['Digest', ('str', M.digest)], ['Subject', ['Machine', mn]],
         ['Source', mn], ['Target', mn], ['Interface', ['Tolerance', 'Exact']]]), 'Binding differs')
    need(show(find(env, 'Scope')) == show(['Scope', ['Profile', M.profile], ['Fragment', 'M2-GradedDeterministic'], ['InitialStates', 'AllDeclared'],
         ['ReachableStates', 'AllDeclared'], ['Horizon', 'Unbounded'], ['Discount', rs(g)], ['PolicyClass', 'None']]), 'Scope differs')
    need(find(env, 'Assumptions') == ['Assumptions'], 'no assumptions')
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M2-ExactReplay'], ['Replayed', 'True'], ['Ground', 'Replayed']]), 'Assurance differs')
    v = find(env, 'Value')[1]; need(v[0] == 'WeakestPartition', 'WeakestPartition expected')
    P = [[key(x) for x in B[1:]] for B in find(v, 'Partition')[1:]]
    need(sorted(x for B in P for x in B) == sorted(S) and all(B for B in P), 'reported partition is not a partition of the states')
    need(diam(P) <= bound, 'reported partition exceeds the bound')
    need(wk(P) == best, 'reported weakness %s is not the optimum %s' % (rs(wk(P)), rs(best)))
    rest = [x for x in v[1:] if x[0] != 'Partition']
    need(show(rest) == show([['Representation', dname or '?'], ['Weakness', rs(best)], ['Defect', IV(diam(P))], ['Bound', rs(bound)],
         ['Kind', 'Behavioral'], ['Under', law], ['Optimality', 'Checked']]), 'Value fields differ from the recomputation')
    evd = find(env, 'Evidence'); need(len(evd) == 3, 'two certificates expected')
    need(show(evd[1]) == show(['Certificate', ['Kind', 'ExhaustiveSearch'], ['Family', 'AllPartitions'], ['Count', str(len(parts))]]), 'search certificate differs')
    C.h = None; check_kernel(C, evd[2], None)
    return 'ok'

def rgs(n):
    """Partitions as restricted growth strings, in lexicographic order."""
    a = [0] * n
    def rec(i, mx):
        if i == n: yield list(a); return
        for v in range(mx + 2):
            a[i] = v; yield from rec(i + 1, max(mx, v))
    yield from rec(0, -1)

def premise_partition(M, dn):
    """(machine, class map key -> block-minimum key) of a Refine or WeakestWithin premise, recomputed."""
    rq = M.der[dn]
    if rq[0] == 'Refine':
        C = Ctx(M, rq[1]); _, cls, _ = refine(C); return C.r['machine'], cls
    need(rq[0] == 'WeakestWithin', 'premise %s has no Representation output' % dn)
    f = {x[0]: x for x in rq[2:]}; mn = rq[1]
    bound, g = rat(f['Within'][1]), rat(f['Discount'][1]) if 'Discount' in f else Q(1)
    C = MCtx(M, mn, g); S = C.S; n = len(S); best, bsq = None, -1
    for a in rgs(n):          # the first partition of largest weakness within the bound
        diam = max([C.beh[S[i], S[j]] for i in range(n) for j in range(i + 1, n) if a[i] == a[j]] or [Q(0)])
        sq = sum(a.count(b) ** 2 for b in range(n))
        if diam <= bound and sq > bsq: best, bsq = a, sq
    return mn, {S[i]: S[best.index(best[i])] for i in range(n)}

def replay_approx(M, req, env, st, dname):
    o = req[1]
    need(isinstance(o, list) and len(o) == 3 and o[0] == 'Output' and o[2] == 'Representation' and o[1] in M.der, 'bad Output')
    dn = o[1]; mn, cls = premise_partition(M, dn)
    sel, w, g = 'Center', None, Q(1)
    for f in req[2:]:
        if f[0] == 'Representatives': sel = f[1]
        elif f[0] == 'Within': w = rat(f[1])
        elif f[0] == 'Discount': g = rat(f[1])
        else: raise GFail('unknown InduceApprox field %s' % show(f))
    C = MCtx(M, mn, g); S = C.S; st_car = M.mach[mn]['states']; raw = M.car[st_car]
    mins = [x for x in S if cls[x] == x]; cn = {x: mins.index(cls[x]) for x in S}; k = len(mins)
    rep = []
    for c in range(k):
        mem = [x for x in S if cn[x] == c]
        if sel == 'First': rep.append(mem[0])
        elif sel == 'Center':
            ecc = {x: max(C.beh[x, y] for y in mem) for x in mem}; e0 = min(ecc.values())
            rep.append(next(x for x in mem if ecc[x] == e0))
        else:
            need(isinstance(sel, list) and sel[0] == 'Choose' and sel[1] in M.map, 'bad selector')
            mp = M.map[sel[1]]; need(mp['from'] == st_car and mp['to'] == st_car, 'section map off the states')
            rs_ = set(mp['f'][x] for x in mem); need(len(rs_) == 1 and cn[next(iter(rs_))] == c, 'section picks no single member')
            rep.append(next(iter(rs_)))
    U = S + [('class', c) for c in range(k)]
    obs = []
    for lab, f, t in C.obs:
        fu = dict(f); fu.update({('class', c): f[rep[c]] for c in range(k)}); obs.append((fu, t))
    act = []
    for lab, f in C.act:
        fu = dict(f); fu.update({('class', c): ('class', cn[f[rep[c]]]) for c in range(k)}); act.append((lab, fu))
    d0 = {(x, y): max([dist(M, t, f[x], f[y]) for f, t in obs] or [Q(0)]) for x in U for y in U}
    D = dict(d0)
    for _ in range(len(U) ** 2 + 2):
        N = {(x, y): max([d0[x, y]] + [g * D[f[x], f[y]] for _, f in act]) for (x, y) in D}
        if N == D: break
        D = N
    else: raise GFail('union iteration did not stabilise')
    radius = max(C.beh[x, rep[cn[x]]] for x in S); defect = max(D[x, ('class', cn[x])] for x in S)
    bound = rs(radius / (1 - g)) if g < 1 else 'Unbounded'
    exp_st = 'Refuted' if w is not None and defect > w else 'Checked'
    need(st == exp_st, 'status %s, recomputed %s' % (st, exp_st))
    heads = [x[0] if isinstance(x, list) and x else None for x in env[1:]]
    need(env[0] == 'Result' and heads == HEADS, 'envelope fields %s' % heads)
    need(show(find(env, 'Claim')) == show(['Claim', req, ['Equality', 'Literal']]), 'Claim differs')
    need(show(find(env, 'Binding')) == show(['Binding', ['Module', M.name], ['Digest', ('str', M.digest)],
         ['Subject', ['Partition', dn], ['Machine', mn]], ['Source', mn], ['Target', dname or '?'], ['Interface', ['Tolerance', 'Exact']]]), 'Binding differs')
    need(show(find(env, 'Scope')) == show(['Scope', ['Profile', M.profile], ['Fragment', 'M2-GradedDeterministic'], ['InitialStates', 'AllDeclared'],
         ['ReachableStates', 'AllDeclared'], ['Horizon', 'Unbounded'], ['Discount', rs(g)], ['PolicyClass', 'None']]), 'Scope differs')
    need(find(env, 'Assumptions') == ['Assumptions'], 'no assumptions')
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M2-ExactReplay'], ['Replayed', 'True'],
         ['Ground', 'Witness' if st == 'Refuted' else 'Replayed']]), 'Assurance differs')
    exp = ['ApproximateAbstraction', ['Machine', ['Output', dname or '?', 'Machine']], ['States', str(k)], ['Selector', sel],
           ['Representatives'] + [['Class', str(c), ['Block'] + [raw[i] for i, x in enumerate(S) if cn[x] == c], raw[S.index(rep[c])]] for c in range(k)],
           ['Radius', rs(radius)], ['Defect', IV(defect)], ['Bound', bound], ['AbstractionMap', ['Kind', 'Graded'], ['Defect', rs(defect)]]]
    if w is not None: exp.append(['Within', rs(w)])
    need(show(find(env, 'Value')[1]) == show(exp), 'Value differs from the recomputed %s' % show(exp))
    upd = ['Updates'] + [['Do', lab] + [['Step', str(c), str(f[('class', c)][1])] for c in range(k)] for lab, f in act]
    need(show(find(env, 'Evidence')) == show(['Evidence', ['Certificate', ['Kind', 'InducedMachine'], ['Discount', rs(g)], upd]]), 'certificate differs from the recomputed induced machine')
    return 'ok'

def congruence_fail(C):
    """First pair with equal codes (literally, whatever the code tolerance) whose successors' codes differ."""
    S = C.S
    for i, x in enumerate(S):
        for y in S[i + 1:]:
            if C.e[x] != C.e[y]: continue
            for lab, f in C.act:
                if C.e[f[x]] != C.e[f[y]]: return x, y, lab, f
    return None

def replay_induce(M, req, env, st, dname):
    need(len(req) == 2 and req[1] in M.rep, 'InduceExact takes one representation'); rn = req[1]
    need(not M.mach[M.rep[rn]['machine']].get('merge'), 'Merge machines are outside graded InduceExact')
    C = Ctx(M, rn); dn, du, cg = C.defect('Current'), C.defect('Update'), congruence_fail(C)
    fail = 'Current' if dn > 0 else 'Update' if du > 0 else 'Congruence' if cg else None
    need(st == ('Refuted' if fail else 'Checked'), 'status %s, recomputed %s' % (st, 'Refuted' if fail else 'Checked'))
    envelope_gen(M, req, env, st, rn, ['Subject', ['Representation', rn], ['Machine', C.r['machine']]], C.eq)
    val, evd = find(env, 'Value')[1], find(env, 'Evidence')[1:]
    if fail:
        need(show(val) == show(['Refutation', ['Obligation', fail]]), 'Value differs from the recomputed refutation')
        need(evd and evd[0] == ['Obligation', fail], 'evidence must name the first failing obligation %s' % fail)
        if fail == 'Current': evidence_ok(C, 'Current', dn, evd[1:], None)
        elif fail == 'Update': evidence_ok(C, 'Update', du, evd[1:], None)
        else:
            need(len(evd) == 2 and evd[1][0] == 'Witness', 'congruence witness expected'); w = evd[1][1]
            need(w[0] == 'CongruenceWitness' and len(w) == 5, 'malformed CongruenceWitness')
            x, y = key(w[1][1]), key(w[1][2]); acts = dict(C.act)
            need(x in C.S and y in C.S and w[2][0] == 'Do' and w[2][1] in acts, 'congruence witness off the machine'); f = acts[w[2][1]]
            need(C.e[x] == C.e[y] and same_val(w[3][1], C.e[x]), 'congruence witness pair has different codes')
            need(same_val(w[4][1], C.e[f[x]]) and same_val(w[4][2], C.e[f[y]]) and C.e[f[x]] != C.e[f[y]], 'congruence witness successors agree')
        return 'ok'
    S = C.S; codes = []
    for x in S:
        if C.e[x] not in codes: codes.append(C.e[x])
    exp = ['ExactAbstraction', ['Defect', IV(Q(0))], ['Machine', ['Output', dname or '?', 'Machine']], ['States', str(len(codes))],
           ['Encode', C.r['encode']], ['Equality', C.eq], ['Decoders', 'ZeroDistanceQuotient' if C.eq == 'Observer' else 'Literal']]
    need(show(val) == show(exp), 'Value differs from the recomputed %s' % show(exp))
    need(len(evd) == 1 and evd[0][0] == 'Certificate', 'one certificate expected'); c = evd[0]
    need(show(c[1:3]) == show([['Kind', 'Prefixpoint'], ['Checks', 'Current', 'Update', 'Congruence']]) and len(c) == 4, 'certificate header differs')
    fib = c[3]; need(fib[0] == 'Fibers', 'Fibers expected'); seen, fc = [], []
    for F in fib[1:]:
        need(F[0] == 'Fiber' and len(F) >= 3, 'malformed Fiber')
        for x_ in F[2:]: x = key(x_); need(x in S and same_val(F[1], C.e[x]), 'fiber code differs from the encoding'); seen.append(x)
        fc.append(C.e[key(F[2])])
    need(sorted(seen) == sorted(S) and len(set(map(str, fc))) == len(fc), 'fibers do not partition the states by code')
    return 'ok'

# ---- GradedKernels (G01-G04), recomputed from the source ----
def luk(a, b): return max(Q(0), a + b - 1)
def kernel_of(M, x):
    """(carrier, {(a, b): value}) of a SymmetricTable tolerance or (Output D Kernel) of a PathClosure."""
    if isinstance(x, str):
        need(x in M.tol and M.tol[x]['kind'] == 'SymmetricTable', 'kernel %s is not a SymmetricTable' % x)
        return M.tol[x]['on'], dict(M.tol[x]['k'])
    need(isinstance(x, list) and len(x) == 3 and x[0] == 'Output' and x[2] == 'Kernel' and x[1] in M.der, 'bad kernel operand')
    d = M.der[x[1]]; need(d[0] == 'PathClosure' and d[2] == ['Algebra', 'Lukasiewicz01'], 'Kernel output from no PathClosure')
    on, K = kernel_of(M, d[1]); return on, closure(M, on, K)
def closure(M, on, K):
    els = [key(e) for e in M.car[on]]; K = dict(K)
    for k in els:
        for i in els:
            for j in els: K[i, j] = max(K[i, j], luk(K[i, k], K[k, j]))
    return K
def relation_of(M, x):
    need(isinstance(x, list) and len(x) == 3 and x[0] == 'Output' and x[2] == 'Relation' and x[1] in M.der, 'bad relation operand')
    d = M.der[x[1]]; need(d[0] == 'Threshold' and d[2][0] == 'AtLeast', 'Relation output from no Threshold')
    on, K = kernel_of(M, d[1]); r = rat(d[2][1]); return on, {p for p, v in K.items() if v >= r}
def bracket_of(M, d):
    need(d[0] == 'Bracket' and d[2][0] == 'Under', 'not a Bracket')
    pl = [f for f in M.form[2:] if isinstance(f, list) and f[:2] == ['PairLaw', d[2][1]]]
    need(len(pl) == 1 and pl[0][2][0] == 'Independent' and pl[0][3] == ['Diagonal', 'Included'], 'unsupported pair law')
    on, K = kernel_of(M, d[1]); need(all(M.meas.get(l) == on for l in pl[0][2][1:]), 'pair law not uniform on the kernel carrier')
    tot = sum(K.values()); return tot / len(K), tot, len(K)
def first_bad(els, T, rel):
    for i in els:
        for j in els:
            for k in els:
                if (rel and (i, j) in T and (j, k) in T and (i, k) not in T) or (not rel and T[i, k] < luk(T[i, j], T[j, k])): return i, j, k
    return None
def replay_kernels(M, req, env, st):
    h = req[0]; heads = [x[0] if isinstance(x, list) and x else None for x in env[1:]]
    need(env[0] == 'Result' and heads == HEADS, 'envelope fields %s' % heads)
    need('GradedKernels' in M.uses, 'module does not use GradedKernels')
    need(show(find(env, 'Claim')) == show(['Claim', req, ['Equality', 'Literal']]), 'Claim differs')
    need(show(find(env, 'Binding')) == show(['Binding', ['Module', M.name], ['Digest', ('str', M.digest)], ['Subject', ['Operand', req[1]]],
         ['Source', 'None'], ['Target', 'None'], ['Interface', ['Tolerance', 'Exact']]]), 'Binding differs')
    need(show(find(env, 'Scope')) == show(['Scope', ['Profile', M.profile], ['Fragment', 'M2-GradedDeterministic'], ['InitialStates', 'AllDeclared'],
         ['ReachableStates', 'AllDeclared'], ['Horizon', 'Unbounded'], ['Discount', '1'], ['PolicyClass', 'None']]), 'Scope differs')
    need(find(env, 'Assumptions') == ['Assumptions'], 'no assumptions')
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M2-ExactReplay'], ['Replayed', 'True'],
         ['Ground', 'Witness' if st == 'Refuted' else 'Replayed']]), 'Assurance differs')
    val, evd = find(env, 'Value')[1], find(env, 'Evidence')
    def table(on, K): return ['Kernel', ['On', on], ['Entries'] + [['Entry', a, b, rs(K[key(a), key(b)])] for a in M.car[on] for b in M.car[on]]]
    def relt(on, T): return ['Relation', ['On', on], ['Pairs'] + [['Pair', a, b] for a in M.car[on] for b in M.car[on] if (key(a), key(b)) in T]]
    if h == 'PathClosure':
        need(st == 'Checked' and req[2] == ['Algebra', 'Lukasiewicz01'], 'PathClosure is Checked over Lukasiewicz01')
        on, K0 = kernel_of(M, req[1]); K = closure(M, on, K0)
        need(show(val) == show(table(on, K)), 'closed kernel differs from the recomputation')
        c = evd[1]; need(len(evd) == 2 and c[:3] == ['Certificate', ['Kind', 'PathClosure'], ['Algebra', 'Lukasiewicz01']], 'closure certificate expected')
        raised = c[3]; need(raised[0] == 'Raised', 'Raised expected'); got = set()
        for e in raised[1:]:
            a, b, v, P = key(e[1]), key(e[2]), rat(e[3]), [key(x) for x in e[4][1:]]
            need(v == K[a, b] and v > K0[a, b] and P[0] == a and P[-1] == b, 'raised entry wrong')
            acc = Q(1)
            for x, y in zip(P, P[1:]): acc = luk(acc, K0[x, y])
            need(acc == v, 'path does not attain the raised value'); got.add((a, b))
        need(got == {p for p in K if K[p] > K0[p]}, 'raised entries incomplete')
    elif h == 'Bracket':
        need(st == 'Checked', 'a bracket is Checked'); mean, tot, n = bracket_of(M, req)
        need(show(val) == show(['Bracket', ['Mean', rs(mean)], ['Under', req[2][1]], ['Pairs', str(n)]]), 'Bracket value differs')
        need(show(evd) == show(['Evidence', ['Certificate', ['Kind', 'rule'], ['Rule', 'UniformMean'], ['Sum', rs(tot)]]]), 'bracket certificate differs')
    elif h == 'Delta':
        need(st == 'Checked', 'Delta is Checked'); xs = []
        for f, hd in ((req[1], 'From'), (req[2], 'To')):
            need(f[0] == hd and f[1][0] == 'Output' and f[1][2] == 'Value' and f[1][1] in M.der, 'bad Delta operand'); xs.append(bracket_of(M, M.der[f[1][1]])[0])
        need(show(val) == show(['Delta', ['From', rs(xs[0])], ['To', rs(xs[1])], ['Increase', rs(xs[1] - xs[0])]]), 'Delta value differs')
        need(show(evd) == show(['Evidence', ['Certificate', ['Kind', 'rule'], ['Rule', 'Difference']]]), 'Delta certificate differs')
    elif h == 'Threshold':
        need(st == 'Checked', 'Threshold is Checked'); on, K = kernel_of(M, req[1]); r = rat(req[2][1])
        need(show(val) == show(relt(on, {p for p, v in K.items() if v >= r})), 'Relation differs')
        need(show(evd) == show(['Evidence', ['Certificate', ['Kind', 'rule'], ['Rule', 'Threshold'], ['AtLeast', rs(r)]]]), 'Threshold certificate differs')
    else:
        x = req[1]; rel = isinstance(x, list) and x[2:] == ['Relation']
        on, T = relation_of(M, x) if rel else kernel_of(M, x)
        alg = 'Boolean' if rel else 'Lukasiewicz01'
        if len(req) == 3: need(req[2] == ['Algebra', 'Boolean'] if rel else req[2][1] in ('Lukasiewicz', 'Lukasiewicz01'), 'algebra does not fit the operand')
        bad = first_bad([key(e) for e in M.car[on]], T, rel)
        need(st == ('Refuted' if bad else 'Checked'), 'transitivity status differs')
        need(show(val) == show(['Verdict', ['Holds', 'False' if bad else 'True'], ['Algebra', alg]]), 'Verdict differs')
        if bad:
            w = find(evd, 'Witness')[1]; need(w[0] == 'TransitivityWitness', 'TransitivityWitness expected')
            i, j, k = [key(e) for e in w[1][1:]]
            vals = [str(int(p in T)) for p in ((i, j), (j, k), (i, k))] if rel else [rs(T[p]) for p in ((i, j), (j, k), (i, k))]
            need(w[2] == ['Values'] + vals, 'witness values differ')
            ok = ((i, j) in T and (j, k) in T and (i, k) not in T) if rel else T[i, k] < luk(T[i, j], T[j, k])
            need(ok, 'witness triple is transitive')
        else:
            need(show(evd) == show(['Evidence', ['Certificate', ['Kind', 'rule'], ['Rule', 'Transitivity'], relt(on, T) if rel else table(on, T)]]), 'certificate differs')
    return 'ok'

class MCtx(Ctx):
    """Machine-level context (BehavioralTolerance): no representation, no codes."""
    def __init__(self, M, mn, g=Q(1), h=None):
        mc = M.mach[mn]; self.M, self.r, self.g, self.h = M, None, g, h
        self.S = [key(s) for s in M.car[mc['states']]]
        self.obs = [(lab, M.map[mp]['f'], t) for lab, mp, t in mc['obs']]
        self.act = [(lab, M.map[mp]['f']) for lab, mp in mc['act']]
        self.raw = {key(s): s for s in M.car[mc['states']]}
        self.merge = []; self.e = None; self.dq = None; S = self.S; self.states = mc['states']
        self.d0 = {(x, y): max([dist(M, t, f[x], f[y]) for _, f, t in self.obs] or [Q(0)]) for x in S for y in S}
        self.beh = self.iterate(h)
        self.eq = 'Observer' if any(t and not separated(M, t) for _, _, t in self.obs) else 'Literal'

def check_mword(C, w, horizon):
    """A machine-level WordWitness: g^|w| * d(o_j T_w x, o_j T_w y) attains d_beh(x, y) > 0."""
    need(isinstance(w, list) and w[0] == 'WordWitness' and len(w) == 7, 'machine WordWitness expected')
    P, W, Qy, L, R, LB = w[1:]
    need(P[0] == 'Pair' and W[0] == 'Word' and Qy[0] == 'Query' and L[0] == 'Left' and R[0] == 'Right', 'malformed WordWitness')
    nK = sum(1 for i, x in enumerate(C.S) if not any(C.d0[y, x] == 0 for y in C.S[:i]))
    need(LB == ['LengthBound', str(len(C.S) - nK)], 'LengthBound differs from n - |X/K_O|')
    need(len(W) - 1 <= len(C.S) - nK, 'witness word longer than n - |X/K_O|')
    x, y = key(P[1]), key(P[2]); need(x in C.S and y in C.S, 'witness pair not states')
    acts = dict(C.act); a, b = x, y; n = 0
    for st in W[1:]:
        need(st[0] == 'Do' and st[1] in acts, 'witness word names no action'); a, b = acts[st[1]][a], acts[st[1]][b]; n += 1
    need(horizon is None or n <= horizon, 'witness word longer than the horizon')
    ob = [o for o in C.obs if o[0] == Qy[1]]; need(ob, 'witness query names no observation')
    lab, f, t = ob[0]
    need(same_val(L[1], f[a]) and same_val(R[1], f[b]), 'witness answers differ from the recomputed answers')
    need(C.g ** n * dist(C.M, t, f[a], f[b]) == C.beh[x, y] > 0, 'witness test does not attain the behavioral distance')
    return (x, y)

def replay_beh_tol(M, req, env, st):
    need(len(req) >= 2 and isinstance(req[1], str) and req[1] in M.mach, 'BehavioralTolerance names no machine')
    h, g = None, Q(1)
    for f in req[2:]:
        need(isinstance(f, list) and len(f) == 2, 'malformed request field')
        if f[0] == 'Horizon':
            if f[1] != 'AllFiniteWords': need(f[1][0] == 'Steps', 'Horizon needs Steps'); h = int(f[1][1]); need(h >= 0, 'negative horizon')
        elif f[0] == 'Discount': g = rat(f[1]); need(0 < g <= 1, 'discount outside (0,1]')
        elif f[0] == 'Precision': need(0 <= rat(f[1]) <= 1, 'precision outside [0,1]')
        else: raise GFail('unknown request field %s' % show(f))
    need(st == 'Checked', 'a behavioral tolerance is Checked')
    C = MCtx(M, req[1], g, h)
    heads = [x[0] if isinstance(x, list) and x else None for x in env[1:]]
    need(env[0] == 'Result' and heads == HEADS, 'envelope fields %s' % heads)
    need(show(find(env, 'Claim')) == show(['Claim', req, ['Equality', C.eq]]), 'Claim differs from the request and equality')
    exp_b = ['Binding', ['Module', M.name], ['Digest', ('str', M.digest)], ['Subject', ['Machine', req[1]]],
             ['Source', 'None'], ['Target', 'None'], ['Interface', ['Tolerance', 'Exact']]]
    need(show(find(env, 'Binding')) == show(exp_b), 'Binding differs from the recomputed binding %s' % show(exp_b))
    exp_s = ['Scope', ['Profile', M.profile], ['Fragment', 'M2-GradedDeterministic'], ['InitialStates', 'AllDeclared'],
             ['ReachableStates', 'AllDeclared'], ['Horizon', 'Unbounded' if h is None else ['Steps', str(h)]],
             ['Discount', rs(g)], ['PolicyClass', 'None']]
    need(show(find(env, 'Scope')) == show(exp_s), 'Scope differs from the recomputed scope %s' % show(exp_s))
    need(find(env, 'Assumptions') == ['Assumptions'], 'graded table results carry no assumptions')
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M2-ExactReplay'], ['Replayed', 'True'], ['Ground', 'Replayed']]),
         'Assurance differs from the recomputed assurance')
    on = C.states; pos = [(x, y) for i, x in enumerate(C.S) for y in C.S[i + 1:] if C.beh[x, y] > 0]
    exp_v = ['ToleranceResult',
             ['Tolerance', ['Kernel', ['On', on], ['Entries'] + [['Entry', a, b, rs(1 - C.beh[key(a), key(b)])] for a in M.car[on] for b in M.car[on]]]],
             ['Certificate', ['Kind', 'TwoSided'], ['Lower', ['WordTests', str(len(pos))]],
              ['Upper', 'LayeredPrefixpoint' if h is not None else 'Prefixpoint']]]
    need(show(find(env, 'Value')[1]) == show(exp_v), 'Value differs from the recomputed tolerance')
    evd = find(env, 'Evidence')[1:]
    need(len(evd) == len(pos) + 1, 'evidence must be one word test per positive pair and one kernel')
    got = [check_mword(C, e[1], h) for e in evd[:-1] if e[0] == 'Witness']
    need(got == pos, 'word tests do not cover exactly the pairs at positive distance')
    check_kernel(C, evd[-1], h)
    return 'ok'

def replay(M, req, env):
    st = find(env, 'Status')[1]
    if st not in ('Checked', 'Refuted'): return 'skip'
    dname = None
    if isinstance(req, str): need(req in M.der, 'unknown Derive %s' % req); dname = req; req = M.der[req]
    if req[0] == 'Refine': return replay_refine(M, req, env, st, dname)
    if req[0] == 'BehavioralTolerance': return replay_beh_tol(M, req, env, st)
    if req[0] == 'SamePartition': return replay_same(M, req, env, st)
    if req[0] == 'WeakestWithin': return replay_weakest(M, req, env, st, dname)
    if req[0] == 'InduceApprox': return replay_approx(M, req, env, st, dname)
    if req[0] == 'InduceExact': return replay_induce(M, req, env, st, dname)
    if req[0] in KERNEL_HEADS: return replay_kernels(M, req, env, st)
    hd = req[0]; need(len(req) >= 2 and req[1] in M.rep, 'request names no graded representation')
    w, h, g, pol = opts(req)
    is_def, is_check = hd == 'Defects', hd.startswith('Check')
    if not is_check: need(w == 0 and not any(f[0] == 'Within' for f in req[2:]), 'Within on a measurement')
    k = 'Current' if 'Now' in hd else 'Update' if 'Updates' in hd else 'Trace' if 'Trace' in hd else 'Behavioral'
    if not is_def and k not in ('Behavioral', 'Trace'): need(h is None and g == 1, 'Horizon/Discount on a non-behavioral claim')
    need(pol is None or k == 'Trace', 'Policies on a non-trace claim')
    if k == 'Trace': need(not any(f[0] == 'Discount' for f in req[2:]), 'a trace claim takes no Discount')
    C = Ctx(M, req[1], g, h)
    if k == 'Trace': need(all(v in (0, 1) for v in C.d0.values()), 'trace replay needs discrete value tolerances')
    envelope_ok(M, req, env, st, C, h, g, (pol or 'Words') if k == 'Trace' else 'None')
    val, evd = find(env, 'Value')[1], find(env, 'Evidence')[1:]
    if is_def:
        ds = [C.defect(x) for x in KN]
        exp = ['Defects'] + [[x, IV(d)] for x, d in zip(KN, ds)] + [['Equality', C.eq]]
        need(show(val) == show(exp), 'Value differs from the recomputed %s' % show(exp))
        need(st == 'Checked', 'a measurement is Checked')
        need(len(evd) == 3 and [p[:2] for p in evd] == [['Part', x] for x in KN], 'Defects evidence must be three Parts')
        for p, x, d in zip(evd, KN, ds): evidence_ok(C, x, d, p[2:], h)
        return 'ok'
    d = C.defect(k)
    if is_check:
        exp = ['DefectCheck', ['Defect', IV(d)], ['Bound', rs(w)], ['Kind', k], ['Equality', C.eq]]
        need(st == ('Checked' if d <= w else 'Refuted'), 'status disagrees with defect %s and bound %s' % (rs(d), rs(w)))
    else:
        exp = ['DefectMeasurement', ['Defect', IV(d)], ['Kind', k], ['Equality', C.eq]]
        need(st == 'Checked', 'a measurement is Checked')
    need(show(val) == show(exp), 'Value differs from the recomputed %s' % show(exp))
    evidence_ok(C, k, d, evd, h)
    return 'ok'
