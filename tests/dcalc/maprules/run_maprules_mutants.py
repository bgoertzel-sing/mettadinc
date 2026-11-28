#!/usr/bin/env python3
"""t-2026-11-26-mettadinc-shared-loader acceptance 1, second half: for every shared map rule in every loader,
a build with that loader's shared call (maprules.h) removed must fail run_maprules.py on exactly the fixture
rows that break the rule (both modes for Crisp and Families fixtures) and on no other row.  Each mutant patches one site of a scratch copy of src/dcalc, builds it, and runs the
unchanged gate against it.  Template: tests/dcalc/natarith/run_natarith_mutants.py."""
import os, shutil, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC = os.path.join(ROOT, 'src', 'dcalc')
OUT = os.path.join(ROOT, 'build', 'maprules_mutants')
CC = os.environ.get('CC', 'cc')
B = '--beyond-release'
# (name, file, site, replacement, FAIL lines the gate must print)
MUTANTS = [
    ('nd_dup', 'ops_nondet.c', 'if (rc == DC_MR_DUP) return nd_err(err, es, "Map %s: %s has two cases"', 'if (0) return nd_err(err, es, "Map %s: %s has two cases"', ['FAIL  nd_rules --beyond-release NdDup:']),
    ('nd_total', 'ops_nondet.c', 'if (dc_mr_total(&mr, NULL) == DC_MR_PARTIAL) return nd_err', 'if (0) return nd_err', ['FAIL  nd_rules --beyond-release NdTotal:']),
    ('nd_codomain', 'ops_nondet.c', 'if (dc_mr_value(y) == DC_MR_CODOMAIN) return nd_err', 'if (y < 0) continue; if (0) return nd_err', ['FAIL  nd_rules --beyond-release NdCodomain:']),
    ('st_map_total', 'stoch.c', '            if (dc_mr_total(&mr, NULL)) return st_err(err, es, "map is not total:", nm);\n            s->nmap++;', '            if (0) return st_err(err, es, "map is not total:", nm);\n            s->nmap++;', ['FAIL  st_rules --beyond-release StMapTotal:']),
    ('st_map_codomain', 'stoch.c', 'if (dc_mr_put(&mr, a, b)) return st_err(err, es, "bad or duplicate case in map", nm);', 'if (dc_mr_put(&mr, a, b < 0 ? 0 : b)) return st_err(err, es, "bad or duplicate case in map", nm);', ['FAIL  st_rules --beyond-release StMapCodomain:']),
    ('st_ker_dup_row', 'stoch.c', 'if (dc_mr_mark(&mr, a)) return st_err(err, es, "bad or duplicate Row in kernel", nm);', 'if (dc_mr_mark(&mr, a) == DC_MR_KEY) return st_err(err, es, "bad or duplicate Row in kernel", nm);', ['FAIL  st_rules --beyond-release StKerDupRow:']),
    ('st_ker_missing_row', 'stoch.c', 'if (dc_mr_total(&mr, NULL)) return st_err(err, es, "kernel has a missing Row:", nm);', 'if (0) return st_err(err, es, "kernel has a missing Row:", nm);', ['FAIL  st_rules --beyond-release StKerMissingRow:']),
    ('st_ker_dup_outcome', 'stoch.c', 'if (b >= 0 && dc_mr_mark(&mo, b) == DC_MR_DUP) return st_err', 'if (0 && dc_mr_mark(&mo, b) == DC_MR_DUP) return st_err', ['FAIL  st_rules --beyond-release StKerDupOutcome:']),
    ('st_ker_codomain', 'stoch.c', 'if (dc_mr_value(b) || st_rat(ms->items[2], &w)', 'if (b < 0) continue; if (st_rat(ms->items[2], &w)', ['FAIL  st_rules --beyond-release StKerCodomain:']),
    ('st_ker_mass_neg', 'stoch.c', '|| dc_mr_mass_entry(w)) return st_err(err, es, "bad Mass', ') return st_err(err, es, "bad Mass', ['FAIL  st_rules --beyond-release StKerMassNeg:']),
    # review 1 F1: the Reach restriction checks go through the shared module too; remove each call
    ('mc_reach_restrict_codomain', 'model.c', 'if (dc_mr_value(j) == DC_MR_CODOMAIN) {   /* R3 on the restricted image', 'if (0) {   /* R3 on the restricted image', ['FAIL  mc_rules rel McReachImage:', 'FAIL  mc_rules --beyond-release McReachImage:']),
    ('st_reach_restrict_codomain', 'stoch.c', 'if (dc_mr_value(j < C->n ? j : -1)) return -3;', 'if (0) return -3;', ['FAIL  st_rules --beyond-release StReachImage:']),
    ('st_reach_restrict_mass', 'stoch.c', 'if (ovf || dc_mr_mass_row(sum)) return -3;', 'if (ovf) return -3;', ['FAIL  st_rules --beyond-release StReachMass:']),
    ('st_ker_mass_sum', 'stoch.c', 'if (dc_mr_mass_row(sum)) return st_err(', 'if (0) return st_err(', ['FAIL  st_rules --beyond-release StKerMassSum:']),
    ('mc_table_dup', 'model.c', 'if (rc == DC_MR_DUP) { free(mp->table); return fail(err, es, "Map %s: Table key at row %zu repeated"', 'if (0) { free(mp->table); return fail(err, es, "Map %s: Table key at row %zu repeated"', ['FAIL  mc_rules --beyond-release McTableDup:']),
    ('mc_table_codomain', 'model.c', 'if (rc == DC_MR_CODOMAIN) { free(mp->table); return fail(err, es, "Map %s: Table row %zu value outside carrier', 'if (0) { free(mp->table); return fail(err, es, "Map %s: Table row %zu value outside carrier', ['FAIL  mc_rules --beyond-release McTableCodomain:']),
    ('mc_total', 'model.c', '    if (dc_mr_total(&mr, &miss)) {\n        char *s = sx_print(F->elems[miss]);', '    if (0 && dc_mr_total(&mr, &miss)) {\n        char *s = sx_print(F->elems[miss]);', ['FAIL  mc_rules --beyond-release McTableTotal:', 'FAIL  mc_rules --beyond-release McCasesTotal:']),
    ('mc_cases_codomain', 'model.c', 'if (dc_mr_put(&mr, (int)i, b) == DC_MR_CODOMAIN) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu gives a value outside carrier', 'if (dc_mr_put(&mr, (int)i, b < 0 ? 0 : b) == DC_MR_CODOMAIN && 0) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu gives a value outside carrier', ['FAIL  mc_rules --beyond-release McCasesCodomain:']),
    ('mc_cases_overlap', 'model.c', 'if (match(r2->items[0], F->elems[i], &e2) && dc_mr_mark(&mr, (int)i) == DC_MR_DUP) {', 'if (0 && match(r2->items[0], F->elems[i], &e2) && dc_mr_mark(&mr, (int)i) == DC_MR_DUP) {', ['FAIL  mc_rules --beyond-release McCasesOverlap:']),
    ('tm_overlap', 'model.c', '            if (dc_mr_mark(&ov, (int)i) == DC_MR_DUP) {', '            if (dc_mr_mark(&ov, (int)i) == DC_MR_DUP && 0) {', ['FAIL  tm_rules --beyond-release TmOverlap:']),
    ('tm_total', 'model.c', 'if (dc_mr_missing(&ov, (int)i)) { char *xs', 'if (dc_mr_missing(&ov, (int)i)) { (void)dc_mr_put(&mr, (int)i, 0); continue; } if (0) { char *xs', ['FAIL  tm_rules --beyond-release TmTotal:']),
    ('tm_codomain', 'model.c', '(totype && dc_mr_value(has_type(v, totype) ? 0 : -1) == DC_MR_CODOMAIN)', '(totype && 0)', ['FAIL  tm_rules --beyond-release TmCodomain:']),
    ('m7_enc_total', 'ops_m7.c', '\n        if (rr == DC_MR_PARTIAL) { sx_free(claim); return dc_invalid(m, "CheckNow: Encode map', '\n        if (0) { sx_free(claim); return dc_invalid(m, "CheckNow: Encode map', ['FAIL  m7_rules --beyond-release M7EncPartial:']),
    ('m7_obs_total', 'ops_m7.c', 'if (rr == DC_MR_PARTIAL) { sx_free(claim); return dc_invalid(m, "CheckNow: observation map', 'if (0) { sx_free(claim); return dc_invalid(m, "CheckNow: observation map', ['FAIL  m7_rules --beyond-release M7ObsPartial:']),
    ('m7_codomain', 'ops_m7.c', 'if (dc_mr_value(m7_inhabits(m, to->items[1], m7_case(map, nm[s]), 0) ? 0 : -1) == DC_MR_CODOMAIN) return nm[s];', 'if (0) return nm[s];', ['FAIL  m7_rules --beyond-release M7EncCodomain:']),
    ('fm_dup', 'families.c', 'if (rc == DC_MR_DUP) { fe_invalid(f, "Map %s: Table key at row %zu repeated"', 'if (0) { fe_invalid(f, "Map %s: Table key at row %zu repeated"', ['FAIL  fm_rules --beyond-release FmTableDup:']),
    ('fm_codomain', 'families.c', 'if (rc == DC_MR_CODOMAIN) { fe_invalid(f,', 'if (0) { fe_invalid(f,', ['FAIL  fm_rules --beyond-release FmTableCodomain:']),
    ('fm_total', 'families.c', 'if (dc_mr_total(&mr, &miss)) { char *s = sx_print(en->items[miss + 1]); fe_invalid', 'if (0) { char *s = sx_print(en->items[miss + 1]); fe_invalid', ['FAIL  fm_rules --beyond-release FmTableTotal:']),
    # rebase review 1 F1: the literal Coin branch of st_lawx decides R4 through the shared module; remove each call
    ('st_law_coin_lit_neg', 'stoch.c', 'if (dc_mr_mass_entry(p)) return -1;   /* R4 (maprules.h): p >= 0 */', 'if (0) return -1;   /* R4 (maprules.h): p >= 0 */', ['FAIL  law_rules --beyond-release StLawCoinNegLit:']),
    ('st_law_coin_lit_gt1', 'stoch.c', 'if (dc_mr_mass_entry(q)) return -1;   /* R4 (maprules.h): 1 - p >= 0, i.e. p <= 1 */', 'if (0) return -1;   /* R4 (maprules.h): 1 - p >= 0, i.e. p <= 1 */', ['FAIL  law_rules --beyond-release StLawCoinLit:']),
    # rebase-monitors review 1 F1: the Monitors Table reader (ops_mon.c mn_table_rules) decides R1-R3 through maprules
    ('mon_dup', 'ops_mon.c', 'else if (rc == DC_MR_DUP) snprintf(w, sizeof w,', 'else if (0) snprintf(w, sizeof w,', ['FAIL  mon_rules --beyond-release MonRulesDup:', 'FAIL  mon_rules --beyond-release MonRulesDupSwap:']),
    ('mon_codomain', 'ops_mon.c', 'else if (rc == DC_MR_CODOMAIN) snprintf(w, sizeof w,', 'else if (0) snprintf(w, sizeof w,', ['FAIL  mon_rules --beyond-release MonRulesCodomain:']),
    ('mon_total', 'ops_mon.c', 'if (!w[0] && dc_mr_total(&mr, &miss))', 'if (!w[0] && 0 && dc_mr_total(&mr, &miss))', ['FAIL  mon_rules --beyond-release MonRulesTotal:']),
]
fails = 0
def report(name, ok, det=''):
    global fails
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  :: %s' % (det,)))
    if not ok: fails += 1
