#!/bin/sh
# AC7: one command builds the MeTTaDinC M0 core and runs every M0 test.
#   tools/dcalc-run-all.sh        (CC/AR from PATH; gcc 11+ or zig cc)
# Exit 0 iff the build and all suites pass.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 2
CC=${CC:-gcc}
rc=0
step() { echo "== $*"; }
step build;            (cd src/dcalc && make -s CC="$CC") || exit 1
step test_boundaries;  $CC -std=c11 -Wall -Wextra -O2 -Isrc/dcalc tests/dcalc/test_boundaries.c build/dcalc/libdcalc.a -o build/dcalc/test_boundaries \
                         && build/dcalc/test_boundaries | tail -1 || rc=1
step check_claims;     python3 tests/dcalc/check_claims.py | tail -4 || rc=1
step negative_suite;   python3 tests/dcalc/negative/run_negative.py || rc=1
step mutation;         python3 tests/dcalc/mutate.py || rc=1
echo "dcalc-run-all: $([ $rc = 0 ] && echo PASS || echo FAIL)"
exit $rc
