# run_stoch large runs: seeds and disagreeing inputs (review 1 F4)

Each directory holds the inputs that disagreed, copied from a full run, plus `disagreements.txt` with the
DISAGREE and SUMMARY lines. The 200 inputs of each run can be regenerated exactly from the seed:

    python3 tests/dcalc/differential/run_stoch.py --seed S --count 200 --family F --cli build/dcalc/dcalc --out DIR

| Directory | Family | Seed | Cases | Disagreements | Kind |
|---|---|---|---|---|---|
| random_s2  | random  | 2 | 200 | 6  | kant_disc, all D1 |
| mixture_s3 | mixture | 3 | 200 | 18 | kant_disc, all D1 |
| random_s1  | random  | 1 | 200 | 5  | kant_disc, all D1 |
| mixture_s1 | mixture | 1 | 200 | 21 | kant_disc, all D1 |

The first report's "24" is random seed 2 (6) plus mixture seed 3 (18). Seeds 1 were added after review 1.
Each of the 50 disagreements was re-run through `dcalc --beyond-release`, and every one answers Unsupported
"rational overflow (int64)" where the oracle gives an exact Checked value (D1). The other 5 kinds (bisim,
trace classes, linear dimension, Kantorovich horizon, check trace) give 0 disagreements in all four runs.

D1 fixed (t-2026-11-24-mettadinc-d1-exact-rationals): all 50 inputs now give the oracle value exactly.
`known_d1.py --stored` re-runs them in gate.sh (pilot `stoch_d1_stored`) and fails on any mismatch or overflow.
