# Exact rationals in dcalc (D1)

Task t-2026-11-24-mettadinc-d1-exact-rationals, base d0704b6fb2cf.

## The bug
`DcRat` (src/dcalc/rat.{h,c}) is int64/int64 with an `__int128` intermediate and an
overflow flag. In the stochastic paths, exact values grow past int64 on valid inputs.
Example: `MeasureBehavioral` with `(Discount (Rat 9 10))` on
tests/dcalc/differential/disagreements/D1_kant_disc_int64_overflow.metta. The request
answered Unsupported "rational overflow (int64)" when the exact answer is Checked, defect
9/10. The differential runs stored 50 such cases in stoch_runs/.

## Where the type changes
New type `DcQ` (src/dcalc/qrat.{h,c}): an exact rational with arbitrary precision.
- **Small form** (`b == NULL`): n/d in int64, d > 0, gcd 1, the same as `DcRat`.
  Arithmetic uses `__int128` intermediates. A result that does not fit int64 is
  promoted to the big form, never flagged as overflow.
- **Big form** (`b != NULL`): magnitudes are little-endian base-2^32 limb vectors
  (schoolbook add/sub/mul, Knuth Algorithm D division, Euclid gcd). The sign is kept
  in `n` (-1/+1) and `d = 1`, so sign tests written as `q.n < 0` stay correct.
- Big values live in a per-request arena (`dc_q_arena_reset` at the start of each
  stochastic request; `mark`/`release` around `dc_lp_max`). A `DcQ` is therefore a plain
  value: struct copies, static tables and memcpy are safe.
- The only failure left is the arena memory cap (default 1 GiB). It is reported as
  `*ovf = 2`, and the request answers Unsupported. It is never a wrong value. Division by
  zero sets `*ovf = 1` as before. The 24 exits in stoch.c that said "rational overflow
  (int64)" now say "exact rational limit (bignum memory cap or division by zero)", because
  int64 overflow can no longer happen there. The D1 gates reject both phrases.

Files switched to `DcQ`:
- `src/dcalc/stoch.c`, the whole file: Kantorovich transport (`st_kant`), behavioral
  distance and its discounted least fixed point (`st_behav`, horizon and discount
  variants), trace distance and classes, lumping, span/linear arrows, and certificates
  (`st_rsx` prints numerals of any length). Inputs are still parsed by `dc_sx_rat` (int64
  literals in the module text) and converted with `dc_q_from_rat`.
- `src/dcalc/lp_exact.c`: the simplex tableau is now `DcQ`. The interface stays `DcRat`
  (its only caller is `ops_hives.c` `hv_lcr_lp`, whose inputs are int64). Outputs are
  converted back with `dc_q_to_rat`, so overflow can now happen only if a *final* x/y/value
  does not fit int64, not in pivoting.

## Which bignum, and why
A small vendored one (qrat.c, about 300 lines, no dependency). GMP was considered.
GMP 6.3.0 is in the CeTTa toolchain env (conda), but it is **not** pinned on every host
that builds dcalc:
- src/dcalc/Makefile builds without CeTTa and links only `-lm`.
- The build host has only the runtime `libgmp.so.10`, with no `gmp.h`.
- tools/cetta-baseline.sh needs an `MDINC_GMP_PREFIX` workaround.

Adding GMP would be a new external dependency of the dcalc CLI, so it was not used.

Tests: tests/dcalc/qrat/test_qrat.py with qrat_driver.c checks random
add/sub/mul/div/cmp on values from small up to about 600 bits exactly against Python
`fractions`. It runs in the normal mode and in a forced-bignum mode (`dc_q_force_big`), so
the big path is exercised even on small values.

## What stays int64 (overflow still answers Unsupported)
These modules keep `DcRat` and answer Unsupported naming "rational overflow (int64)" when
it fires. They are outside D1 (not stochastic distances or fixed points). These are exactly the files
that still use `DcRat`; the four marked * also contain a "rational overflow" exit:
- `graded.c`, `ops_graded.c`: M2 graded core.
- `model.c`: module reading and the tolerance distance.
- `ops_contracts.c`*, `ops_nondet.c`*, `ops_transfers.c`*, `ops_hives.c`* (except inside
  `dc_lp_max`), `ops_kernels.c`, `ops_est.c`, `ops_approx.c`,
  `ops_refine.c`, `ops_weakest.c`, `ops_m7.c`, `ops_core.c`.
- `rat.c` itself is unchanged.

## Gates
- `tests/dcalc/differential/gate.sh`: canary `D1_kant_disc_exact` (D1 input must be
  Checked with `(BehavioralDefect (Rat 9 10))` and no "rational overflow"). The
  `stoch_random` and `stoch_mixture` pilots now pass their case dirs to known_d1.py, which
  re-runs every case and fails on any "rational overflow". The pilot `stoch_d1_stored`
  re-runs the 50 stored stoch_runs inputs and requires the oracle value exactly.
- `tests/dcalc/differential/known_d1.py` is a hard check: any DISAGREE line counts as NEW
  and fails, and any overflow output fails.
- `tests/dcalc/differential/mutate_gate.sh` mutant M8 `d1_int64_restored` puts back int64
  semantics in qrat.c (a result that does not fit int64 sets the overflow flag); it must be
  killed.
