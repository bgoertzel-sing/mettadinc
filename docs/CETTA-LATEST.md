# Cetta latest main (4c285a97) against the 12da03b4 baseline

Hive task t-2026-11-06-mettadinc-cetta-pin-latest. Question: does mettadinc build and pass a green baseline on Zar's
current CeTTa main, and which tests that were green at 12da03b4 are not green now?

## Status (2026-11-06): builds with overrides; lanes run; NOT green; blocked on a decision

- **Build:** 4c285a97 does not build unmodified with gcc 11.4 here (Upstream issues 1 to 3 below). Per the decision on
  the hive (answer 1, "B now, and A in parallel"), it is built with make command-line overrides only, no Cetta file
  changed (below). With them, both builds succeed (core 502 s, python 454 s).
- **Lanes:** all three ran (latest-run2-overrides). None is green against the 12da03b4 baseline:
  the **rhocalc lane stops before running any test**, because a prerequisite that 4c285a97 added to test-rhocalc
  runs the `swipl` program, which pop-os does not have (issue 5); and core and python both fail one new target,
  `test-test-target-scope`, with "Argument list too long" (issue 6).
- **Not done yet, waiting on the decision:** regenerating tools/cetta-baseline.expected and the break-a-test check.
  Both depend on what the frozen rhocalc lane should be. The expected file is still the 12da03b4 baseline, so the
  harness reports NOT GREEN at this pin.
- **Done and unchanged:** registry checks and the eight reference oracles pass (below).

So the baseline label "green at 4c285a97 **with build overrides**" cannot be applied yet: with the overrides it
builds, but it is not green.

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

Evidence: `evidence/cetta-pin-latest/cetta-baseline/latest-run2-overrides/` (summary.txt and the logs; repo commit
3c6472c, submodule at 4c285a97 with no changes to tracked files at the start). Counts from
`evidence/cetta-pin-latest/new_skips.py`.

| Lane | 12da03b4 (E0's frozen logs) | 4c285a97 with build overrides |
|---|---|---|
| rhocalc (`make BUILD=core test-rhocalc`) | 261 PASS / 5 SKIP / 0 FAIL; "253 passed, 0 failed"; exit 0 | **0 PASS** / 0 SKIP / 0 FAIL; no summary line; exit 2. Failed targets: `langdef/metamath/generated/syntax_parser_pack_v1.abi`, `test-metamath-state-proof-runtime-rhometta-v1` (no `swipl`; issue 5) |
| core (`make -k BUILD=core test-correctness test-profiles`) | 502 PASS / 6 SKIP / 1 FAIL (py-call); failed targets catalog-guards, petta-search-machine; exit 2 | 704 PASS / 84 SKIP / 0 FAIL; failed target `test-test-target-scope` (issue 6); exit 2 |
| python (`make -k BUILD=python test-correctness test-profiles`) | 503 PASS / 6 SKIP / 0 FAIL; failed target catalog-guards; exit 2 | 709 PASS / 80 SKIP / 0 FAIL; failed target `test-test-target-scope`; exit 2 |

Of the PASS lines: core has 599 lines that were not in E0's log and lacks 397 of E0's; python has 604 new and lacks 398.
`test-he-compat-catalog-guards` now passes (it is `python3 scripts/test_he_compat_catalog_guards.py` at 4c285a97),
so it no longer hides the targets that depend on it: the main-corpus loop over `tests/test_*.metta` etc. now runs
inside the core and python lanes, and no separate "extra lanes" run was needed. `test-test-target-scope` hides
nothing else: `test` and `test-correctness` have no recipes of their own.

## Tests green at 12da03b4 and not green now

The full by-name list, with a cause for each, is
[evidence/cetta-pin-latest/analysis/MISSING.md](../evidence/cetta-pin-latest/analysis/MISSING.md) (from
`analysis/missing-core.tsv` and `missing-python.tsv`, made by `classify_missing.py`). No test that ran at 4c285a97
printed FAIL. By cause (core; python differs by one or two lines, see the files):

| Cause | Lines | What |
|---|---|---|
| rhocalc suite not run | 261 | At 12da03b4 test-correctness reached test-rhocalc; at 4c285a97 NORMAL_TEST_TARGETS (Makefile:19038) does not include it, and the rhocalc lane stops before any test (issue 5). These are all 261 PASS lines of the rhocalc lane. |
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

## The rhocalc lane and SWI-Prolog (diagnostic)

d9b3f42d (2026-08-24, "feat(cogslt): add direct PeTTa/rho lowering for MM and MM0") made test-rhocalc depend on
`test-metamath-*` targets, one of which builds `langdef/metamath/generated/syntax_parser_pack_v1.abi` with
`runtime/langdef-compile-v1-* parser-pack`, which executes `swipl` (tools/langdef_compile_v1.c:390). pop-os has no
SWI-Prolog. Upstream's README lists SWI-Prolog as optional.

As a diagnostic only (not a baseline run, no host change), Ubuntu 22.04's own SWI-Prolog 8.4.2 was extracted
user-locally (`apt-get download` + `dpkg -x`, as for GMP; hashes in
`cetta-baseline/diag-rhocalc-swipl/swipl-debs.SHA256SUMS`) and put on PATH for the rhocalc command
(`run-rhocalc-swipl-diag.sh`): it still fails, because swipl 8.4.2 **segfaults** in
`crypto:crypto_data_hash/3` (library(crypto) against OpenSSL 3) when the exporter hashes the presentations
(`cetta-baseline/diag-rhocalc-swipl/swipl-8.4.2-crash.log`). So the rhocalc lane needs a newer SWI-Prolog (9.x) than
Ubuntu 22.04 ships. Cetta does not say which version it needs.

The failed rhocalc run also deletes a tracked generated file (`langdef/metamath/generated/syntax_lock_v1.metta`), so
the pin check fails after it until `git -C cetta checkout -- .`
(`00_pin_check_after_run2.out` exit 1; `00_pin_check_after_run2_restored.out` exit 0).

## Registry and oracle checks (unchanged commands)

`evidence/cetta-pin-latest/run-registry-oracles.sh`, the same commands as evidence/m0-prep-submodule (they do not use
Cetta): adopt check, check_fixtures, check_bundles (Detect and all) and digest all exit 0 (`registry/`); the eight
oracles give spec 157 / four examples 305 / mg 195 / ls 94 / wx 99, as expected, exit 0 (`oracles/`).

## Decision requested

See the hive block on this task. In short: the rhocalc lane cannot run here without SWI-Prolog 9.x, and
`test-test-target-scope` fails for a reason outside our control; what should the frozen 4c285a97 baseline be?

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
- Suggested fix: loop over `$(filter-out %.d,$(MAKEFILE_LIST))` (only real makefiles can declare `test:`), or write
  the list to a file with `$(file >...)` and read it in the shell.
