#!/bin/sh
# Differential gate (t-2026-11-18-mettadinc-m4m6-differential), per docs/EXPERIMENT_SANITY_GATE.md.
# 1. Known-answer canaries through the production path (dcalc --beyond-release).
# 2. Small pilots of every runner; any disagreement must match a listed D-id (see disagreements/README.md).
# usage: tests/dcalc/differential/gate.sh [DCALC]   (run from the repo root)
set -u
DC=${1:-build/dcalc/dcalc}
H=tests/dcalc/differential
FIX=docs/e0/docs/01_language_specification/validation_package/fixtures
fail=0
canary() { # name file expected-regex
  if timeout 60 "$DC" --beyond-release "$2" 2>&1 | grep -qE "$3"; then echo "CANARY ok   $1"; else echo "CANARY FAIL $1"; fail=1; fi
}
canary seven_state_positive   $FIX/seven_state.metta            'PositiveDimension \(Interval 5 5\)'
# D4 fixed (t-2026-11-19-mettadinc-d4-contract-clip): spec l.686-694 clips the distance at 1, so both minimal
# inputs are Checked with Grade 0 1. These are normal gates now, no longer EXPECTED-BUG canaries.
canary D4_con_clip           $H/disagreements/d_con_clip.metta 'Status Checked.*Value \(Grade \(Rat 0 1\) \(Rat 1 1\)'
canary D4_con_clip_two_point $H/disagreements/D4_contract_distance_unclipped.metta 'Status Checked.*Value \(Grade \(Rat 0 1\) \(Rat 1 1\)'
# review-1 F2: dc_tol_dist (model.c) site. Observations 0 and 2 are distance min(1,2) = 1, kernel degree 0 (unclipped: -1).
canary D4_tol_dist           $H/disagreements/D4_tol_dist_unclipped.metta 'Status Checked.*\(Entry P Q 0\) \(Entry Q P 0\)'
# D5 fixed (t-2026-11-19-mettadinc-d5-behavioral-classpairs): spec Def 4.4(3) / l.1080 gives defect 1 = d_beh(a, c)
# on BOTH requests (horizon 1 and unbounded); the witness pair is (a, c). The old answer 1/2 must not appear.
o=$(timeout 60 "$DC" --beyond-release $H/disagreements/d_kant_classpairs.metta 2>&1)
if [ "$(printf '%s\n' "$o" | grep -cE 'Status Checked.*Value \(BehavioralDefect 1\).*Pair a c')" = 2 ] && ! printf '%s\n' "$o" | grep -qE 'BehavioralDefect \(Rat'; then
  echo "CANARY ok   D5_kant_classpairs"; else echo "CANARY FAIL D5_kant_classpairs"; fail=1; fi
# t-2026-11-19 D2 fixed: regression gates with the spec answer (Def 3.8: S_y = Pi_y L - L Pi'_y is graded into rho).
canary D2_obs_residual        $H/disagreements/D2_obs_residual_refuted.metta 'Status Checked.*LinearArrow Positive \(Valid True\) \(Grade \(Lambda 1\) \(Rho \(Rat 1 2\)\)\)'
canary D2_linear_arrow_obs    $H/disagreements/D2_linear_arrow_obs_refuted.metta 'Status Checked.*LinearArrow Positive \(Valid True\) \(Grade \(Lambda 1\) \(Rho 1\)\)'
# D6 (t-2026-11-20-mettadinc-d6-trace-check): EXPECTED-BUG canary. It asserts today's wrong horizon trace
# defect 1/2 (the spec gives 1, pair a c). When D6 is fixed this fails on purpose: flip the regex to 'TraceDefect 1\)'.
canary D6_trace_classpairs    $H/disagreements/D6_trace_classpairs.metta 'TraceDefect \(Rat 1 2\)'
[ $fail = 0 ] || { echo "GATE FAIL (canary)"; exit 1; }
echo "GATE canaries passed"
# 2. Pilots (small, fixed seeds). Every disagreement must be a listed D-id, else the gate fails.
OUT=${GATE_OUT:-build/differential_gate}
mkdir -p "$OUT"
pilot() { # label command...
  l=$1; shift
  if "$@" > "$OUT/$l.log" 2>&1; then echo "PILOT ok   $l"; else echo "PILOT FAIL $l (see $OUT/$l.log)"; fail=1; fi
}
python3 $H/run_diff.py --seed 7 --count 20 --out "$OUT/diff" --dcalc "$DC" > "$OUT/diff.run.log" 2>&1
pilot diff_classify python3 $H/classify.py --runner diff --seed 7 --count 20 --out "$OUT/diff"
python3 $H/run_con.py --seed 7 --count 20 --out "$OUT/con" --dcalc "$DC" > "$OUT/con.run.log" 2>&1
pilot con_classify  python3 $H/classify.py --runner con --seed 7 --count 20 --out "$OUT/con"
pilot lin           python3 $H/run_lin.py --seed 7 --count 200 --out "$OUT/lin" --dcalc "$DC"   # review 1 F1: 20 cases missed a rho mutant
pilot pos           python3 $H/run_pos.py --seed 7 --count 20 --out "$OUT/pos" --dcalc "$DC"
# review 1 F6: stochastic (D1 path, check trace, mixture family) and run_linear obs family are gated too
python3 $H/run_stoch.py --seed 7 --count 20 --family random  --cli "$DC" --out "$OUT/stoch_r" > "$OUT/stoch_r.run.log" 2>&1
pilot stoch_random  python3 $H/known_d1.py "$OUT/stoch_r.run.log" "$DC"
python3 $H/run_stoch.py --seed 7 --count 20 --family mixture --cli "$DC" --out "$OUT/stoch_m" > "$OUT/stoch_m.run.log" 2>&1
pilot stoch_mixture python3 $H/known_d1.py "$OUT/stoch_m.run.log" "$DC"
pilot linear_obs    python3 $H/run_linear.py --seed 7 --count 50 --family obs --cli "$DC" --out "$OUT/linear_obs"
[ $fail = 0 ] || { echo "GATE FAIL (pilot)"; exit 1; }
echo "GATE PASS"
