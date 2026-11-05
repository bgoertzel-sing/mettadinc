# Cetta: pin, build, tests and extension points (E0)

## Pin

The work plan names a pin. §2.1 ("Pin and inspect the host", p. 13 [PDF 14]) says: "The inspected repository is `https://github.com/zariuq/CeTTa`, branch `main`, at commit `12da03b4b055bfecff2add505e7e1ad4125bb352`, recorded on 14 August 2026. It was still the head of `main` (215 commits) when rechecked on 3 November 2026." DEPENDENCIES.json pins the same commit.

- Cloned `https://github.com/zariuq/cetta` (the same repository; GitHub names are case-insensitive) on 2026-11-05. `git rev-parse HEAD` = `12da03b4b055bfecff2add505e7e1ad4125bb352` (2026-08-14 16:58:16 +0200, "purging surface slop"), 215 commits. `git ls-remote` shows that this is still HEAD of `main` on 2026-11-05, so the pin and the current HEAD are the same commit. `VERSION` = 1.4.0-dev.
- Location: `projects/mettadinc/repos/cetta` on pop-os. The working tree is clean; no commits were made (stop-line).

## Build record

Host: Ubuntu 22.04 (Pop!_OS), gcc 11.4.0, Python 3.10 headers (`python3-config --embed`), GNU make. **The host had no GMP headers.** The first plain `make` failed with `src/atom.h:21:10: fatal error: gmp.h: No such file or directory`. Without sudo, I extracted Ubuntu's `libgmp-dev_2:6.2.1+dfsg-3ubuntu1_amd64.deb` (sha256 e4ce547c5c5e4efd98854d06559349b3a03272eb343f1bd8e4ccac7b783229a3, fetched with `apt-get download`) into a scratch prefix, linked its `libgmp.so` to the system `libgmp.so.10`, and exported `CPATH`/`LIBRARY_PATH` (`tools/env.sh`). The Makefile was not changed.

These are the plan's baseline commands (§2.1), run in order. Logs are in `evidence/cetta/`.

| Step | Command | Result |
|---|---|---|
| 00 | `make -j8` (default BUILD=python) | exit 0; `cetta 1.4.0-dev (python)` |
| 01 | `make BUILD=core doctor-gmp` | exit 0, "PASS: GMP compile/link probe" |
| 02 | `make -j8 BUILD=core` | exit 0 |
| 03 | `./cetta --version` | `cetta 1.4.0-dev (core)` |
| 04 | `./cetta --list-languages` | he, prime, subzero, zero, mm2, petta, rhocalc implemented; 8 planned |
| 05 | `./cetta --list-profiles` | he, he-compat, he-extended, he-prime |
| 06 | `make BUILD=core test-correctness test-profiles` | **exit 2**: stops at `test-he-compat-catalog-guards` (FileNotFoundError: "unable to locate Mettapedia Lean root"; needs `METTAPEDIA_ROOT`) |
| 07 | `make BUILD=core test-rhocalc` | **exit 0**; final suite "253 passed, 0 failed"; 261 PASS lines in all, 0 FAIL |
| 08 | `make -k BUILD=core test-correctness test-profiles` (continue past failures, to get counts) | exit 2 after 185 s: **502 PASS lines, 6 SKIP, 1 FAIL line, 2 failed make targets** |
| 09–10 | `make -j8 BUILD=python` then `make -k BUILD=python test-correctness test-profiles` | build exit 0 (`cetta 1.4.0-dev (python)`); tests **exit 2** after 283 s: **503 PASS lines, 6 SKIP, 0 FAIL lines**; the only failed target is `test-he-compat-catalog-guards` (Mettapedia checkout missing). The core-lane Python-namespace assertion passes here. |

The two failures in the core lane:
1. `test-he-compat-catalog-guards` (Makefile:8913) needs a local Mettapedia Lean checkout (`METTAPEDIA_ROOT`). It is an environment dependency, not a code failure. The six SKIPs need the same checkout (or `rholang-cli`): ABT differential, rhocalc M3 rholang-cli overlap, rhocalc lean trace bridge, rhocalc cost lean bridge, cost-rho differential harness and rhocalc lean microcheck.
2. `test-petta-search-machine` (Makefile:7652): "FAIL: native PeTTa source-relative Python namespace" (expected `true`/`42`, got `(py-call (python_bridge.answer))`). The core binary has no Python, so this assertion can only pass in the Python lane. Every other assertion in that target passed.

Three records stay separate, as §2.1 asks. The upstream-reported status was not checked here. The newly executed host baseline is the table above. No MeTTaDinC-specific validation exists yet.

## Extension points the plan relies on, at 12da03b4

Each entry is from the guide's Source map (§2.2, pp. 14–15 [PDF 15–16]) and the Admission section (§2.3), located by `grep -n` on the pinned tree. All files exist. "Lacks" lists anything the plan expects that is absent or different.

