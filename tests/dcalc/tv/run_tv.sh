#!/bin/sh
# M3 translation-validation suite (t-2026-11-11-mettadinc-m3-tv-suite), run by tools/dcalc-run-all.sh.
# 1. build/dcalc/tv_m3 (built by `make tests`) dumps the production CNF of every obligation kind
#    on tests/dcalc/tv/tv_small.metta (five-bit copy of forty_bits.metta plus SAT cases);
# 2. tv_m3.py checks each CNF against the independent semantics over all assignments;
# 3. tv_mut.py: dropped clause / flipped literal / wrong variable map / vacuous UNSAT mutants
#    whose LRAT proofs cake_lpr verifies must each be rejected (needs DCALC_CADICAL, DCALC_CAKE_LPR).
set -e
M=tests/dcalc/tv/tv_small.metta; D=build/dcalc/tv; W=build/dcalc/tv-mut
rm -rf "$D" "$W"; mkdir -p "$D"
build/dcalc/tv_m3 "$M" "$D" partition:ZeroTailOnly:ZeroMachine partition:ZeroTailReach:ZeroReach \
  partition:Gappy:ZeroMachine partition:ByX0:ZeroMachine minimize:ZeroMachine minimize:ParityMachine \
  minimize:ZeroMachine:1 minimize:ParityMachine:2 now:KeepX0 now:KeepX1 > build/tv_dump.out
python3 tests/dcalc/tv_m3.py check "$M" "$D" > build/tv_check.out || { grep FAIL build/tv_check.out; echo "tv_check: FAIL"; exit 1; }
n=$(grep -c ' PASS ' build/tv_check.out); s=$(grep -c '(SAT)' build/tv_check.out); u=$(grep -c '(UNSAT)' build/tv_check.out)
for k in partition minimize now; do
  grep -q "^$k-.*(SAT)" build/tv_check.out && grep -q "^$k-.*(UNSAT)" build/tv_check.out || { echo "tv_check: kind $k lacks a SAT or an UNSAT case"; exit 1; }
done
echo "tv_check: PASS ($n CNFs: $s SAT, $u UNSAT; every kind has both)"
python3 tests/dcalc/tv_mut.py "$M" "$D" "$W" > build/tv_mut.out || { cat build/tv_mut.out; exit 1; }
tail -1 build/tv_mut.out
