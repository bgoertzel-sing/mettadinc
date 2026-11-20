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
# review 1 F6: the D4 canary below is an EXPECTED-BUG canary. It asserts today's wrong answer
# (valid contract Refuted), so it proves the gate reaches the buggy code path. When D4 is fixed, it fails on
# purpose: flip its regex to the spec answer ('Status Checked') and drop the KNOWN-D4 tag in classify.py.
canary D4_con_clip_known      $H/disagreements/d_con_clip.metta 'Status Refuted'
# D5 fixed (t-2026-11-19-mettadinc-d5-behavioral-classpairs): spec Def 4.4(3) / l.1080 gives defect 1 = d_beh(a, c)
# on BOTH requests (horizon 1 and unbounded); the witness pair is (a, c). The old answer 1/2 must not appear.
o=$(timeout 60 "$DC" --beyond-release $H/disagreements/d_kant_classpairs.metta 2>&1)
if [ "$(printf '%s\n' "$o" | grep -cE 'Status Checked.*Value \(BehavioralDefect 1\).*Pair a c')" = 2 ] && ! printf '%s\n' "$o" | grep -qE 'BehavioralDefect \(Rat'; then
  echo "CANARY ok   D5_kant_classpairs"; else echo "CANARY FAIL D5_kant_classpairs"; fail=1; fi
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
