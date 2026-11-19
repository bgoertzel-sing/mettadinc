# examples_e2e: Ben's worked examples through the real CLI (t-2026-11-18-mettadinc-examples-e2e)

Report-only. No product code changed and the registry is unchanged. Base: mettadinc main dd0960a. The modules run unedited, from their bundle directories.

## Rerun

    make -C src/dcalc                                        # builds build/dcalc/dcalc
    python3 tests/dcalc/examples_e2e/run_e2e.py              # writes out/<id>_{release,beyond}.tsv
    (cd tests/dcalc/examples_e2e && python3 make_tables.py)  # writes doc0N_*.md

Literal per-module commands (R = repository root; drop `--beyond-release` and the LIBS for release mode):

    R=$(git rev-parse --show-toplevel); W=$R/docs/e0/docs/03_four_worked_examples/validation_bundles
    cd $W/ex1_belief_memory && $R/build/dcalc/dcalc --beyond-release belief_memory.metta
    cd $W/ex2_access_policy && $R/build/dcalc/dcalc --beyond-release access_policy.metta
    cd $W/ex3_skill_share   && $R/build/dcalc/dcalc --beyond-release skill_share.metta
    cd $W/ex4_market_maker  && $R/build/dcalc/dcalc --beyond-release market_maker.metta
    cd $R/docs/e0/docs/04_omega_memory_goals_part1/validation_bundle && $R/build/dcalc/dcalc --beyond-release memory_goals.metta
    cd $R/docs/e0/docs/05_live_memory_part2/validation_bundle && $R/build/dcalc/dcalc --beyond-release live_memory.metta memory_goals.metta
    cd $R/docs/e0/docs/06_wmtm_worked_example/validation_bundle && $R/build/dcalc/dcalc --beyond-release wmtm_example.metta live_memory.metta memory_goals.metta

Repros, run from R, in both modes:

    build/dcalc/dcalc --beyond-release tests/dcalc/examples_e2e/repro/stoch_reach_carrier.metta          # InvalidInput (finding 3)
    build/dcalc/dcalc --beyond-release tests/dcalc/examples_e2e/repro/stoch_reach_carrier_control.metta  # Checked
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/map_name_element_clash.metta          # InvalidInput "map-call cycle deadline -> deadline" (finding 4)
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/map_name_element_clash_control.metta  # passes admission
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/map_name_equals_element.metta         # same bug, smaller variant (+ _control)
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/carrier_subset_reach.metta            # S Subset, T Reach: Unsupported "outside the M0 fragment"; U Enum: Checked (finding 5)

## Tables

Each `doc0N_*.md` has one row per request with these columns: the document's answer and its source (table or line), our answer in release mode and in beyond mode, a class for each answer, and the beyond-mode reason. The document answers are in `doc_expected.tsv` (306 rows, keyed by run and request index). Where the document gives only a value (class counts, rates), the row says "no status word". "inferred" marks a status that I derived from the document's numbers rather than read directly. "not stated" marks a request (7 in ex1) with no matching sentence in the document.

Class legend:
- `match`: same status as the document. This includes the negative fixtures, and ex3/ex4 Unsupported in release mode, because doc03 s2.6 (l.488-493) names ex3 and ex4 as M6 and M4 conformance targets that a first release answers with Unsupported.
- `GATED`: the request uses a PROPOSED library that no milestone admits, or a stochastic profile in release mode.
- `GAP`: the M0 lowering skips Subset and Reach carriers (model.c:175).
- `BUG`: a checker bug (findings 3 and 4).
- `CLI`: in release mode the LIBS imports are not loaded (main.c:129).

## Totals (306 requests: ex1 61, ex2 15, ex3 32, ex4 36, mg 92, ls 37, wx 33)

| mode | match | GATED | GAP | BUG | CLI |
|---|---|---|---|---|---|
| release | 70 (ex3 32 + ex4 36 by s2.6; 2 ls fixtures) | 203 | 7 | 3 | 23 |
| beyond | 2 (ls fixtures) | 286 | 7 | 11 | 0 |

No Checked, Refuted, Conditional or Estimated answer in the documents is reproduced, because no request reaches a decision procedure.

## Findings

1. **ex2 contradicts the documents.** Doc03 s2.6 says "Example 2 lies entirely within" the first release. dcalc rejects all 15 ex2 requests in both modes with "library Families is outside the first release". Either the manifest or the document is wrong. This is the main mismatch a user who follows the documents will hit.
2. **PROPOSED libraries are admitted by no milestone.** The registry's `first_release` list is Core, GradedKernels, BitVectors and FiniteSets. `M4_LIBS` (admit.c:1074) does not list NatArith, Families, Laws, RationalArith, Parallel, Monitors, Statistics or BoundedSets. This gates ex1, ex2, mg (except AnchorMigration/TaskResume), ls and wx. The gate reports only the first failing library (admit.c:1096).
3. **The stochastic reader rejects `(Reach ...)` carriers** (ex4 NewsLeak: all 8 requests return InvalidInput in beyond mode). stoch.c:52 requires `(Enum ...)`, but spec l.1719 allows `(Reach M (From s+))`.
4. **False map-call cycle when a Map has the same name as an Enum element** (doc04 ClaimArbitration: 3 requests, both modes). `sym_atoms` (admit.c:776) records every symbol that names a Map as a call. This check runs before the library gate.
5. **Seven library-free doc04 requests are not lowered.** AnchorMigration (memory_goals.metta:341, Subset carriers) and TaskResume (:390, Reach carrier) use no library. All 7 of their requests answer "outside the M0/M2 fragment" because the M0 lowering takes only Enum and Product carriers (model.c:175). The spec grammar allows both carrier forms, and doc04 s6.4 says AnchorMigration "uses only forms of the base registry".
6. **Negative fixtures.** The 2 ls fixtures (live_memory.metta:102 and :354) return InvalidInput as intended. The 2 doc04 ItemGoals fixtures (memory_goals.metta:586) should return InvalidInput but come back Unsupported, because the NatArith gate hides them.
7. **CLI.** Release mode ignores LIBS (main.c:129), so the cross-file imports in ls and wx fail with "Import of unknown module".
