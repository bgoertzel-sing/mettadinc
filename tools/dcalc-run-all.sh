#!/bin/sh
# AC7: one command builds the MeTTaDinC M0 core and runs every M0 test.
#   tools/dcalc-run-all.sh        (CC/AR from PATH; gcc 11+ or zig cc)
# Exit 0 iff the build and all suites pass.  The last step builds a patched
# scratch CeTTa (tools/dcalc-cetta-smoke.sh) and runs the MeTTa smoke tests;
# CETTA_CFLAGS overrides the extra CeTTa CFLAGS; the default (-Wno-error=stringop-overflow
# -Wno-error=maybe-uninitialized) is what gcc 11.4 / Ubuntu 22.04 needs (review 3 F1).
set -u
# M3 proof backend: check_claims (F01/F03/F04/F06 Checked), m3_gates and m3_tv need the pinned
# CaDiCaL rel-3.0.1 and cake_lpr 033aad5 via DCALC_CADICAL / DCALC_CAKE_LPR (see
# docs/PROOF-BACKEND.md). Without them those rows are Conditional by design.
if [ -z "${DCALC_CADICAL:-}" ] || [ -z "${DCALC_CAKE_LPR:-}" ]; then
  echo "dcalc-run-all: DCALC_CADICAL and DCALC_CAKE_LPR must name the pinned proof tools (docs/PROOF-BACKEND.md)"; exit 2
