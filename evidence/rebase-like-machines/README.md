# Evidence: t-2026-11-24-mettadinc-rebase-like-machines

Supersedes: t-2026-11-23-mettadinc-m0-like-machines

Rebase of hive/t-2026-11-23-mettadinc-m0-like-machines (e10b23a + 9a91273, base 8ae0fa7) onto GitHub main
fc6bffe (merge of PR #46 = the typeform-maps rebase; contains PR #41 = the bool-observe rebase). Commits brought over
with `git cherry-pick -x`: e10b23a -> c40b618 (with the conflict resolutions below), 9a91273 -> 27a2b42 (the original
evidence, evidence/m0-like/, unchanged). Host: pop-os, gcc 11.4. No new behaviour was written.

## Conflicts

| file | conflict | resolution |
|---|---|---|
| src/dcalc/model.h | both sides added a `skipwhy` table to DcModule (main 32 x 256, PR 8 x 192) and a comment on `dc_skip_why` | main's table (32 x 256) and declaration, one copy; comments now also name Like machines |
| src/dcalc/model.c (statics) | main: `allow_bool` + `pending_why[256]`; PR: `pending_why[192]` (the same mechanism, a third copy) | main's lines; the comment names Like machines |
| src/dcalc/model.c (auto-merged, duplicate) | git merged without a marker but left two definitions of `dc_skip_why` (main's next to `admit_bool_observe_map`, the PR's next to `dc_is_skipped`) and two skipwhy records in the admission loop (main's on `rc == -2` before the Import case, the PR's inside the `rc == -2` block) | one helper: the PR's duplicate `dc_skip_why` (identical body) removed; one record: main's (it also has the `referenced_why` fallback); the PR's second record removed, since with one buffer it would add each entry twice. The PR's per-declaration `pending_why[0] = 0` reset and its `admit_repr` reason were already on main, identical, and merged as one |
| src/dcalc/ops_induce.c (and the PR's ops_req.c line) | same lines on both sides | already on main from PR 41; nothing to add |
| tools/dcalc-run-all.sh | both added steps at the same place (main: m0_bool_observe, m0_typeform_maps; PR: m0_like) | all three steps kept |
| tests/dcalc/examples_e2e/make_tables.py | both rewrote the GAP class text | new text: (c) and (f) remain; (a) Bool Observe maps, (b) type-form maps, (d) Machine Like and Subset/Reach carriers are lowered |
| tests/dcalc/examples_e2e/doc04_omega_memory_goals.md | rows 43-49 GAP text (14 cells) | main's rows, then regenerated with make_tables.py (only the GAP class text changes; status and reason cells unchanged) |
| tests/dcalc/examples_e2e/README.md | GAP legend; findings 3-5 | GAP legend: main's, with (d) moved to the lowered list (repro/m0_blocker_d now Checked); main's findings 3-5 kept; the PR's finding-5 content added as an "Update (t-2026-11-23-mettadinc-m0-like-machines)" paragraph, with the ablation re-run on this base (below). The repro D1 line merged cleanly from the PR |
| tests/dcalc/m0_like/README.md (new file, edited) | not a conflict: two sentences were true only on 8ae0fa7 | the reason-table sentence now says the table is shared with the Bool Observe and type-form lowerings; the ablate_taskresume.py line gives the result on this base and on 8ae0fa7 |

Nothing on main was dropped; every gate, canary, mutant and report entry from both sides is present.

## Meaning

1. The C changes beyond the like-machines branch's own lines are removals of duplicates (one `dc_skip_why`, one skipwhy record). The Like
   reasons now go into main's table (32 x 256 instead of the PR's 8 x 192); only the capacity differs (it grows).
2. No e2e answer changes. run_e2e.py on this branch leaves every out/*.tsv byte-identical to fc6bffe; make_tables.py then
   changes only the GAP class text of doc04 rows 43-49.
3. **The TaskResume ablation reads differently on this base.** On 8ae0fa7, putting back (a) the (To Bool) Observe maps
   blocked all five rows and (b) a type-form To blocked row 48. On fc6bffe + Like those forms are lowered, so they change
   no answer: only (c) If/And/Eq (all five rows) and the Body map (f, row 48) still block. ablate_taskresume.txt. The
   e2e README and tests/dcalc/m0_like/README.md say this.

## Files

| file | what |
|---|---|
| change_equivalence.txt | sorted +/- lines of 8ae0fa7..e10b23a vs fc6bffe..c40b618 (src/, tools/, tests/): every difference is one of the resolutions above (duplicate skip-why helper/table/record dropped, ops_* lines already on main, legend/table/README text) |
| gate_like_new.txt | tests/dcalc/m0_like on this branch: 173 PASS |
| gate_like_on_base_binary.txt | the same gate with the fc6bffe binary (sha256 b86b25ab..., identical to the typeform-rebase build): 118 FAIL; PASS/FAIL pattern identical to the PR's gate_on_base_binary.txt |
| gate_like_on_mutant_drop_observe.txt / _ignore_scope.txt | the PR's two meaning mutants of admit_like applied to this branch: 56 and 46 FAIL, patterns identical to the PR |
| gate_like_sanitized.txt | m0_like with an ASan/UBSan build of this branch: 173 PASS, no sanitizer report |
| gate_bool_observe_new.txt, gate_typeform_new.txt, gate_subset_reach_new.txt | main's M0 gates on this branch: 71, 85, 20 PASS |
| bytediff.txt, probe_release.diff, probe_beyond.diff | every tracked .metta outside cetta/ (259 files, both modes; metta_bytediff.py), fc6bffe binary vs this branch: only repro/m0_blocker_d_like.metta (D1 Unsupported -> Checked) and the 4 m0_like fixtures differ |
| ablate_taskresume.txt | tests/dcalc/m0_like/ablate_taskresume.py on this branch |
| run_e2e.log | run_e2e.py on this branch (out/*.tsv unchanged) |
| mutate_gate.log | tests/dcalc/differential/mutate_gate.sh: MUTATION CHECK PASS, 7/7 mutants killed |
| differential_gate.out | tests/dcalc/differential/gate.sh build/dcalc/dcalc (from run-all) |
| dcalc-run-all.log | tools/dcalc-run-all.sh with the pinned proof backend (tools/dcalc-proof-backend.sh: CaDiCaL 3.0.1, cake_lpr 033aad5, sha256 pins) and the E0 GMP prefix; CeTTa submodule at its pin 4c285a97 |

New binary sha256 8051950d7116f50004006ad33cf615ff906743b26f2b73c733756fdc035edc37.
