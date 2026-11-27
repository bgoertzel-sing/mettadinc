# Evidence: t-2026-11-26-mettadinc-families-gates-2 (Families gates, round 2)

Base: mettadinc main 8fd2fec (Merge PR #59, the Families follow-ups rebase). Branch hive/t-2026-11-26-mettadinc-families-gates-2.
No change to src/: families.c and the dcalc binary are identical to 8fd2fec. Changed: run_families.py, run_families_mutants.py,
two new fixtures, one comment in tools/dcalc-run-all.sh.

Environment for every run below: host pop-os, 8 cores, 15 GiB RAM, gcc from PATH; pinned proof backend (CaDiCaL rel-3.0.1,
cake_lpr 033aad5, DCALC_*_SHA256 set; built by tools/dcalc-proof-backend.sh); E0 GMP prefix through CPATH/LIBRARY_PATH
(projects/mettadinc/tools/env.sh; the host has no gmp.h, which cetta_smoke needs).

## Item 1: memory peak of the For mutant

The for_drops_last_element mutant no longer runs on ex2. run_families_mutants.py sets DCALC_FAMILIES_SKIP_EX2=1 for every
mutant binary (run_families.py then prints a SKIP line for For/ex2); the unmutated families step still runs ex2 and
replay.py exactly as before. The For mutant is now required to FAIL the small For fixture
tests/dcalc/families/fixtures/for_small.metta in both modes, and its control rows must still PASS:

| row | HEAD (both modes) | for_drops_last_element (both modes) | role |
|---|---|---|---|
| FS CheckBlockPartition Bit2Low (needs set.i2, the last For element) | Refuted, Coverage, witness word 4 | Checked | must FAIL under the mutant |
| FT CheckBlockPartition Bit1Low (set.i1) | Refuted, Coverage, witness word 2 | Refuted, Coverage, witness word 2 | control, must still PASS |

## Item 2: ForAll/Exists unfolding gate

tests/dcalc/families/fixtures/forall_exists.metta; gate lines "ForAll/Exists (<mode>): ..." in run_families.py, exact
status, obligation and witness word.  Mutant forall_exists_drops_last_element in run_families_mutants.py replaces
`fold(..., p, k)` by `fold(..., p, k - 1)` at the Exists/ForAll unfolding site in term_list (the last instance is
elaborated but dropped from the Or/And).

| row | body | HEAD (both modes) | mutant (both modes) | role |
|---|---|---|---|---|
| QE Quiet | (Not (Exists $i Ix (Eq (BitAt $x (idx $i)) 1))) | Refuted, Coverage, witness word 4 | Checked | must FAIL under the mutant |
| QA Good | (ForAll $i Ix (Eq (BitAt $x (idx $i)) 0)) | Refuted, Coverage, witness word 4 | Checked | must FAIL under the mutant |
| QF Good (action sets bit 0) | (ForAll $i Ix (Eq (BitAt $x (idx $i)) 0)) | Refuted, Coverage, witness word 1 | Refuted, Coverage, witness word 1 | control, must still PASS |

The gate accepts only "(Status Refuted)" together with "(Witness (Word N) (Obligation Coverage)" for the exact N; any other
answer (Checked, Conditional, Unsupported, InvalidInput, a Refuted on another obligation or word) fails it.
(A first draft observed bit 2 in QE/QA; the mutant then still answered Refuted, on the Constancy obligation, and the gate
caught it only through the obligation. QE/QA now observe bit 1, constant on the reachable words, so the mutant's answer
changes status.)

## Run-all, before and after (acceptance 1)

before = tools/dcalc-run-all.sh on 8fd2fec (worktree wt-fg2-baseline); after = the same on this branch; run one after the
other on the same idle host and environment. Both: dcalc-run-all: PASS, exit 0.  Logs: run-all-before.log,
run-all-after.log; per-step rows: resources-before.tsv, resources-after.tsv (tools/dcalc_res.py: wall, user, sys,
max RSS of the step's children).

| | before (8fd2fec) | after (this branch) |
|---|---:|---:|
| total wall (/usr/bin/time) | 25:00.75 | 16:06.24 |
| peak RSS of the whole run | 4,213,612 KiB | 442,468 KiB |
| families_mutants step | 633.8 s, 4114.9 MiB | 54.3 s, 113.8 MiB |
| highest step | families_mutants 4114.9 MiB | cetta_smoke 432.1 MiB |

| step | before wall s | before peak RSS MiB | after wall s | after peak RSS MiB |
|---|---:|---:|---:|---:|
| build | 0.0 | 9.8 | 0.0 | 9.7 |
| test_boundaries | 0.2 | 27.9 | 0.2 | 27.7 |
| qrat | 0.5 | 31.1 | 0.6 | 31.5 |
| check_claims | 0.9 | 55.0 | 1.5 | 55.1 |
| negative_suite | 36.9 | 148.9 | 37.3 | 148.8 |
| refuted_abs | 0.1 | 16.5 | 0.1 | 16.5 |
| envelope | 0.4 | 14.9 | 0.4 | 15.0 |
| limits | 0.0 | 14.3 | 0.0 | 14.3 |
| limits_sanitized | 0.2 | 19.8 | 0.3 | 19.8 |
| mutation | 2.4 | 17.1 | 3.4 | 17.1 |
| held | 0.0 | 10.3 | 0.0 | 10.3 |
| registry_gen | 0.0 | 14.5 | 0.0 | 14.6 |
| package | 0.5 | 55.1 | 0.6 | 55.1 |
| admission_mutations | 1.2 | 14.6 | 1.3 | 14.6 |
| m2_claims | 0.2 | 17.0 | 0.2 | 17.0 |
| m2_gates | 1.0 | 16.9 | 1.2 | 16.9 |
| m2_differential | 0.2 | 24.5 | 0.2 | 24.5 |
| m2_screen | 0.1 | 26.8 | 0.1 | 26.7 |
| m2_claimless | 0.0 | 10.2 | 0.0 | 10.0 |
| m3_incremental | 0.0 | 9.7 | 4.2 | 70.2 |
| m3_gates | 45.5 | 148.8 | 50.6 | 148.8 |
| m3_tv | 26.1 | 58.1 | 26.7 | 58.2 |
| m4_gates | 0.4 | 17.8 | 0.5 | 17.8 |
| m4_estimates | 0.2 | 30.1 | 0.3 | 30.3 |
| m4_coverage | 5.0 | 26.8 | 4.8 | 26.8 |
| m4_coverage_01 | 4.8 | 9.8 | 4.4 | 9.9 |
| cetta_smoke | 512.4 | 432.5 | 532.8 | 432.1 |
| m5_weakbarbed | 0.9 | 12.6 | 1.0 | 12.8 |
| m5_gates | 4.7 | 43.6 | 4.5 | 43.7 |
| m6_gates | 2.4 | 13.2 | 2.3 | 13.6 |
| m6rest_gates | 0.2 | 11.6 | 0.3 | 11.6 |
| m6graded_gates | 73.3 | 58.3 | 81.2 | 58.6 |
| m7_gates | 0.3 | 55.0 | 0.3 | 55.1 |
| m7_replay | 0.5 | 55.0 | 0.5 | 55.1 |
| review_fixes | 0.7 | 55.1 | 0.7 | 55.1 |
| m0_subset_reach | 0.0 | 10.4 | 0.0 | 10.4 |
| m0_bool_observe | 0.1 | 10.6 | 0.1 | 10.7 |
| m0_typeform_maps | 0.1 | 14.3 | 0.1 | 15.9 |
| m0_like | 0.2 | 16.2 | 0.2 | 16.0 |
| m0_body_maps | 0.2 | 17.3 | 0.2 | 17.3 |
| m0_cases_logic | 0.2 | 14.2 | 0.2 | 14.3 |
| m0_gap_g | 0.9 | 16.9 | 1.0 | 16.9 |
| families | 67.9 | 148.8 | 74.5 | 148.8 |
| stoch_reach | 0.1 | 10.6 | 0.1 | 10.7 |
| families_mutants | 633.8 | 4114.9 | 54.3 | 113.8 |
| differential | 74.0 | 48.9 | 72.3 | 48.8 |
| sum of steps | 1499.7 | | 965.5 | |

build, limits_sanitized and (before) m3_incremental show near-zero times because both trees' objects were already built
by an earlier run on the same tree; cetta_smoke built its scratch CeTTa from scratch in both runs.

## Mutant gate (acceptance 1, 2)

build/families_mutants.out of the after run (mutants-after.out):

```
PASS  mutant eq_symbols_always_false: caught by run_families (exit 1, 6 FAIL lines; required Fold (release): FE CheckNow R ; Fold (--beyond-release): FE CheckNow R )
PASS  mutant and_folded_as_or: caught by run_families (exit 1, 2 FAIL lines; required Fold (release): FA CheckNow R ; Fold (--beyond-release): FA CheckNow R )
PASS  mutant for_drops_last_element: caught by run_families (exit 1, 2 FAIL lines; required For/small (release): FS ; For/small (--beyond-release): FS ; controls still PASS: For/small (release): FT ; For/small (--beyond-release): FT )
PASS  mutant forall_exists_drops_last_element: caught by run_families (exit 1, 4 FAIL lines; required ForAll/Exists (release): QE ; ForAll/Exists (--beyond-release): QE ; ForAll/Exists (release): QA ; ForAll/Exists (--beyond-release): QA ; controls still PASS: ForAll/Exists (release): QF ; ForAll/Exists (--beyond-release): QF )
run_families_mutants: PASS
```

## Byte-diff of tracked .metta (acceptance 3)

bytediff.sh: every git-tracked .metta of this branch, release and --beyond-release, run with the 8fd2fec binary and with
this branch's binary (paths normalised); files new on this branch run only with the new binary.

```
NEW tests/dcalc/families/fixtures/for_small.metta release
NEW tests/dcalc/families/fixtures/for_small.metta beyond
NEW tests/dcalc/families/fixtures/forall_exists.metta release
NEW tests/dcalc/families/fixtures/forall_exists.metta beyond
bytediff: 286 tracked .metta, 572 outputs: 568 identical, 0 differ, 4 new-only
```

The 568 outputs of the 284 files present on 8fd2fec are byte-identical; the only new outputs are the two new fixtures, both modes.
