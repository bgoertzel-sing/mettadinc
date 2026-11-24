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

    build/dcalc/dcalc --beyond-release tests/dcalc/examples_e2e/repro/stoch_reach_carrier.metta          # Unsupported (finding 3; was InvalidInput)
    build/dcalc/dcalc --beyond-release tests/dcalc/examples_e2e/repro/stoch_reach_carrier_control.metta  # Checked
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/map_name_element_clash.metta          # Unsupported, same as its control (finding 4, fixed; was InvalidInput "map-call cycle deadline -> deadline")
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/map_name_element_clash_control.metta  # passes admission
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/map_name_equals_element.metta         # Checked, same as its control (finding 4, fixed; smaller variant)
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/carrier_subset_reach.metta            # S Subset, T Reach, U Enum: all Checked (finding 5; S and T were Unsupported before the M0 Subset/Reach lowering)
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/m0_blocker_a_bool_observe.metta       # A1 Checked since t-2026-11-23-mettadinc-m0-bool-observe (was Unsupported, Bool Observe map); A1C control Checked (finding 5)
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/m0_blocker_b_typeform_map.metta       # B1 Unsupported (map declared (From (Tuple Symbol Symbol))); B1C control Checked
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/m0_blocker_c_if_eq_cases.metta        # C1 Unsupported (If/Eq in Cases); C1C control Checked
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/m0_blocker_d_like.metta               # D1 Unsupported (Machine Like); D1C control Checked
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/m0_blocker_e_minimize.metta           # E1 Checked: MinimizeForQueries alone is not a blocker
    build/dcalc/dcalc tests/dcalc/examples_e2e/repro/m0_blocker_f_crisp_body.metta         # F1 Unsupported (Body map in a Crisp module); F1C control Checked

## Tables

Each `doc0N_*.md` has one row per request with these columns: the document's answer and its source (table or line), our answer in release mode and in beyond mode, a class for each answer, and the beyond-mode reason. The document answers are in `doc_expected.tsv` (306 rows, keyed by run and request index). Where the document gives only a value (class counts, rates), the row says "no status word". "inferred" marks a status that I derived from the document's numbers rather than read directly. "not stated" marks a request (7 in ex1) with no matching sentence in the document.

Class legend:
- `match`: same status as the document. This includes the negative fixtures, and ex3/ex4 Unsupported in release mode, because doc03 s2.6 (l.488-493) names ex3 and ex4 as M6 and M4 conformance targets that a first release answers with Unsupported.
- `GATED`: the request uses a PROPOSED library that no milestone admits, or a stochastic profile in release mode.
- `GAP`: the M0 lowering rejects one of these forms: (b) a map declared with a type form in From/To, (c) If/Eq/And/Or/Not in Cases bodies, (d) Machine Like, (f) a Body map in a Crisp module (repro/m0_blocker_b..d, f). Subset and Reach carriers are lowered, and so is (a) a (To Bool) map used as an Observe port (t-2026-11-23-mettadinc-m0-bool-observe, repro/m0_blocker_a now Checked). In beyond mode GAP also covers the 8 ex4 NewsLeak rows: a stochastic module with a Reach carrier, valid by the spec (l.1719) but outside the stochastic backend fragment, so it answers Unsupported (finding 3).
- `BUG`: a checker bug. No row has this class now (findings 3 and 4 are resolved).
- `CLI`: in release mode the LIBS imports are not loaded (main.c:129). Fixed by t-2026-11-20-mettadinc-release-libs: no row has this class now.

## Totals (306 requests: ex1 61, ex2 15, ex3 32, ex4 36, mg 92, ls 37, wx 33)

| mode | match | GATED | GAP | BUG | CLI |
|---|---|---|---|---|---|
| release | 70 (ex3 32 + ex4 36 by s2.6; 2 ls fixtures) | 229 | 7 | 0 | 0 |
| beyond | 2 (ls fixtures) | 289 | 15 (7 M0 + 8 ex4 NewsLeak Reach carrier) | 0 | 0 |

No Checked, Refuted, Conditional or Estimated answer in the documents is reproduced, because no request reaches a decision procedure.

## Scope notes

- **The bundles' registry patches are not skipped.** All 7 bundle patches (ex1-ex4, mg, ls, wx) are already part of `registry/mettadinc_registry.json`: Ben's decision 1 adopted them before M0, and `tools/adopt_registry.py` applies them (see `registry/SOURCES.md`, which lists each patch with its sha256). dcalc reads that registry, because `src/dcalc/registry_gen.c` is generated from it by `tools/gen_registry.py`. So running the modules unedited against the repository registry is the patched setup the documents assume.
- **Table 10 rows M1 and M2 are excluded.** In doc03 Table 10 (mettadinc_worked_examples.txt:1551-1556), the rows "mutation M1 (approver rule reads the auditor session): NoBreach" and "mutation M2 (revoking clerk keeps approver): ClerksOnlyProved" are checked only by the oracle. `ex2_oracle.py` (section 8, `MUTATIONS`, l.678ff) runs them on mutated copies of the source. They are not `dc.run` forms in `access_policy.metta`, which has 15 requests, so the CLI has nothing to run for them and they are not among the 15 ex2 rows of `doc_expected.tsv`.

## Findings

