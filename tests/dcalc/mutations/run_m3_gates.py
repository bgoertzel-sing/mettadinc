#!/usr/bin/env python3
"""M3 claim rows F01-F06 and negative gates (t-2026-11-11-mettadinc-m3).

Needs the proof backend in the environment: DCALC_CADICAL (CaDiCaL 3.0.1) and
DCALC_CAKE_LPR (cake_lpr 033aad5); DCALC_PROOF_DIR is optional.  Exit 0 iff all pass."""
import os, re, stat, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); TD = os.path.dirname(HERE); ROOT = os.path.dirname(os.path.dirname(TD))
FIX = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures/forty_bits.metta')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m3'))
GEN = re.search(r'#define SYM_GEN_VERSION "([^"]+)"', open(os.path.join(ROOT, 'src/dcalc/ops_sym.c')).read()).group(1)
fails = 0
def report(name, ok, note=''):
    global fails
    fails += not ok; print('%-62s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
def run(src, tag, env=None):
    os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, tag + '.metta'); open(p, 'w').write(src)
    r = subprocess.run([DCALC, p], capture_output=True, text=True, timeout=120, env=env)
    lines = {}
    for line in r.stdout.splitlines():
        if ' => ' in line: head = line.split(' => ', 1)[0]; mod, req = head.split(' ', 1); lines[(mod, req)] = line
    return lines
def st(line): m = re.search(r'\(Result \(Status (\w+)\)', line or ''); return m.group(1) if m else 'missing'
def has(line, pat): return re.search(pat, line or '') is not None
def gen_ok(line):
    """Replay-side pin: every Proof names generator dcalc-symgen at the recorded version."""
    g = re.findall(r'\(Generator dcalc-symgen ([^)\s]+)\)', line or '')
    return bool(g) and all(v == GEN for v in g)

if not (os.environ.get('DCALC_CADICAL') and os.environ.get('DCALC_CAKE_LPR')):
    print('DCALC_CADICAL and DCALC_CAKE_LPR must name the pinned solver and checker'); sys.exit(2)
src = open(FIX, encoding='utf-8').read(); L = run(src, 'fixture')
rows = [('F01', '(CheckNow KeepX0)', 'Checked', None), ('F02', '(CheckBehavioral KeepX0)', 'Refuted', r'\(Pair 0 2\) \(Word swap\)'),
        ('F03', 'ZeroQuotient', 'Checked', r'\(Classes 8\).*\(Nodes 7\) \(MaxWord 2\)'),
        ('F04', 'ParityQuotient', 'Checked', r'\(ObservableDimension 3\) \(UnobservableDimension 37\)'),
        ('F05', 'WholeCarrier', 'Refuted', r'\(Obligation Coverage\) \(Witness 4\)'),
        ('F06', 'OnReach', 'Checked', r'\(Invariant \(Words 0 2 1 3\)\)')]
for cid, req, want, pat in rows:
    line = L.get(('FortyBits', req)); s = st(line)
    ok = s == want and (pat is None or has(line, pat)) and has(line, r'\(EnumeratedCarrier False\)')
    if want == 'Checked': ok = ok and gen_ok(line) and has(line, r'\(Checker cake_lpr-033aad5\)')
    else: ok = ok and has(line, r'\(Replayed True\)')
    report('%s %s' % (cid, req), ok, s)
