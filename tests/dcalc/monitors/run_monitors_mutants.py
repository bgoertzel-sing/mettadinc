#!/usr/bin/env python3
"""t-2026-11-27-mettadinc-monitors: one source mutant per Monitors form (Monitor declaration, CheckMonitor,
Detect) and per wiring site must fail run_monitors.py.  Each mutant patches exactly one site in a scratch copy
under build/monitors_mutants/<name>, builds it, and runs run_monitors.py against that binary (DCALC).  A mutant
passes this gate only if run_monitors exits non-zero with at least one FAIL line."""
import os, shutil, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
CC = os.environ.get('CC', 'gcc')
SRC = os.path.join(ROOT, 'src', 'dcalc')
OUT = os.path.join(ROOT, 'build', 'monitors_mutants')
MUTANTS = [
    # (name, file, original text, mutated text)
    # Monitor declaration: law resolution (Table row lookup, raw source kept, Families pass-through)
    ('table_row_ignored', 'ops_mon.c', 'if (row->kind == SX_LIST && row->n == 2 && sx_equal(row->items[0], a)) {', 'if (row->kind == SX_LIST && row->n == 2) {'),
    ('raw_source_not_kept', 'api.c', 'if (m->monitors) m->raw_source = sx_copy(raw); }', 'if (0 && m->monitors) m->raw_source = sx_copy(raw); }'),
    ('families_elaborates_monitor', 'families.c', 'if (sx_head_is(d, "Monitor")) { sx_push(o, sx_copy(d)); continue; }', 'if (0 && sx_head_is(d, "Monitor")) { sx_push(o, sx_copy(d)); continue; }'),
    # CheckMonitor
    ('chi2_no_minus_one', 'ops_mon.c', 'x2 = dc_q_sub(x2, dc_q(1, 1, &ovf), &ovf);', 'x2 = dc_q_sub(x2, dc_q(0, 1, &ovf), &ovf);'),
    ('blind_ignores_masses', 'ops_mon.c', 'if (dc_q_cmp(mn_mass(&d.A[i], d.N[i].val[j]), d.N[i].m[j])) blind = 0;', 'if (0 && dc_q_cmp(mn_mass(&d.A[i], d.N[i].val[j]), d.N[i].m[j])) blind = 0;'),
    # Detect
    ('factor_inverted', 'ops_mon.c', 'E[j] = dc_q_mul(E[j], dc_q_div(a1, n0, &ovf), &ovf);', 'E[j] = dc_q_mul(E[j], dc_q_div(n0, a1, &ovf), &ovf);'),
    ('union_threshold_not_k', 'ops_mon.c', 'DcQ thr = mix ? dc_q_div(one, L, &ovf) : dc_q_div(kk, L, &ovf);', 'DcQ thr = mix ? dc_q_div(one, L, &ovf) : dc_q_div(one, L, &ovf);'),
    ('mixture_sum_not_average', 'ops_mon.c', 'stat = dc_q_div(stat, kk, &ovf);', 'stat = dc_q_div(stat, one, &ovf);'),
    ('scheme_not_checked', 'ops_mon.c', 'if (sc && (sc->kind == SX_LIST || strcmp(sc->text, "Ville")))', 'if (0 && sc && (sc->kind == SX_LIST || strcmp(sc->text, "Ville")))'),
    # monitors-followups item 1: the Estimand must depend on the request (a constant one is caught)
    ('estimand_constant', 'ops_mon.c', 'sx_push(det, dc_form("Estimand", sx_str(estm), NULL));', 'sx_push(det, dc_form("Estimand", sx_str("constant"), NULL));'),
    # monitors-followups item 2: Union with no firing reports the largest-at-end monitor, not the first
    ('union_evalue_first', 'ops_mon.c', 'mn_qsx(mix ? stat : E[endj])', 'mn_qsx(mix ? stat : E[0])'),
    # admission and dispatch
    ('not_dispatched', 'ops_dispatch.c', 'm->monitors && !m->profile_unsupported[0]) return dc_req_monitors(r, q, h);', '0 && m->monitors && !m->profile_unsupported[0]) return dc_req_monitors(r, q, h);'),
    ('not_admitted', 'admit.c', '"NatArith", "Laws", "Monitors", NULL };', '"NatArith", "Laws", NULL };'),
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
    rf = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'monitors', 'run_monitors.py')],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
    with open(os.path.join(d, 'run_monitors.out'), 'w') as fh: fh.write(rf.stdout + rf.stderr)
    lines = rf.stdout.splitlines(); nf = sum(l.startswith('FAIL') for l in lines)
    report('mutant %s (%s): caught by run_monitors (exit %d, %d FAIL lines)' % (name, fn, rf.returncode, nf),
           rf.returncode != 0 and nf > 0, lines[-1:] if lines else rf.stderr[-300:])
print('run_monitors_mutants: %s' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
