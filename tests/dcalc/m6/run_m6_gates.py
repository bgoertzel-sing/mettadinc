#!/usr/bin/env python3
"""M6 gates (t-2026-11-13-mettadinc-m6): Contracts/Hives/Transfers opt-in, both modes, independent replay, tamper canaries."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DCALC = os.path.join(ROOT, 'build/dcalc/dcalc'); OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m6')); os.makedirs(OUT, exist_ok=True)
FX = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures')
RP = os.path.join(HERE, 'replay_m6.py'); fails = 0
def report(name, ok, detail=''):
    global fails; fails += not ok; print('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
def st(l): m = re.search(r'\(Status (\w+)\)', l); return m.group(1) if m else '?'
def rows(txt): return [l for l in txt.splitlines() if ' => ' in l]
def replay(fx, out):
    t = subprocess.run([sys.executable, RP, fx, out], capture_output=True, text=True, timeout=120)
    return t.returncode, (t.stdout.strip().splitlines() or [''])[-1]
# (fixture, module whose rows are M6 Contracts rows, their expected beyond-release statuses); rows of other
# modules belong to earlier milestones and must answer the same status in both modes
CASES = (('affine_contracts.metta', 'AffineContracts', ['Checked', 'Checked', 'Refuted']),
         ('receipt_packets.metta', 'PacketMerges', ['Checked', 'Refuted']),
         ('parity_triangle.metta', 'ParityTriangle', ['Refuted', 'Checked', 'Checked', 'Checked']),
         ('skill_hive.metta', 'SkillHive|SkillHiveOriented|TickLibrary', ['Refuted', 'Checked', 'Checked', 'Checked', 'Checked', 'Refuted', 'Refuted', 'Checked', 'Checked', 'Refuted', 'Checked', 'Checked', 'Refuted', 'Refuted']),
         (os.path.join(HERE, 'fixtures', 'holo3.metta'), 'Holo3', ['Checked', 'Checked']))   # review-1 F3: (phi, iota^-1) in G
ismod = lambda l, mod: l.split(' ', 1)[0] in mod.split('|')   # mod may name several modules: 'A|B'
mine = lambda ls, mod: [l for l in ls if ismod(l, mod)]
for fx, mod, want in CASES:
    f = os.path.join(FX, fx); base = os.path.basename(fx)[:-6]   # fx may be an absolute path (review fixtures)
    r = subprocess.run([DCALC, f], capture_output=True, text=True, timeout=120); rel = rows(r.stdout); got = [st(l) for l in mine(rel, mod)]
    report('%s release mode: every answer Unsupported' % base, got == ['Unsupported'] * len(want), str(got))
    r = subprocess.run([DCALC, '--beyond-release', f], capture_output=True, text=True, timeout=120)
    o = os.path.join(OUT, base + '.out'); open(o, 'w').write(r.stdout); allr = rows(r.stdout); ls = mine(allr, mod); got = [st(l) for l in ls]
    oth = lambda X: [(l.split(' => ')[0], st(l)) for l in X if not ismod(l, mod)]
    report('%s other-module rows: same statuses in both modes' % base, oth(rel) == oth(allr), '%d rows' % len(oth(allr)))
    report('%s beyond-release statuses' % base, got == want, str(got))
    report('%s every Checked/Refuted row says Replayed True' % base, all('(Replayed True)' in l for l in ls if st(l) in ('Checked', 'Refuted')))
    rc, last = replay(f, o); report('%s independent replay' % base, rc == 0 and last.endswith('PASS'), last[:70])
    # canaries: each single edit must be rejected by the replayer
    full = r.stdout.splitlines(); idx = [i for i, l in enumerate(full) if ' => ' in l and ismod(l, mod)]
    edits = []
    for i in idx:
        l = full[i]
        if st(l) == 'Checked': edits.append(('Checked->Refuted', i, l.replace('(Status Checked)', '(Status Refuted)', 1)))
        if st(l) == 'Refuted':
            edits.append(('Refuted->Checked', i, l.replace('(Status Refuted)', '(Status Checked)', 1)))
            edits.append(('OutputGap changed', i, re.sub(r'\(OutputGap \(Rat (-?\d+) (\d+)\)\)', lambda m: '(OutputGap (Rat %d %s))' % (int(m.group(1)) + 1, m.group(2)), l, 1)))
            edits.append(('witness not audited', i, re.sub(r'\(Audited \((Rat -?\d+ \d+|Tuple [^()]*)\)\)', lambda m: '(Audited (Rat 7777 1))' if m.group(1).startswith('Rat') else '(Audited (Tuple Nowhere Nowhere))', l, 1)))
            edits.append(('witness pair swapped to a meeting pair', i, re.sub(r'\(Reference \((Rat -?\d+ \d+|Tuple [^()]*)\)\)', lambda m: '(Reference (Rat 1 1))' if m.group(1).startswith('Rat') else '(Reference (Tuple Empty Empty))', l, 1)))
        g = re.search(r'\(Value \(Grade \(Rat (-?\d+) (\d+)\) \(Rat (-?\d+) (\d+)\)\)\)', l)
        v = re.search(r'\(Value \(Rat (-?\d+) (\d+)\)\)', l)
        dd = re.search(r'\(Defect \(Rat (-?\d+) (\d+)\)\)', l)
        if dd: edits.append(('Defect changed', i, l.replace(dd.group(0), '(Defect (Rat %d %s))' % (int(dd.group(1)) + 1, dd.group(2)), 1)))
        if v: edits.append(('scalar Value changed', i, l.replace(v.group(0), '(Value (Rat %d %s))' % (int(v.group(1)) + 1, v.group(2)), 1)))
        if g: edits.append(('Grade eta changed', i, l.replace(g.group(0), '(Value (Grade (Rat %s %s) (Rat %d %s)))' % (g.group(1), g.group(2), int(g.group(3)) + 1, g.group(4)), 1)))
    for k, (nm, i, nl) in enumerate(edits):
        if nl == full[i]: continue   # edit not applicable to this row shape
        t = list(full); t[i] = nl; tp = os.path.join(OUT, '%s_canary%d.out' % (base, k)); open(tp, 'w').write('\n'.join(t) + '\n')
        rc, last = replay(f, tp); report('%s canary %d (%s, row %d) rejected' % (base, k, nm, idx.index(i) + 1), rc != 0, last[:60])
    report('%s canaries: at least one per row' % base, sum(1 for nm, i, nl in edits if nl != full[i]) >= len(idx), '%d applied' % sum(1 for nm, i, nl in edits if nl != full[i]))
# negative gates (MILESTONES.md M6, negative tests 1-8; review-1 F2): mutants of skill_hive built at run time
SH = os.path.join(FX, 'skill_hive.metta'); _s = open(SH).read(); _i = _s.index('!(dc.run SkillHive'); SH_BODY, SH_REQS = _s[:_i], _s[_i:]
def neg(name, body, reqs):
    f = os.path.join(OUT, 'neg_%s.metta' % name); open(f, 'w').write(body + reqs)
    t = subprocess.run([DCALC, '--beyond-release', f], capture_output=True, text=True, timeout=60)
    return rows(t.stdout)
def run1(name, req): return neg(name, SH_BODY, '!(dc.run SkillHive %s)\n' % req)
r = run1('n1', '(ComposeTransfers (Output GoodCAchecked Transfer) (Output BCchecked Transfer) (Output ABchecked Transfer))')
report('neg1 wrong-direction composition -> InvalidInput', [st(l) for l in r] == ['InvalidInput'], r[0][-80:] if r else 'no row')
r = run1('n2', '(CheckKernelCoherence (Output GoodCAchecked Transfer))')
report('neg2 checked transfer read as a kernel/hive -> InvalidInput', [st(l) for l in r] == ['InvalidInput'], r[0][-80:] if r else 'no row')
_g = '    (Gauge A MirrorA) (Gauge B MirrorB) (Gauge C MirrorC))'; assert SH_BODY.count(_g) == 1
r = [l for l in neg('n3a', SH_BODY.replace(_g, '    (Gauge A MirrorA))'), SH_REQS) if '(Output Saturated Hive)' in l and 'CheckKernelCoherence' in l]
report('neg3a gauge saturated only at the base member -> Refuted with an intransitive triple', len(r) == 1 and st(r[0]) == 'Refuted' and '(Witness (Triple' in r[0], str([st(l) for l in r]))
_m = '(Symmetry MirrorB (Of B) (States flip-state) (Methods flip-method))'; assert SH_BODY.count(_m) == 1
r = [l for l in neg('n3b', SH_BODY.replace(_m, '(Symmetry MirrorB (Of B) (States same-state) (Methods same-method))'), SH_REQS) if '(Output Saturated Hive)' in l and 'CheckKernelCoherence' in l]
report('neg3b gauges at every member but not intertwined -> Refuted with an intransitive triple', len(r) == 1 and st(r[0]) == 'Refuted' and '(Witness (Triple' in r[0], str([st(l) for l in r]))
_e = '(Derive Saturated (KernelOf Beacons (Saturate Gauge))))'; assert SH_BODY.count(_e) == 1
_b7 = SH_BODY.replace(_e, '(Derive Saturated (KernelOf Beacons (Saturate Gauge)))\n  (Derive VPBad (CheckValuePullback BadCA)))')
r = neg('n7', _b7, ''.join('!(dc.run SkillHive %s)\n' % q for q in [
    '(ComposeTransfers (Output ABchecked Transfer) (Output BCchecked Transfer) (Output VPBad Transfer))',
    '(ComposeTransfers (Output ABchecked Transfer) (Output BCchecked Transfer) (Output VPBad ValueCertificate))',
    '(CheckKernelCoherence (Output VPBad Transfer))']))
report('neg7 value-pullback (sensitivity) certificate used as an adequacy/transfer premise -> InvalidInput', [st(l) for l in r] == ['InvalidInput'] * 3, str([st(l) for l in r]))
GC = os.path.join(FX, 'graded_closure.metta')
t = subprocess.run([DCALC, '--beyond-release', GC], capture_output=True, text=True, timeout=60)
r = [l for l in rows(t.stdout) if '(CheckTransitive (Output Thresholded Relation)' in l]
report('neg6 thresholded closure is not an equivalence closure -> Refuted with a transitivity witness', len(r) == 1 and st(r[0]) == 'Refuted' and 'TransitivityWitness' in r[0], str([st(l) for l in r]))
AC = os.path.join(FX, 'affine_contracts.metta')
t = subprocess.run([DCALC, '--beyond-release', AC], capture_output=True, text=True, timeout=60); full = t.stdout.splitlines()
ci = [i for i, l in enumerate(full) if l.startswith('AffineContracts Composite =>')]
ok8 = len(ci) == 1 and '(Grade (Rat 6 1) (Rat 1 2))' in full[ci[0]]
if ok8:
    u = list(full); u[ci[0]] = u[ci[0]].replace('(Grade (Rat 6 1) (Rat 1 2))', '(Grade (Rat 6 1) (Rat 3 10))', 1)
    tp = os.path.join(OUT, 'neg8_unamplified.out'); open(tp, 'w').write('\n'.join(u) + '\n')
    rc, last = replay(AC, tp); ok8 = rc != 0
report('neg8 composite residual 1/10+1/5 without amplification (6, 3/10) -> rejected by the replayer', ok8, '')
# KernelOf as a request (review-1 F4): Checked with a construction certificate, replayed; one tampered entry is rejected
_kq = ''.join('!(dc.run SkillHive %s)\n' % q for q in ['(KernelOf Beacons)', '(KernelOf Beacons (Saturate Gauge))'])
kf = os.path.join(OUT, 'kernelof.metta'); open(kf, 'w').write(SH_BODY + _kq)
tb = subprocess.run([DCALC, '--beyond-release', kf], capture_output=True, text=True, timeout=60).stdout
tr = subprocess.run([DCALC, kf], capture_output=True, text=True, timeout=60).stdout
kr = rows(tb)
report('KernelOf as a request: beyond-release Checked with a construction certificate', [st(l) for l in kr] == ['Checked'] * 2 and all('(Construction (Kind KernelOf)' in l for l in kr), str([st(l) for l in kr]))
report('KernelOf as a request: release mode Unsupported', [st(l) for l in rows(tr)] == ['Unsupported'] * 2, str([st(l) for l in rows(tr)]))
ko = os.path.join(OUT, 'kernelof.out'); open(ko, 'w').write(tb)
rc, last = replay(kf, ko); report('KernelOf rows replayed (construction recomputed)', rc == 0, last)
for k, (old, new) in enumerate([(' 1) (Entry', ' 0) (Entry'), (' 0) (Entry', ' 1) (Entry')]):
    u = tb.splitlines(); i = [j for j, l in enumerate(u) if old in l]
    if not i: report('KernelOf tamper %d applicable' % k, False, 'pattern absent'); continue
    u[i[0]] = u[i[0]].replace(old, new, 1); tp = os.path.join(OUT, 'kernelof_t%d.out' % k); open(tp, 'w').write('\n'.join(u) + '\n')
    rc, last = replay(kf, tp); report('KernelOf tamper %d (entry %s->%s) rejected' % (k, old.strip()[0], new.strip()[0]), rc != 0, last)
# neg4 / neg5 have no mechanism in this milestone (review-1 F2): stated as NOT IMPLEMENTED, never counted as PASS
print('NOTE  neg4 zero-filled unmeasured correspondence: NOT IMPLEMENTED (no CompleteHive; such requests answer Unsupported, which the order does not accept as the gate)')
print('NOTE  neg5 merge claim with unmeasured receipt identities -> Unknown: NOT IMPLEMENTED (no receipt-identity/merge construct; posterior-only merge contracts answer Checked/Refuted)')
print('m6_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails)); sys.exit(1 if fails else 0)
