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
[ $rc = 0 ] && echo "MUTATION CHECK PASS" || echo "MUTATION CHECK FAIL"; exit $rc
