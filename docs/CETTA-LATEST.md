# Cetta latest main (4c285a97) against the 12da03b4 baseline

Hive task t-2026-11-06-mettadinc-cetta-pin-latest. Question: does mettadinc build and pass a green baseline on Zar's
current CeTTa main, and which tests that were green at 12da03b4 are not green now?

## Status (2026-11-06): green at 4c285a97 with build overrides and SWI-Prolog 9.2.9; frozen

Decisions on the hive (answer 1: build overrides, "B now"; answer 2: SWI-Prolog "A2", freeze test-test-target-scope):

- **Build:** 4c285a97 does not build unmodified with gcc 11.4 here (Upstream issues 1 to 3). It is built with make
  command-line overrides only, no Cetta file changed ("Build overrides" below).
- **SWI-Prolog:** since d9b3f42d test-rhocalc runs the `swipl` program (issue 5). SWI-Prolog 9.2.9, the last 9.x
  stable release, was built from source in a scratch folder without sudo
  ([evidence/cetta-pin-latest/swipl-9.2.9/](../evidence/cetta-pin-latest/swipl-9.2.9/)) and is put on PATH by the
  harness's new optional `MDINC_SWIPL_DIR` (recorded in summary.txt, every lane log and every lane summary line;
  unset changes nothing).
- **Lanes (latest-run3-swipl):** rhocalc **285 passed, 0 failed**, exit 0 (12da03b4: 253/0); core 704 PASS / 84 SKIP /
  0 FAIL and python 709 / 80 / 0, both failing only the make target `test-test-target-scope` (issue 6), which is
  frozen as an expected failed target, as catalog-guards was at 12da03b4.
- **Frozen baseline:** tools/cetta-baseline.expected was regenerated from latest-run3-swipl. Its header records the
  build overrides, the SWI-Prolog, and the expected failed target. latest-run3-swipl compares GREEN against it
  (`cetta-baseline/run3-vs-new-expected.out`).
- **Break-a-test:** two expected-output files broken -> RED in all three lanes, exactly on the broken tests; reverted ->
  GREEN in all three lanes ("Break-a-test" below).
- **Unchanged and passing:** the registry checks and the eight reference oracles.

So the baseline is **"green at 4c285a97 with build overrides"** (and SWI-Prolog 9.2.9 on PATH). Without
`MDINC_MAKE_ARGS` the core build fails; without `MDINC_SWIPL_DIR` (and no 9.x `swipl` on PATH) the rhocalc lane fails.
The harness prints a NOTE in both cases.

## Build overrides

Exact string, as passed to the harness (tools/cetta-baseline.sh, which now splits it with shell quoting rules):

    MDINC_MAKE_ARGS="PACK_RELATIVE_RELOCS= 'CFLAGS=-O3 -Wall -Werror -std=c11 -pthread -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized'"

i.e. two make arguments: `PACK_RELATIVE_RELOCS=` and
`CFLAGS=-O3 -Wall -Werror -std=c11 -pthread -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized`.

- The CFLAGS value is Cetta's own `CFLAGS = -O3 -Wall -Werror -std=c11 -pthread` (Makefile:693) with the two flags
  appended. A make command-line `CFLAGS+=...` cannot be used: a command-line variable replaces the Makefile's
  assignments, so `CFLAGS+=x` gives just `x` (checked with a two-line makefile). Repeating the Makefile's value is
  therefore the only way to append from the command line.
- Checked that this is the same as appending for these builds: `make -pn BUILD=core|python` shows the Makefile's
  CFLAGS is exactly `-O3 -Wall -Werror -std=c11 -pthread` for both (ENABLE_PIC=0, ENABLE_SANITIZERS=0,
  ENABLE_DURABLE=0, so neither `-fPIC` nor the sanitizer CFLAGS nor the vendored-sqlite CFLAGS rule applies), and
  no recipe statically reachable from test-rhocalc, test-correctness or test-profiles sets ENABLE_PIC=1,
  ENABLE_SANITIZERS=1 or ENABLE_DURABLE=1 (evidence/cetta-pin-latest/reach_targets.py; recursive `$(MAKE)` calls
  inside recipes were not followed). Recursive makes do inherit the command-line CFLAGS through MAKEFLAGS.
- Nothing else is overridden. The harness's default (MDINC_MAKE_ARGS unset) is still the unmodified build; at
  4c285a97 that fails at the core build (exit 2), as before. When the expected file is regenerated, its header will
  carry the override string, and the harness prints a NOTE when a run's MDINC_MAKE_ARGS differs from it.

