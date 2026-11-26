#!/usr/bin/env python3
"""t-2026-11-26-mettadinc-natarith-v2 step 4: one source mutant per NatArith primitive must fail run_natarith.py.
Each mutant patches exactly one site of src/dcalc/model.c (explicit evaluator) or src/dcalc/ops_sym.c (symbolic
BDD layer) in a scratch copy under build/natarith_mutants/<name>, builds it, and runs run_natarith.py against
that binary (DCALC_NATARITH_DC).  A mutant passes this gate only if run_natarith exits non-zero AND the named
gate lines FAIL."""
import os, shutil, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
CC = os.environ.get('CC', 'gcc')
SRC = os.path.join(ROOT, 'src', 'dcalc')
OUT = os.path.join(ROOT, 'build', 'natarith_mutants')
V = 'FAIL  Values (--beyond-release): '
A = 'FAIL  Agree: '
MUTANTS = [
    # (name, file, original text, mutated text, gate prefixes that must FAIL)
    ('le_as_lt', 'model.c', 'if (!strcmp(h, "Le")) return sx_sym(a <= c ?', 'if (!strcmp(h, "Le")) return sx_sym(a < c ?',
     [V + 'NLE CheckNow R', A + 'D_le4']),
    ('lt_as_le', 'model.c', 'if (!strcmp(h, "Lt")) return sx_sym(a < c ?', 'if (!strcmp(h, "Lt")) return sx_sym(a <= c ?',
     [V + 'NLT CheckNow R', A + 'D_lt4']),
    ('min_as_max', 'model.c', 'if (!strcmp(h, "Min")) r = a < c ? a : c;', 'if (!strcmp(h, "Min")) r = a < c ? c : a;',
     [V + 'NMN CheckNow R', A + 'D_mn5']),
    ('max_as_min', 'model.c', 'else if (!strcmp(h, "Max")) r = a > c ? a : c;', 'else if (!strcmp(h, "Max")) r = a > c ? c : a;',
     [V + 'NMX CheckNow R', A + 'D_mx5']),
    ('quot_truncates', 'model.c', 'long q = a / c; if (a % c != 0 && a < 0) q--;', 'long q = a / c;',
     [V + 'NQ CheckNow R']),
    ('rem_truncates', 'model.c', 'r = !strcmp(h, "Quot") ? q : a - q * c;', 'r = !strcmp(h, "Quot") ? q : a % c;',
     [V + 'NR CheckNow R']),
    ('negative_divisor_admitted', 'model.c', 'if (c <= 0) { Sx *f = sx_list();', 'if (c == 0) { Sx *f = sx_list();',
     [V + 'NNQ CheckNow R']),
    # the Body-map path (model.c, Crisp (Body ...) maps) calls eval_body without logic_on, so NIF's If is the
    # NatArith lazy If block, not eval_logic's If: mutate that block to evaluate the untaken branch first
    ('if_strict_untaken_branch', 'model.c', '        return eval_body(b->items[t ? 2 : 3], e, ok);\n',
     '        { Sx *u = eval_body(b->items[t ? 3 : 2], e, ok); if (nat_failed(u)) return u; sx_free(u); }\n'
     '        return eval_body(b->items[t ? 2 : 3], e, ok);\n',
     [V + 'NIF CheckNow R']),
    ('sym_le_as_lt', 'ops_sym.c', 'o->b[0] = le ? dc_bdd_not(bm, bdd_ult(bm, b.b, a.b, w)) :', 'o->b[0] = le ? bdd_ult(bm, a.b, b.b, w) :',
     [A + 'D_le4']),
    ('sym_lt_as_le', 'ops_sym.c', ': bdd_ult(bm, a.b, b.b, w); return 0; }', ': dc_bdd_not(bm, bdd_ult(bm, b.b, a.b, w)); return 0; }',
     [A + 'D_lt4']),
    ('sym_min_as_max', 'ops_sym.c', 'mn ? dc_bdd_ite(bm, lt, a.b[k], b.b[k])', 'mn ? dc_bdd_ite(bm, lt, b.b[k], a.b[k])',
     [A + 'D_mn5']),
    ('sym_max_as_min', 'ops_sym.c', ': dc_bdd_ite(bm, lt, b.b[k], a.b[k]);\n        return 0;', ': dc_bdd_ite(bm, lt, a.b[k], b.b[k]);\n        return 0;',
     [A + 'D_mx5']),
    ('sym_quot_drops_bit0', 'ops_sym.c', 'o->b[k] = quot ? q[k] : (k < dw ? r[k] : 0);', 'o->b[k] = quot ? (k ? q[k] : 0) : (k < dw ? r[k] : 0);',
     [A + 'D_q3']),
    ('sym_rem_as_quot', 'ops_sym.c', 'o->b[k] = quot ? q[k] : (k < dw ? r[k] : 0);', 'o->b[k] = quot ? q[k] : (k < dw ? q[k] : 0);',
     [A + 'D_r3']),
]
fails = 0
def report(name, ok, det=''):
    global fails
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  :: %s' % (det,)))
    if not ok: fails += 1
only = sys.argv[1:]
for name, fn, a, b, need in MUTANTS:
    if only and name not in only: continue
    d = os.path.join(OUT, name); shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, os.path.join(d, 'src', 'dcalc'), ignore=shutil.ignore_patterns('*.o', '*.a'))
    f = os.path.join(d, 'src', 'dcalc', fn); s = open(f).read()
    if s.count(a) != 1: report('mutant %s: patch site in %s found exactly once' % (name, fn), False, s.count(a)); continue
    open(f, 'w').write(s.replace(a, b))
    bd = subprocess.run(['make', '-s', 'CC=' + CC, 'BUILD=' + os.path.join(d, 'build')], cwd=os.path.join(d, 'src', 'dcalc'),
                        capture_output=True, text=True, timeout=900)
    if bd.returncode != 0: report('mutant %s: builds' % name, False, bd.stderr[-400:]); continue
    env = dict(os.environ, DCALC_NATARITH_DC=os.path.join(d, 'build'))
    rf = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'natarith', 'run_natarith.py')],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    with open(os.path.join(d, 'run_natarith.out'), 'w') as fh: fh.write(rf.stdout + rf.stderr)
    lines = rf.stdout.splitlines()
    miss = [g for g in need if not any(l.startswith(g) for l in lines)]
    report('mutant %s (%s): caught by run_natarith (exit %d, %d FAIL lines; required %s)'
           % (name, fn, rf.returncode, sum(l.startswith('FAIL') for l in lines), '; '.join(x[6:] for x in need)),
           rf.returncode != 0 and not miss, miss or (lines[-1:] if lines else ''))
print('run_natarith_mutants: %s' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