| Plan item | file:line at 12da03b4 | Notes |
|---|---|---|
| Exact numbers: `GV_RATIONAL` | `src/atom.h:59` | enum member |
| `atom_rational` and GMP helpers | `src/atom.h:292` (`atom_rational`), `:295` (`atom_rational_get_mpq`), `:296` (`atom_rational_from_mpq`), `:287–290` (bigint/mpz) | `#include <gmp.h>` at `src/atom.h:21` (GMP headers are required to build) |
| Canonical term storage | `src/term_universe.h` (292 lines; `term_universe_init` :194), `src/term_canon.h` (48 lines; `CettaVarMap` API :29–38) | the guide asks for MeTTaDinC's own binder-aware serialization; host identity is not portable |
| `cetta_library_dispatch_native` | declared `src/library.h:211`, defined `src/library.c:8712` | `CettaLibraryContext` struct at `src/library.h:87–133` |
| `CettaNativeBuiltinModule` (name, import bit, dispatch callback) | `native/native_modules.h:10–15` | callback signature `(ctx, space, arena, head, args, nargs)` matches the guide |
| Static native-module table registering `gparse` | `native/native_modules.c:1125–1127` (`g_native_modules[]`), import bit `CETTA_NATIVE_IMPORT_GPARSE (1u << 24)` at `:11`; active-mask check at `:1150` | a `dcalc` entry needs a new import bit (proposed; absent) |
| Native handles | `src/native_handle.h:19–29` (`cetta_native_handle_atom`, `_arg`, `_alloc` :22, `_get` :25, `_close` :27, `_cleanup_all` :29) | – |
| `grounded_op_is_type_pure` | declared `src/grounded.h:19`, defined `src/grounded.c:553`; used `src/eval.c:3716` | comment at `src/grounded.c:549–552` excludes "every __cetta_lib_ op (semantics not audited)", consistent with the guide's "without adding the service to the type-pure list" |
| `is_grounded_op` and the `__cetta_lib_` prefix | `src/grounded.h:12`, `src/grounded.c:519`; prefix test `src/grounded.c:526–529` | – |
| `grounded_dispatch_accepts_data_arg` | **`src/eval.c:2309` (`static`)**; used `src/eval.c:2651`, `:19782`, `:19832` | The guide lists it with `grounded.[ch]`. At the pin it is file-local to `eval.c`, so a data-argument exception for `__cetta_lib_dcalc_admit` means editing `eval.c` |
| `noeval` | `lib/stdlib.metta:9` (`(: noeval (-> Atom Atom))`), `:439` (`(= (noeval $x) $x)`), notes at `:436` | – |
| `compile_space_to_llvm` | `src/compile.h:12`, `src/compile.c:574` | – |
| Generated language packs: classify/produce/observe | `src/gslt_language_runtime.h:20–28`; generator `tools/generate_gslt_language_v1.py` (514 lines); `langdef/zero`, `langdef/subzero` present | `langdef/dcalc/` absent (proposed) |
| Compiled finite-Horn runtime | `src/gslt_compiled_runtime.h` (50 lines; worklist note at :37–40) | – |
| rho-calculus bounded checks | `scripts/rhocalc_bounded_bisimulation.py` (279 lines; `reachable_barbs_upto` :69, barbs import :12), `scripts/rhocalc_bounded_relation_equivalence.py` (59), `tests/rhocalc_bisimulation.tsv` (16 lines); run from `test-rhocalc` (Makefile:3918) | the guide's M5 WeakBarbed adapter reuses these |
| Answer tabling keyed by space instance and revision | `src/table_store.c:19–20` (`space_instance_id`, `revision`), `:148` | M7 precedent |
| MORK bridge and MM2 lowering | `src/mork_space_bridge_runtime.c` (5264 lines), `src/mm2_lower.c` (1139 lines; `cetta_mm2_atom_is_exec_rule` :61) | not built in BUILD=core; needs BUILD=main/mork with sibling MORK and PathMap checkouts (README); not built here |
| Build switches | `Makefile:21` `BUILD ?= python`, `Makefile:30` `ENABLE_GMP ?= 1`, `doctor-gmp` :3442, `test-correctness` :3704, `test-correctness-all` :5337, `test-profiles` :6135 | as the guide states |

Absent at the pin, as the guide says ("None of them is runnable on unmodified Cetta"): `lib/dcalc.metta`, `native/dcalc/`, `src/dcalc/`, `replay/`, `tests/dcalc/`, and every `make test-dcalc-*` target. `grep -rn dcalc` over the C, header, MeTTa and Makefile sources finds nothing.

Differences from the plan's description: (a) `grounded_dispatch_accepts_data_arg` is in `eval.c`, not `grounded.c`, and is `static`; (b) the guide's "runtime profiles (`--lang he`, `--profile he-extended`, `rhocalc`, `prime`)" mixes languages with profiles: at the pin, `rhocalc` and `prime` are `--lang` values and the profiles are he, he-compat, he-extended and he-prime. Neither blocks the plan.
