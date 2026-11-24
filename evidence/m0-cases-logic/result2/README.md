# Evidence: t-2026-11-23-mettadinc-m0-cases-logic, result 2 (review 1)

Review 1 (reviewer.claude, failed): F1 a Const name nested in an operand of Eq (inside a Tuple) was read as the literal
symbol, so a form in scope answered Checked where the spec meaning answers Refuted; F2 Eq compared integer literals by
value only at the top level. Code commit: 933f4c5 (on result 1, 0eebb9d/f448ac7; base main fc6bffe). Host pop-os, gcc 11.4.
Binaries for the comparisons were built clean from `git archive` of each commit's src/.

## The change (src/dcalc/model.c)

- F1: `logic_arg` now looks for a Const name anywhere in the operand tree it is about to evaluate (`logic_const_in`):
  directly, or nested in a Tuple, Add or Mul. It does not enter a nested If/Eq/And/Or/Not, which checks its own operands
  when it is evaluated (so a Const in an If branch that is not taken is not read, matching "If evaluates only the branch it
  takes"). A Const read answers Unsupported with the same reason form as UC: "(Eq ...) reads the Const ka, which the M0
  lowering of Eq does not resolve".
- F2: Eq uses `logic_eq`: structural equality in which every pair of integer literals is compared by value, at every depth.
  (Tuple 1) and (Tuple 01) are the same value, as in the reference (Python values).

## Files

| file | what |
|---|---|
| gate_new.txt | run_m0_cases_logic.py with the 933f4c5 binary: 167 gates PASS (155 of result 1, plus LG7 x3 and UF/UG/UH, in both modes) |
| gate_on_base_binary.txt | the same gate with the fc6bffe binary: 128 FAIL |
| gate_on_result1_binary.txt | the same gate with the result-1 binary 0eebb9d: 10 FAIL, exactly the new cases (LG7 reference and twin, UF, UG, UH; both modes) |
| gate_on_mutant_if_swapped.txt, mutant_if_swapped.patch | If takes the other branch: 40 FAIL |
| gate_on_mutant_or_as_and.txt, mutant_or_as_and.patch | Or computed as And: 26 FAIL |
| gate_sanitized.txt | the gate with the ASan/UBSan build (build/dcalc-sanitized, flags of dcalc-run-all): PASS, no sanitizer output |
| other_gates.txt | m0_bool_observe, m0_typeform_maps, m0_subset_reach with the 933f4c5 binary: PASS |
| review1_cases.txt | the reviewer's repro (fixture UF) on Ben's reference evaluator: Refuted (Pair a b) (Observe ob); UF/UG/UH and LG7/LG7C per binary: fc6bffe Unsupported (form not lowered), 0eebb9d Checked/Checked/InvalidInput and LG7 Checked (the findings), 933f4c5 Unsupported naming the Const, LG7 Refuted = LG7C = reference |
| bytediff.txt | every tracked .metta outside cetta/ (260 files, 520 outputs), base fc6bffe, result 1 0eebb9d and result 2 933f4c5 binaries on the 933f4c5 tree, all exit 0 |
| run_e2e.log | tests/dcalc/examples_e2e/run_e2e.py on 933f4c5; then make_tables.py; git status clean after both (committed out/*.tsv and doc04 table unchanged) |
| dcalc-run-all.log | tools/dcalc-run-all.sh on 933f4c5 with the pinned proof backend (CaDiCaL 3.0.1, cake_lpr 033aad5; ~/scratch/mettadinc-proof-backend/env.sh) and the E0 GMP prefix (projects/mettadinc/tools/env.sh), no memory cap: PASS, 39 steps exit 0, cetta_smoke built fresh. Two earlier attempts did not finish for environmental reasons: the first was killed with its tool session during the cetta build, and the second then failed cetta_smoke at once on the half-written build/cetta-dcalc it left; after removing that build directory (ignored output), the third run passed |

## Byte-diff

- Result 1 (0eebb9d) vs result 2 (933f4c5): only logic_gates.metta and logic_unsupported.metta differ (both modes), and only
  in their new modules (LG7 Checked -> Refuted; UF, UG Checked -> Unsupported; UH InvalidInput -> Unsupported). Every
  other output, including all of docs/e0 and the earlier gates' fixtures, is byte-identical.
- Base (fc6bffe) vs result 2: the same 18 outputs of the same 9 files as result 1's bytediff.txt, nothing else.

## Limits

- A Const name that no logic form reads (for example a row giving `(Tuple $s ka)` directly) is still read as the literal
  symbol, as at fc6bffe (pre-existing; type-form probe T1). This change refuses only the reads by If/Eq/And/Or/Not, where
  a literal reading silently changes a comparison. Resolving Const names in bodies remains outside this task.
- The Const check is by name: a carrier element spelled like a declared Const name, read by a logic form, is now refused as
  Unsupported (conservative, never a wrong Checked/Refuted).