1. **ex2 contradicts the documents.** Doc03 s2.6 says "Example 2 lies entirely within" the first release. dcalc rejects all 15 ex2 requests in both modes with "library Families is outside the first release". Either the manifest or the document is wrong. This is the main mismatch a user who follows the documents will hit.
2. **PROPOSED libraries are admitted by no milestone.** The registry's `first_release` list is Core, GradedKernels, BitVectors and FiniteSets. `M4_LIBS` (admit.c:1074) does not list NatArith, Families, Laws, RationalArith, Parallel, Monitors, Statistics or BoundedSets. This gates ex1, ex2, mg (except AnchorMigration/TaskResume), ls and wx. The gate reports only the first failing library (admit.c:1096).
3. **The stochastic reader rejects `(Reach ...)` carriers** (ex4 NewsLeak: all 8 requests return InvalidInput in beyond mode). stoch.c:52 requires `(Enum ...)`, but spec l.1719 allows `(Reach M (From s+))`. **Reclassified** (t-2026-11-23-mettadinc-lowering-unsupported): the reader still handles only `(Enum ...)`, but a well-formed non-enumerated carrier is now a fragment limit, so the 8 requests answer Unsupported ("form outside the stochastic backend fragment") instead of InvalidInput. Status: resolved for this finding (the rows are classed GAP, not BUG). Lowering the Reach carrier in the stochastic reader is a later task.
4. **False map-call cycle when a Map has the same name as an Enum element** (doc04 ClaimArbitration: 3 requests, both modes). `sym_atoms` (admit.c:776) records every symbol that names a Map as a call. This check runs before the library gate. **Fixed** (t-2026-11-20-mettadinc-map-name-cycle): the map-call graph (`map_section_calls`/`map_calls` in admit.c, replacing `sym_atoms` there) now counts a Map name as a call only at an application head (spec 5.4 "typed map application"), or as a bare symbol that is not an Enum element of the module; rows of Cases, Table and Choice bodies are data rows, not applications. The 3 ClaimArbitration requests now reach the library gate: Unsupported, GATED (PROPOSED library Families) in both modes. Gates: tests/dcalc/review_fixes (repros vs _control, real f <-> g cycle still rejected).
5. **Seven library-free doc04 requests are not lowered.** AnchorMigration (memory_goals.metta:341, Subset carriers) and TaskResume (:390, Reach carrier) use no library. All 7 of their requests answer "outside the M0/M2 fragment". The M0 lowering now lowers Subset carriers (filter by an admitted predicate, spec l.1718 and s5.3 l.1774) and Reach carriers (forward closure, l.1810), so the carriers are no longer the reason. What still blocks these rows: AnchorMigration (rows 43-44) uses (a) Bool live-old/live-new Observe ports, (b) maps declared (From (Tuple Symbol Symbol)), (c) If/Eq/And/Or/Not in Cases. TaskResume (rows 45-49) uses (a), (c), (d) Resume (Like Restart), and type-form To on checkpoint maps. Each blocker alone gives "outside the M0 fragment" (repro/m0_blocker_a..d, each with a Checked control). (Derive X (MinimizeForQueries M)) alone is not a blocker (repro/m0_blocker_e_minimize.metta: Checked). doc04 s6.4 says AnchorMigration "uses only forms of the base registry".
   *Update (t-2026-11-23-mettadinc-m0-bool-observe):* (a) is lowered: a (To Bool) map from a declared carrier, named by an Observe port of a Crisp machine, is the query into Bool = {False, True} under literal equality (spec Def 3.1/3.2; Core builtin type Bool). No answer of rows 43-49 changes, because each still hits another blocker first. AnchorMigration (43-44): every map, including the Bool Observe maps live-old/live-new, is declared (From (Tuple Symbol Symbol)) (b); the Subset predicates and repairs use Or/And/Eq/Not/If (c); lesion is a Body map (f). TaskResume (45-49): its Bool Observe maps needs-revalidation and available now start at the named carrier Task, so (a) and (b) no longer stop them, but their bodies use Eq/And/Not (c), as do derive/withdraw/revalidate; Resume is (Like Restart) (d); the checkpoint maps declare a type form in To (b), and checkpoint-with-reads is a Body map (f). With (b), (c), (d) and (f) removed by hand (tests/dcalc/m0_bool_observe/desugar_doc04.py, Bool Observe maps kept), dcalc gives doc04's answer on all seven requests: NaiveMigration Refuted, CellMigration Checked, NoReadSets CheckNow Checked / CheckUpdates Refuted / CheckBehavioral Refuted, ReadSets CheckBehavioral Checked, ResumeMemory 11 classes on 12 states.
6. **Negative fixtures.** The 2 ls fixtures (live_memory.metta:102 and :354) return InvalidInput as intended. The 2 doc04 ItemGoals fixtures (memory_goals.metta:586) should return InvalidInput but come back Unsupported, because the NatArith gate hides them.
7. **CLI (fixed, t-2026-11-20-mettadinc-release-libs).** Release mode ignored LIBS (main.c:129), so the cross-file imports in ls and wx failed with "Import of unknown module". Release mode now loads LIBS. The 23 rows (ls 21-24, wx 1-19) resolve the import and are GATED by the first-release gate (PROPOSED library RationalArith), the same reason as in beyond mode.
