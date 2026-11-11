#!/usr/bin/env python3
"""Independent replay checker for dcalc M0 result envelopes.

It shares no code with src/dcalc: it re-reads the fixture, re-admits each
module (carriers, Table/Cases maps, machines, representations, tolerances,
abstraction maps), recomputes the module digest, and replays the evidence of
every Checked or Refuted envelope from the envelope's own data:
  - Prefixpoint certificates (Blocks or Fibers) for MeasureNow, CheckUpdates
    and InduceExact;
  - Current/Update/Congruence witnesses;
  - rule certificates (Commutation table, Composition table) and
    CommutationWitness.
Usage: replay.py FIXTURE.metta DCALC_OUTPUT.txt  -> exit 0 iff all replay."""
import hashlib, re, sys

def parse(src):
    toks = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()";]+|;[^\n]*', src)
    pos = 0
    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            out = []
            while toks[pos] != ')': out.append(rd())
            pos += 1; return out
        if t.startswith('"'): return ('str', re.sub(r'\\(.)', r'\1', t[1:-1]))
        return t
    toks = [t for t in toks if not t.startswith(';')]
    forms = []
    while pos < len(toks): forms.append(rd())
    return forms

def show(x):
    if isinstance(x, list): return '(' + ' '.join(show(y) for y in x) + ')'
    if isinstance(x, tuple): return '"' + x[1].replace('\\', '\\\\').replace('"', '\\"') + '"'
    return x

def find(l, head):
    for x in l[1:] if isinstance(l, list) else []:
        if isinstance(x, list) and x and x[0] == head: return x
    return None

def key(x): return show(x)

class Module:
    def __init__(self, form):
        self.name = form[1]; self.digest = hashlib.sha256(show(form).encode()).hexdigest()
        pf = find(form, 'Profile'); self.profile = pf[1] if pf and len(pf) == 2 else 'Crisp'
        self.car, self.map, self.mach, self.rep, self.tol, self.abs = {}, {}, {}, {}, {}, {}
        for d in form[2:]:
            h = d[0]
            try:
                if h == 'Carrier': self.carrier(d)
                elif h == 'Map': self.mapdecl(d)
                elif h == 'Machine' and not find(d, 'Bag'):
                    self.mach[d[1]] = {'states': find(d, 'States')[1],
                        'obs': [(x[1], x[2]) for x in d[2:] if x[0] == 'Observe'],
                        'act': [(x[1], x[2]) for x in d[2:] if x[0] == 'Action']}
                elif h == 'Tolerance' and isinstance(d[3], list) and d[3] == ['Trivial']:
                    self.tol[d[1]] = d[2][1]
                elif h == 'Representation':
                    co = find(d, 'Codes')
                    self.rep[d[1]] = {'machine': find(d, 'Of')[1], 'encode': find(d, 'Encode')[1],
                                      'all': bool(co and co[1] in self.tol),
                                      'tol': co[1] if (co and co[1] in self.tol) else 'Exact'}
                elif h == 'AbstractionMap':
                    self.abs[d[1]] = {'source': find(d, 'Source')[1], 'target': find(d, 'Target')[1], 'map': find(d, 'Map')[1]}
            except (KeyError, IndexError, TypeError, ValueError, AssertionError):
                pass   # outside the fragment this checker knows; envelopes on it must not be Checked

    def carrier(self, d):
        b = d[3]
        if b[0] == 'Enum': self.car[d[1]] = list(b[1:])
        elif b[0] == 'Product':
            els = [['Tuple']]
            for f in b[1:]: els = [e + [v] for e in els for v in self.car[f]]
            self.car[d[1]] = els

    def mapdecl(self, d):
        src, dst, body = self.car[d[2][1]], self.car[d[3][1]], d[4]
        tab = {}
        if body[0] == 'Table':
            for k, v in body[1:]: tab[key(k)] = v
        elif body[0] == 'Cases':
            for s in src:
                for pat, rhs in body[1:]:
                    env = {}
                    if match(pat, s, env): tab[key(s)] = ev(rhs, env); break
        else: return
        assert all(key(s) in tab for s in src) and all(v in dst or key(v) in map(key, dst) for v in tab.values())
        self.map[d[1]] = {'from': d[2][1], 'to': d[3][1], 'f': {k: key(v) for k, v in tab.items()}}

