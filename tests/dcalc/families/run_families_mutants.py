#!/usr/bin/env python3
"""t-2026-11-26-mettadinc-families-followups-v2 steps 1-2: source mutants of the Families elaborator must fail
run_families.py.  Each mutant patches exactly one site of src/dcalc/families.c in a scratch copy under
build/families_mutants/<name>, builds it, and runs run_families.py against that binary (DCALC_FAMILIES_DC).
A mutant passes this gate only if run_families exits non-zero AND the named gates FAIL in both modes."""
import os, shutil, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
CC = os.environ.get('CC', 'gcc')
SRC = os.path.join(ROOT, 'src', 'dcalc')
OUT = os.path.join(ROOT, 'build', 'families_mutants')
MUTANTS = [
    # (name, original text, mutated text, gate prefixes that must FAIL)
    ('eq_symbols_always_false',
     'sx_sym(strcmp(a[1]->text, a[2]->text) ?', 'sx_sym(1 ?',
     ['FAIL  Fold (release): FE CheckNow R ', 'FAIL  Fold (--beyond-release): FE CheckNow R ']),
    ('and_folded_as_or',
     'r = fold(h, a + 1, (int)n - 1);', 'r = fold(strcmp(h, "And") ? h : "Or", a + 1, (int)n - 1);',
     ['FAIL  Fold (release): FA CheckNow R ', 'FAIL  Fold (--beyond-release): FA CheckNow R ']),
    ('for_drops_last_element',
     'for (size_t k = 1; k < en->n; k++) { e2.val[e2.n - 1] = en->items[k];',
     'for (size_t k = 1; k + 1 < en->n; k++) { e2.val[e2.n - 1] = en->items[k];',
     ['FAIL  For/ex2 (release): replay.py', 'FAIL  For/ex2 (--beyond-release): replay.py']),
]
fails = 0
def report(name, ok, det=''):
    global fails
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  :: %s' % (det,)))
    if not ok: fails += 1
for name, a, b, need in MUTANTS:
    d = os.path.join(OUT, name); shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, os.path.join(d, 'src', 'dcalc'), ignore=shutil.ignore_patterns('*.o', '*.a'))
    f = os.path.join(d, 'src', 'dcalc', 'families.c'); s = open(f).read()
    if s.count(a) != 1: report('mutant %s: patch site found exactly once' % name, False, s.count(a)); continue
    open(f, 'w').write(s.replace(a, b))
    bd = subprocess.run(['make', '-s', 'CC=' + CC, 'BUILD=' + os.path.join(d, 'build')], cwd=os.path.join(d, 'src', 'dcalc'),
                        capture_output=True, text=True, timeout=900)
    if bd.returncode != 0: report('mutant %s: builds' % name, False, bd.stderr[-400:]); continue
    env = dict(os.environ, DCALC_FAMILIES_DC=os.path.join(d, 'build', 'dcalc'))
    rf = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'families', 'run_families.py')],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    with open(os.path.join(d, 'run_families.out'), 'w') as fh: fh.write(rf.stdout + rf.stderr)
    lines = rf.stdout.splitlines()
    miss = [g for g in need if not any(l.startswith(g) for l in lines)]
    report('mutant %s: caught by run_families (exit %d, %d FAIL lines; required %s)'
           % (name, rf.returncode, sum(l.startswith('FAIL') for l in lines), '; '.join(x[6:] for x in need)),
           rf.returncode != 0 and not miss, miss or (lines[-1:] if lines else ''))
print('run_families_mutants: %s' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
