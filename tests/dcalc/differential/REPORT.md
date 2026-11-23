# Differential test of dcalc M4-M6 operations against independent oracles

Task: t-2026-11-18-mettadinc-m4m6-differential. Base: mettadinc main dd0960a (newer than the hive base 54df33f, which is an ancestor).
Branch: hive/t-2026-11-18-mettadinc-m4m6-differential (local, not pushed). No C fixes, no registry changes.

## Summary

The task was to check the dcalc CLI (dcalc --beyond-release) against small Python oracles. The oracles are written from the
language specification, not from the C code. Seeded random generators cover chains and encodings, linear and stochastic
arrows, PositiveRealization and affine implementation contracts. About 8,400 generated checks were run across fixed seeds (table below).
Every disagreement was reduced to a minimal .metta input and traced to one of five defects, D1-D5 (disagreements/README.md).
Replaying the CLI's known behaviour explains all of them, and there are 0 unexplained cases.

Most important are D4 and D5, where the CLI gives a wrong answer with status Checked or Refuted. D4: CheckImplementation does
not clip the OneMinusAbsoluteDifference distance at 1, so valid contracts are Refuted (spec l.686-694; fixed on branch hive/t-2026-11-19-mettadinc-d4-contract-clip, see the D4 list entry). D5: MeasureBehavioral
compares each state only with its class representative instead of all same-code pairs, so the defect can be under-reported
(spec Def 4.4(3)). D1 is a CLI that answers Unsupported (int64 overflow with a discount). D2 and D3 are CheckLinearArrow
accept/refute bugs. Open for decision: which D-ids to fix (each fix is a separate C task), and spec gap N1. N1: when a
PositiveRealization candidate is Rejected, the spec does not say what bound to report, and the CLI keeps the LumpedQuotient bound.
This rule is provisional, pending Ben (docs/e0/OPEN_QUESTIONS.md item 13).

## Results

| Runner (oracle) | Operations | Seeds x cases | Checks | Disagreements |
|---|---|---|---|---|
| run_diff.py (oracle.py) | TracePartition, MinimalLinear, MinimizeForQueries, MeasureBehavioral horizon | 100 x200 | 800 | 1, KNOWN-D5 (after the D5 fix: 0) |
| run_con.py (gen_con.py, clip per spec) | CheckImplementation C1, C2, ThenContracts | 100 x200 | 600 | 352, all KNOWN-D4 before the D4 fix; 0 after it (seed 100 x200, C1/C2/C12 200/200 each) |
| run_lin.py (oracle.py linear_arrow) | CheckLinearArrow KC/LC, Then | 11 x200, 100 x200 | 1,200 | D2/D3 only, plus Then downstream; 0 NEW |
| run_pos.py (oracle.py positive_realization) | PositiveRealization perm/quot/rand | 1 x30, 11 x200, 100 x200 | 430 | 0 |
| run_stoch.py (oracle_stoch.py, oracle_lp.py) | bisim, trace classes, linear dim, Kantorovich horizon/discount, check trace | random seeds 2, 1 and mixture seeds 3, 1; x200 each, 6 kinds | 4,800 | 50, all D1 (24 = random s2 6 + mixture s3 18); inputs in stoch_runs/ |
| run_linear.py (oracle_linear.py) | CheckLinearArrow obs/random/exact, Then | 6 x200 x3 | 600 | obs 0; others all D2 |

A runner was replayed with the CLI's behaviour for each D-id (classify.py for run_diff/run_con, NEW tags in run_lin).
After the replay, 0 cases are left unexplained. run_contracts.py was dropped because it copied the unclipped
|p-q| from ops_contracts.c, so it was not independent and hid D4.

## Defects (details and spec references in disagreements/README.md)

- D1 MeasureBehavioral with discount: Unsupported "rational overflow (int64)" where the oracle gives an exact value.
- D2 CheckLinearArrow: Refuted when the observation residual S_y is nonzero; Rho omits S_y. **Fixed** in t-2026-11-19-mettadinc-d2-linear-obs-residual: graded into rho, KNOWN-D2 tag removed, both minimal inputs are gate.sh canaries with the spec answer.
- D3 CheckLinearArrow: a Signed arrow is accepted without the normalization L eta' = eta.
- D4 CheckImplementation: OneMinusAbsoluteDifference distance not clipped at 1 (ct_dist in ops_contracts.c and the shared dc_tol_dist in model.c:562; a fix must cover both; spec l.686-694). FIXED: ct_dist and dc_tol_dist now return min(1, |p - p'|); the KNOWN-D4 tag was removed from classify.py. FIXED by t-2026-11-19-mettadinc-d4-contract-clip (both sites clipped; contracts family 600/600 agree).
- D5 MeasureBehavioral: defect = max d(x, rep(x)), not the maximum over all same-code pairs (spec Def 4.4(3)). FIXED in t-2026-11-19-mettadinc-d5-behavioral-classpairs.
- N1 (spec gap, not a defect): the bound reported for a Rejected PositiveRealization candidate is not specified.
  The current rule (keep the LumpedQuotient bound) is provisional, pending Ben (docs/e0/OPEN_QUESTIONS.md item 13).

## Reproduction and gate

From the repo root after building dcalc: `sh tests/dcalc/differential/gate.sh [path/to/dcalc]` (about 10 s).
It runs 5 known-answer canaries through dcalc --beyond-release (seven_state [5,5], three D4, D5). The D4 canaries assert the spec answer:
d_con_clip and D4_contract_distance_unclipped give Checked, Grade 0 1 (ct_dist site), and D4_tol_dist_unclipped gives kernel degree 0 (dc_tol_dist site); the D5 canary
is a normal gate (D5 fixed, t-2026-11-19-mettadinc-d5-behavioral-classpairs): both requests must give
BehavioralDefect 1 with Pair a c, and the old 1/2 must not appear. Then it runs pilots at seed 7: run_diff and run_con x20 (each with classify.py), run_lin x200 (raised from
20 after review 1), run_pos x20, run_stoch random and mixture x20 (each disagreement re-run and checked to be D1 by
known_d1.py), and run_linear obs x50. Any disagreement without a D-id fails it. Result on dd0960a: GATE PASS.
The gate is wired into tools/dcalc-run-all.sh as step `differential` (skip with DCALC_SKIP_DIFFERENTIAL=1).
(Historical, before the D2 fix:) KNOWN-D2 in run_lin also required the CLI's stated reason "observation report differs"; reruns at seeds
7, 11, 100 x200 still give 0 NEW.

## Mutation check

`sh tests/dcalc/differential/mutate_gate.sh` builds mutants from a copy of src/dcalc into build/dt_mut/ (src/ is
not modified) and runs gate.sh on each. It passes only if the gate fails on every mutant. Mutants: lin_rho_lastrow
(CheckLinearArrow rho keeps only the last row's residual; this one escaped the old 20-case lin pilot) and
kant_half (behavioral layer distance halved). Result: both killed, MUTATION CHECK PASS (46 s).

## Graded composition (stop-line)

Then over Graded arrows is not differentially tested. By operator decision recorded in the m6-graded gates
(tests/dcalc/m6graded/run_m6graded_gates.py), Then over graded arrows answers InvalidInput, so there is no
composed grade to compare with an oracle. Then over linear arrows (run_lin, run_linear) and ThenContracts
(run_con) are covered.

## Not done / open

- Fixes for D1-D5 are separate C tasks, and N1 needs a spec decision (provisional, pending Ben: OPEN_QUESTIONS.md item 13).
- The PositiveRealization oracle adopts the CLI's rule for a Rejected candidate (N1), so the rand-mode agreements
  are weaker evidence on that point.