def match(p, v, env):
    if isinstance(p, str) and p.startswith('$'):
        if p in env: return key(env[p]) == key(v)
        env[p] = v; return True
    if isinstance(p, list):
        return isinstance(v, list) and len(p) == len(v) and all(match(a, b, env) for a, b in zip(p, v))
    return key(p) == key(v)

def ev(x, env):
    if isinstance(x, str) and x.startswith('$'): return env[x]
    if isinstance(x, list) and x and x[0] in ('Add', 'Mul') and len(x) == 3:
        a, b = int(ev(x[1], env)), int(ev(x[2], env))
        return str(a + b if x[0] == 'Add' else a * b)
    if isinstance(x, list): return [ev(y, env) for y in x]
    return x

class Fail(Exception): pass

def need(c, msg):
    if not c: raise Fail(msg)

def derives(M, form):
    return {d[1]: d[2] for d in form[2:] if isinstance(d, list) and d and d[0] == 'Derive' and len(d) == 3}

def rep_of(M, name):
    need(name in M.rep, 'unknown representation %s' % name); return M.rep[name]

def enc(M, r): return M.map[r['encode']]['f']

def view_machine(M, name):
    need(name in M.mach, 'unknown machine %s' % name); mc = M.mach[name]
    return {'id': name, 'states': [key(s) for s in M.car[mc['states']]],
            'obs': {l: M.map[f]['f'] for l, f in mc['obs']}, 'act': {l: M.map[f]['f'] for l, f in mc['act']},
            'ocar': {l: M.map[f]['to'] for l, f in mc['obs']}}

def view_quotient(M, rname, did):
    r = rep_of(M, rname); mc = M.mach[r['machine']]; e = enc(M, r); pre = {}
    for s in M.car[mc['states']]: pre.setdefault(e[key(s)], []).append(key(s))
    obs, act = {}, {}
    for l, f in mc['obs']:
        t = M.map[f]['f']; obs[l] = {}
        for c, ss in pre.items():
            vals = {t[s] for s in ss}; need(len(vals) == 1, 'quotient observation %s not well defined' % l); obs[l][c] = vals.pop()
    for l, f in mc['act']:
        t = M.map[f]['f']; act[l] = {}
        for c, ss in pre.items():
            vals = {e[t[s]] for s in ss}; need(len(vals) == 1, 'quotient action %s not well defined' % l); act[l][c] = vals.pop()
    order = [key(c) for c in M.car[M.map[r['encode']]['to']] if key(c) in pre]
    return {'id': '(Output %s Machine)' % did, 'states': order, 'obs': obs, 'act': act,
            'ocar': {l: M.map[f]['to'] for l, f in mc['obs']}}

def same_interface(sv, tv):
    # review 4 F4 (spec Definition 3.5): both sides carry the same observation
    # labels (with the same carriers) and the same action labels.
    need(set(sv['obs']) == set(tv['obs']), 'interfaces differ: observation labels')
    need(all(sv['ocar'][l] == tv['ocar'][l] for l in sv['obs']), 'interfaces differ: observation carriers')
    need(set(sv['act']) == set(tv['act']), 'interfaces differ: action labels')

def commute_fail(sv, tv, f):
    for s in sv['states']:
        if f.get(s) not in tv['states']: return ('State', s, 'outside target')
        for l, o in sv['obs'].items():
            if l not in tv['obs'] or o[s] != tv['obs'][l][f[s]]: return ('Observe', s, l)
        for l, a in sv['act'].items():
            if l not in tv['act'] or f[a[s]] != tv['act'][l][f[s]]: return ('Action', s, l)
    return None

def src_view(M, D, src):
    if isinstance(src, str): return view_machine(M, src)
    need(isinstance(src, list) and len(src) == 3 and src[0] == 'Output' and src[2] == 'Machine', 'bad source')
    q = D.get(src[1]); need(isinstance(q, list) and q[0] == 'InduceExact', 'source derive is not InduceExact')
    obligations_hold(M, rep_of(M, q[1]))
    return view_quotient(M, q[1], src[1])

