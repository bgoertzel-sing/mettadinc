#!/usr/bin/env python3
"""M4 claim rows S01-S07 and negative gates (t-2026-11-11-mettadinc-m4).

Runs build/dcalc/dcalc on seven_state.metta, once by default (release 1: every
request must answer Unsupported) and once with --beyond-release (the M4
answers).  Negative cases are inline source mutations written to DCALC_OUT;
no fixture under tests/dcalc/mutations/ is named.  Exit 0 iff all pass."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FIX = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures/seven_state.metta')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m4'))
fails = 0
def report(name, ok, note=''):
    global fails
    fails += not ok; print('%-66s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
def run(src, tag, beyond=True):
    os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, tag + '.metta'); open(p, 'w').write(src)
    r = subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [p], capture_output=True, text=True, timeout=120)
    open(os.path.join(OUT, tag + '.out'), 'w').write(r.stdout)
    lines = {}
    for line in r.stdout.splitlines():
        if ' => ' in line: head = line.split(' => ', 1)[0]; mod, req = head.split(' ', 1); lines[(mod, req)] = line
    return lines
def st(line): m = re.search(r'\(Result \(Status (\w+)\)', line or ''); return m.group(1) if m else 'missing'
def has(line, pat): return re.search(pat, line or '') is not None

src = open(FIX, encoding='utf-8').read()
MB = '(MeasureBehavioral MergeXY (Discount (Rat 9 10)))'
REQS = ['Bisimulation', 'TraceClasses', 'Behavioral', MB, 'Trace', 'Linear', 'Positive']
# release 1 (default): the fixture header requires Unsupported for every request
D = run(src, 'default', beyond=False)
report('R1 default: all seven requests Unsupported', all(st(D.get(('SevenState', q))) == 'Unsupported' for q in REQS),
       ' '.join(st(D.get(('SevenState', q))) for q in REQS))
L = run(src, 'fixture')
POL = r'\(Policy M4-StochasticReplay\) \(Replayed True\)'
rows = [('S01', 'Bisimulation', 'Checked', r'\(Classes 7\).*\(Kind StrongLumping\)'),
        ('S02', 'TraceClasses', 'Checked', r'\(Block x y\).*\(Classes 6\)'),
        ('S03', 'Behavioral', 'Refuted', r'\(BehavioralDefect \(Rat 1 2\)\).*\(ModalTestWitness \(Pair y x\) \(Phi \(x \(Rat 1 2\)\) \(y 0\)\)\)'),
        ('S04', MB, 'Checked', r'\(BehavioralDefect \(Rat 81 200\)\).*\(Discount \(Rat 9 10\)\)'),
        ('S05', 'Trace', 'Checked', r'\(TraceEquivalent True\)'),
        ('S06', 'Linear', 'Checked', r'\(Dimension 5\).*\(Minor \(Columns( \w+){5}\) \(Determinant (?!0\))'),
        ('S07', 'Positive', 'Checked', r'\(Interval 5 5\).*\(SignedMinimum 5\).*\(Candidate Lpos Replayed \(States 5\)\)')]
for cid, req, want, pat in rows:
    line = L.get(('SevenState', req)); s = st(line)
    report('%s %s' % (cid, req[:40]), s == want and has(line, pat) and has(line, POL), s)
sys.exit(1 if fails else 0)