fi
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 2
CC=${CC:-gcc}
rc=0
step() { echo "== $*"; }
R="python3 tools/dcalc_res.py"; rm -f build/dcalc-resources.tsv
step build;            $R build "cd src/dcalc && make -s CC='$CC'" || exit 1
step test_boundaries;  $R test_boundaries "$CC -std=c11 -Wall -Wextra -O2 -Isrc/dcalc tests/dcalc/test_boundaries.c build/dcalc/libdcalc.a -lm -o build/dcalc/test_boundaries && { build/dcalc/test_boundaries > build/test_boundaries.out; r=\$?; tail -1 build/test_boundaries.out; exit \$r; }" || rc=1
step check_claims;     $R check_claims "python3 tests/dcalc/check_claims.py > build/check_claims.out; r=\$?; tail -4 build/check_claims.out; exit \$r" || rc=1
step negative_suite;   $R negative_suite "python3 tests/dcalc/negative/run_negative.py" || rc=1
step refuted_abs;      $R refuted_abs "sh tests/dcalc/refuted_abs/run_refuted_abs.sh" || rc=1
step envelope;         $R envelope "python3 tests/dcalc/envelope/run_envelope.py > build/envelope.out; r=\$?; tail -3 build/envelope.out; exit \$r" || rc=1
step limits;           $R limits "python3 tests/dcalc/limits/run_limits.py" || rc=1
step limits_sanitized; $R limits_sanitized "cd src/dcalc && make -s CC='$CC' BUILD=../../build/dcalc-sanitized CFLAGS='-std=c11 -Wall -Wextra -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all' && cd ../.. && DCALC=build/dcalc-sanitized/dcalc python3 tests/dcalc/limits/run_limits.py" || rc=1
step mutation;         $R mutation "python3 tests/dcalc/mutate.py" || rc=1
step held;             $R held "python3 tests/dcalc/held/run_held.py" || rc=1
step registry_gen;     $R registry_gen "python3 tools/gen_registry.py --check" || rc=1
step package;          $R package "python3 tests/dcalc/package/run_package.py > build/package.out; r=\$?; tail -5 build/package.out; exit \$r" || rc=1
step admission_mutations; $R admission_mutations "python3 tests/dcalc/mutations/run_mutations.py > build/admission_mutations.out; r=\$?; tail -1 build/admission_mutations.out; exit \$r" || rc=1
step m2_claims;        $R m2_claims "python3 tests/dcalc/check_claims_m2.py > build/m2_claims.out; r=\$?; tail -1 build/m2_claims.out; exit \$r" || rc=1
step m2_gates;         $R m2_gates "python3 tests/dcalc/mutations/run_m2_gates.py > build/m2_gates.out; r=\$?; tail -1 build/m2_gates.out; exit \$r" || rc=1
step m2_differential;  $R m2_differential "$CC -std=c11 -Wall -Wextra -O2 -Isrc/dcalc tests/dcalc/differential_m2.c build/dcalc/libdcalc.a -lm -o build/dcalc/differential_m2 && build/dcalc/differential_m2 20261110 5000 7" || rc=1
step m2_screen;  $R m2_screen "$CC -std=c11 -Wall -Wextra -O2 -Isrc/dcalc tests/dcalc/screen_m2.c build/dcalc/libdcalc.a -lm -o build/dcalc/screen_m2 && build/dcalc/screen_m2 20261110" || rc=1
step m2_claimless;     $R m2_claimless "python3 tests/dcalc/claimless/run_claimless.py > build/m2_claimless.out; r=\$?; tail -1 build/m2_claimless.out; exit \$r" || rc=1
step m3_incremental;    $R m3_incremental "cd src/dcalc && make -s CC='$CC' tests && cd ../.. && build/dcalc/m3_incremental > build/m3_incremental.out; r=\$?; tail -1 build/m3_incremental.out; exit \$r" || rc=1
step m3_gates;         $R m3_gates "python3 tests/dcalc/mutations/run_m3_gates.py > build/m3_gates.out; r=\$?; tail -1 build/m3_gates.out; exit \$r" || rc=1
step m3_tv;            $R m3_tv "sh tests/dcalc/tv/run_tv.sh" || rc=1
step m4_gates;         $R m4_gates "python3 tests/dcalc/m4/run_m4_gates.py > build/m4_gates.out; r=\$?; tail -1 build/m4_gates.out; exit \$r" || rc=1
step m4_estimates;     $R m4_estimates "$CC -std=c11 -Wall -Wextra -O2 -Isrc/dcalc tests/dcalc/m4/test_estimates.c build/dcalc/libdcalc.a -lm -o build/dcalc/test_estimates && build/dcalc/test_estimates docs/e0/docs/06_wmtm_worked_example/validation_bundle > build/m4_estimates.out; r=\$?; tail -1 build/m4_estimates.out; exit \$r" || rc=1
step m4_coverage;      $R m4_coverage "$CC -std=c11 -Wall -Wextra -O2 -Isrc/dcalc tests/dcalc/m4/sim_coverage.c build/dcalc/libdcalc.a -lm -o build/dcalc/sim_coverage && build/dcalc/sim_coverage 20261112 2000 > build/m4_coverage.out; r=\$?; tail -1 build/m4_coverage.out; exit \$r" || rc=1
step m4_coverage_01;   $R m4_coverage_01 "build/dcalc/sim_coverage 20261112 2000 0.01 > build/m4_coverage_01.out; r=\$?; tail -1 build/m4_coverage_01.out; exit \$r" || rc=1
step cetta_smoke;      if [ "${DCALC_SKIP_CETTA:-0}" = 1 ]; then echo "skipped (DCALC_SKIP_CETTA=1)"; else $R cetta_smoke "tools/dcalc-cetta-smoke.sh" || rc=1; fi
# review 1 F3: record the CeTTa weak-barbed script verdicts whenever the scratch CeTTa exists
# (built by cetta_smoke).  Recorded only: (ScriptCostBudget d), Horizon None, Oracle False.
step m5_weakbarbed;    if [ -x build/cetta-dcalc/cetta ] && [ -f build/cetta-dcalc/scripts/rhocalc_bounded_bisimulation.py ]; then $R m5_weakbarbed "python3 tests/dcalc/m5/weakbarbed_record.py build/cetta-dcalc \"$ROOT/build/cetta-dcalc/cetta\" build/m5_weakbarbed.tsv" || rc=1; else echo "skipped (no CeTTa scratch build at build/cetta-dcalc; run cetta_smoke first)"; fi
# review 2 F5: m5_gates runs after m5_weakbarbed so the recorded-verdict row sees build/m5_weakbarbed.tsv on a fresh tree
step m5_gates;         $R m5_gates "python3 tests/dcalc/m5/run_m5_gates.py > build/m5_gates.out; r=\$?; tail -1 build/m5_gates.out; exit \$r" || rc=1   # M5 (t-2026-11-12-mettadinc-m5)
step m6_gates;         $R m6_gates "python3 tests/dcalc/m6/run_m6_gates.py > build/m6_gates.out; r=\$?; tail -1 build/m6_gates.out; exit \$r" || rc=1   # M6 (t-2026-11-13-mettadinc-m6, review-1 F5)
step resources;        cat build/dcalc-resources.tsv
echo "dcalc-run-all: $([ $rc = 0 ] && echo PASS || echo FAIL)"
exit $rc