## Count table

Evidence: `evidence/cetta-pin-latest/cetta-baseline/latest-run3-swipl/` (repo commit cdc03ec, submodule at 4c285a97
with no changes to tracked files at the start, MDINC_SWIPL_DIR set) and `latest-run2-overrides/` (commit 3c6472c,
no swipl). Counts from `tools/cetta_baseline_check.py` (summary.txt).

| Lane | 12da03b4 (E0's frozen logs) | 4c285a97 with build overrides, no swipl (run2) | 4c285a97 with build overrides and SWI-Prolog 9.2.9 (run3, the frozen baseline) |
|---|---|---|---|
| rhocalc (`make BUILD=core test-rhocalc`) | 261 PASS / 5 SKIP / 0 FAIL; **"253 passed, 0 failed"**; exit 0 | 0 PASS; no summary line; exit 2 (no `swipl`; issue 5) | 295 PASS / 1 SKIP / 0 FAIL; **"285 passed, 0 failed"**; exit 0 |
| core (`make -k BUILD=core test-correctness test-profiles`) | 502 PASS / 6 SKIP / 1 FAIL (py-call); failed targets catalog-guards, petta-search-machine; exit 2 | 704 PASS / 84 SKIP / 0 FAIL; failed target `test-test-target-scope`; exit 2 | identical to run2 (same multisets of PASS/SKIP/FAIL lines and failed targets) |
| python (`make -k BUILD=python test-correctness test-profiles`) | 503 PASS / 6 SKIP / 0 FAIL; failed target catalog-guards; exit 2 | 709 PASS / 80 SKIP / 0 FAIL; failed target `test-test-target-scope`; exit 2 | identical to run2 |

Both rhocalc runs also print an earlier "6 passed, 0 failed" (a sub-suite), as at 12da03b4.

### Rhocalc lane by name, against 12da03b4's 253/0

From `evidence/cetta-pin-latest/rhocalc_diff.py` (full list:
[analysis/rhocalc-run3-vs-12da03b4.txt](../evidence/cetta-pin-latest/analysis/rhocalc-run3-vs-12da03b4.txt)):

- **No FAIL, no new SKIP, no failed make target.** Exit 0, "285 passed, 0 failed".
- **50 PASS lines of 12da03b4 are not printed under the same name, and all 50 pass under a new name:** 45 differ only
  by "surface" becoming "syntax" (e.g. `rhocalc bounded bisimulation pure-surface-vs-core-comm` ->
  `pure-syntax-vs-core-comm`, the `rhocalc lib/rho surface tests/...` lines -> `rhocalc lib/rho syntax tests/...`,
  `rhocalc scheduler reachability surface-*` -> `syntax-*`); 5 are renamed files or cases, checked with
  `git diff -M 12da03b4 4c285a97`: `cost-rho parallel stress independent-surfaces` -> `independent-locations`;
  `tests/test_lts_rho_cost_surface.metta` -> `tests/test_lts_rho_cost_location.metta` (R099);
  `tests/rhocalc/surface_open_name_variable.rho` -> `rho_open_name_variable.rho`;
  `tests/rhocalc_run/pipeline_two_forwarders_surface.rho` -> `pipeline_two_forwarders_rho.rho`;
  `tests/rhocalc_run/quiescent_nil_surface.rho` -> `quiescent_nil_rho.rho`. A rename is evidence from names and
  git, not proof that the renamed test checks the same thing.
- **The other 34 new PASS lines are new tests:** 18 `rhocalc lean trace bridge <case>` and 12 `rhocalc run lean bridge
  rhometta-run-*` (at 12da03b4 the lean trace bridge printed SKIP without METTAPEDIA_ROOT; at 4c285a97 that branch is
  gone and the checks run, Makefile:20076ff), `direct rho payload keys agree with ordinary atom rendering`,
  `rhocalc generation compaction preserves bounded residual`, `rhocalc lib/rho syntax tests/test_rhometta_value_delivery.metta`,
  and `pure-rho canonical selector agrees with exhaustive frontier ...` (new in this lane; at 12da03b4 it ran in core).
- **SKIPs:** 5 -> 1. Still skipped: `rhocalc MN rholang-cli overlap` (no rholang-cli). Gone: the four
  "set METTAPEDIA_ROOT" skips (cost-rho differential harness, cost lean bridge, lean microcheck, lean trace bridge).

Of the PASS lines: core has 599 lines that were not in E0's log and lacks 397 of E0's; python has 604 new and lacks 398.
`test-he-compat-catalog-guards` now passes (it is `python3 scripts/test_he_compat_catalog_guards.py` at 4c285a97),
so it no longer hides the targets that depend on it: the main-corpus loop over `tests/test_*.metta` etc. now runs
inside the core and python lanes, and no separate "extra lanes" run was needed. `test-test-target-scope` hides
nothing else: `test` and `test-correctness` have no recipes of their own.

## Break-a-test (the regenerated expected file catches a regression)

Driver: `evidence/cetta-pin-latest/run-break-revert.sh` (same environment as run3: overrides, MDINC_SWIPL_DIR, GMP
prefix; expected file at commit e62a206). One line appended to each of two expected-output files in the submodule
checkout (`cetta-baseline/BREAK.txt`):

- `tests/rhocalc/translate_rho_to_mrho.expected` (the rhocalc lane's `rhocalc translate rho -> mrho`; E0's break);
- `tests/test_arithmetic.expected` (the main-corpus test `tests/test_arithmetic.metta`, in the core and python lanes).

| Step | Evidence | Result |
|---|---|---|
| pin check while broken | `cetta-baseline/pin_check_while_broken.out` | exit 1, the two files M |
| harness, broken | `cetta-baseline/latest-run4-broken/` | **RED in all three lanes**, HARNESS_EXIT=1. rhocalc: "284 passed, 1 failed", FAIL `rhocalc translate rho -> mrho`, failed target test-rhocalc, exit 2. core and python: FAIL `tests/test_arithmetic.metta`, failed target test-main-corpus-default. All 14 REGRESSION lines concern these two tests (counts, final line, exit, missing PASS, new FAIL, new failed target). |
| revert | `git -C cetta checkout -- <both files>`; `cetta-baseline/pin_check_after_revert.out` | exit 0 |
| harness, reverted | `cetta-baseline/latest-run5-reverted/` | **GREEN in all three lanes**, HARNESS_EXIT=0 (rhocalc 285/0 exit 0; core 704/84/0; python 709/80/0; the only failed target test-test-target-scope, expected) |

A first attempt at the broken run was aborted and is not evidence: a stale harness from an earlier launch was still
building the same tree, so two builds collided and the core build failed (logs moved to
`build/cetta-baseline/aborted/`, untracked). The runs above were made with a single harness running.

## Tests green at 12da03b4 and not green now

For the core and python lanes (run2; run3 is identical there). The full by-name list, with a cause for each, is
[evidence/cetta-pin-latest/analysis/MISSING.md](../evidence/cetta-pin-latest/analysis/MISSING.md) (from
`analysis/missing-core.tsv` and `missing-python.tsv`, made by `classify_missing.py`). No test that ran at 4c285a97
printed FAIL. By cause (core; python differs by one or two lines, see the files):

| Cause | Lines | What |
|---|---|---|
| rhocalc suite not run in this lane | 261 | At 12da03b4 test-correctness reached test-rhocalc; at 4c285a97 NORMAL_TEST_TARGETS (Makefile:19038) does not include it. These are all 261 PASS lines of the rhocalc lane, and in the rhocalc lane with SWI-Prolog (run3) all 261 pass: 211 under the same name, 50 under a new name (above). |
| removed or renamed upstream | 59 | The text or file exists at 12da03b4 and nowhere at 4c285a97: mostly the formal-he, he-compat "Rust surface" and he-extended extension checks, "checked-in PeTTa direct reader regenerates byte-for-byte", "shared lib_prolog surface in HE, Prime, and PeTTa", "mm2 has no named profiles". |
| still defined, no longer reached | 25 | 22 targets, all still in the Makefile but no longer prerequisites of test-correctness/test-profiles: test-abt, test-abt-mutations, test-abt-mm2-boundary, test-lib-parse-abt-bridge, test-help-flags, test-he-return-contract-correlation, test-mettazero, test-subzero, test-rhometta-macro-audit, test-closed-stream-fastpath, test-mork-shared-bridge (4 lines), and eleven test-petta-* targets (extended-query-algebra, libpl, mam-contender-mutations, match-existence-fusion, memoization, multifile, prepared-register-loop, process-text, source-memo-reset-mutation, specialized-pure-call, specializer-relevance-filter). |
| not attributed to one target | 52 | Lines composed at run time (e.g. 23 "ABT mutation rejected" lines, the he-extended capability/import loop, HE return-contract correlation per profile) or printed by a helper script/C test whose target was not identified. Most look like the same restructuring; not verified one by one. |

**New SKIPs:** 84 (core) and 80 (python), none of them a test that passed at 12da03b4: they are tests of the main-corpus
loop, which never ran at 12da03b4 (hidden by catalog-guards). Reasons as printed by Cetta: "covered by test-heavy"
(32), "covered by test-pathmap-lane" (30), "covered by isolated opt-in feature gates" (11), "requires a
Python-enabled build" (4, core only), "covered by probe-pathmap-lane" (3), "reads the metamath-test checkout beside
this repository, which is absent" (2), "imports a Mettapedia checkout; covered by test-lean" (1), "covered by
probe-core-lane" (1). By name: `analysis/new-skips-core.tsv`, `analysis/new-skips-python.tsv`.

**New FAILs:** none. **New failed make targets:** the rhocalc pair (issue 5) and `test-test-target-scope` (issue 6).
The E0 baseline's FAIL (py-call) and failed targets (catalog-guards, petta-search-machine) are gone.

Caveat: the categories come from text search over the two trees plus a static prerequisite walk, not from running
each old test at 4c285a97. A test moved to another target under the same message would show as "still defined, no
longer reached"; a test whose message was reworded shows as removed. The lists are a map for Zar and the reviewers,
not proof that each test still passes or fails.

## The rhocalc lane and SWI-Prolog

d9b3f42d (2026-08-24, "feat(cogslt): add direct PeTTa/rho lowering for MM and MM0") made test-rhocalc depend on
`test-metamath-*` targets, one of which builds `langdef/metamath/generated/syntax_parser_pack_v1.abi` with
`runtime/langdef-compile-v1-* parser-pack`, which executes `swipl` (tools/langdef_compile_v1.c:390). pop-os has no
SWI-Prolog. Upstream's README lists SWI-Prolog as optional and names no version.

- **Ubuntu 22.04's 8.4.2 (diagnostic only):** extracted user-locally (`apt-get download` + `dpkg -x`; hashes in
  `cetta-baseline/diag-rhocalc-swipl/swipl-debs.SHA256SUMS`) and put on PATH for the rhocalc command
  (`run-rhocalc-swipl-diag.sh`): it **segfaults** in `crypto:crypto_data_hash/3` (library(crypto) against OpenSSL 3)
  when the exporter hashes the presentations (`cetta-baseline/diag-rhocalc-swipl/swipl-8.4.2-crash.log`).
