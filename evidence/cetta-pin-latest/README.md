# Evidence: CeTTa pin moved to zariuq/CeTTa main 4c285a97

Hive task t-2026-11-06-mettadinc-cetta-pin-latest, on pop-os (Ubuntu 22.04, gcc 11.4.0, GNU ld 2.38, glibc 2.35,
GNU Make 4.3, Python 3.10.12; GMP headers from an extracted libgmp-dev via `MDINC_GMP_PREFIX`, as before). Branch
off 727b5af. Summary of findings: [docs/CETTA-LATEST.md](../../docs/CETTA-LATEST.md). Driver: [run-baseline.sh](run-baseline.sh).

| File | What | Result |
|---|---|---|
| 00_submodule_status.out | `git ls-remote` of upstream main at 2026-11-06T05:09:49Z, submodule status, gitlink | 4c285a97 |
| 00_pin_check.out | `tools/check-vendored-cetta.sh` after the pin commit | exit 0 |
| cetta-baseline/latest-run0-default-build | `tools/cetta-baseline.sh`, unmodified harness, at 2989924 | core build fails: GLIBC_ABI_DT_RELR (exit 2) |
| cetta-baseline/latest-run1 | the harness with `MDINC_MAKE_ARGS="PACK_RELATIVE_RELOCS="` | core build fails: src/tensor.c -Werror=stringop-overflow (exit 2) |
| cetta-baseline/diag-gcc11-make-k-core.log | `make -k -j8 BUILD=core PACK_RELATIVE_RELOCS=` (every gcc 11 error) | tensor.c:212; json_cst_value_v1.c:295, :518; EXIT=2 |
| cetta-baseline/diag-gcc12-make-k-core-partial.log | `make -k -j8 BUILD=core CC=gcc-12`, stopped early | DT_RELR in every generator; use-after-free errors in petta_program.c, rhocalc_core.c |
| 00_pin_check_after_builds.out | pin check after the builds (`git -C cetta checkout -- .` restored generated headers a failed generator had deleted) | exit 0 |

Not done, because the build fails and the order says to block there: test lanes at 4c285a97, regenerating
tools/cetta-baseline.expected, break-a-test, registry/oracle rerun.
