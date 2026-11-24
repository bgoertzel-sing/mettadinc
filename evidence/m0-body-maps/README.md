# Evidence: t-2026-11-24-mettadinc-m0-body-maps

Base: mettadinc main d2177e3 (merge of PR #47, the like-machines rebase; contains the bool-observe and typeform-maps
rebases). The cases-logic branch (If/Eq/And/Or/Not in Cases) was not merged when this task started, so it is not in the
base. Host: pop-os, gcc 11.4. Base binary sha256 8051950d7116f50004006ad33cf615ff906743b26f2b73c733756fdc035edc37 (the same
as the like-machines rebase build); new binary sha256 34ff516ca317683e21d01d6d5e736ade7d7e9c479cc9b0fac535dec5bfcc0039.

| file | what |
|---|---|
| gate_new.txt | tests/dcalc/m0_body_maps/run_m0_body_maps.py on this branch: 194 PASS |
| gate_on_base_binary.txt | the same gate with the d2177e3 binary: 168 FAIL (Body maps were Unsupported) |
| gate_on_mutant_first.txt, mutant_first.diff | a meaning mutant binding $v to the carrier's first element on declared carriers (a constant map): 56 FAIL |
| gate_on_mutant_reversed.txt, mutant_reversed.diff | a meaning mutant binding $v to the elements in reverse order on type-form maps: 20 FAIL |
| gate_sanitized.txt | the gate with an ASan/UBSan build of this branch: 194 PASS, no sanitizer report |
| bytediff.txt | every tracked .metta outside cetta/ (259 files) run alone in release and --beyond-release mode, base binary vs new binary (tests/dcalc/m0_like/metta_bytediff.py): 4 of 518 outputs differ, the repro and one typeform fixture, both modes |
| probe_release.diff, probe_beyond.diff | repro f: F1 (CheckNow R) Unsupported -> Checked, Blocks (p) (q); F1C unchanged |
| typeform_uc_release.diff, typeform_uc_beyond.diff | tests/dcalc/m0_typeform_maps fixture UC, a type-form Body identity map, which that gate kept as Unsupported: now Checked with four singleton blocks; the typeform gate now checks that answer |
| run_e2e.log | run_e2e.py on this branch: out/*.tsv byte-identical to d2177e3 (no e2e answer changes) |
| ablate_taskresume.txt | tests/dcalc/m0_like/ablate_taskresume.py on this branch: putting back the Body map (f) no longer changes any TaskResume answer; only (c) does |
| scratch_merge_cases_logic.txt, resolve_scratch_merge.py | report only: this branch merged in a scratch tree with the cases-logic branch (933f4c5), model.c conflicts resolved by the script: doc04 TaskResume (rows 45-49) gives doc04's five answers; AnchorMigration (rows 43-44) is still Unsupported because its Bool Observe maps are declared with a type-form From (repro g of the cases-logic task). Also the cases-logic binary alone for comparison |
| dcalc-run-all.log, dcalc-run-all.env | tools/dcalc-run-all.sh on this branch with the pinned proof backend (tools/dcalc-proof-backend.sh: CaDiCaL 3.0.1, cake_lpr 033aad5, sha256 pins) and the E0 GMP prefix (projects/mettadinc/tools/env.sh); CeTTa submodule at its pin 4c285a97 |
| dcalc-run-all-first-no-submodule.log | the first attempt: the fresh worktree had no CeTTa submodule checkout (cetta_smoke exit 2), and the run was cut off at m6graded_gates when its shell ended; every step before it was 0 |

Changed e2e rows: none. make_tables.py changes only the GAP class text of doc04 rows 43-49 (14 cells): (f) moves from the
rejected forms to the lowered ones. Status and reason cells are unchanged.

Release registry: unchanged (registry/ untouched; gen_registry.py --check in run-all).
