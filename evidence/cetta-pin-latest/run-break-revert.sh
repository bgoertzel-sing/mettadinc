#!/usr/bin/env bash
# Break-a-test check for the 4c285a97 baseline (hive answer 2, item 3): with tools/cetta-baseline.expected regenerated
# from latest-run3-swipl, break two tests in the submodule checkout, run the harness (must be RED), revert, run it
# again (must be GREEN).  Same environment as latest-run3-swipl (build overrides, MDINC_SWIPL_DIR, GMP prefix).
# The two breaks, one line appended to each expected-output file:
#   tests/rhocalc/translate_rho_to_mrho.expected  (rhocalc lane: "rhocalc translate rho -> mrho"; E0's break)
#   tests/test_arithmetic.expected                (core and python lanes: main-corpus "tests/test_arithmetic.metta")
set -u
cd "$(dirname "$0")/../.."
E=evidence/cetta-pin-latest; C=$E/cetta-baseline
export MDINC_SWIPL_DIR=$HOME/scratch/mettadinc-e0/swipl9/install
ARGS="PACK_RELATIVE_RELOCS= 'CFLAGS=-O3 -Wall -Werror -std=c11 -pthread -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized'"
F1=tests/rhocalc/translate_rho_to_mrho.expected; F2=tests/test_arithmetic.expected
echo "deliberately broken by mettadinc break-a-test" >> cetta/$F1
echo "deliberately broken by mettadinc break-a-test" >> cetta/$F2
{ echo "== $(date -u +%FT%TZ) break: one line appended to each file =="; git -C cetta diff; } > $C/BREAK.txt
{ tools/check-vendored-cetta.sh; echo "EXIT=$?"; } > $C/pin_check_while_broken.out 2>&1
$E/run-baseline.sh latest-run4-broken "$ARGS"
git -C cetta checkout -- $F1 $F2
{ tools/check-vendored-cetta.sh; echo "EXIT=$?"; } > $C/pin_check_after_revert.out 2>&1
$E/run-baseline.sh latest-run5-reverted "$ARGS"
{ tools/check-vendored-cetta.sh; echo "EXIT=$?"; } > $C/pin_check_after_run5.out 2>&1
echo done > build/cetta-baseline/break-revert.done
