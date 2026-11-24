# Evidence: t-2026-11-23-mettadinc-m0-cases-logic

Base: mettadinc main fc6bffe (merge of PR #46; contains m0-subset-reach, merge 8ae0fa7). Code commit: 0eebb9d.
Host: pop-os, gcc 11.4. Binaries for the comparisons were built clean from `git archive` of each commit's src/.

| file | what |
|---|---|
| gate_new.txt | tests/dcalc/m0_cases_logic/run_m0_cases_logic.py on 0eebb9d: 155 PASS (release and --beyond-release) |
| gate_on_base_binary.txt | the same gate with the fc6bffe binary: 118 FAIL (the form was Unsupported; negatives and reasons differ) |
| gate_on_mutant_if_swapped.txt, mutant_if_swapped.patch | a mutant whose If takes the other branch (wrong meaning, answers still Checked/Refuted): 38 FAIL |
| gate_on_mutant_or_as_and.txt, mutant_or_as_and.patch | a mutant that computes Or as And: 26 FAIL |
| gate_sanitized.txt | the gate with the ASan/UBSan build that dcalc-run-all makes (build/dcalc-sanitized) |
| other_gates.txt | m0_typeform_maps, m0_bool_observe, m0_subset_reach gates on 0eebb9d (after their fixtures BU2/UB/UE moved to Xor) |
| bytediff.txt | every tracked .metta outside cetta/ (260 files), each alone, release and --beyond-release, fc6bffe binary vs 0eebb9d binary on the 0eebb9d tree, with the differences of the non-new files |
| fixtures_at_base.diff | bool_observe_gates.metta and typeform_unsupported.metta as they were at fc6bffe (If/Eq in BU2, UB, UE), base vs new binary |
| ablation.py, ablation_new.txt, ablation_base.txt | doc04 AnchorMigration/TaskResume from doc04's text with every subset of the other gaps' rewrites, on the new and the base binary: which gap blocks each row now |
| run_e2e.log | tests/dcalc/examples_e2e/run_e2e.py on 0eebb9d; out/mg_*.tsv rows 43-48 change reason only (committed in 0eebb9d) |
| dcalc-run-all.log | tools/dcalc-run-all.sh on 0eebb9d with the pinned proof backend (CaDiCaL 3.0.1, cake_lpr 033aad5, sha256 pins, ~/scratch/mettadinc-proof-backend/env.sh) and the E0 GMP prefix (projects/mettadinc/tools/env.sh) |

## Byte-diff of every tracked .metta (both modes)

Outputs that differ between the fc6bffe and the 0eebb9d binary (bytediff.txt), and why:

| file | change | why |
|---|---|---|
| tests/dcalc/examples_e2e/repro/m0_blocker_c_if_eq_cases.metta | C1 Unsupported -> Checked; C1C unchanged | the probe: this lowering |
| tests/dcalc/m0_cases_logic/fixtures/*.metta (4 new files) | all | new gate fixtures (Unsupported on the base binary) |
| docs/e0/docs/04_.../memory_goals.metta and its copies in the 05 and 06 bundles (same difference) | AnchorMigration rows 43-44 and TaskResume rows 45-48: status Unsupported unchanged, reason changes | the If/Eq/And/Or/Not bodies no longer stop admission, so the first remaining blocker is reported (AnchorMigration: "Observe live: Map live-new: field From", gap g; TaskResume: the Like machine, gap d, which records no reason) |
| tests/dcalc/m0_typeform_maps/fixtures/typeform_unsupported.metta | UB, UE: Unsupported unchanged, reason text "which admits Tuple, Add and Mul" -> "which admits Tuple, Add, Mul, If, Eq, And, Or and Not" | the fragment list in that reason now includes the lowered forms |

Nothing else changes: the other 251 files give byte-identical output in both modes. With the two fixtures as they were at
fc6bffe (fixtures_at_base.diff), BU2, UB and UE (If/Eq) change from Unsupported to Refuted, Checked and Refuted; those
answers are worked by hand and gated in tests/dcalc/m0_cases_logic as LG5, LG6 and LG4.

## e2e rows that change (run_e2e.py, both modes identical)

| row | request | doc04 | ours before | ours now | blocked now by |
|---|---|---|---|---|---|
| mg 43 | AnchorMigration (CheckAbstractionMap NaiveMigration) | Refuted | Unsupported (no reason) | Unsupported: Observe live: Map live-new: field From | (g) Bool Observe map with a type-form From, and (f) lesion Body map |
| mg 44 | AnchorMigration (CheckAbstractionMap CellMigration) | Checked | Unsupported (no reason) | same as 43 | (g) and (f) |
| mg 45 | TaskResume (CheckNow NoReadSets) | Checked | Unsupported: ... needs-revalidation: Cases row 0 uses an operator outside the M0 fragment | Unsupported (no reason) | (d) Machine Like only |
| mg 46 | TaskResume (CheckUpdates NoReadSets) | Refuted | as 45 | as 45 | (d) only |
| mg 47 | TaskResume (CheckBehavioral NoReadSets) | Refuted | as 45 | as 45 | (d) only |
| mg 48 | TaskResume (CheckBehavioral ReadSets) | Checked | as 45 | as 45 | (d) and (f) checkpoint-with-reads Body map |
| mg 49 | TaskResume ResumeMemory | 11 classes on 12 states | Unsupported: Machine Resume is outside the M2 fragment | unchanged | (d) only |

"Blocked now by" comes from the ablation (ablation_new.txt): with only the named gaps rewritten, the row gives doc04's
answer. On the base binary no rewrite subset helps (ablation_base.txt), because the logic bodies blocked every row.