def arrow(M, D, ref, depth=0):
    """(src_id, tgt_id, table, src_view, tgt_view) of the arrow a Derive produces, recomputed."""
    need(depth < 16, 'derive cycle')
    need(isinstance(ref, list) and len(ref) == 3 and ref[0] == 'Output' and ref[1] in D, 'bad arrow reference')
    q = D[ref[1]]
    if q[0] == 'InduceExact':
        r = rep_of(M, q[1]); obligations_hold(M, r)
        sv, tv = view_machine(M, r['machine']), view_quotient(M, q[1], ref[1])
        return sv, tv, dict(enc(M, r))
    if q[0] == 'CheckAbstractionMap':
        a = M.abs[q[1]]; sv, tv = src_view(M, D, a['source']), view_machine(M, a['target'])
        f = {s: M.map[a['map']]['f'][s] for s in sv['states']}
        same_interface(sv, tv)
        need(commute_fail(sv, tv, f) is None, 'component map does not commute'); return sv, tv, f
    if q[0] == 'Then':
        s1, t1, f = arrow(M, D, q[1], depth + 1); s2, t2, g = arrow(M, D, q[2], depth + 1)
        need(t1['id'] == s2['id'], 'interface mismatch'); return s1, t2, {s: g[f[s]] for s in s1['states']}
    raise Fail('derive %s has no arrow' % ref[1])

def ceq(r, a, b, literal): return (not literal and r['all']) or a == b

def obligation_fail(M, r, kind):
    """Least failing pair for Current/Update/Congruence, or None."""
    mc = M.mach[r['machine']]; e = enc(M, r); S = [key(s) for s in M.car[mc['states']]]; lit = kind == 'Congruence'
    for i, s in enumerate(S):
        for t in S[i + 1:]:
            if not ceq(r, e[s], e[t], lit): continue
            if kind == 'Current':
                for l, f in mc['obs']:
                    if M.map[f]['f'][s] != M.map[f]['f'][t]: return (s, t, l)
            else:
                for l, f in mc['act']:
                    a = M.map[f]['f']
                    if not ceq(r, e[a[s]], e[a[t]], lit): return (s, t, l)
    return None

def obligations_hold(M, r):
    for k in ('Current', 'Update', 'Congruence'): need(obligation_fail(M, r, k) is None, '%s obligation fails' % k)

def witness_fail(M, r, kind, w):
    """Check a Current/Update/Congruence witness from its own data."""
    head = {'Current': 'CurrentWitness', 'Update': 'UpdateWitness', 'Congruence': 'CongruenceWitness'}[kind]
    need(isinstance(w, list) and w[0] == head, 'witness head %s expected' % head)
    mc = M.mach[r['machine']]; e = enc(M, r); lit = kind == 'Congruence'
    p = find(w, 'Pair'); s, t = key(p[1]), key(p[2])
    need(s != t and ceq(r, e[s], e[t], lit), 'witness pair does not share a code')
    cw = find(w, 'Codes'); need([key(cw[1]), key(cw[2])] == [e[s], e[t]], 'witness codes wrong')
    if kind == 'Current':
        l = find(w, 'Observe')[1]; f = dict(mc['obs'])[l]; o = M.map[f]['f']
        need(o[s] != o[t], 'observation does not differ')
        need([key(find(w, 'Left')[1]), key(find(w, 'Right')[1])] == [o[s], o[t]], 'witness values wrong')
    else:
        l = find(w, 'Action')[1]; a = M.map[dict(mc['act'])[l]]['f']
        need(not ceq(r, e[a[s]], e[a[t]], lit), 'successor codes do not differ')
        need([key(find(w, 'Left')[1]), key(find(w, 'Right')[1])] == [e[a[s]], e[a[t]]], 'witness successor codes wrong')
    need(obligation_fail(M, r, kind) == (s, t, l), 'witness is not the canonical least witness')

def blocks_ok(M, r, blocks, actions):
    mc = M.mach[r['machine']]; e = enc(M, r); S = [key(s) for s in M.car[mc['states']]]
    cls = {}
    for i, b in enumerate(blocks[1:]):
        for s in b[1:]: need(key(s) not in cls, 'state in two blocks'); cls[key(s)] = i
    need(set(cls) == set(S), 'blocks do not cover the states')
    for s in S:
        for t in S:
            need((cls[s] == cls[t]) == ceq(r, e[s], e[t], False), 'blocks are not the code classes')
            if cls[s] != cls[t]: continue
            # review 4 F5: Current checks observations, Update checks actions
            if not actions:
                for l, f in mc['obs']: need(M.map[f]['f'][s] == M.map[f]['f'][t], 'observation varies in a block')
            if actions:
                for l, f in mc['act']: need(cls[M.map[f]['f'][s]] == cls[M.map[f]['f'][t]], 'action splits a block')

