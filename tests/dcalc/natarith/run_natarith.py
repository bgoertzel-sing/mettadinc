#!/usr/bin/env python3
"""t-2026-11-26-mettadinc-natarith-v2 gates for the NatArith library (doc03 s3.13 l.1166-1172, B.1 l.4395-4398).
  values: fixtures/nat_values.metta -- one exact value per primitive (zero/negative divisor, equal operands,
          If whose untaken branch is Quot by zero); beyond-release: Checked / InvalidInput naming the failure value;
          release: every request Unsupported (NatArith is outside the first release).
  agree:  fixtures/nat_agree.metta -- the same six maps on {0..7} as an explicit Int carrier (NAE) and as
          (BitVector 3) words (NAS); partitions must be identical and equal the known answers below.
  symlimits: fixtures/nat_symlimits.metta -- forms outside the symbolic fragment (symbolic or zero divisor,
          constant wider than the word) answer Unsupported with a reason, never InvalidInput (review 1 finding 2),
          also when nested under another head or used as Action/Encode map or block predicate (review 2 finding 1).
DCALC_NATARITH_DC overrides the build dir (run_natarith_mutants.py)."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BD = os.environ.get('DCALC_NATARITH_DC') or os.path.join(ROOT, 'build', 'dcalc')
DC = os.path.join(BD, 'dcalc')
FX = os.path.join(HERE, 'fixtures')
FAILV = '(Failed NonPositiveDivisor)'
VALUES = {'NQ': 'Checked', 'NR': 'Checked', 'NMN': 'Checked', 'NMX': 'Checked', 'NLE': 'Checked', 'NLT': 'Checked',
          'NIF': 'Checked', 'NZQ': 'InvalidInput', 'NZR': 'InvalidInput', 'NNQ': 'InvalidInput'}
# known answers (hand-checked): blocks as (min element, size); action x -> Max(Quot x 2, 1)
AGREE = {'D_q3': ((0, 3), (3, 3), (6, 2)),
         'D_r3': ((0, 2), (1, 1), (2, 1), (4, 1), (5, 1), (6, 1), (7, 1)),
         'D_mn5': ((0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 2)),
         'D_mx5': ((0, 6), (6, 1), (7, 1)),
         'D_lt4': ((0, 1), (1, 1), (2, 1), (3, 1), (4, 2), (6, 2)),
         'D_le4': ((0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 2))}
fails = 0
def report(name, ok, det=''):
    global fails
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  :: %s' % (det,)))
    if not ok: fails += 1
def run(fx, beyond):
    a = [DC] + (['--beyond-release'] if beyond else []) + [os.path.join(FX, fx)]
    p = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, timeout=600)
    out = {}
    for l in p.stdout.splitlines():
        m = re.match(r'(\S+) (\(CheckNow R\w*\)|D_\w+|D[PZ]) =>', l)
        if m: out[(m.group(1), m.group(2))] = l
    return p.returncode, out
def status(l): m = re.search(r'\(Status (\w+)\)', l); return m.group(1) if m else None
def reason(l): m = re.search(r'\(Reason "([^"]*)"', l); return m.group(1) if m else ''
def part(l):
    m = re.search(r'\(Partition((?: \(Block [^()]*\))+)\)', l)
    if m and '(Rep' not in m.group(1):
        return tuple(sorted((min(b), len(b)) for b in ([int(x) for x in s.split()] for s in re.findall(r'\(Block ([^()]*)\)', m.group(1)))))
    m = re.search(r'\(Partition(.*?)\(Classes \d+\)', l)
    return tuple(sorted((int(a), int(b)) for a, b in re.findall(r'\(Block \(Rep (\d+)\) \(Size (\d+)\)\)', m.group(1)))) if m else None
for beyond in (False, True):
    mode = '--beyond-release' if beyond else 'release'
    rc, out = run('nat_values.metta', beyond)
    report('values (%s): dcalc exit 0, %d requests' % (mode, len(VALUES)), rc == 0 and len(out) == len(VALUES), (rc, len(out)))
    for mod, want in VALUES.items():
        l = out.get((mod, '(CheckNow R)'), '')
        if not beyond:
            ok = status(l) == 'Unsupported' and 'NatArith is outside the first release' in reason(l)
            report('Values (release): %s CheckNow R Unsupported (NatArith outside the first release)' % mod, ok, l[:200])
        elif want == 'Checked':
            report('Values (--beyond-release): %s CheckNow R Checked' % mod, status(l) == 'Checked', (status(l), reason(l)[:160]))
        else:
            ok = status(l) == 'InvalidInput' and FAILV in reason(l)
            report('Values (--beyond-release): %s CheckNow R InvalidInput naming %s' % (mod, FAILV), ok, (status(l), reason(l)[:160]))
rc, out = run('nat_agree.metta', True)
report('agree (--beyond-release): dcalc exit 0, 12 requests', rc == 0 and len(out) == 12, (rc, len(out)))
for d, want in AGREE.items():
    a, b = out.get(('NAE', d), ''), out.get(('NAS', d), '')
    pa, pb = part(a), part(b)
    report('Agree: %s explicit (NAE) = symbolic (NAS) = known answer' % d,
           status(a) == status(b) == 'Checked' and pa == pb == want, ('NAE', status(a), pa, 'NAS', status(b), pb, reason(a)[:80], reason(b)[:80]))
# review 1 finding 2: symbolic-engine limits answer Unsupported with a reason, never InvalidInput
SYMLIM = {'D_qv': 'needs a constant divisor', 'D_qz': 'Quot/Rem by zero', 'D_mx9': 'constant wider than the word',
          'D_qm': 'needs a constant divisor', 'D_qa': 'needs a constant divisor'}
# review 2 finding 1: the limited form nested one level below another head, in an Action map, an Encode map
# (CheckNow) and a block predicate (CheckBlockPartition) -- modules NSN and NSD
NC, ZD, WD = 'needs a constant divisor', 'Quot/Rem by zero', 'constant wider than the word'
SYMLIM = dict([(('NSL', d), w) for d, w in SYMLIM.items()] + [
    (('NSN', 'D_d1'), NC), (('NSN', 'D_d2'), NC), (('NSN', 'D_d3'), WD), (('NSN', 'D_d5'), WD),
    (('NSD', 'D_d6'), ZD), (('NSD', 'D_d7'), ZD), (('NSD', 'D_d4'), NC), (('NSD', 'D_da'), ZD),
    (('NSD', '(CheckNow R6)'), ZD), (('NSD', '(CheckNow R1)'), NC), (('NSD', 'DP'), NC), (('NSD', 'DZ'), ZD)])
rc, out = run('nat_symlimits.metta', True)
report('symlimits (--beyond-release): dcalc exit 0, 18 requests', rc == 0 and len(out) == 18, (rc, len(out)))
for (mod, d), why in SYMLIM.items():
    l = out.get((mod, d), '')
    report('SymLimits: %s %s Unsupported naming "%s" (not InvalidInput)' % (mod, d, why),
           status(l) == 'Unsupported' and why in reason(l), (status(l), reason(l)[:160]))
l = out.get(('NSE', 'D_qm'), '')
report('SymLimits: NSE D_qm (Quot 6 (Max $x 1)) explicit Checked with the known partition',
       status(l) == 'Checked' and part(l) == ((0, 2), (2, 1), (3, 1), (4, 2), (6, 1), (7, 1)), (status(l), part(l), reason(l)[:120]))
print('run_natarith: %s' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