- **SWI-Prolog 9.2.9 built from source (the baseline, hive answer 2 "A2"):** source tarball
  `https://www.swi-prolog.org/download/stable/src/swipl-9.2.9.tar.gz`, sha256
  `53f428e2d9bbdf30e53b06c9c42def9a13ff82fc36a111d410fc8b0bc889ee2d` (the same as published on
  swi-prolog.org/download/stable, checked 2026-11-06); 9.2.9 is the last 9.x stable release (10.0.x is the current
  stable series). Installed under `$HOME/scratch/mettadinc-e0/swipl9/install`, no sudo. Configure options:

      cmake -G Ninja -DCMAKE_INSTALL_PREFIX=$HOME/scratch/mettadinc-e0/swipl9/install -DCMAKE_BUILD_TYPE=Release \
        -DUSE_GMP=OFF -DSWIPL_PACKAGES_JAVA=OFF -DSWIPL_PACKAGES_X=OFF -DSWIPL_PACKAGES_ODBC=OFF \
        -DSWIPL_PACKAGES_QT=OFF -DSWIPL_PACKAGES_PYTHON=OFF -DINSTALL_DOCUMENTATION=OFF -DBUILD_TESTING=OFF ../swipl-9.2.9
      ninja -j8 && ninja install

  GMP is off because pop-os has no libgmp-dev (SWI-Prolog then uses its bundled LibBF); OpenSSL 3, zlib, pcre2, uuid
  and libffi headers are the system's; no readline/editline/curses. Build: cmake + ninja + install exit 0 in 33 s
  (ninja -j8; `swipl-9.2.9/build.log`, `build-swipl.sh`). Smoke test (`swipl-9.2.9/smoke.out`): `swipl --version` is
  "SWI-Prolog version 9.2.9 for x86_64-linux", PLVERSION 90209, and the sha256 through library(crypto) that crashed
  8.4.2 works. `pkg-config --exists swipl` stays false with the harness's PATH, so Cetta's ENABLE_LIB_PROLOG=auto
  probe is unchanged and the Cetta build does not link libswipl; core and python are identical with and without it.