def defect_of(val):
    d = find(val, 'Defect'); iv = d[1]; need(iv[0] == 'Interval' and iv[1] == iv[2], 'defect interval not exact'); return int(iv[1])

# review 4 F1: every field of a Checked/Refuted envelope is recomputed and
# compared, not only Status/Value/Evidence.  A forged Claim, Binding, Scope,
# Assumptions or Assurance must not replay.
HEADS = ['Status', 'Claim', 'Binding', 'Scope', 'Value', 'Evidence', 'Assumptions', 'Assurance']
SCOPE_FIXED = [['Fragment', 'M0-EnumeratedDeterministic'], ['InitialStates', 'AllDeclared'],
               ['ReachableStates', 'AllDeclared'], ['Horizon', 'Unbounded'], ['Discount', '1'],
               ['PolicyClass', 'None']]
REP_REQUESTS = ('MeasureNow', 'CheckUpdates', 'CheckNow', 'InduceExact')

def expected_binding(M, D, q):
    need(isinstance(q, list) and q, 'request is not a form')
    h = q[0]
    if h in REP_REQUESTS:
        r = rep_of(M, q[1])
        src, tgt, tol = r['machine'], M.map[r['encode']]['to'], r['tol']
        subj = ['Subject', ['Representation', q[1]], ['Machine', src]]
    elif h == 'CheckAbstractionMap':
        need(q[1] in M.abs, 'unknown abstraction map %s' % q[1]); a = M.abs[q[1]]
        src, tgt, tol = src_view(M, D, a['source'])['id'], view_machine(M, a['target'])['id'], 'Exact'
        subj = ['Subject', ['AbstractionMap', q[1]], ['Source', src], ['Target', tgt]]
    elif h == 'Then':
        need(len(q) == 3, 'Then needs two arrows')
        src, tol = arrow(M, D, q[1])[0]['id'], 'Exact'; tgt = arrow(M, D, q[2])[1]['id']
        subj = ['Subject', ['First', q[1][1]], ['Second', q[2][1]]]
    else: raise Fail('request %s has no M0 replay rule' % h)
    return ['Binding', ['Module', M.name], ['Digest', ('str', M.digest)], subj,
            ['Source', src], ['Target', tgt], ['Interface', ['Tolerance', tol]]]

def envelope_ok(M, D, q, env, st):
    heads = [x[0] if isinstance(x, list) and x else None for x in env[1:]]
    need(env[0] == 'Result' and heads == HEADS, 'envelope fields %s, expected %s' % (heads, HEADS))
    need(show(find(env, 'Claim')) == show(['Claim', q, ['Equality', 'Literal']]), 'Claim differs from the request')
    need(show(find(env, 'Binding')) == show(expected_binding(M, D, q)), 'Binding differs from the recomputed binding')
    need(show(find(env, 'Scope')) == show(['Scope', ['Profile', M.profile]] + SCOPE_FIXED), 'Scope differs from the M0 scope')
    need(find(env, 'Assumptions') == ['Assumptions'], 'M0 results carry no assumptions')
    ground = 'Witness' if st == 'Refuted' else 'Replayed'
    need(show(find(env, 'Assurance')) == show(['Assurance', ['Policy', 'M0-ExactReplay'], ['Replayed', 'True'], ['Ground', ground]]),
         'Assurance differs from the recomputed assurance')

# review-fixes review 1 F1: the Value and the Evidence heads are rebuilt from
# the request and the recomputation and compared whole, so a forged flag,
# bound, kind, source or target cannot replay.
def DEF(d): return ['Defect', ['Interval', str(d), str(d)]]
def value_is(val, exp): need(show(val) == show(exp), 'Value differs from the recomputed value %s' % show(exp))
def evidence_one(evd, head):
    need(len(evd) == 2 and isinstance(evd[1], list) and evd[1] and evd[1][0] == head, 'Evidence must be exactly one %s' % head)
    return evd[1]
def cert_ok(c, fixed, rest):
    heads = [x[0] if isinstance(x, list) and x else None for x in c[1:]]
    need(heads == [f[0] for f in fixed] + rest, 'certificate fields %s' % heads)
    for f in fixed: need(show(find(c, f[0])) == show(f), 'certificate %s differs from %s' % (f[0], show(f)))
