#!/bin/sh
# Committed mutation check for the differential gate (review 1 F1, order acceptance 5).
# Each mutant is one sed edit of a copy of src/dcalc, built into build/dt_mut/<name>.
# gate.sh is run against the mutant binary; the check PASSES only if every mutant makes gate.sh FAIL.
# Nothing in src/ is modified.  usage: sh tests/dcalc/differential/mutate_gate.sh   (CC from env, default gcc)
set -u
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); cd "$ROOT" || exit 2
CC=${CC:-gcc}; MUT=build/dt_mut; rc=0
mutant() {   # name file sed-expr
  d=$MUT/$1; rm -rf "$d"; mkdir -p "$d/src"; cp -r src/dcalc "$d/src/dcalc"
  before=$(md5sum < "$d/src/dcalc/$2"); sed -i "$3" "$d/src/dcalc/$2"
  if [ "$before" = "$(md5sum < "$d/src/dcalc/$2")" ]; then echo "MUTANT $1: sed did not apply"; rc=1; return; fi
  if ! (cd "$d/src/dcalc" && make -s -j1 CC="$CC" BUILD=../../build/dcalc > ../../build.log 2>&1); then echo "MUTANT $1: build failed"; rc=1; return; fi
  if sh tests/dcalc/differential/gate.sh "$d/build/dcalc/dcalc" > "$d/gate.out" 2>&1; then echo "MUTANT $1 SURVIVED (gate passed)"; rc=1
  else echo "MUTANT $1 killed ($(grep -cE 'FAIL|NEW' "$d/gate.out") fail lines)"; fi
}
# M1: CheckLinearArrow rho keeps only the last row's residual (escaped the 20-case pilot in review 1)
mutant lin_rho_lastrow stoch.c 's/\*rho = dc_rat_max(\*rho, row);/*rho = row;/'
# M2: behavioral layer distance halved (Kantorovich recurrence)
mutant kant_half stoch.c 's/nd\[x\]\[y\] = dc_rat_mul(gamma, best, ovf);/nd[x][y] = dc_rat_mul(dc_rat_mul(gamma, best, ovf), dc_rat(1, 2, ovf), ovf);/'
# M3 (D4 review-1 F2): dc_tol_dist (model.c) unclipped again; only the D4_tol_dist canary sees it
mutant d4_tol_unclipped model.c 's/return dc_rat_min(one, dc_rat_abs(dc_rat_sub(a, b, ovf))); }/return dc_rat_abs(dc_rat_sub(a, b, ovf)); }/'
# M4 (D4): ct_dist (ops_contracts.c) unclipped again
mutant d4_con_unclipped ops_contracts.c 's/\*d = dc_rat_min((DcRat){1, 1}, dc_rat_abs(dc_rat_sub(a, b, ovf)));/*d = dc_rat_abs(dc_rat_sub(a, b, ovf));/'
# M5 (D5, t-2026-11-19-mettadinc-d5-behavioral-classpairs): defect restricted to pairs where one state is the
# other's representative (the old max_x d(x, rep(x))); the D5 canary must catch it
mutant d5_rep_only stoch.c 's/if (E->tab\[x\] == E->tab\[y\] && dc_rat_cmp(d\[x\]\[y\], def) > 0)/if ((E->tab[x] == y || E->tab[y] == x) \&\& dc_rat_cmp(d[x][y], def) > 0)/'
# M6 (D6, t-2026-11-24-mettadinc-d6-trace-fix-v2): horizon trace defect restricted to (E(x), x) pairs again (the old
# representative-only rule); the D6 gate must catch it
mutant d6_rep_only stoch.c 's/for (int x = 0; x < n; x++) for (int j = -1; j < n; j++) {/for (int x = 0; x < n; x++) for (int j = -1; j < 0; j++) {/'
# M7 (D3, t-2026-11-19-mettadinc-d3-signed-normalization): the row-sum normalization checked only for Kind Positive
# again (the old behaviour); the D3 canary must catch it
mutant d3_positive_only stoch.c 's/        if (dc_rat_cmp(sum, dc_rat(1, 1, ovf))) { snprintf(why, ws, "row %s does not sum to 1"/        if (!strcmp(L->kind, "Positive") \&\& dc_rat_cmp(sum, dc_rat(1, 1, ovf))) { snprintf(why, ws, "row %s does not sum to 1"/'
[ $rc = 0 ] && echo "MUTATION CHECK PASS" || echo "MUTATION CHECK FAIL"; exit $rc
