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
GRADED_HEADS = ('Defects', 'MeasureUpdates', 'MeasureBehavioral', 'CheckBehavioral')
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
        self.car, self.map, self.tol, self.mach, self.rep = {}, {}, {}, {}, {}
        decls = [d for d in form[2:] if isinstance(d, list) and d]
        for h, fn in (('Carrier', self.carrier), ('Tolerance', self.toldecl), ('Map', self.mapdecl),
                      ('Machine', self.machine), ('Representation', self.repdecl)):
            for d in decls:
                if d[0] != h: continue
                try: fn(d)
                except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError, GFail): pass

    def carrier(self, d):
        b = d[3]
        if b[0] == 'Enum': self.car[d[1]] = list(b[1:])
        elif b[0] == 'Product':
            els = [['Tuple']]
            for f in b[1:]: els = [e + [v] for e in els for v in self.car[f]]
            self.car[d[1]] = els

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
        if not isinstance(fr, str): return          # inline Product source: not in this checker yet
        src, val = self.car[fr], to in VALUE_TYPES
        f = {}
        if body[0] == 'Table':
            for k_, v in body[1:]: f[key(k_)] = v
        elif body[0] == 'Cases':
            for s in src:
                for pat, rhs in body[1:]:
                    env = {}
                    if match(pat, s, env): f[key(s)] = ev(rhs, env); break
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
                need(self.map[x[2]]['from'] == m['states'], 'observation off the states')
                need(t is None or self.tol[t]['on'] == self.map[x[2]]['to'], 'tolerance off the observation')
                m['obs'].append((x[1], x[2], t))
            elif x[0] == 'Action':
                need(len(x) == 3 and self.map[x[2]]['from'] == m['states'] and self.map[x[2]]['to'] == m['states'], 'bad Action')
                m['act'].append((x[1], x[2]))
            else: return                              # Merge, Bag, ...: outside this checker
        self.mach[d[1]] = m

    def repdecl(self, d):
        co, mach, e = find(d, 'Codes'), find(d, 'Of')[1], find(d, 'Encode')[1]
        need(mach in self.mach and self.map[e]['from'] == self.mach[mach]['states'], 'bad representation')
        t = co[1] if co else None
        need(t is None or (t in self.tol and self.tol[t]['on'] == self.map[e]['to']), 'bad Codes')
        self.rep[d[1]] = {'machine': mach, 'encode': e, 'tol': t}

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
    return any(t for _, _, t in M.mach[r['machine']]['obs']) or (r['tol'] is not None and M.tol[r['tol']]['kind'] != 'Trivial')

def is_graded(M, req):
    if not isinstance(req, list) or not req: return False
    return req[0] in GRADED_HEADS or (req[0] in REP_HEADS and len(req) >= 2 and graded_rep(M, req[1]))

# ---- part 2: independent recomputation and the replay of one graded result ----
class Ctx:
    def __init__(self, M, rn, g=Q(1), h=None):
        r = M.rep[rn]; mc = M.mach[r['machine']]
        self.M, self.r, self.g, self.h = M, r, g, h
        self.S = [key(s) for s in M.car[mc['states']]]
        self.obs = [(lab, M.map[mp]['f'], t) for lab, mp, t in mc['obs']]
        self.act = [(lab, M.map[mp]['f']) for lab, mp in mc['act']]
        e = M.map[r['encode']]['f']; self.e = e
        S = self.S
        self.d0 = {(x, y): max([dist(M, t, f[x], f[y]) for _, f, t in self.obs] or [Q(0)]) for x in S for y in S}
        self.dq = {(x, y): dist(M, r['tol'], e[x], e[y]) for x in S for y in S}
        self.beh = self.iterate(h)
        self.eq = 'Observer' if any(t and not separated(M, t) for _, _, t in self.obs) else 'Literal'

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
            return max([Q(0)] + [max(Q(0), self.dq[f[x], f[y]] - self.dq[x, y]) for _, f in self.act for x in S for y in S])
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
    need(isinstance(w, list) and w[0] == 'WordWitness' and len(w) == 7, 'WordWitness expected')
    P, Cd, W, Qy, L, R = w[1:]
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
    lower = C.g ** n * dist(C.M, t, f[a], f[b]) - C.dq[x, y]
    need(lower == d and d > 0, 'witness bound %s does not attain the defect %s' % (rs(lower), rs(d)))