def parse_bound(t):
    # review-fixes review 1 F3: accept what dcalc's strtod accepts (hex floats too)
    need(isinstance(t, str), 'Within bound is not a number')
    try: return float(t)
    except ValueError: pass
    try: return float.fromhex(t)
    except ValueError: raise Fail('Within bound %s is not a number' % t)

def replay(M, D, req, env):
    st = find(env, 'Status')[1]
    if st not in ('Checked', 'Refuted'): return 'skip'
    need(find(find(env, 'Binding'), 'Digest')[1][1] == M.digest, 'digest mismatch')
    dname = None
    if isinstance(req, str): need(req in D, 'unknown derive'); dname = req; req = D[req]
    envelope_ok(M, D, req, env, st)
    val = find(env, 'Value')[1]; evd = find(env, 'Evidence')
    h = req[0]
    if h in ('MeasureNow', 'CheckUpdates', 'CheckNow'):
        # review 4 F5: CheckNow is the Current obligation against a Within bound
        r = rep_of(M, req[1]); kind = 'Update' if h == 'CheckUpdates' else 'Current'
        d = defect_of(val); bound = 0.0; btxt = '0'
        if h != 'MeasureNow':
            w = find(req, 'Within'); btxt = w[1] if w else '0'; bound = parse_bound(btxt)
            need((st == 'Checked') == (d <= bound), 'status disagrees with defect and bound')
        else: need(st == 'Checked', 'MeasureNow reports a measurement')
        c, w = find(evd, 'Certificate'), find(evd, 'Witness')
        if d == 0:
            need(c is not None, 'defect 0 needs a certificate')
            need(find(c, 'Checks') == ['Checks', kind], 'certificate checks the wrong obligation')
            blocks_ok(M, r, find(c, 'Blocks'), kind == 'Update')
        else: need(w is not None and d == 1, 'defect 1 needs a witness'); witness_fail(M, r, kind, w[1])
        dd = 0 if obligation_fail(M, r, kind) is None else 1
        need(d == dd, 'defect differs from the recomputed defect')
        value_is(val, ['DefectMeasurement', DEF(dd), ['Equality', 'Literal']] if h == 'MeasureNow'
                 else ['DefectCheck', DEF(dd), ['Bound', btxt], ['Equality', 'Literal']])
        if dd == 0: cert_ok(evidence_one(evd, 'Certificate'), [['Kind', 'Prefixpoint'], ['Codes', 'Tolerance' if r['all'] else 'Literal'], ['Checks', kind]], ['Blocks'])
        else: evidence_one(evd, 'Witness')
    elif h == 'InduceExact':
        r = rep_of(M, req[1])
        if st == 'Checked':
            obligations_hold(M, r); fib = find(find(evd, 'Certificate'), 'Fibers')
            e = enc(M, r); seen = []
            for F in fib[1:]:
                for s in F[2:]: need(e[key(s)] == key(F[1]), 'fiber code wrong'); seen.append(key(s))
            need(sorted(seen) == sorted(key(s) for s in M.car[M.mach[r['machine']]['states']]), 'fibers do not partition')
            need(len(set(key(F[1]) for F in fib[1:])) == len(fib) - 1, 'two fibers share a code')
            cert_ok(evidence_one(evd, 'Certificate'), [['Kind', 'Prefixpoint']], ['Checks', 'Fibers'])
            value_is(val, ['ExactAbstraction', DEF(0), ['Machine', ['Output', dname or '?', 'Machine']],
                           ['States', str(len(fib) - 1)], ['Encode', r['encode']]])
        else:
            k = find(evd, 'Obligation')[1]; order = ['Current', 'Update', 'Congruence']
            for prev in order[:order.index(k)]: need(obligation_fail(M, r, prev) is None, 'an earlier obligation fails')
            witness_fail(M, r, k, find(evd, 'Witness')[1])
            value_is(val, ['Refutation', ['Obligation', k]])
    elif h in ('CheckAbstractionMap', 'Then'):
        if h == 'CheckAbstractionMap':
            a = M.abs[req[1]]; sv, tv = src_view(M, D, a['source']), view_machine(M, a['target'])
            f = {s: M.map[a['map']]['f'][s] for s in sv['states']}
            same_interface(sv, tv)
        else:
            s1, t1, f1 = arrow(M, D, req[1]); s2, t2, g = arrow(M, D, req[2])
            need(t1['id'] == s2['id'], 'interface mismatch'); sv, tv = s1, t2; f = {s: g[f1[s]] for s in s1['states']}
        bad = commute_fail(sv, tv, f)
        if st == 'Refuted':
            need(bad is not None, 'refuted map commutes')
            value_is(val, ['Refutation', ['Obligation', 'Commutation']])
            # review 2 F2: the witness itself must replay, not just "some commutation fails"
            w = find(evd, 'Witness')[1]
            need(isinstance(w, list) and len(w) == 5 and w[0] == 'CommutationWitness', 'CommutationWitness expected')
            stf, port, L, R = w[1], w[2], w[3], w[4]
            need(stf[0] == 'State' and L[0] == 'Left' and R[0] == 'Right' and len(port) == 2, 'malformed CommutationWitness')
            s = key(stf[1]); lab = port[1]
            need(s in sv['states'] and f.get(s) in tv['states'], 'witness state not a source state')
            if port[0] == 'Observe':
                need(lab in sv['obs'] and lab in tv['obs'], 'witness names no shared observation')
                left, right = sv['obs'][lab][s], tv['obs'][lab][f[s]]
            elif port[0] == 'Action':
                need(lab in sv['act'] and lab in tv['act'], 'witness names no shared action')
                left, right = f[sv['act'][lab][s]], tv['act'][lab][f[s]]
            else:
                raise Fail('witness port must be Observe or Action')
            need(key(L[1]) == left and key(R[1]) == right, 'witness sides differ from the recomputed sides')
            need(left != right, 'witness sides agree: no commutation failure')
            return 'ok'
        need(bad is None, 'checked map does not commute')
        rows = {key(x[1]): key(x[2]) for x in find(find(evd, 'Certificate'), 'Table')[1:]}
        need(rows == f, 'certificate table differs from the recomputed map')
        surj = set(f.values()) == set(tv['states'])
        kd = ['Kind', 'Quotient' if surj else 'Homomorphism']
        if h == 'CheckAbstractionMap':
            value_is(val, ['CheckedAbstractionMap', kd, ['Surjective', 'True' if surj else 'False']])
        else:
            value_is(val, ['ComposedArrow', ['Source', sv['id']], ['Target', tv['id']], kd])
        cert_ok(evidence_one(evd, 'Certificate'), [['Kind', 'rule'], ['Rule', 'Commutation' if h == 'CheckAbstractionMap' else 'Composition']], ['Table'])
    else: raise Fail('request %s has no M0 replay rule' % h)
    return 'ok'