only = sys.argv[1:]
os.makedirs(OUT, exist_ok=True)
for name, fn, a, b, need in MUTANTS:
    if only and name not in only: continue
    d = os.path.join(OUT, name); shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, os.path.join(d, 'src', 'dcalc'), ignore=shutil.ignore_patterns('*.o', '*.a'))
    f = os.path.join(d, 'src', 'dcalc', fn); s = open(f).read()
    if s.count(a) != 1: report('mutant %s: patch site in %s found exactly once' % (name, fn), False, s.count(a)); continue
    open(f, 'w').write(s.replace(a, b))
    bd = subprocess.run(['make', '-s', '-j4', 'CC=' + CC, 'BUILD=' + os.path.join(d, 'build')], cwd=os.path.join(d, 'src', 'dcalc'),
                        capture_output=True, text=True, timeout=900)
    if bd.returncode != 0: report('mutant %s: builds' % name, False, bd.stderr[-400:]); continue
    env = dict(os.environ, DCALC_MAPRULES_DC=os.path.join(d, 'build'))
    rf = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'maprules', 'run_maprules.py')],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    with open(os.path.join(d, 'run_maprules.out'), 'w') as fh: fh.write(rf.stdout + rf.stderr)
    lines = rf.stdout.splitlines()
    need = need + [g.replace(' ' + B + ' ', ' rel ') for g in need if g.split()[1] in ('mc_rules', 'tm_rules', 'fm_rules')]
    miss = [g for g in need if not any(l.startswith(g) for l in lines)]
    extra = [l.split(':', 1)[0] + ':' for l in lines if l.startswith('FAIL') and l.split(':', 1)[0] + ':' not in need]
    miss = miss + ['unexpected ' + x for x in extra]   # a mutant must break only its own rule's rows
    report('mutant %s (%s): caught by run_maprules (exit %d, %d FAIL lines; required %s)'
           % (name, fn, rf.returncode, sum(l.startswith('FAIL') for l in lines), '; '.join(x[6:].rstrip(':') for x in need)),
           rf.returncode != 0 and not miss, miss or (lines[-1:] if lines else ''))
    shutil.rmtree(os.path.join(d, 'build'), ignore_errors=True)
print('run_maprules_mutants: %s (%d mutants)' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails, len(MUTANTS)))
sys.exit(1 if fails else 0)