def check_update_witness(C, w, d):
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
    w, h, g = Q(0), None, Q(1)
    for f in req[2:]:
        need(isinstance(f, list) and len(f) == 2, 'malformed request field')
        if f[0] == 'Within': w = rat(f[1])
        elif f[0] == 'Horizon': need(f[1][0] == 'Steps', 'Horizon needs Steps'); h = int(f[1][1]); need(h >= 0, 'negative horizon')
        elif f[0] == 'Discount': g = rat(f[1]); need(0 < g <= 1, 'discount outside (0,1]')
        else: raise GFail('unknown request field %s' % show(f))
    return w, h, g

def envelope_ok(M, req, env, st, C, h, g):
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
             ['Discount', rs(g)], ['PolicyClass', 'None']]
    need(show(find(env, 'Scope')) == show(exp_s), 'Scope differs from the recomputed scope %s' % show(exp_s))
    need(find(env, 'Assumptions') == ['Assumptions'], 'graded table results carry no assumptions')
    ground = 'Witness' if st == 'Refuted' else 'Replayed'
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M2-ExactReplay'], ['Replayed', 'True'], ['Ground', ground]]),
         'Assurance differs from the recomputed assurance')

def evidence_ok(C, k, d, items, h):
    """items: the evidence entries for one defect kind."""
    if k == 'Behavioral':
        if d > 0:
            need(len(items) == 2 and items[0][0] == 'Witness', 'a positive behavioral defect needs a witness and a kernel')
            check_word(C, items[0][1], k, d, h); items = items[1:]
        need(len(items) == 1, 'behavioral evidence must end in one kernel certificate'); check_kernel(C, items[0], h)
        return
    need(len(items) == 1, '%s evidence must be one item' % k)
    it = items[0]
    if d == 0:
        need(show(it) == show(['Certificate', ['Kind', 'Prefixpoint'], ['Checks', k]]), 'zero %s defect needs its certificate' % k)
    elif k == 'Current': need(it[0] == 'Witness', 'current witness expected'); check_word(C, it[1], k, d, 0)
    else: need(it[0] == 'Witness', 'update witness expected'); check_update_witness(C, it[1], d)

def replay(M, req, env):
    st = find(env, 'Status')[1]
    if st not in ('Checked', 'Refuted'): return 'skip'
    hd = req[0]; need(len(req) >= 2 and req[1] in M.rep, 'request names no graded representation')
    w, h, g = opts(req)
    is_def, is_check = hd == 'Defects', hd.startswith('Check')
    if not is_check: need(w == 0 and not any(f[0] == 'Within' for f in req[2:]), 'Within on a measurement')
    k = 'Current' if 'Now' in hd else 'Update' if 'Updates' in hd else 'Behavioral'
    if not is_def and k != 'Behavioral': need(h is None and g == 1, 'Horizon/Discount on a non-behavioral claim')
    C = Ctx(M, req[1], g, h)
    envelope_ok(M, req, env, st, C, h, g)
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

# ---- part 3: request options, envelope and the replay of one graded result ----
def gopts(req):
    o = {'within': Q(0), 'wtxt': '0', 'h': None, 'g': Q(1)}
    for f in req[2:]:
        need(isinstance(f, list) and len(f) == 2, 'malformed request field')
        if f[0] == 'Within': o['within'] = rat(f[1]); o['wtxt'] = rs(o['within'])
        elif f[0] == 'Horizon': need(f[1][0] == 'Steps', 'horizon not (Steps h)'); o['h'] = int(f[1][1])
        elif f[0] == 'Discount': o['g'] = rat(f[1]); need(0 < o['g'] <= 1, 'discount out of (0,1]')
        else: raise GFail('unknown request field %s' % f[0])
    return o

def kind_of(h):
    return 'Current' if 'Now' in h else 'Update' if 'Updates' in h else 'Behavioral'

