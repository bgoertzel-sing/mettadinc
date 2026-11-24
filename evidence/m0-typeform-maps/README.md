# Evidence: t-2026-11-23-mettadinc-m0-typeform-maps

Base: mettadinc main 8ae0fa7 (merge of PR #32, m0-subset-reach). Code commit: 544bc76. Host: pop-os, gcc 11.4.

| file | what |
|---|---|
| gate_new.txt | tests/dcalc/m0_typeform_maps/run_m0_typeform_maps.py on 544bc76: 85 PASS (release and --beyond-release) |
| gate_on_base_binary.txt | the same gate with the 8ae0fa7 binary: 66 FAIL (the form was Unsupported; negatives and Unsupported reasons differ) |
| gate_on_mutant_permuted_argument.txt, mutant_permuted_argument.patch | a mutant that admits type-form maps but evaluates each one at the wrong element (wrong meaning, answers still Checked/Refuted): 28 FAIL |
| gate_on_mutant_constant_code.txt, mutant_constant_code.patch | a mutant that collapses every type-form code/observation value into one: 24 FAIL |
| gate_sanitized.txt | the gate with the ASan/UBSan build that dcalc-run-all makes (build/dcalc-sanitized): PASS; the three fixtures in both modes exit 0 with empty stderr |
| bytediff.txt, run_all_metta.sh | every tracked .metta outside cetta/ (227 files), each alone, release and --beyond-release, base binary vs new binary on the same tree: only the probe repro and the three new fixtures differ |
| probe_release.diff, probe_beyond.diff | the probe's difference: B1 (CheckNow R) Unsupported -> Checked; B1C unchanged |
| run_e2e.log | tests/dcalc/examples_e2e/run_e2e.py on 544bc76; out/*.tsv byte-identical to 8ae0fa7 (git diff empty), so no e2e row's status or reason changes |
| dcalc-run-all.log | tools/dcalc-run-all.sh on 544bc76 with the pinned proof backend (CaDiCaL 3.0.1 and cake_lpr 033aad5 built by tools/dcalc-proof-backend.sh from the pinned archives, *_SHA256 set) and the E0 GMP prefix (projects/mettadinc/tools/env.sh) |

The expected answers in the gate come from two independent routes. They were worked by hand
(tests/dcalc/m0_typeform_maps/README.md), and Ben's reference evaluator gives them too (reference_answers.py: docs/e0
mg_eval.World plus models/dclib check_now, check_updates and check_abstraction_map, the routines mg_oracle.py uses).
On top of that, every type-form module has a carrier-name twin that must answer byte-identically after masking.
