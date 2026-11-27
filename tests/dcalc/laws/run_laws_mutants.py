#!/usr/bin/env python3
"""t-2026-11-27-mettadinc-laws: one source mutant per Laws primitive must fail run_laws.py.
Each mutant patches exactly one site of src/dcalc/laws.c in a scratch copy under build/laws_mutants/<name>,
builds it, and runs run_laws.py against that binary (DCALC).  A mutant passes this gate only if run_laws exits
non-zero with at least one FAIL line."""
import os, shutil, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
CC = os.environ.get('CC', 'gcc')
SRC = os.path.join(ROOT, 'src', 'dcalc')
OUT = os.path.join(ROOT, 'build', 'laws_mutants')
MUTANTS = [
    # (name, file, original text, mutated text)
    ('coin_complement_is_p', 'laws.c', 'dc_law_add(out, zero, dc_q_sub(dc_q(1, 1, ovf), p, ovf), ovf)', 'dc_law_add(out, zero, p, ovf)'),
    ('indep_no_product', 'laws.c', 'dc_q_mul(acc.m[i], f.m[j], ovf)', 'f.m[j]'),
    ('image_ignores_body', 'laws.c', 'int r = dc_law_add(out, w, in.m[i], ovf);', 'int r = dc_law_add(out, in.val[i], in.m[i], ovf);'),
    ('div_as_mul', 'laws.c', 'return q_sx(dc_q_div(a, b, ovf));', 'return q_sx(dc_q_mul(a, b, ovf));'),
    ('expect_doubled', 'laws.c', '        return q_sx(x);', '        return q_sx(dc_q_add(x, x, ovf));'),
]
fails = 0
def report(name, ok, det=''):
    global fails
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  :: %s' % (det,)))
    if not ok: fails += 1
only = sys.argv[1:]
for name, fn, a, b in MUTANTS:
    if only and name not in only: continue
    d = os.path.join(OUT, name); shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, os.path.join(d, 'src', 'dcalc'), ignore=shutil.ignore_patterns('*.o', '*.a'))
    f = os.path.join(d, 'src', 'dcalc', fn); s = open(f).read()
    if s.count(a) != 1: report('mutant %s: patch site in %s found exactly once' % (name, fn), False, s.count(a)); continue
    open(f, 'w').write(s.replace(a, b))
    bd = subprocess.run(['make', '-s', 'CC=' + CC, 'BUILD=' + os.path.join(d, 'build')], cwd=os.path.join(d, 'src', 'dcalc'),
                        capture_output=True, text=True, timeout=900)
    if bd.returncode != 0: report('mutant %s: builds' % name, False, bd.stderr[-400:]); continue
    env = dict(os.environ, DCALC=os.path.join(d, 'build', 'dcalc'))
    rf = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'laws', 'run_laws.py')],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    with open(os.path.join(d, 'run_laws.out'), 'w') as fh: fh.write(rf.stdout + rf.stderr)
    lines = rf.stdout.splitlines(); nf = sum(l.startswith('FAIL') for l in lines)
    report('mutant %s (%s): caught by run_laws (exit %d, %d FAIL lines)' % (name, fn, rf.returncode, nf),
           rf.returncode != 0 and nf > 0, lines[-1:] if lines else rf.stderr[-300:])
print('run_laws_mutants: %s' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
