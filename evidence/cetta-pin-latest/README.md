# Evidence: CeTTa pin moved to zariuq/CeTTa main 4c285a97

Hive task t-2026-11-06-mettadinc-cetta-pin-latest, on pop-os (Ubuntu 22.04, gcc 11.4.0, GNU ld 2.38, glibc 2.35,
GNU Make 4.3, Python 3.10.12; GMP headers from an extracted libgmp-dev via `MDINC_GMP_PREFIX`, as before). Summary of
findings: [docs/CETTA-LATEST.md](../../docs/CETTA-LATEST.md). Drivers: [run-baseline.sh](run-baseline.sh) (baseline runs),
[run-registry-oracles.sh](run-registry-oracles.sh), [run-rhocalc-swipl-diag.sh](run-rhocalc-swipl-diag.sh).

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

Not done, pending the decision requested on the hive: regenerating tools/cetta-baseline.expected and the
break-a-test check.
