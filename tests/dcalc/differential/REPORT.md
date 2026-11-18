# Differential test of dcalc M4-M6 operations against independent oracles

Task: t-2026-11-18-mettadinc-m4m6-differential. Base: mettadinc main dd0960a (newer than the hive base 54df33f, which is an ancestor).
Branch: hive/t-2026-11-18-mettadinc-m4m6-differential (local, not pushed). No C fixes, no registry changes.

## Summary

The task was to check the dcalc CLI (dcalc --beyond-release) against small Python oracles. The oracles are written from the
language specification, not from the C code. Seeded random generators cover chains and encodings, linear and stochastic
arrows, PositiveRealization and affine implementation contracts. About 6,000 generated checks were run across fixed seeds (table below).
Every disagreement was reduced to a minimal .metta input and traced to one of five defects, D1-D5 (disagreements/README.md).
Replaying the CLI's known behaviour explains all of them, and there are 0 unexplained cases.

Most important are D4 and D5, where the CLI gives a wrong answer with status Checked or Refuted. D4: CheckImplementation does
not clip the OneMinusAbsoluteDifference distance at 1, so valid contracts are Refuted (spec l.686-694). D5: MeasureBehavioral
compares each state only with its class representative instead of all same-code pairs, so the defect can be under-reported
(spec Def 4.4(3)). D1 is a CLI that answers Unsupported (int64 overflow with a discount). D2 and D3 are CheckLinearArrow
accept/refute bugs. Open for decision: which D-ids to fix (each fix is a separate C task), and spec gap N1. N1: when a
PositiveRealization candidate is Rejected, the spec does not say what bound to report, and the CLI keeps the LumpedQuotient bound.

## Results

| Runner (oracle) | Operations | Seeds x cases | Checks | Disagreements |
|---|---|---|---|---|
| run_diff.py (oracle.py) | TracePartition, MinimalLinear, MinimizeForQueries, MeasureBehavioral horizon | 100 x200 | 800 | 1, KNOWN-D5 |
| run_con.py (gen_con.py, clip per spec) | CheckImplementation C1, C2, ThenContracts | 100 x200 | 600 | 352, all KNOWN-D4 |
| run_lin.py (oracle.py linear_arrow) | CheckLinearArrow KC/LC, Then | 11 x200, 100 x200 | 1,200 | D2/D3 only, plus Then downstream; 0 NEW |
| run_pos.py (oracle.py positive_realization) | PositiveRealization perm/quot/rand | 1 x30, 11 x200, 100 x200 | 430 | 0 |
| run_stoch.py (oracle_stoch.py, oracle_lp.py) | bisim, trace classes, linear dim, Kantorovich horizon/discount, check trace | 2 x200 and mixture 3 x200, 6 kinds | 2,400 | 24, all D1 |
| run_linear.py (oracle_linear.py) | CheckLinearArrow obs/random/exact, Then | 6 x200 x3 | 600 | obs 0; others all D2 |

A runner was replayed with the CLI's behaviour for each D-id (classify.py for run_diff/run_con, NEW tags in run_lin).
After the replay, 0 cases are left unexplained. run_contracts.py was dropped because it copied the unclipped
|p-q| from ops_contracts.c, so it was not independent and hid D4.

## Defects (details and spec references in disagreements/README.md)

- D1 MeasureBehavioral with discount: Unsupported "rational overflow (int64)" where the oracle gives an exact value.
- D2 CheckLinearArrow: Refuted when the observation residual S_y is nonzero; Rho omits S_y.
- D3 CheckLinearArrow: a Signed arrow is accepted without the normalization L eta' = eta.
- D4 CheckImplementation: OneMinusAbsoluteDifference distance not clipped at 1 (ct_dist, spec l.686-694).
- D5 MeasureBehavioral: defect = max d(x, rep(x)), not the maximum over all same-code pairs (spec Def 4.4(3)).
- N1 (spec gap, not a defect): the bound reported for a Rejected PositiveRealization candidate is not specified.

## Reproduction and gate

From the repo root after building dcalc: `sh tests/dcalc/differential/gate.sh [path/to/dcalc]`.
It runs 3 known-answer canaries through dcalc --beyond-release (seven_state [5,5], D4, D5) and then pilots of run_diff,
run_con (both with classify.py), run_lin and run_pos at seed 7 x20. Any disagreement without a D-id fails it. Result
on dd0960a: GATE PASS. Large runs use the runners directly with --seed/--count/--out (see each file's docstring).

## Not done / open

- The gate is not yet wired into dcalc run-all. No mutation check and no graded Then coverage.
- Fixes for D1-D5 are separate C tasks, and N1 needs a spec decision.
