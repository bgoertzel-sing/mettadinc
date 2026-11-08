#!/bin/sh
# Review 2 finding 2: Refuted CheckAbstractionMap must carry a CommutationWitness
# that replays (dcalc and tests/dcalc/replay.py), and forged witnesses must be
# rejected by the independent checker.  Exit 0 iff all four checks hold.
set -u
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); cd "$ROOT" || exit 2
M=tests/dcalc/refuted_abs/refuted_abs.metta; O=build/refuted_abs; mkdir -p $O; rc=0
build/dcalc/dcalc $M > $O/good.out 2>&1
grep -q '(Status Refuted)' $O/good.out && grep -q '(Replayed True) (Ground Witness)' $O/good.out \
  && echo "PASS dcalc: Refuted with replayed CommutationWitness" || { echo "FAIL dcalc status"; rc=1; }
python3 tests/dcalc/replay.py $M $O/good.out >/dev/null 2>&1 && echo "PASS replay.py accepts the real witness" || { echo "FAIL replay.py rejects real witness"; rc=1; }
n=0
for f in 's/(State 0) (Action t) (Left 1) (Right 0)/(State 1) (Action t) (Left 9) (Right 9)/' \
         's/(State 0) (Action t) (Left 1) (Right 0)/(State 0) (Action t) (Left 0) (Right 0)/'; do
  n=$((n+1)); sed "$f" $O/good.out > $O/forged$n.out
  if python3 tests/dcalc/replay.py $M $O/forged$n.out >/dev/null 2>&1; then echo "FAIL replay.py accepted forged witness $n"; rc=1; else echo "PASS replay.py rejects forged witness $n"; fi
done
echo "refuted_abs: $([ $rc = 0 ] && echo PASS || echo FAIL)"; exit $rc