- **Result:** the rhocalc lane passes: 285 passed, 0 failed, exit 0 (above).
- **Side effect:** a rhocalc run rewrites the tracked `langdef/metamath/generated/direct_runtime_lock_v1.metta`
  (issue 7), so the pin check fails after it until `git -C cetta checkout -- .`
  (`00_pin_check_after_run3.out` exit 1; `00_pin_check_after_run3_restored.out` exit 0). A failed rhocalc run
  (no swipl) instead deletes the tracked `syntax_lock_v1.metta` (run2; `00_pin_check_after_run2*.out`).

## Registry and oracle checks (unchanged commands)

`evidence/cetta-pin-latest/run-registry-oracles.sh`, the same commands as evidence/m0-prep-submodule (they do not use
Cetta): adopt check, check_fixtures, check_bundles (Detect and all) and digest all exit 0 (`registry/`); the eight
oracles give spec 157 / four examples 305 / mg 195 / ls 94 / wx 99, as expected, exit 0 (`oracles/`).

## Decisions taken (hive, answer 2)

1. SWI-Prolog: A2, build 9.x from source without sudo, `MDINC_SWIPL_DIR` in the harness (done, above).
2. `test-test-target-scope`: frozen as an expected failed target (as catalog-guards was at 12da03b4), upstream issue 6.
3. Rerun all lanes with swipl, regenerate the expected file from that run, break-a-test red then reverted green (above
   and below).
