#!/usr/bin/env python3
"""M6 claim rows (t-2026-11-13-mettadinc-m6): release mode must answer Unsupported, --beyond-release the M6
answers; every Checked/Refuted row claiming (Replayed True) is replayed by replay_m6.py, and tampers are rejected."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FIXD = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m6'))
fails = 0
def report(name, ok, note=''):
    global fails
    fails += 0 if ok else 1
    print('%-70s %s  %s' % (name[:70], 'PASS' if ok else 'FAIL', note))
def norm(s): return re.sub(r'\s+', ' ', s.strip())
def st(line):
    m = re.search(r'\(Result \(Status (\w+)\)', line or ''); return m.group(1) if m else None
def run(fx, beyond):
    r = subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [fx], capture_output=True, text=True, timeout=120)
    return r.stdout
ROWS = [
    ('A01', 'affine_contracts.metta', 'AffineContracts', 'Composite', 'Checked', [r'\(Value \(Grade \(Rat 6 1\) \(Rat 1 2\)\)\)']),
    ('A02', 'affine_contracts.metta', 'AffineContracts', '(CheckImplementation Direct (Grade 6 (Rat 1 2)))', 'Checked', [r'\(Value \(Grade \(Rat 6 1\) \(Rat 1 2\)\)\)']),
    ('A03', 'affine_contracts.metta', 'AffineContracts', '(CheckImplementation Direct (Grade 6 (Rat 3 10)))', 'Refuted', [r'\(Witness \(Pair']),
]
os.makedirs(OUT, exist_ok=True); outs = {}
for f in sorted({r[1] for r in ROWS}):
    for beyond in (False, True):
        txt = run(os.path.join(FIXD, f), beyond); outs[(f, beyond)] = txt
        open(os.path.join(OUT, f.split('.')[0] + ('_beyond' if beyond else '_release') + '.out'), 'w').write(txt)
def line_of(f, beyond, mod, req):
    for l in outs[(f, beyond)].splitlines():
        if ' => ' in l:
            h = l.split(' => ', 1)[0]; m, q = h.split(' ', 1)
            if m == mod and norm(q) == norm(req): return l
    return None
for cid, f, mod, req, want, pats in ROWS:
    s = st(line_of(f, False, mod, req)); report('%s release: Unsupported' % cid, s == 'Unsupported', str(s))
    l = line_of(f, True, mod, req); s = st(l)
    report('%s %s %s' % (cid, req[:40], want), s == want and all(re.search(p, l or '') for p in pats), str(s))
REP = os.path.join(HERE, 'replay_m6.py')
def replay(fx, outp):
    t = subprocess.run([sys.executable, REP, fx, outp], capture_output=True, text=True, timeout=120)
    return t.returncode, (t.stdout.strip().splitlines() or [''])[-1]
for f in sorted({r[1] for r in ROWS}):
    rc, last = replay(os.path.join(FIXD, f), os.path.join(OUT, f.split('.')[0] + '_beyond.out'))
    report('%s independent replay (replay_m6.py)' % f, rc == 0, last[:60])
# tamper canaries: one edit per replayed evidence kind; each must be REJECTed
CAN = (('composite Grade eta lowered', 'affine_contracts.metta', 'AffineContracts Composite', '(Value (Grade (Rat 6 1) (Rat 1 2)))', '(Value (Grade (Rat 6 1) (Rat 1 4)))'),
       ('Checked claim with eta lowered below the worst gap', 'affine_contracts.metta', 'AffineContracts (CheckImplementation Direct (Grade 6 (Rat 1 2)))', '(Claim (CheckImplementation Direct (Grade 6 (Rat 1 2)))', '(Claim (CheckImplementation Direct (Grade 6 (Rat 1 5)))'),
       ('Refuted witness OutputGap edited', 'affine_contracts.metta', 'AffineContracts (CheckImplementation Direct (Grade 6 (Rat 3 10)))', '(OutputGap (Rat 1 2))', '(OutputGap (Rat 1 3))'))
for name, f, key, a, b in CAN:
    ls = outs[(f, True)].splitlines(); i = next((k for k, l in enumerate(ls) if l.startswith(key + ' => ') and a in l), None)
    if i is None: report('M6 canary: %s is rejected' % name, False, 'row/pattern absent'); continue
    ls[i] = ls[i].replace(a, b, 1); tp = os.path.join(OUT, 'm6_tamper.out'); open(tp, 'w').write('\n'.join(ls) + '\n')
    rc, last = replay(os.path.join(FIXD, f), tp)
    report('M6 canary: %s is rejected' % name, rc != 0, last[:60])
print('m6_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
