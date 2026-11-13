#!/usr/bin/env python3
"""m6-graded gates (beyond release, plus release mode over every m6graded fixture).  Each check prints PASS/FAIL; exit 1 on any FAIL."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
DCALC = os.path.join(ROOT, 'build/dcalc/dcalc'); OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m6graded')); os.makedirs(OUT, exist_ok=True)
RP = os.path.join(HERE, 'replay_m6graded.py'); fails = 0
def report(name, ok, detail=''):
    global fails; fails += 0 if ok else 1; print('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, str(detail)[:200]))
def run(fx, beyond=True): return subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [fx], capture_output=True, text=True, timeout=600).stdout
def statuses(o): return [l.split('(Status ', 1)[1].split(')', 1)[0] for l in o.splitlines() if '(Status ' in l]
def replay(fx, out): return subprocess.run([sys.executable, RP, fx, out], capture_output=True, text=True)
def lines(o): return [l for l in o.splitlines() if ' => ' in l]
# graded triangle (spec Def 10.1 l.2821; Lukasiewicz l.288-289, l.736-742): hand-checked values
tf = os.path.join(HERE, 'fixtures', 'graded_triangle.metta'); to = os.path.join(OUT, 'graded_triangle.out'); tt = run(tf); open(to, 'w').write(tt); tl = lines(tt)
report('graded triangle statuses: coherence Refuted, holonomy/cost/LCR/associator Checked', statuses(tt) == ['Refuted', 'Checked', 'Checked', 'Checked', 'Checked'], statuses(tt))
report('graded triangle hand-checked values: cost 1/12, LCR 1/18', len(tl) > 3 and '(Value (Rat 1 12))' in tl[2] and '(Value (Rat 1 18))' in tl[3])
r1 = replay(tf, to); report('graded triangle replays (Fractions, Lukasiewicz FW closure, LP certificate)', r1.returncode == 0, r1.stdout.strip().splitlines()[-1:])
# CompleteHive on graded hives
cf = os.path.join(HERE, 'fixtures', 'graded_complete.metta'); co = os.path.join(OUT, 'graded_complete.out'); ct = run(cf); open(co, 'w').write(ct); cl = lines(ct)
report('graded CompleteHive statuses: Chain Checked, coherence Unknown, cost Unsupported, Broken Unsupported', statuses(ct) == ['Checked', 'Unknown', 'Unsupported', 'Unsupported'], statuses(ct))
report('graded CompleteHive value 1/36 (hand-checked: 4 fills x 1/36 x 1/4)', len(cl) > 0 and '(Value (Rat 1 36))' in cl[0])
r2 = replay(cf, co); report('graded CompleteHive certificate replays', r2.returncode == 0, r2.stdout.strip().splitlines()[-1:])
report('graded neg: coherence on an Unmeasured graded hive is Unknown with an Open triple (no zero fill)', len(cl) > 1 and '(Open (Triple' in cl[1] and 'not zero-filled' in cl[1])
report('graded neg: measured entry below its closure -> CompleteHive Unsupported naming the closure', len(cl) > 3 and 'Lukasiewicz path closure' in cl[3] and '(Filled' not in cl[3])
# tamper canaries on fixture answers: each must be rejected
for nm, fx, ln, a, b in [('triangle cost', tf, tl[2] if len(tl) > 2 else '', '(Value (Rat 1 12))', '(Value (Rat 1 13))'),
                         ('triangle LCR', tf, tl[3] if len(tl) > 3 else '', '(Value (Rat 1 18))', '(Value (Rat 1 19))'),
                         ('triangle witness degrees', tf, tl[0] if tl else '', '(Degrees (Rat 1 1)', '(Degrees (Rat 1 2)'),
                         ('associator Zero flag', tf, tl[4] if len(tl) > 4 else '', '(Zero False)', '(Zero True)'),
                         ('CompleteHive fill degree', cf, cl[0] if cl else '', '(Degree (Rat 1 4))', '(Degree (Rat 1 2))'),
                         ('CompleteHive zero fill', cf, cl[0] if cl else '', '(Value (Rat 1 36))', '(Value (Rat 0 1))')]:
    tp = os.path.join(OUT, 'tamper.out'); tl2 = ln.replace(a, b, 1); open(tp, 'w').write(tl2 + '\n'); rr = replay(fx, tp)
    report('graded tamper: %s is rejected by the replayer' % nm, tl2 != ln and rr.returncode != 0 and 'REJECT' in rr.stdout, rr.stdout.strip().splitlines()[:1])
# degree outside [0, 1] is invalid input (spec Def 10.1: c_ij in [0, 1])
bf = os.path.join(OUT, 'graded_outside.metta'); open(bf, 'w').write(open(tf).read().replace('(0 1 (Rat 1 4)) (1 0 (Rat 1 4))', '(0 1 (Rat 5 4)) (1 0 (Rat 5 4))', 1))
bs = statuses(run(bf)); report('graded neg: a degree 5/4 outside [0, 1] -> InvalidInput', bs and set(bs) == {'InvalidInput'}, bs)
# random probes vs brute force / separate sympy LP, with value tamper canaries
for n, seed in [(24, 1), (40, 2026)]:
    pr = subprocess.run([sys.executable, os.path.join(HERE, 'probe_graded.py'), str(n), str(seed)], capture_output=True, text=True, timeout=900)
    report('graded random probe N=%d seed %d (replay + brute force + sympy LP + tamper)' % (n, seed), pr.returncode == 0, pr.stdout.strip().splitlines()[-2:-1])
# release mode: graded kernel hives are beyond release
for fx in sorted(os.listdir(os.path.join(HERE, 'fixtures'))):
    st = statuses(run(os.path.join(HERE, 'fixtures', fx), beyond=False))
    report('release mode: %s answers only Unsupported/InvalidInput' % fx, len(st) > 0 and set(st) <= {'Unsupported', 'InvalidInput'}, st)
print('m6graded_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails)); sys.exit(1 if fails else 0)
