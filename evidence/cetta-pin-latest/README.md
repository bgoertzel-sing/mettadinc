# Evidence: CeTTa pin moved to zariuq/CeTTa main 4c285a97

Hive task t-2026-11-06-mettadinc-cetta-pin-latest, on pop-os (Ubuntu 22.04, gcc 11.4.0, GNU ld 2.38, glibc 2.35,
GNU Make 4.3, Python 3.10.12; GMP headers from an extracted libgmp-dev via `MDINC_GMP_PREFIX`, as before). Summary of
findings: [docs/CETTA-LATEST.md](../../docs/CETTA-LATEST.md). Drivers: [run-baseline.sh](run-baseline.sh) (baseline runs; MDINC_SWIPL_DIR is passed through from the environment),
[run-break-revert.sh](run-break-revert.sh) (break-a-test, then reverted),
[run-registry-oracles.sh](run-registry-oracles.sh), [run-rhocalc-swipl-diag.sh](run-rhocalc-swipl-diag.sh).

SWI-Prolog from latest-run3 on (hive answer 2, "A2"): 9.2.9 built from source without sudo
([swipl-9.2.9/build-swipl.sh](swipl-9.2.9/build-swipl.sh)), `MDINC_SWIPL_DIR=$HOME/scratch/mettadinc-e0/swipl9/install`.

Build overrides used from latest-run2 on (hive decision, answer 1):
`MDINC_MAKE_ARGS="PACK_RELATIVE_RELOCS= 'CFLAGS=-O3 -Wall -Werror -std=c11 -pthread -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized'"`.

| File | What | Result |
|---|---|---|
| 00_submodule_status.out | `git ls-remote` of upstream main at 2026-11-06T05:09:49Z, submodule status, gitlink | 4c285a97 |
| 00_pin_check.out | `tools/check-vendored-cetta.sh` after the pin commit | exit 0 |
| cetta-baseline/latest-run0-default-build | `tools/cetta-baseline.sh`, unmodified harness, at 2989924 | core build fails: GLIBC_ABI_DT_RELR (exit 2) |
| cetta-baseline/latest-run1 | the harness with `MDINC_MAKE_ARGS="PACK_RELATIVE_RELOCS="` | core build fails: src/tensor.c -Werror=stringop-overflow (exit 2) |
| cetta-baseline/diag-gcc11-make-k-core.log | `make -k -j8 BUILD=core PACK_RELATIVE_RELOCS=` (every gcc 11 error) | tensor.c:212; json_cst_value_v1.c:295, :518; EXIT=2 |
| cetta-baseline/diag-gcc12-make-k-core-partial.log | `make -k -j8 BUILD=core CC=gcc-12`, stopped early | DT_RELR in every generator; use-after-free errors in petta_program.c, rhocalc_core.c |
| 00_pin_check_after_builds.out | pin check after those builds (`git -C cetta checkout -- .` restored generated headers a failed generator had deleted) | exit 0 |
| cetta-baseline/latest-run2-overrides | the harness at 3c6472c with the build overrides, all lanes | builds pass; rhocalc 0 PASS exit 2 (no swipl); core 704/84/0, python 709/80/0, both fail test-test-target-scope; HARNESS_EXIT=1 against the 12da03b4 expected file |
| 00_pin_check_after_run2.out, 00_pin_check_after_run2_restored.out | pin check after run2 (the failed rhocalc generator deleted a tracked file), and after `git -C cetta checkout -- .` | exit 1, then exit 0 |
| analysis/ | reach-*.txt (targets reachable from test-correctness/test-profiles), missing-*.tsv and MISSING.md (E0 PASS lines not PASS now, with causes), new-skips-*.tsv | made by reach_targets.py, classify_missing.py, missing_md.py, new_skips.py |
| cetta-baseline/diag-rhocalc-swipl | diagnostic: the rhocalc command with a user-local SWI-Prolog 8.4.2 (Ubuntu jammy debs) on PATH | still exit 2: swipl 8.4.2 segfaults in library(crypto) (swipl-8.4.2-crash.log) |
| registry/, oracles/ | the unchanged registry and oracle checks | all exit 0; oracle totals 157 / 305 / 195 / 94 / 99 as expected |
| swipl-9.2.9/ | build-swipl.sh (source URL, sha256, cmake options), build.log, smoke.out (version, library(crypto) hash, pkg-config probe still false) | cmake/ninja/install exit 0; 9.2.9, PLVERSION 90209 |
| cetta-baseline/latest-run3-swipl | the harness at cdc03ec with the build overrides and MDINC_SWIPL_DIR, all lanes | rhocalc 285 passed / 0 failed, exit 0; core 704/84/0 and python 709/80/0 (identical to run2), each failing only test-test-target-scope; HARNESS_EXIT=1 against the old 12da03b4 expected file |
| 00_pin_check_after_run3.out, 00_pin_check_after_run3_restored.out, latest-run3-swipl/cetta-diff-after-run3.patch | pin check after run3 (the rhocalc run rewrote the tracked direct_runtime_lock_v1.metta, issue 7), the diff, and after restoring | exit 1, then exit 0 |
| (tools/cetta-baseline.expected) | regenerated from latest-run3-swipl with `expected-from-logs --header=... --cetta=...`; test-test-target-scope frozen as expected failed target | cetta-baseline/run3-vs-new-expected.out: GREEN in all three lanes, EXIT=0 |
| analysis/rhocalc-run3-vs-12da03b4.txt | rhocalc lane by name against E0's 07 log (rhocalc_diff.py) | 0 FAIL; 50 old PASS lines renamed (45 surface -> syntax, 5 renamed files/cases), 34 new tests; SKIP 5 -> 1 |
| analysis/MISSING.md | regenerated (missing_md.py): core/python tables unchanged; rhocalc-suite section now gives each line's status in run3's rhocalc lane | 211 same name, 50 renamed, 0 not PASS |
| cetta-baseline/BREAK.txt, pin_check_while_broken.out, latest-run4-broken (a first attempt was aborted: two harnesses had built the same tree at once, see build/cetta-baseline/aborted/, not evidence) | one line appended to tests/rhocalc/translate_rho_to_mrho.expected and tests/test_arithmetic.expected; the harness | pin check exit 1 (both files M); RED in all three lanes, HARNESS_EXIT=1: rhocalc 284 passed / 1 failed (FAIL `rhocalc translate rho -> mrho`, failed target test-rhocalc); core and python each FAIL `tests/test_arithmetic.metta` (failed target test-main-corpus-default); 14 REGRESSION lines, all about these two tests |
| cetta-baseline/pin_check_after_revert.out, latest-run5-reverted, pin_check_after_run5.out | after `git -C cetta checkout --` of both files (and the lock), the harness again | pin check after revert exit 0; run5 GREEN in all three lanes (rhocalc 285/0, core 704/84/0, python 709/80/0), HARNESS_EXIT=0, submodule clean at start; pin check after run5 exit 1 only for the rewritten lock (issue 7), restored afterwards |
