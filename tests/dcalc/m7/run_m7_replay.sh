#!/bin/sh
# M7 (t-2026-11-14-mettadinc-m7): independent replay of every M7 manifest fixture under --beyond-release.
# Each fixture's dcalc output is re-checked by a Python replayer that does not use the C code.
# forty_bits (F07 ClockRates) is replayed by replay_m7_f07.py (k=4..12 brute force, 40-bit closed form, Binding Digest).
set -u
V=docs/e0/docs/01_language_specification/validation_package/fixtures
D=build/dcalc/dcalc
mkdir -p build/m7_replay
rc=0
run() {  # replayer fixture
  "$D" --beyond-release "$V/$2.metta" > "build/m7_replay/$2.out" 2>&1
  line=$(python3 "$1" "$V/$2.metta" "build/m7_replay/$2.out" | tail -1)
  echo "$2: $line"
  case "$line" in *"-> PASS") ;; *) rc=1 ;; esac
}
run tests/dcalc/m7/replay_m7.py availability
run tests/dcalc/m7/replay_m7.py neural_audit
run tests/dcalc/m7/replay_m7.py arithmetic_probes
run tests/dcalc/m7/replay_m7.py patterns
run tests/dcalc/m7/replay_m7_snapshot.py snapshot_receipts
run tests/dcalc/m7/replay_m7_f07.py forty_bits   # review-1 F5: F07 ClockRates, k-bit brute force + 40-bit closed form + digest
# review-1 F5: M01 cross-file positive replay (hyperseed_methods imports HyperseedMemory from receipt_packets)
"$D" --beyond-release "$V/hyperseed_methods.metta" "$V/receipt_packets.metta" > build/m7_replay/hyperseed_methods.out 2>&1
line=$(python3 tests/dcalc/m7/replay_m7_m01.py "$V/hyperseed_methods.metta" build/m7_replay/hyperseed_methods.out "$V/receipt_packets.metta" | tail -1)
echo "hyperseed_methods (M01, cross-file): $line"
case "$line" in *"-> PASS") ;; *) rc=1 ;; esac
# review-1 F7d: nested (CompleteHive (Output D Hive)) fixtures, replayed by the M6-rest replayer (Output after CompleteHive)
for f in complete_hive_nested nested_complete; do
  "$D" --beyond-release "tests/dcalc/m7/fixtures/$f.metta" > "build/m7_replay/$f.out" 2>&1
  line=$(python3 tests/dcalc/m6rest/replay_m6rest.py "tests/dcalc/m7/fixtures/$f.metta" "build/m7_replay/$f.out" | tail -1)
  echo "$f (nested Output hive): $line"
  case "$line" in *"-> PASS") ;; *) rc=1 ;; esac
done
echo "m7_replay: $([ $rc = 0 ] && echo PASS || echo FAIL)"
exit $rc