report('neg 1: adversarial zero-tail candidate refused on the full carrier', st(L.get(('FortyBits', 'WholeCarrier'))) == 'Refuted')
# neg 2: a representative outside Reach(0) (7: in block Z11, tail nonzero) must fail membership
i = src.index('(BlockPartition ZeroTailReach'); blk = '(Eq (BitAt $x 1) 1))) 3)'; j = src.index(blk, i)
v2 = run(src[:j] + blk[:-2] + '7)' + src[j + len(blk):], 'neg2-unreachable-rep').get(('FortyBits', 'OnReach'))
report('neg 2: membership needs a reachability word (rep 7)', st(v2) == 'Refuted' and has(v2, r'\(Obligation Membership\) \(Witness 7\)'), st(v2))
# neg 3: the solver returns a proof of a different formula; the checker runs on the regenerated CNF
os.makedirs(OUT, exist_ok=True); other = os.path.join(OUT, 'other.cnf'); open(other, 'w').write('p cnf 1 2\n1 0\n-1 0\n')
fake = os.path.join(OUT, 'fake_cadical.sh')
open(fake, 'w').write('#!/bin/sh\n# proof for another formula, written where the real proof belongs\nexec "%s" -q --no-binary --lrat "%s" "$5"\n' % (os.environ['DCALC_CADICAL'], other))
os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
v3 = run(src, 'neg3-other-proof', dict(os.environ, DCALC_CADICAL=fake))
ok3 = all(st(v3.get(('FortyBits', r))) != 'Checked' for r in ('(CheckNow KeepX0)', 'ZeroQuotient', 'ParityQuotient', 'OnReach'))
report('neg 3: proof log for a different formula never Checked', ok3 and has(v3.get(('FortyBits', 'OnReach')), 'cake_lpr did not verify'))
# neg 4: a certificate naming another generator version is refused by the replay-side pin
good = L.get(('FortyBits', 'OnReach')); bad = (good or '').replace('(Generator dcalc-symgen %s)' % GEN, '(Generator dcalc-symgen m3.0)')
report('neg 4: CNF from another generator version refused', gen_ok(good) and not gen_ok(bad), 'pinned %s' % GEN)
# neg 5: a source mutation that restores a bug must change the verdict (here the rotate range drags x1 into the tail)
rb = '(RotateRange $x 2 39)'; assert src.count(rb) == 1
v5 = run(src.replace(rb, '(RotateRange $x 1 39)'), 'neg5-rotate-bug').get(('FortyBits', 'OnReach'))
report('neg 5: restored-bug source mutation changes OnReach verdict', st(L.get(('FortyBits', 'OnReach'))) == 'Checked' and st(v5) == 'Refuted', st(v5))
# neg 6: no backend -> decision-diagram answers stay Conditional
env6 = {k: v for k, v in os.environ.items() if k not in ('DCALC_CADICAL', 'DCALC_CAKE_LPR')}
v6 = run(src, 'neg6-no-backend', env6); ss = [st(l) for l in v6.values()]
report('neg 6: solver/DD verdict without replayed proof never Checked', 'Checked' not in ss and ss.count('Conditional') == 4, ' '.join(sorted(ss)))
# neg 8: the four-class encoding (keep bits 0 and 1) is refuted with behavioral defect one
k = src.index('  (Representation KeepX0')
v8src = src[:k] + '  (Carrier Two (Of (BitVector 2)) (All))\n  (Map keep01 (From Word) (To Two) (Body ($x) (Slice $x 0 1)))\n  (Representation Keep01 (Of ZeroMachine) (Encode keep01))\n' + src[k:]
v8src += '\n!(dc.run FortyBits (CheckBehavioral Keep01))\n!(dc.run FortyBits (MeasureBehavioral Keep01))\n'
v8 = run(v8src, 'neg8-four-class'); c8 = v8.get(('FortyBits', '(CheckBehavioral Keep01)')); m8 = v8.get(('FortyBits', '(MeasureBehavioral Keep01)'))
report('neg 8: four-class encoding refuted, behavioral defect 1', st(c8) == 'Refuted' and has(c8, r'\(Replayed True\)')
       and has(m8, r'\(Defect \(Interval 1 1\)\) \(Kind Behavioral\)') and has(m8, r'\(Replayed True\)'), '%s / %s' % (st(c8), st(m8)))
# neg 9: cone keeps all forty bits of both machines
report('neg 9: cone of influence keeps all 40 bits', all(has(L.get(('FortyBits', q)), r'\(Cone \(Pass Syntactic\) \(Kept 40\) \(Width 40\) \(Dropped\)\)') for q in ('ZeroQuotient', 'ParityQuotient')))
# neg 10-11: incrementality
inc = os.path.join(ROOT, 'build/dcalc/m3_incremental')
r = subprocess.run([inc, FIX], capture_output=True, text=True, cwd=ROOT) if os.path.exists(inc) else None
report('neg 10-11: add x1 resumes == scratch; remove inject transports', bool(r) and r.returncode == 0 and 'm3_incremental: PASS' in r.stdout)
print('run_m3_gates: %s' % ('FAIL (%d)' % fails if fails else 'PASS')); sys.exit(1 if fails else 0)
