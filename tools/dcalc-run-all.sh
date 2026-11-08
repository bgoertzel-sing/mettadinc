#!/bin/sh
# AC7: one command builds the MeTTaDinC M0 core and runs every M0 test.
#   tools/dcalc-run-all.sh        (CC/AR from PATH; gcc 11+ or zig cc)
# Exit 0 iff the build and all suites pass.  The last step builds a patched
# scratch CeTTa (tools/dcalc-cetta-smoke.sh) and runs the MeTTa smoke tests;
# CETTA_CFLAGS passes extra flags (e.g. -Wno-error=... for gcc 11).
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 2
CC=${CC:-gcc}
rc=0
step() { echo "== $*"; }
R="python3 tools/dcalc_res.py"; rm -f build/dcalc-resources.tsv
step build;            $R build "cd src/dcalc && make -s CC='$CC'" || exit 1
step test_boundaries;  $R test_boundaries "$CC -std=c11 -Wall -Wextra -O2 -Isrc/dcalc tests/dcalc/test_boundaries.c build/dcalc/libdcalc.a -o build/dcalc/test_boundaries && { build/dcalc/test_boundaries > build/test_boundaries.out; r=\$?; tail -1 build/test_boundaries.out; exit \$r; }" || rc=1
step check_claims;     $R check_claims "python3 tests/dcalc/check_claims.py > build/check_claims.out; r=\$?; tail -4 build/check_claims.out; exit \$r" || rc=1
step negative_suite;   $R negative_suite "python3 tests/dcalc/negative/run_negative.py" || rc=1
step refuted_abs;      $R refuted_abs "sh tests/dcalc/refuted_abs/run_refuted_abs.sh" || rc=1
step mutation;         $R mutation "python3 tests/dcalc/mutate.py" || rc=1
step cetta_smoke;      if [ "${DCALC_SKIP_CETTA:-0}" = 1 ]; then echo "skipped (DCALC_SKIP_CETTA=1)"; else $R cetta_smoke "tools/dcalc-cetta-smoke.sh" || rc=1; fi
step resources;        cat build/dcalc-resources.tsv
echo "dcalc-run-all: $([ $rc = 0 ] && echo PASS || echo FAIL)"
exit $rc