def evidence_ok(C, k, d, o, items):
    """items: the evidence forms of one defect, in producer order."""
    W = [x for x in items if x[0] == 'Witness']; Cs = [x for x in items if x[0] == 'Certificate']
    if k == 'Behavioral':
        need(len(Cs) == 1, 'behavioral evidence needs one kernel certificate'); check_kernel(C, Cs[0], o['h'])
        if d > 0: need(len(W) == 1, 'positive behavioral defect needs a witness'); check_word(C, W[0][1], k, d, o['h'])
        else: need(not W, 'zero defect carries no witness')
        return
    if d == 0:
        need(len(Cs) == 1 and not W, 'zero defect needs exactly one certificate')
        need(find(Cs[0], 'Checks') == ['Checks', k], 'certificate checks the wrong obligation')
        # the certificate is claimed by recomputation: d == 0 was recomputed independently
        return
    need(len(W) == 1 and not Cs, 'positive defect needs exactly one witness')
    if k == 'Current': check_word(C, W[0][1], k, d, 0)
    else: check_update_witness(C, W[0][1], d)

def replay(GM, req, env):
    need(env[0] == 'Result' and [x[0] for x in env[1:]] == HEADS, 'envelope fields differ from the M2 envelope')
    st = find(env, 'Status')[1]
    if st not in ('Checked', 'Refuted'): return 'skip'
    h, rn = req[0], req[1]
    need(rn in GM.rep, 'representation outside the graded checker')
    o = gopts(req); C = Ctx(GM, rn, o['g'], o['h'])
    B = find(env, 'Binding')
    need(find(B, 'Module') == ['Module', GM.name] and find(B, 'Digest')[1].strip('"') == GM.digest, 'binding differs from the module')
    need(find(B, 'Subject') == ['Subject', ['Representation', rn], ['Machine', C.r['machine']]], 'subject differs')
    need(find(env, 'Claim') == ['Claim', req, ['Equality', C.eq]], 'claim differs from request + equality %s' % C.eq)
    sc = find(env, 'Scope')
    need(find(sc, 'Profile') == ['Profile', 'Graded'] and find(sc, 'Fragment') == ['Fragment', 'M2-GradedDeterministic'], 'scope profile/fragment')
    need(find(sc, 'Horizon')[1] == ('Unbounded' if o['h'] is None else ['Steps', str(o['h'])]), 'scope horizon differs')
    need(rat(find(sc, 'Discount')[1]) == o['g'], 'scope discount differs')
    asr = find(env, 'Assurance')
    need(find(asr, 'Policy') == ['Policy', 'M2-ExactReplay'] and find(asr, 'Replayed') == ['Replayed', 'True'], 'assurance not replayed exact')
    val = find(env, 'Value')[1]; evd = find(env, 'Evidence')[1:]
    if h == 'Defects':
        ds = {k: C.defect(k) for k in KN}
        exp = ['Defects'] + [[k, IV(ds[k])] for k in KN] + [['Equality', C.eq]]
        need(show(val) == show(exp), 'Defects value differs from recomputed %s' % show(exp))
        need(st == 'Checked', 'Defects is a measurement')
        need([p[:2] for p in evd] == [['Part', k] for k in KN], 'Defects evidence parts differ')
        for p in evd: evidence_ok(C, p[1], ds[p[1]], o, p[2:])
        return 'ok'
    k = kind_of(h); d = C.defect(k)
    if h.startswith('Check'):
        need(st == ('Checked' if d <= o['within'] else 'Refuted'), 'status disagrees with defect and bound')
        exp = ['DefectCheck', ['Defect', IV(d)], ['Bound', o['wtxt']], ['Kind', k], ['Equality', C.eq]]
    else:
        need(st == 'Checked', 'a measurement is Checked')
        exp = ['DefectMeasurement', ['Defect', IV(d)], ['Kind', k], ['Equality', C.eq]]
    need(show(val) == show(exp), 'value differs from recomputed %s' % show(exp))
    evidence_ok(C, k, d, o, evd)
    return 'ok'
