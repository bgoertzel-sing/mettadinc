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
  minimize:ZeroMachine:1 minimize:ParityMachine:2 minimize:ZeroMachine:3 now:KeepX0 now:KeepX1 > build/tv_dump.out
python3 tests/dcalc/tv_m3.py check "$M" "$D" > build/tv_check.out || { grep FAIL build/tv_check.out; echo "tv_check: FAIL"; exit 1; }
n=$(grep -c ' PASS ' build/tv_check.out); s=$(grep -c '(SAT)' build/tv_check.out); u=$(grep -c '(UNSAT)' build/tv_check.out)
# M4 (t-2026-11-11-mettadinc-m4): SAT and UNSAT are required per obligation SUB-kind, not per kind:
#   partition-<R>-<i> (one obligation), partition-<R>-all, minimize-<M>-k<n> (bounded tests), now-<R>.
# minimize-<M> (unbounded) checks the computed fixed point, so it is UNSAT by construction: a SAT case
# there would itself be a generator bug.  It must have an UNSAT case and must never be SAT.
for sk in 'partition-[A-Za-z0-9]+-[0-9]+' 'partition-[A-Za-z0-9]+-all' 'minimize-[A-Za-z0-9]+-k[0-9]+' 'now-[A-Za-z0-9]+'; do
  grep -Eq "^$sk\.tv .*\(SAT\)" build/tv_check.out && grep -Eq "^$sk\.tv .*\(UNSAT\)" build/tv_check.out \
    || { echo "tv_check: sub-kind $sk lacks a SAT or an UNSAT case"; exit 1; }
done
grep -Eq '^minimize-[A-Za-z0-9]+\.tv .*\(UNSAT\)' build/tv_check.out || { echo "tv_check: minimize fixed point has no UNSAT case"; exit 1; }
if grep -Eq '^minimize-[A-Za-z0-9]+\.tv .*\(SAT\)' build/tv_check.out; then echo "tv_check: minimize fixed point is SAT (generator bug)"; exit 1; fi
echo "tv_check: PASS ($n CNFs: $s SAT, $u UNSAT; every sub-kind has both, the minimize fixed point is UNSAT)"
python3 tests/dcalc/tv_mut.py "$M" "$D" "$W" > build/tv_mut.out || { cat build/tv_mut.out; exit 1; }
tail -1 build/tv_mut.out
