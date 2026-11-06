# Reference oracles and evaluators: conformance baseline (E0)

Run on 2026-11-05 on pop-os (Linux x86_64, 8 cores), on a copy of `docs/`, because the oracles rewrite their results JSON. Runner: `tools/run_oracles.sh`. Logs: `evidence/oracles/*.out`. The tools come from the package's own instructions (folder README.txt and each bundle README).

Environment: Python 3.13.7 in a venv (`/opt/hive/uv venv`) with numpy 2.5.3, scipy 1.18.1, z3-solver 5.3.3.0 and cvc5 1.4.2 (the versions the READMEs name), plus networkx 3.7, python-sat 1.9.dev21 and dd 0.6.0, which the READMEs name without versions. `MDINC_TOOLS` points at drat-trim built from 2e3b2dc0ecf938addbd779d42877b6ed69d9a985 and cake_lpr built from 033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2, the commits pinned in DEPENDENCIES.json. cake_lpr was built with `cc -O2 basis_ffi.c cake_lpr.S`; the sha256 of cake_lpr.S matches the repository's cake_lpr.sha256, and `./cake_lpr example.cnf example.lpr` prints `s VERIFIED UNSAT`. CaDiCaL is the 1.5.3 that python-sat bundles, as the bundles specify. The rel-3.0.1 pin is for the future obligation pipeline.

| Oracle (reference evaluator it drives) | Expected | Got | Exit | Time | Results vs shipped |
|---|---|---|---|---|---|
| 01 `validation_package/oracle/verify_mettadinc.py` (exact-arithmetic oracle; standard library only) | 157 | **157** ok, 0 fail ("All checks passed.") | 0 | 6 s (11 s on system Python 3.10) | `mettadinc_oracle_results.json` byte-identical; printed report identical to `oracle_report.txt` |
| 01 `check_fixtures.py` | exit 0 | "21 fixture files, 32 modules, 357 declarations, 125 run requests / 123 manifest claims; first release must answer 45 and return Unsupported for 78 / All fixtures conform to the registry; the manifest agrees with the oracle." | 0 | <1 s | – |
| 03 `ex1_oracle.py` (uses `metta_eval.py`) | 92 | **92** | 0 | 134 s | identical except the `seconds` field |
| 03 `ex2_oracle.py` | 69 | **69** ("proofs checked: True (619 of 619 proofs replayed)") | 0 | 123 s | identical except `seconds` |
| 03 `ex3_oracle.py` (uses `metta_eval.py`) | 57 | **57** | 0 | 7 s | identical except `seconds` |
| 03 `ex4_oracle.py` (uses `metta_eval.py`) | 87 | **87** | 0 | 3 s | identical except `_summary.seconds` |
| 03 total | 305 | **305** | | | |
| 04 `mg_oracle.py` (uses `mg_eval.py`) | 195 | **195** | 0 | 89 s | identical except `seconds` |
| 05 `ls_oracle.py` (uses `ls_eval.py` with cvc5; records Z3 agreement) | 94 | **94** | 0 | 16 s | identical except `seconds` |
| 06 `wx_oracle.py` (uses `ls_eval.py`; regenerates the 12 streams and compares them byte for byte) | 99 | **99** ("99 checks passed, 0 failed") | 0 | 23 s | identical except `facts.seconds` |

All five expected counts in the order (157 / 305 / 195 / 94 / 99) are reproduced, with zero failures. The comparison with the shipped results JSON is a recursive comparison of the parsed JSON (`tools/jdiff.py`), which found one differing field per file, always the elapsed time.

Static checks of the bundles (`ex_check.py`, with `MDINC_PACKAGE` pointing at the specification's package; the commands are the ones in the READMEs). All conform with their patches. The second pass lists diagnostics against the unpatched registry, which are the forms that depend on PROPOSED patches.

| Bundle | First pass and diagnostics without patches (raw) |
|---|---|
| ex1 | 1 file(s), 4 modules, 107 declarations, 61 run requests: conform; 59 diagnostics |
| ex2 | 1 file(s), 2 modules, 57 declarations, 15 run requests: conform; 113 diagnostics |
| ex3 | 1 file(s), 3 modules, 97 declarations, 32 run requests: conform; 11 diagnostics |
| ex4 | 1 file(s), 4 modules, 75 declarations, 36 run requests: conform; 72 diagnostics |
| mg (04) | 1 file(s), 10 modules, 318 declarations, 92 run requests: conform; 128 diagnostics |
| ls (05) | 2 file(s), 16 modules, 490 declarations, 129 run requests: conform; 306 diagnostics |
| wx (06) | 3 file(s), 19 modules, 575 declarations, 162 run requests: conform; 410 diagnostics |

To reproduce from `projects/mettadinc`, first create the venv and build the two proof tools as above:

```
export MDINC_TOOLS=<dir with drat-trim/drat-trim and cake_lpr/cake_lpr>
export MDINC_PACKAGE=$PWD/docs/01_language_specification/validation_package
(cd docs/01_language_specification/validation_package/oracle && python3 verify_mettadinc.py)
(cd docs/01_language_specification/validation_package && python3 check_fixtures.py)
(cd docs/03_four_worked_examples/validation_bundles/ex1_belief_memory && python3 ex1_oracle.py)
(cd docs/03_four_worked_examples/validation_bundles/ex2_access_policy && python3 ex2_oracle.py)
(cd docs/03_four_worked_examples/validation_bundles/ex3_skill_share && python3 ex3_oracle.py)
(cd docs/03_four_worked_examples/validation_bundles/ex4_market_maker && python3 ex4_oracle.py)
(cd docs/04_omega_memory_goals_part1/validation_bundle && python3 mg_oracle.py)
(cd docs/05_live_memory_part2/validation_bundle && python3 ls_oracle.py)
(cd docs/06_wmtm_worked_example/validation_bundle && python3 wx_oracle.py)
```
Run these on a copy if `docs/` must stay byte-identical: each oracle rewrites its results file, and the ex1 and ex2 oracles also write `obligations/`.

What this baseline means, in the package's own words: "Neither tool runs MeTTaDinC: no MeTTaDinC implementation exists yet, and passing these checks is not conformance" (validation_package/README.txt). The oracles fix the expected values; an implementation conforms when it returns those values with replayable evidence.
