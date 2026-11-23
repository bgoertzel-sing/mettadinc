# Evidence: t-2026-11-23-mettadinc-m0-like-machines

Base: mettadinc main 8ae0fa7 (merge of PR #32, m0-subset-reach). Code commit: e10b23a. Host: pop-os, gcc 11.4.
Proof backend: tools/dcalc-proof-backend.sh (CaDiCaL rel-3.0.1, cake_lpr 033aad5, sha256 pins set).
Base binary sha256 5e3cd4f3...afea3; new binary (e10b23a) sha256 5accfc7b...e39c.

| file | what |
|---|---|
| gate_new.txt | tests/dcalc/m0_like/run_m0_like.py on e10b23a: 173 PASS |
| gate_on_base_binary.txt | the same gate with the 8ae0fa7 binary: 118 FAIL (Like was Unsupported). LN1, LN3, LN4, LN7 pass there too: the registry admission already refused them |
| gate_on_mutant_drop_observe.txt | mutant: Like copies only the Action entries: 56 FAIL |
| gate_on_mutant_ignore_scope.txt | mutant: Like uses N's States instead of its own scope: 46 FAIL |
| bytediff.txt | every tracked .metta outside cetta/ (224 at 8ae0fa7), each alone from its directory, release and --beyond-release, base vs new binary (tests/dcalc/m0_like/metta_bytediff.py): only repro/m0_blocker_d_like.metta changes; the 4 new fixtures are only in the new run |
| probe_release.diff, probe_beyond.diff | that change: D1 (CheckNow R) Unsupported -> Checked; D1C unchanged |
| run_e2e.txt, e2e_out_vs_base.txt | run_e2e.py on the new binary: all 14 out/*.tsv byte-identical to 8ae0fa7, so no e2e row's answer changes |
| ablate_taskresume.txt | which gaps still block doc04 TaskResume: (a) or (c) alone, all 5 rows; (b) or the Body map alone, row 48 only |
| dcalc-run-all.log | tools/dcalc-run-all.sh on e10b23a: PASS (exit 0), with the pinned proof backend and the E0 GMP prefix (projects/mettadinc/tools/env.sh) |
| dcalc-run-all-first-no-submodule.log | the first run: every step 0 except cetta_smoke, because the fresh worktree had no cetta/ checkout (fixed with git submodule update --init at the pin 4c285a97) |

registry/ and the generated src/dcalc/registry_gen.c / registry_beyond_gen.c are unchanged vs 8ae0fa7 (git diff empty; gen_registry --check up to date).
