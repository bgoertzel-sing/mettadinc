#!/usr/bin/env python3
"""M6 gates (t-2026-11-13-mettadinc-m6): Contracts opt-in, both modes, independent replay, tamper canaries."""
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
CASES = (('affine_contracts.metta', ['Checked', 'Checked', 'Refuted']),)
for fx, want in CASES:
    f = os.path.join(FX, fx); base = fx[:-6]
    r = subprocess.run([DCALC, f], capture_output=True, text=True, timeout=120); got = [st(l) for l in rows(r.stdout)]
    report('%s release mode: every answer Unsupported' % base, got == ['Unsupported'] * len(want), str(got))
    r = subprocess.run([DCALC, '--beyond-release', f], capture_output=True, text=True, timeout=120)
    o = os.path.join(OUT, base + '.out'); open(o, 'w').write(r.stdout); ls = rows(r.stdout); got = [st(l) for l in ls]
    report('%s beyond-release statuses' % base, got == want, str(got))
    report('%s every Checked/Refuted row says Replayed True' % base, all('(Replayed True)' in l for l in ls if st(l) in ('Checked', 'Refuted')))
    rc, last = replay(f, o); report('%s independent replay' % base, rc == 0 and last.endswith('PASS'), last[:70])
    # canaries: each single edit must be rejected by the replayer
    full = r.stdout.splitlines(); idx = [i for i, l in enumerate(full) if ' => ' in l]
    edits = []
    for i in idx:
        l = full[i]
        if st(l) == 'Checked': edits.append(('Checked->Refuted', i, l.replace('(Status Checked)', '(Status Refuted)', 1)))
        if st(l) == 'Refuted':
            edits.append(('Refuted->Checked', i, l.replace('(Status Refuted)', '(Status Checked)', 1)))
            edits.append(('OutputGap changed', i, re.sub(r'\(OutputGap \(Rat (-?\d+) (\d+)\)\)', lambda m: '(OutputGap (Rat %d %s))' % (int(m.group(1)) + 1, m.group(2)), l, 1)))
            edits.append(('witness not audited', i, re.sub(r'\(Audited \(Rat (-?\d+) (\d+)\)\)', '(Audited (Rat 7777 1))', l, 1)))
        g = re.search(r'\(Value \(Grade \(Rat (-?\d+) (\d+)\) \(Rat (-?\d+) (\d+)\)\)\)', l)
        if g: edits.append(('Grade eta changed', i, l.replace(g.group(0), '(Value (Grade (Rat %s %s) (Rat %d %s)))' % (g.group(1), g.group(2), int(g.group(3)) + 1, g.group(4)), 1)))
    for k, (nm, i, nl) in enumerate(edits):
        if nl == full[i]: report('%s canary %d %s' % (base, k, nm), False, 'edit did not apply'); continue
        t = list(full); t[i] = nl; tp = os.path.join(OUT, '%s_canary%d.out' % (base, k)); open(tp, 'w').write('\n'.join(t) + '\n')
        rc, last = replay(f, tp); report('%s canary %d (%s, row %d) rejected' % (base, k, nm, idx.index(i) + 1), rc != 0, last[:60])
print('m6_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails)); sys.exit(1 if fails else 0)
