# Cetta latest main (4c285a97) against the 12da03b4 baseline

Hive task t-2026-11-06-mettadinc-cetta-pin-latest. Question: does mettadinc build and pass a green baseline on Zar's
current CeTTa main, and which tests that were green at 12da03b4 are not green now?

## Status: BLOCKED at the build. No test lane ran at 4c285a97.

The pin moved (`docs/CETTA-PIN.md`, pin check exit 0), but **Cetta 4c285a97 does not build with gcc on pop-os**
(Ubuntu 22.04: gcc 11.4.0, GNU ld 2.38, glibc 2.35; the same host and toolchain on which 12da03b4 built and ran green,
`evidence/m0-prep-submodule/cetta-baseline/sub-run1-green`). The order says to stop there and not patch Cetta, so
`tools/cetta-baseline.expected` is **not** regenerated: it is still the 12da03b4 baseline from E0's logs, and the
harness reports NOT GREEN (exit 2, build failure) at this pin. There is no per-lane count table and no list of
regressed tests yet, because no test ran.

## The build errors

Evidence: `evidence/cetta-pin-latest/cetta-baseline/`.

| # | Where | Error | Introduced | Evidence |
|---|---|---|---|---|
| 1 | Makefile:701 `PACK_RELATIVE_RELOCS` | The probe adds `-Wl,-z,pack-relative-relocs` whenever the linker *accepts* it. ld 2.38 does, but the linked tools then require `GLIBC_ABI_DT_RELR`, which glibc < 2.36 lacks, so the first generated tool dies: `runtime/langdef-compile-v1-core...: /lib/x86_64-linux-gnu/libc.so.6: version 'GLIBC_ABI_DT_RELR' not found` → `make: *** [Makefile:8487: runtime/generated/match_decision_policy_v1.answers] Error 1`. A two-line C program linked with that flag fails the same way on this host. | 077f99a8 (2026-10-27, "chasing mm2") | latest-run0-default-build/02_build_core.log |
| 2 | src/tensor.c:212 | `error: writing 1 byte into a region of size 0 [-Werror=stringop-overflow=]` (inlined from `cetta_tensor_copy_values`, src/tensor.c:1574; gcc 11 at -O3, `-Werror` from Makefile:693) | file added d14df728 (2026-10-22) | latest-run1/02_build_core.log, diag-gcc11-make-k-core.log |
| 3 | native/json_cst_value_v1.c:295 and :518 | `error: 'scalar' may be used uninitialized in this function [-Werror=maybe-uninitialized]` | file added 80aaa5cd (2026-08-26) | diag-gcc11-make-k-core.log |

Errors 2 and 3 are the complete list from `make -k -j8 BUILD=core PACK_RELATIVE_RELOCS=` with gcc 11.4
(diag-gcc11-make-k-core.log, EXIT=2); each object fails twice (stage0 and final). They look like gcc 11 diagnostic
false positives rather than real bugs, but that is for Zar to judge; `-Werror` makes them fatal either way. Error 1 is
independent of the compiler.

The python build was not reached (the harness stops at the core build).

**gcc 12 is not a way round.** The host also has gcc-12 (12.3.0). `make -k -j8 BUILD=core CC=gcc-12` (partial log,
stopped early: diag-gcc12-make-k-core-partial.log) hits error 1 in every generator and also new `-Werror` errors in
files that existed at 12da03b4: `src/petta_program.c:138: pointer 'storage' used after 'free' [-Werror=use-after-free]`,
`src/rhocalc_core.c:3976` and `:6054: pointer used after 'free' [-Werror=use-after-free]`.

Side observation: when a generator fails, make deletes its target, and some of those targets are tracked files
(`src/generated/*.generated.h`); after the stopped gcc-12 run ten were missing from the checkout and the pin check would
have failed. `git -C cetta checkout -- .` restored them (evidence/cetta-pin-latest/00_pin_check_after_builds.out, exit 0).

## Count table (filled in once a lane runs)

| Lane | 12da03b4 (E0 / sub-run1-green) | 4c285a97 |
|---|---|---|
| rhocalc | 253 passed / 0 failed; 261 PASS lines, 5 SKIP, exit 0 | not run: core build fails |
| core (`make -k test-correctness test-profiles`) | 502 PASS / 6 SKIP / 1 FAIL (py-call), failed targets catalog-guards, petta-search-machine | not run: core build fails |
| python | 503 PASS / 6 SKIP / 0 FAIL, failed target catalog-guards | not run: core build fails |

Already known for when it runs: upstream restructured the targets. `test-correctness` now depends on `test` =
`NORMAL_TEST_TARGETS` (Makefile:19038), which includes `test-main-corpus-default`, the loop over
`tests/test_*.metta tests/spec_*.metta tests/he_*.metta`; and `test-he-compat-catalog-guards` is now
`python3 scripts/test_he_compat_catalog_guards.py`, with no Mettapedia dependency visible. So the aggregate loop
that the catalog-guards failure hid at 12da03b4 should now run inside the core and python lanes, and the PASS counts
will not be comparable line-for-line without naming the new tests separately.

## Ways forward (decision requested on the hive)

- A. Zar fixes errors 1 to 3 upstream (probe that runs the linked program, not only links it; the two gcc 11 warnings),
  and this task re-pins to the fixed main and runs the lanes. Recommended.
- B. Allow build overrides from the make command line, with no Cetta file changed: `PACK_RELATIVE_RELOCS=` and
  `CFLAGS='-O3 -Wall -Werror -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized -std=c11 -pthread'` (or
  `-Wno-error`), recorded in each summary via `MDINC_MAKE_ARGS`. Answers the regression question today; the baseline
  would then be "green with these overrides", which should be stated wherever it is used.
- C. Pin the newest main commit that builds unmodified with gcc 11.4 here (bisect; at most d14df728^ because of error 2,
  and before 077f99a8 because of error 1).
