# Evidence: t-2026-11-24-mettadinc-rebase-bool-observe

Supersedes: t-2026-11-23-mettadinc-m0-bool-observe

Rebase of PR 33 (hive/t-2026-11-23-mettadinc-m0-bool-observe, 1eaa7a8 + 26b14e3, base 8ae0fa7) onto GitHub main
eb5a662 (merge of PR 40, after PR 37). Commits brought over with `git cherry-pick -x`: 1eaa7a8 -> 87f2c0b,
26b14e3 -> d79f9f0. Host: pop-os, gcc 11.4. No new behaviour.

## Conflicts

| file | conflict | resolution |
|---|---|---|
| tests/dcalc/examples_e2e/README.md | class legend: PR 33 rewrote the `GAP` line (a lowered, f added); main (PR 36) rewrote the `BUG` line to "finding 3; finding 4 is fixed" | kept PR 33's `GAP` line and main's `BUG` line; nothing dropped |

Auto-merged without conflict: tests/dcalc/examples_e2e/doc04_omega_memory_goals.md (PR 33 edits rows 43-49 GAP text,
main edited the ClaimArbitration rows), tools/dcalc-run-all.sh (PR 33 adds the m0_bool_observe step; main's steps unchanged).
No C source overlaps: main changed admit.c and stoch.c, PR 33 changes model.c, model.h, ops_graded.c, ops_hives.c,
ops_induce.c, ops_req.c. Only a shared test/report file conflicted; no meaning changed.

## Files

| file | what |
|---|---|
| change_equivalence.txt | the +/- lines of 8ae0fa7..26b14e3 and of eb5a662..d79f9f0 (27 files each) are identical: the diff against main is the original change plus context |
| gate_new.txt | tests/dcalc/m0_bool_observe/run_m0_bool_observe.py on this branch: 71 PASS |
| gate_on_base_binary.txt | the same gate with the eb5a662 binary: 66 FAIL (same PASS/FAIL pattern as evidence/m0-bool-observe with 8ae0fa7) |
| gate_on_constant_true_mutant.txt, constant_true_mutant.patch | the same gate with every Bool observation forced to True: 16 FAIL (same pattern as the original) |
| bytediff.txt | every tracked .metta (234, outside cetta/), release and --beyond-release, eb5a662 vs this branch: only the probe A1 repro and PR 33's own gate fixtures differ; main's new D6 and map_name_cycle fixtures are unchanged |
| mutate_gate.log | tests/dcalc/differential/mutate_gate.sh: MUTATION CHECK PASS, 6/6 mutants killed (lin_rho_lastrow, kant_half, d4_tol_unclipped, d4_con_unclipped, d5_rep_only, d6_rep_only) |
| differential_gate.out | tests/dcalc/differential/gate.sh build/dcalc/dcalc (from run-all): GATE PASS, canaries D4_con_clip, D4_con_clip_two_point, D4_tol_dist, D5_kant_classpairs, D6_trace_classpairs ok |
| dcalc-run-all.log | tools/dcalc-run-all.sh: PASS (exit 0, every step exit 0), pinned proof backend (tools/dcalc-proof-backend.sh, CaDiCaL 3.0.1, cake_lpr 033aad5, sha256 pins) and the E0 GMP prefix; CeTTa build cache HIT from a first run of the same tree that built CeTTa (cetta_smoke PASS) and was then killed by the tool's session timeout at m5_gates (not a test failure) |

Also: run_e2e.py on this branch gives out/*.tsv byte-identical to the committed ones; make_tables.py on a clean copy
reproduces the committed doc0N tables (README, doc03-06) byte for byte.
