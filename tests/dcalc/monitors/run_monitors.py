#!/usr/bin/env python3
"""Monitors gates (t-2026-11-27-mettadinc-monitors): exact CheckMonitor / Detect answers from dcalc
against hand-checked rationals (fixtures) and against the claims of the documents on their pinned streams
(doc04 StaleMonitor, doc05 LiveReceipts, doc06 WMTMReceipts). Any other answer than the exact one FAILs."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build', 'dcalc', 'dcalc'))
fails = 0
def report(name, ok, detail=''):
    global fails
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  -- %r' % (str(detail)[:300],)))
    fails += 0 if ok else 1
def run(path, beyond=True, cwd=None):
    p = subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [os.path.basename(path)],
                       capture_output=True, text=True, timeout=300, cwd=cwd or os.path.dirname(path))
    return p.returncode, [l for l in p.stdout.splitlines() if ' => (Result ' in l]
def has(line, *frags):
    return all(f in line for f in frags)
FIX = os.path.join(HERE, 'fixtures')
# ---- fixtures: hand-checked exact answers.  Up: Bernoulli 1/4 vs 1/2, factors 2 (x=1) and 2/3 (x=0);
# chi2 = (1/2)^2/(1/4) + (1/2)^2/(3/4) - 1 = 1/3.
WANT = [
 ('CheckMonitor Up',      ['(Status Checked)', '(Valid True)', '(Blind False)', '(ChiSquare (Table (Row one (Rat 1 3))))', '(NullMean (Table (Row one 1)))']),
 ('CheckMonitor Same',    ['(Status Checked)', '(Blind True)', '(ChiSquare (Table (Row one 0)))']),
 ('CheckMonitor Direct',  ['(Status Checked)', '(Blind False)', '(ChiSquare (Table (Row one (Rat 1 3))))']),
 ('Detect Up fires on Hot (2^4 >= 10)', ['(Status Estimated)', '(Fired Up) (Step 4) (Observations 4) (EValue 16) (Threshold 10)', '(Ground Statistical)']),
 ('Detect Up never fires on Cold', ['(Status Estimated)', '(Fired None) (Step None) (Observations 6) (EValue (Rat 64 243)) (Largest 2) (LargestAt 1) (Threshold 10)']),
 ('Detect Up Same, Union k/Level = 20', ['(Status Estimated)', '(Fired Up) (Step 5) (Observations 5) (EValue 32) (Threshold 20)', '(Combine Union)']),
 ('Detect Up Same, Mixture (32+1)/2 >= 10', ['(Status Estimated)', '(Fired Mixture) (Step 5) (Observations 5) (EValue (Rat 33 2)) (Threshold 10)', '(Combine Mixture)']),
 ('Detect Scheme ShiryaevRoberts', ['(Status Unsupported)', 'Scheme ShiryaevRoberts is outside the executed Monitors fragment']),
 ('Detect Level 0',       ['(Status InvalidInput)', 'Level must be a rational in (0,1)']),
]
rc, out = run(os.path.join(FIX, 'mon_values.metta'))
report('values: dcalc exit 0, %d requests' % len(WANT), rc == 0 and len(out) == len(WANT), (rc, len(out)))
for i, (nm, frags) in enumerate(WANT):
    got = out[i] if i < len(out) else ''
    report('values: ' + nm, has(got, *frags), got)
rc, out = run(os.path.join(FIX, 'mon_unsup.metta'))
for i, nm in enumerate(['CheckMonitor', 'Detect']):
    got = out[i] if i < len(out) else ''
    report('unsupported: %s Callmap answers Unsupported naming the map call' % nm,
           has(got, '(Status Unsupported)', 'the map call (half one) inside a monitor law'), got)
rc, out = run(os.path.join(FIX, 'mon_neg.metta'))
report('negative: undeclared Context carrier is InvalidInput', len(out) == 1 and has(out[0], '(Status InvalidInput)', 'undeclared name Missing'), out)
# ---- release mode: Monitors stays outside the first release
rc, out = run(os.path.join(FIX, 'mon_values.metta'), beyond=False)
report('release: every request Unsupported (not admitted in release 1)', len(out) == len(WANT) and all('(Status Unsupported)' in l for l in out), out[:1])
# ---- documents on their pinned streams
D = os.path.join(ROOT, 'docs/e0/docs')
DOC = [
 ('04_omega_memory_goals_part1/validation_bundle/memory_goals.metta', [
   ('(CheckMonitor Stale)', ['(Status Checked)', '(Blind False)', '(ChiSquare (Table (Row one (Rat 9 19))))']),
   ('(On LiveSuggestions)', ['(Status Estimated)', '(Fired Stale) (Step 21) (Observations 21) (EValue (Rat %d %d)) (Threshold 100)' % (2**72, 19**15)]),
   ('(On QuietSuggestions)', ['(Status Estimated)', '(Fired None) (Step None) (Observations 400)', '(LargestAt 36) (Threshold 100)'])]),
 ('05_live_memory_part2/validation_bundle/live_memory.metta', [
   ('(CheckMonitor StaleFifth)', ['(Status Checked)', '(ChiSquare (Table (Row one (Rat 9 19))))']),
   ('(Detect StaleFifth (On TenPercent)', ['(Status Estimated)', '(Fired StaleFifth) (Step 27) (Observations 27) (EValue (Rat %d %d))' % (2**96, 19**21)]),
   ('(Combine Mixture))', ['(Status Estimated)', '(Fired Mixture) (Step 132) (Observations 132)', '(Threshold 100)'])]),
 ('06_wmtm_worked_example/validation_bundle/wmtm_example.metta', [
   ('(CheckMonitor MissTenth)', ['(Status Checked)', '(ChiSquare (Table (Row one (Rat 1 19))))']),
   ('(CheckMonitor MissFifth)', ['(Status Checked)', '(ChiSquare (Table (Row one (Rat 9 19))))']),
   ('(CheckMonitor MissTwoFifths)', ['(Status Checked)', '(ChiSquare (Table (Row one (Rat 49 19))))']),
   ('(Combine Mixture)) =>', ['(Status Estimated)', '(Fired None) (Step None) (Observations 916)', '(Largest (Rat 46 57)) (LargestAt 1) (Threshold 100)']),
   ('ShiryaevRoberts', ['(Status Unsupported)', 'Scheme ShiryaevRoberts'])]),
]
for rel, checks in DOC:
    rc, out = run(os.path.join(D, rel))
    for key, frags in checks:
        hits = [l for l in out if key in l and ('Detect' in l or 'CheckMonitor' in l)]
        report('doc %s %s' % (rel.split('/')[0][:2], key), len(hits) == 1 and has(hits[0], *frags), hits[:1] or 'no row')
print('run_monitors: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