def main(fixture, output):
    forms = parse(open(fixture, encoding='utf-8', errors='replace').read())
    import replay_graded as G   # M2: graded results replay through the independent graded checker
    mods = {f[1]: (Module(f), derives(None, f)) for f in forms if isinstance(f, list) and f and f[0] == 'DC.Module'}
    import replay_sym as SY   # M3: symbolic modules replay through the independent symbolic checker
    smods = {f[1]: SY.SymM(f) for f in forms if isinstance(f, list) and f and f[0] == 'DC.Module' and SY.is_symbolic(f)}
    gmods = {f[1]: G.GModule(f) for f in forms if isinstance(f, list) and f and f[0] == 'DC.Module' and f[1] not in smods}
    n_ok = n_skip = n_bad = 0
    for line in open(output):
        if ' => ' not in line: continue
        head, env = line.rstrip('\n').split(' => ', 1)
        mname, req = head.split(' ', 1); req = parse(req)[0]; env = parse(env)[0]
        try:
            M, D = mods[mname]
            if mname in smods: r = SY.replay(smods[mname], D, M.digest, req, env)
            else: r = G.replay(gmods[mname], req, env) if G.is_graded(gmods[mname], req) else replay(M, D, req, env)
            if r == 'ok': n_ok += 1
            else: n_skip += 1
        except (Fail, G.GFail, KeyError, IndexError, TypeError, ValueError, AssertionError, ZeroDivisionError) as ex:
            n_bad += 1; print('REPLAY FAIL %s %s: %s' % (mname, show(req), ex))
    print('replay: %d replayed, %d not Checked/Refuted, %d failed' % (n_ok, n_skip, n_bad))
    return 1 if n_bad else 0

if __name__ == '__main__':
    # replay_sym/replay_graded do 'from replay import Fail': alias this module so they
    # raise the same Fail class main() catches (review 1 F6), not a second import's.
    sys.modules.setdefault('replay', sys.modules['__main__'])
    sys.exit(main(sys.argv[1], sys.argv[2]))
