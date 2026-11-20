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
# review 1 F6: the D4 and D5 canaries below (and D6) are EXPECTED-BUG canaries. They assert today's wrong answers
# (D4: valid contract Refuted; D5: defect 1/2 where the spec gives 1), so they prove the gate reaches the
# buggy code paths. When D4 or D5 is fixed, this canary fails on purpose: flip its regex to the spec answer
# (D4: 'Status Checked'; D5: 'BehavioralDefect 1') and drop the matching KNOWN tag in classify.py.
canary D4_con_clip_known      $H/disagreements/d_con_clip.metta 'Status Refuted'
canary D5_kant_classpairs     $H/disagreements/d_kant_classpairs.metta 'BehavioralDefect \(Rat 1 2\)'
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
