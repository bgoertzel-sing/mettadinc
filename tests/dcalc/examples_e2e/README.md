# examples_e2e: Ben's worked examples through the real CLI (t-2026-11-18-mettadinc-examples-e2e)

Report-only. No product code changed; the registry is unchanged. Base: mettadinc main dd0960a. The modules are run unedited, from their bundle directories.

## Rerun

    python3 tests/dcalc/examples_e2e/run_e2e.py      # writes out/<id>_{release,beyond}.tsv
    cd tests/dcalc/examples_e2e && python3 make_tables.py   # writes doc0N_*.md

`run_e2e.py` runs each module twice: once in release mode, and once with `--beyond-release` with the imported module files passed as LIBS. `main.c` loads LIBS only in beyond mode, so in release mode the cross-file imports of ls and wx stay unresolved.

## Totals (306 requests: ex1 61, ex2 15, ex3 32, ex4 36, mg 92, ls 37, wx 33)

| mode | Checked/Refuted/Conditional | Unsupported | InvalidInput |
|---|---|---|---|
| release | 0 | 301 | 5 (mg 3, ls 2) |
| beyond  | 0 | 293 | 13 (ex4 8, mg 3, ls 2) |

The documents' expected-results tables report Checked, Refuted or Conditional for almost every request. The CLI reproduces none of these answers.

## Findings

1. **PROPOSED libraries are admitted by no milestone.** In the registry, `first_release` allows only Core, GradedKernels, BitVectors and FiniteSets. The beyond opt-in list `M4_LIBS` (admit.c) does not include NatArith, Families, Laws, RationalArith, Parallel, Monitors, Statistics or BoundedSets. Those libraries are compiled into both registries from the bundle registry patches, but the admission gate rejects them. Every module except ex4 NewsLeak uses at least one of them. The gate reports only the first failing library (admit.c:1096).
2. **Stochastic reader rejects `(Reach ...)` carriers** (ex4 NewsLeak, all 8 requests, beyond mode). stoch.c:52 requires `(Enum ...)`, but spec l.1719 allows `(Reach M (From s+))`. See `repro/stoch_reach_carrier.metta` (InvalidInput) and `repro/stoch_reach_carrier_control.metta` (the same module without the Reach carrier: Checked).
3. **False map-call cycle when a Map has the same name as an Enum element** (doc 04 ClaimArbitration, 3 requests, both modes). `sym_atoms` (admit.c:776) records every symbol that names a Map as a call. So the element `deadline` in the body of Map `deadline` is read as a self-call ("map-call cycle deadline -> deadline"). This check runs before the Families library gate. See `repro/map_name_element_clash.metta` and its `_control` (with the Map renamed, admission passes).
4. **Negative fixtures behave as intended.** The 2 ls InvalidInput answers (live_memory.metta:102 and :354) match the fixture comments. The 2 doc-04 ItemGoals fixtures (memory_goals.metta:586), which should be InvalidInput, are hidden behind the NatArith gate and come back Unsupported.

## Files
- `run_e2e.py`, `make_tables.py`: rerun scripts.
- `out/*.tsv`: per-request status and reason for each run and mode.
- `doc03_four_worked_examples.md`, `doc04_omega_memory_goals.md`, `doc05_live_memory.md`, `doc06_wmtm_worked_example.md`: one table per document. Each row gives the request, its release and beyond status, the beyond reason, and the bundle's own inline expectation where the bundle states one.
- `repro/`: minimal reproductions with controls for findings 2 and 3.