4. Kept: MISSING.md (now with the rhocalc lane's status of each rhocalc-suite line), the upstream-issues section, and
   the "with build overrides" labelling.

## Upstream issues for CeTTa (for the humans to file)

One entry per problem, for filing as GitHub issues with Zar (zariuq/CeTTa). All were observed at main
4c285a97fd8c60e3c3fccd5ccd3b3e5e0ebccb4c on pop-os: **Ubuntu 22.04, gcc 11.4.0, GNU ld 2.38, glibc 2.35** (GNU Make
4.3, Python 3.10.12). The same host and toolchain built 12da03b4 unmodified and ran it green
(`evidence/m0-prep-submodule/cetta-baseline/sub-run1-green`). Until these are fixed on main, mettadinc's baseline at
4c285a97 is green only **with build overrides** (see "Build overrides" above); a later task re-pins and drops them.

"Introduced by" is the commit that added the code named, from `git log`/`git blame`; where the exact line was last
changed in a later commit, both are given. This is attribution from history, not a bisect: no intermediate commit was
built.

### 1. The DT_RELR probe only links: binaries then need GLIBC_ABI_DT_RELR, which glibc 2.35 lacks

- Where: Makefile:701 (`PACK_RELATIVE_RELOCS := $(shell printf 'int main(void){return 0;}\n' | $(CC) -x c -Wl,-z,pack-relative-relocs -o /dev/null - ...)`), added to LDFLAGS at Makefile:702.
- Introduced by: 077f99a8 (2026-10-27, "chasing mm2").
- Error: ld 2.38 accepts `-z pack-relative-relocs`, so the probe succeeds, but every program linked with it requires
  the symbol version GLIBC_ABI_DT_RELR, which only glibc >= 2.36 has. The first generated tool the build runs dies:
  `runtime/langdef-compile-v1-core...: /lib/x86_64-linux-gnu/libc.so.6: version 'GLIBC_ABI_DT_RELR' not found`,
  then `make: *** [Makefile:8487: runtime/generated/match_decision_policy_v1.answers] Error 1`. A two-line C program
  linked with the flag fails the same way on this host. Independent of the compiler (gcc 12 hits it too).
- Evidence: `evidence/cetta-pin-latest/cetta-baseline/latest-run0-default-build/02_build_core.log`.
- Suggested fix: probe by linking **and running** a test binary, for example
  `$(shell t=$$(mktemp) && printf 'int main(void){return 0;}\n' | $(CC) -x c -Wl,-z,pack-relative-relocs -o $$t - >/dev/null 2>&1 && $$t && printf '%s' -Wl,-z,pack-relative-relocs; rm -f $$t)`.
  Workaround used here: `make PACK_RELATIVE_RELOCS=`.

### 2. src/tensor.c:212 fails with -Werror=stringop-overflow under gcc 11

- Where: src/tensor.c:212, `for (size_t i = 0u; i < width; ++i) bytes[i] = raw[width - i - 1u];` in
  `native_storage_value`, inlined from `cetta_tensor_copy_values` (src/tensor.c:1574), which passes the compound
  literal `&(CettaTensorScalar){0}` as the scratch buffer.
- Introduced by: d14df728 (2026-10-22, "WIP: add tensor, sparse-postings, and embedding substrate", which added the
  file); line 212 itself was last changed in c12a28ac (2026-11-03).
- Error (gcc 11.4.0 with Makefile:693's `-O3 -Wall -Werror -std=c11 -pthread`):
  `src/tensor.c:212: error: writing 1 byte into a region of size 0 [-Werror=stringop-overflow=]`.
- Evidence: `evidence/cetta-pin-latest/cetta-baseline/latest-run1/02_build_core.log`,
  `evidence/cetta-pin-latest/cetta-baseline/diag-gcc11-make-k-core.log`.
- Suggested fix: it looks like a gcc 11 false positive after inlining, but that is for Zar to judge. Making the bound
  visible should silence it, e.g. `if (width > sizeof *scratch) return NULL;` before the loop, or copying with
  `memcpy` into a local of type `CettaTensorScalar`. Workaround used here: `-Wno-error=stringop-overflow`.

### 3. native/json_cst_value_v1.c:295 and :518 fail with -Werror=maybe-uninitialized under gcc 11

- Where: native/json_cst_value_v1.c:295 and :518, reading `uint32_t scalar;` (declared without an initialiser, e.g.
  at :282 and :503) after `json_lexical_scalar(ctx, children[0], &scalar)`.
- Introduced by: 80aaa5cd (2026-08-26, "integrate honest NIK hosting and presentation-driven runtime foundations",
  which added the file); both lines were last changed in d7cf1209 (2026-10-03).
- Error (gcc 11.4.0, same flags):
  `native/json_cst_value_v1.c:295: error: 'scalar' may be used uninitialized in this function [-Werror=maybe-uninitialized]`,
  and the same at :518.
- Evidence: `evidence/cetta-pin-latest/cetta-baseline/diag-gcc11-make-k-core.log`.
- Suggested fix: initialise at the declaration (`uint32_t scalar = 0u;`, here and in the sibling functions), or have
  `json_lexical_scalar` set `*out` on every path. Workaround used here: `-Wno-error=maybe-uninitialized`.

### 4. For completeness: gcc 12 -Werror=use-after-free

Not needed for the gcc 11 build (gcc 11 has no -Wuse-after-free), but with gcc 12.3.0 (`make CC=gcc-12`) the build
also stops on:

- `src/petta_program.c:138:19: error: pointer 'storage' used after 'free' [-Werror=use-after-free]` (line last changed
  in 199b91fa, 2026-09-14);
- `src/rhocalc_core.c:3976:13: error: pointer used after 'free' [-Werror=use-after-free]` and
  `src/rhocalc_core.c:6054:9: error: pointer used after 'free' [-Werror=use-after-free]` (both lines from 58526bf9,
  2026-06-16, so already present at 12da03b4, where gcc 12 was never tried).
- Evidence: `evidence/cetta-pin-latest/cetta-baseline/diag-gcc12-make-k-core-partial.log` (stopped early, so possibly
  not the complete list).
- Suggested fix: inspect each site; where the freed pointer is only compared or tested afterwards, reorder so the
  `free` comes last or save what is needed first. Some gcc 12 -Wuse-after-free reports are false positives, but each
  should be checked, since a real use-after-free is a memory-safety bug.

### 5. test-rhocalc needs the `swipl` program (SWI-Prolog 9.x?), though the README calls SWI-Prolog optional

- Where: Makefile:19758 (`test-rhocalc:` prerequisites `test-metamath-*`), Makefile:14825
  (`test-metamath-state-proof-runtime-rhometta-v1`), the rule at Makefile:9221 building
  `langdef/metamath/generated/syntax_parser_pack_v1.abi`, and tools/langdef_compile_v1.c:390 (`arguments[0] = "swipl"`).
- Introduced by: d9b3f42d (2026-08-24, "feat(cogslt): add direct PeTTa/rho lowering for MM and MM0"), which added the
  metamath targets to test-rhocalc (at 12da03b4 test-rhocalc had three prerequisites and ran 253 tests without Prolog).
- Error without swipl: `LangDefCompileFailed: GSLT compiler exited unsuccessfully`, then
  `make[1]: *** [Makefile:9229: langdef/metamath/generated/syntax_parser_pack_v1.abi] Error 1` and
  `make: *** [Makefile:14825: test-metamath-state-proof-runtime-rhometta-v1] Error 2`; no rhocalc test runs. With
  Ubuntu 22.04's SWI-Prolog 8.4.2: `received fatal signal 11 (segv)` in `crypto:_crypto_hash_context_copy/2`.
  A failed run also deletes the tracked `langdef/metamath/generated/syntax_lock_v1.metta`.
- Evidence: `latest-run2-overrides/04_test_rhocalc.log`, `diag-rhocalc-swipl/04_test_rhocalc.log`,
  `diag-rhocalc-swipl/swipl-8.4.2-crash.log`.
- Works with SWI-Prolog 9.2.9 built from source: `latest-run3-swipl/04_test_rhocalc.log`, 285 passed, 0 failed.
- Suggested fix: document the SWI-Prolog requirement and minimum version; have the metamath prerequisites print SKIP
  when `swipl` is absent (as the Mettapedia checks do), or keep them out of test-rhocalc; mark the generated files
  `.PRECIOUS` (or write to a temporary file and rename) so a failed generator does not delete tracked files.

### 6. test-test-target-scope: "Argument list too long"

- Where: Makefile:19073-19074, the recipe of `test-test-target-scope`, which expands `$(MAKEFILE_LIST)` twice inside one
  shell command.
- Introduced by: d14df728 (2026-10-22, the same commit as issue 2).
- Error: `make: /bin/bash: Argument list too long` then `make: *** [Makefile:19074: test-test-target-scope] Error 127`,
  in both lanes. After a build, MAKEFILE_LIST holds 943 files (the included dependency files of every object: 438 under
  src/ alone) and is 88,844 bytes; twice that is more than Linux's 128 KiB limit on a single argument
  (MAX_ARG_STRLEN), and make passes the whole recipe to `/bin/bash -c` as one argument. GNU Make 4.3 here.
- Evidence: `latest-run2-overrides/05_test_core_k.log`, `08_test_python_k.log`.
- How mettadinc handles it: frozen as an **expected failed target** of the core and python lanes in
  tools/cetta-baseline.expected (`target test-test-target-scope`), as catalog-guards was at 12da03b4. The test it
  would run (that `test:` is declared once and no multi-target rule extends it, and that promote_runtime.sh uses
  test-all) therefore is not checked at this pin. It hides no other target: `test` and `test-correctness` have no
  recipes of their own. Still the same in latest-run3-swipl (`05_test_core_k.log`, `08_test_python_k.log`).
- Suggested fix: loop over `$(filter-out %.d,$(MAKEFILE_LIST))` (only real makefiles can declare `test:`), or write
  the list to a file with `$(file >...)` and read it in the shell.

### 7. A rhocalc run rewrites a tracked file: direct_runtime_lock_v1.metta records the hash of a locally compiled .so

- Where: Makefile:9525 (`$(METAMATH_DIRECT_RUNTIME_LOCK_V1)`, i.e. `langdef/metamath/generated/direct_runtime_lock_v1.metta`,
  written by `langdef-compile-v1 seal --compiled-cursor ...`), whose prerequisite
  `METAMATH_DIRECT_COMPILED_CURSOR_V1` is `syntax_cursor_fold_direct_v1.generated.so` (Makefile:2752); the lock's
  `(compiled-cursor-sha256 ...)` is that shared object's sha256 (tools/langdef_compile_v1.c:598).
- Observed: after a successful rhocalc run (latest-run3-swipl) the tracked lock differs from 4c285a97 in one line,
  `compiled-cursor-sha256` 201e67de... -> 50e3fc4f... (`latest-run3-swipl/cetta-diff-after-run3.patch`). A compiled
  .so's bytes depend on the compiler, flags and host, so any build not identical to upstream's rewrites the tracked file.
  (Here the CFLAGS override may contribute; not separated.)
- Suggested fix: keep machine-dependent hashes out of tracked files (write the lock to the build directory), or record
  a hash of the generated C source rather than of the .so.
