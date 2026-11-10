#!/usr/bin/env python3
"""M2 negative gates and the replay mutation set (t-2026-11-10-mettadinc-m2-v2).

Part A, claim gates: the producer refuses each gate as the milestone says.
Part B, fixture-variant gates (OQ12: gates that name no fixture are written here).
Part C, replay mutations: forged results that replay.py must reject.  Every
mutated line first passes a canary (the unmodified line replays).
A refusal by Unsupported never counts as a refusal."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); TD = os.path.dirname(HERE)
sys.path.insert(0, TD)
import replay as R
import check_claims_m2 as C

FIX = os.path.join(C.PKG, 'fixtures'); OUT = C.OUT
rows = C.m2_table(); cache = {}; fails = []
def line_of(cid):
    row = rows[cid]; p = C.fixture_of(row)
    if p not in cache: cache[p] = C.run_fixture(p)
    return p, cache[p][2].get((row['module'], row['request']))
def env_of(line): return R.parse(line.split(' => ', 1)[1])[0]
def st(env): return R.find(env, 'Status')[1]
def val(env): return R.find(env, 'Value')[1]
def report(name, ok, note):
    print('%-44s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
    if not ok: fails.append(name)

# ---- A: claim gates ----
def gate(name, cid, want, check=None):
    _, line = line_of(cid); e = env_of(line) if line else None
    s = st(e) if e else 'missing'; ok = s == want and s != 'Unsupported'
    note = '%s %s' % (cid, s)
    if ok and check:
        try: ok, extra = check(e); note += ' ' + extra
        except Exception as ex: ok, note = False, note + ' ERR %s' % ex
    report(name, ok, note)
gate('1 E05 exact induction refused', 'E05', 'Refuted', lambda e: (R.find(val(e), 'Obligation')[1] == 'Update', 'obligation Update'))
for cid, want in (('H05', 'Checked'), ('H06', 'Checked'), ('H07', 'Refuted')):
    gate('2 horizon Phi^{h+1}(1) %s' % cid, cid, want)
gate('3 H01 trivial tolerance: Observer equality', 'H01', 'Checked', lambda e: (R.find(val(e), 'Equality') == ['Equality', 'Observer'], 'Equality Observer'))
gate('3 H02 decoders only into Y/~0', 'H02', 'Checked', lambda e: (R.find(val(e), 'Decoders') == ['Decoders', 'ZeroDistanceQuotient'], 'ZeroDistanceQuotient'))
gate('4 H03 refutation on the full carrier', 'H03', 'Refuted')
gate('4 H04 refutation not transported to {a}', 'H04', 'Checked')
gate('5 H12 homomorphism not a quotient', 'H12', 'Checked', lambda e: (R.find(val(e), 'Kind') == ['Kind', 'Homomorphism'], 'Kind Homomorphism'))
gate('6 P05 check within 3/20', 'P05', 'Checked')
gate('6 P06 check within 1/10 refused', 'P06', 'Refuted')
gate('6 P04 the measurement itself succeeds', 'P04', 'Checked')

# ---- B: fixture-variant gates ----
def variant(name, fixture, old, new, extra, module, req, want, reason=None):
    src = open(os.path.join(FIX, fixture), encoding='utf-8').read()
    if old and src.count(old) != 1: report(name, False, 'variant text not found once'); return
    if old: src = src.replace(old, new)
    os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, 'gate-%s.metta' % re.sub(r'\W+', '_', name)[:40])
    open(p, 'w').write(src + extra); rc, out, lines = C.run_fixture(p); line = lines.get((module, req))
    e = env_of(line) if line else None; s = st(e) if e else 'missing'
    rs = R.find(e, 'Reason') if e else None; why = rs[1][1] if rs and isinstance(rs[1], tuple) else (rs[1] if rs else '')
    ok = s == want and (reason is None or reason in str(why))
    report(name, ok, '%s %s' % (s, str(why)[:90]))
STAY = '(Map stay     (From Two) (To Two)   (Cases (a a) (b b)))'
variant('7 update leaving its carrier', 'hypotheses.metta', STAY, STAY.replace('(b b)', '(b c)'), '',
        'ObserverEquality', '(MeasureNow BlindConstant)', 'InvalidInput')
variant('8 overlapping cases that agree', 'hypotheses.metta', STAY, STAY.replace('(b b)', '($x $x)'), '',
        'ObserverEquality', '(MeasureNow BlindConstant)', 'InvalidInput', 'overlapping cases are rejected')
es = open(os.path.join(FIX, 'eight_state.metta'), encoding='utf-8').read()
mk = re.search(r'\(Representation\s+KeepA\s+\(Of\s+(\w+)\)', es); stc = re.search(r'\(Machine\s+%s\s+\(States\s+(\w+)\)' % (mk.group(1) if mk else '?'), es)
if mk and stc:
    anchor = es[es.index('(Representation KeepA'):].split('\n')[0]
    fine = '(Map fine-id (From %s) (To %s) (Cases ($s $s)))\n  (Representation Fine (Of %s) (Encode fine-id))\n  %s' % (stc.group(1), stc.group(1), mk.group(1), anchor)
    variant('9 stable, not coarsest: sufficient', 'eight_state.metta', anchor, fine,
            '\n!(dc.run EightState (CheckUpdates Fine))\n', 'EightState', '(CheckUpdates Fine)', 'Checked')
    variant('9 stable, not coarsest: not the coarsest', 'eight_state.metta', anchor, fine,
            '\n!(dc.run EightState (SamePartition (Output Repair Representation) Fine))\n', 'EightState',
            '(SamePartition (Output Repair Representation) Fine)', 'Refuted')
else: report('9 stable, not coarsest', False, 'KeepA machine not found')

# ---- C: replay mutation set ----
def replay_one(path, line, tag):
    p = os.path.join(OUT, 'mut-%s.out' % tag); open(p, 'w').write(line + '\n')
    r = subprocess.run([sys.executable, os.path.join(TD, 'replay.py'), path, p], capture_output=True, text=True)
    return r.returncode, r.stdout
def mutation(tag, cid, fn, donor=None):
    path, line = line_of(cid)
    if not line: report('M ' + tag, False, 'no line for %s' % cid); return
    rc, out = replay_one(path, line, tag + '-canary')
    if rc or 'replay: 1 replayed' not in out: report('M ' + tag, False, 'canary did not replay: ' + out.strip()[-120:]); return
    e = env_of(line)
    if donor: fn(e, env_of(line_of(donor)[1]))
    else: fn(e)
    forged = line.split(' => ', 1)[0] + ' => ' + R.show(e)
    if forged == line: report('M ' + tag, False, 'mutation changed nothing'); return
    rc, out = replay_one(path, forged, tag)
    ok = rc != 0 and 'REPLAY FAIL' in out
    report('M ' + tag, ok, 'rejected: ' + (out.split(': ', 2)[-1].strip().splitlines()[0][:80] if ok else 'ACCEPTED'))
def setf(env, *path_val):
    *path, v = path_val; x = env
    for h in path: x = R.find(x, h) if h != '#1' else x[1]
    x[1] = v
def wit(env): return C.witness(env)
mutation('E03 witness word emptied', 'E03', lambda e: R.find(wit(e), 'Word').__delitem__(slice(1, None)))
mutation('P04 discounted defect changed', 'P04', lambda e: R.find(val(e), 'Defect').__setitem__(1, ['Interval', '3/20', '3/20']))
def misread(e, d):   # H07 (h=2) answered with the h=1 reading
    for h in ('Status', 'Value', 'Evidence'): R.find(e, h)[:] = R.find(d, h)
mutation('H07 horizon misread as Phi^h(1)', 'H07', misread, donor='H06')
mutation('P06 bound check flipped to Checked', 'P06', lambda e: setf(e, 'Status', 'Checked'))
mutation('E06 Repair replaced by singletons', 'E06', lambda e: R.find(val(e), 'Partition').__setitem__(
    slice(1, None), [['Block', x] for B in R.find(val(e), 'Partition')[1:] for x in B[1:]]))
mutation('H02 Observer reported as Literal', 'H02', lambda e: setf(e, 'Claim', 'Equality', 'Literal'))
mutation('H04 refutation transported', 'H04', lambda e: setf(e, 'Status', 'Refuted'))
mutation('H12 homomorphism reported as quotient', 'H12', lambda e: setf(val(e), 'Kind', 'Quotient'))
mutation('P08 weakness inflated', 'P08', lambda e: setf(val(e), 'Weakness', '3/4'))
mutation('P10 merge witness results swapped', 'P10', lambda e: R.find(wit(e), 'Results').reverse())
mutation('G04 witness triple made transitive', 'G04', lambda e: R.find(wit(e), 'Triple').__setitem__(slice(1, None), [R.find(wit(e), 'Triple')[1]] * 3))

print('run_m2_gates: %s (%d failing)' % ('PASS' if not fails else 'FAIL', len(fails)))
sys.exit(1 if fails else 0)
