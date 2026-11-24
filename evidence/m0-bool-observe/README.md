# Evidence: t-2026-11-23-mettadinc-m0-bool-observe

Base: mettadinc main 8ae0fa7 (merge of PR #32, m0-subset-reach). Host: pop-os, gcc 11.4.

| file | what |
|---|---|
| gate_new.txt | tests/dcalc/m0_bool_observe/run_m0_bool_observe.py on this branch: 71 PASS |
| gate_on_base_binary.txt | the same gate with the 8ae0fa7 binary: 66 FAIL (the form was Unsupported) |
| gate_on_constant_true_mutant.txt | the same gate with a mutant whose Bool observations are all True: 16 FAIL |
| bytediff.txt, run_all_metta.sh | every tracked .metta (224, outside cetta/), each alone, release and --beyond-release, base vs new binary: only the probe repro differs |
| probe_release.diff, probe_beyond.diff | that difference: A1 (CheckNow R) Unsupported -> Checked; A1C unchanged |
| dcalc-run-all.log | tools/dcalc-run-all.sh on this branch: PASS (exit 0), with the pinned proof backend (tools/dcalc-proof-backend.sh, CaDiCaL 3.0.1, cake_lpr 033aad5, sha256 pins set) and the E0 GMP prefix (projects/mettadinc/tools/env.sh: CPATH/LIBRARY_PATH; the host has no gmp.h) |
| dcalc-run-all-first-no-gmp.log | the first run without the GMP prefix: every step 0 except cetta_smoke (CeTTa build: gmp.h not found) |

run_e2e.py + make_tables.py rerun on this branch: out/*.tsv byte-identical to 8ae0fa7 (no row's answer changes);
doc04_omega_memory_goals.md changes only in the GAP class text of rows 43-49 (14 cells).
