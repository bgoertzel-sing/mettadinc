#!/usr/bin/env python3
"""t-2026-11-27-mettadinc-engine-limits-unsupported gates: an engine limit answers Unsupported naming the limit,
a real module error stays InvalidInput. fixtures/el_cases.metta, both modes:
  EL_M9  9 machines, symbolic engine holds at most 8 -> Unsupported naming the limit and the count (both modes)
  EL_M8  exactly 8 machines (boundary) -> Checked (both modes)
  EL_ZQ  (Quot x 0) = (Failed NonPositiveDivisor), spec l.1858-1860 / doc03 B.1 -> beyond: Unsupported naming it;
         release: Unsupported (NatArith outside the first release)
  EL_BAD (Quot 7 2) = 3, an ordinary value outside carrier {7} -> beyond: InvalidInput (negative); release: Unsupported
DCALC_EL_DC overrides the build dir."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BD = os.environ.get('DCALC_EL_DC') or os.path.join(ROOT, 'build', 'dcalc')
DC = os.path.join(BD, 'dcalc')
FX = os.path.join(HERE, 'fixtures', 'el_cases.metta')
fails = 0
def report(name, ok, det):
    global fails
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  :: %s' % (det,)))
    if not ok: fails += 1
def run(beyond):
    a = [DC] + (['--beyond-release'] if beyond else []) + [FX]
    p = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, timeout=600)
    out = {}
    for l in p.stdout.splitlines():
        m = re.match(r'(EL_\w+) (\(CheckNow R\)|D) =>', l)
        if m: out[m.group(1)] = l
    return p.returncode, out
def status(l): m = re.search(r'\(Status (\w+)\)', l); return m.group(1) if m else None
def reason(l): m = re.search(r'\(Reason "([^"]*)"', l); return m.group(1) if m else ''
M9 = 'too many machines: the symbolic engine holds at most 8, the module declares 9'
ZQ = 'gives the tagged failure value (Failed NonPositiveDivisor), which the engine cannot yet hold in carrier A0'
REL = 'library NatArith is outside the first release'
BAD = 'Map m0: Body sends 7 to 3, which is not in carrier A0'
WANT = {False: {'EL_M9': ('Unsupported', M9), 'EL_M8': ('Checked', None), 'EL_ZQ': ('Unsupported', REL), 'EL_BAD': ('Unsupported', REL)},
        True:  {'EL_M9': ('Unsupported', M9), 'EL_M8': ('Checked', None), 'EL_ZQ': ('Unsupported', ZQ), 'EL_BAD': ('InvalidInput', BAD)}}
for beyond in (False, True):
    mode = '--beyond-release' if beyond else 'release'
    rc, out = run(beyond)
    report('el_cases (%s): dcalc exit 0, 4 requests' % mode, rc == 0 and len(out) == 4, (rc, sorted(out)))
    for mod, (st, why) in WANT[beyond].items():
        l = out.get(mod, '')
        ok = status(l) == st and (why is None or why in reason(l))
        if mod == 'EL_M8': ok = ok and 'too many machines' not in l
        report('EngineLimits (%s): %s %s%s' % (mode, mod, st, '' if why is None else ' naming "%s"' % why[:70]), ok, (status(l), reason(l)[:200]))
print('run_engine_limits: %s' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
