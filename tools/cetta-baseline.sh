#!/usr/bin/env bash
# Cetta baseline harness: is Cetta, the submodule checkout under cetta/ (pinned in docs/CETTA-PIN.md), still "green" in the sense of Ben's decision 2
# (README "Decisions", item 2): no regression against E0's frozen baseline at Cetta 12da03b4?
#
# Builds the submodule checkout cetta/ (BUILD=core, then BUILD=python) in place and runs E0's three gates exactly as E0 ran them
# (docs/e0/CETTA.md, steps 07, 08 and 10):
#   rhocalc  make BUILD=core test-rhocalc                                  expected: 253 passed, 0 failed, exit 0
#   core     make -k BUILD=core   test-correctness test-profiles           expected: 502 PASS / 6 SKIP / 1 FAIL (py-call)
#   python   make -k BUILD=python test-correctness test-profiles           expected: 503 PASS / 6 SKIP / 0 FAIL
# and compares each log with tools/cetta-baseline.expected (derived from E0's logs, never from a new run) using
# tools/cetta_baseline_check.py.  Exit status: 0 green; 1 regression (a missing PASS, a new SKIP or FAIL line, a
# new failed make target, or a changed rhocalc summary); 2 build or setup failure.
#
# Mettapedia-dependent targets are excluded: METTAPEDIA_ROOT points at a path that must not exist, so the
# Mettapedia-dependent checks take their SKIP branch (the six known skips) and test-he-compat-catalog-guards fails
# at setup as in E0's run; that failure is an expected failed target in both lanes.  Note the consequence of
# running E0's command unchanged: under make -k the recipes of targets that depend on catalog-guards (the
# test-he-contract-suite and the aggregate "test" recipe that loops over tests/test_*.metta) do not run, in E0's
# baseline or here.  Widening the gate is a change to decision 2's baseline, not something this script does.
#
# Environment (all optional):
#   MDINC_GMP_PREFIX  a prefix holding GMP headers and libgmp.so when the system has no libgmp-dev, laid out as
#                     an extracted Debian/Ubuntu package (<prefix>/include, <prefix>/include/x86_64-linux-gnu,
#                     <prefix>/lib/x86_64-linux-gnu).  Without sudo:
#                       apt-get download libgmp-dev && dpkg -x libgmp-dev_*.deb root
#                       ln -sf /usr/lib/x86_64-linux-gnu/libgmp.so.10 root/usr/lib/x86_64-linux-gnu/libgmp.so
#                       export MDINC_GMP_PREFIX=$PWD/root/usr
#                     With sudo, "apt-get install libgmp-dev" makes this unnecessary.
#   MDINC_JOBS        parallel build jobs (default 8); tests always run serially, as in E0's baseline
#   MDINC_MAKE_ARGS   extra make command-line arguments, word-split and passed to every make below (recorded in
#                     summary.txt).  Example: on Ubuntu 22.04 (binutils 2.38, glibc 2.35) Cetta 4c285a97's Makefile adds
#                     -Wl,-z,pack-relative-relocs because the linker accepts it, and the binaries then need
#                     GLIBC_ABI_DT_RELR, which glibc 2.35 lacks; MDINC_MAKE_ARGS="PACK_RELATIVE_RELOCS=" turns that off
#                     from the command line without changing Cetta's files.  It is not enough on its own for 4c285a97:
#                     see docs/CETTA-LATEST.md.
#   MDINC_BASELINE_LOGDIR  where logs go (default build/cetta-baseline/<UTC timestamp>, ignored by git)
#
# System packages used: bash, GNU make, gcc, python3 (with python3-config --embed for the python lane),
# libgmp (runtime) and its headers, coreutils, git (only to report the submodule's commit and whether
# its checkout is clean).  The submodule must be checked out first: git submodule update --init.
set -u
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CETTA="$REPO/cetta"
EXPECTED="$REPO/tools/cetta-baseline.expected"
CHECK="$REPO/tools/cetta_baseline_check.py"
JOBS=${MDINC_JOBS:-8}
read -r -a MK <<< "${MDINC_MAKE_ARGS:-}"
LOG=${MDINC_BASELINE_LOGDIR:-$REPO/build/cetta-baseline/$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$LOG"
SUMMARY="$LOG/summary.txt"
: > "$SUMMARY"
say(){ echo "$*" | tee -a "$SUMMARY"; }
die(){ say "SETUP/BUILD FAILURE: $*"; say "RESULT: NOT GREEN (exit 2)"; exit 2; }

[ -f "$CETTA/Makefile" ] || die "no cetta/Makefile under $REPO (the submodule is not checked out: git submodule update --init)"
[ -f "$EXPECTED" ] || die "missing $EXPECTED"

if [ -n "${MDINC_GMP_PREFIX:-}" ]; then
  P=$MDINC_GMP_PREFIX
  [ -f "$P/include/gmp.h" ] || [ -f "$P/include/x86_64-linux-gnu/gmp.h" ] || die "MDINC_GMP_PREFIX=$P has no gmp.h"
  export CPATH="$P/include:$P/include/x86_64-linux-gnu${CPATH:+:$CPATH}"
  export LIBRARY_PATH="$P/lib/x86_64-linux-gnu:$P/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
fi
export METTAPEDIA_ROOT="$REPO/build/no-mettapedia-here"
[ -e "$METTAPEDIA_ROOT" ] && die "$METTAPEDIA_ROOT exists; the frozen baseline is defined without Mettapedia"
unset RHOLANG_CLI

say "cetta-baseline: repo $REPO"
say "cetta-baseline: repo commit $(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
say "cetta-baseline: pin $(sed -n 's/^- Commit: //p' "$REPO/docs/CETTA-PIN.md" 2>/dev/null | head -1)"
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  say "cetta-baseline: gitlink HEAD:cetta $(git -C "$REPO" ls-tree HEAD cetta | awk '{print $3}')"
  say "cetta-baseline: submodule checkout cetta/ at $(git -C "$CETTA" rev-parse HEAD 2>/dev/null || echo unknown)"
  if git -C "$CETTA" diff --quiet HEAD 2>/dev/null; then say "cetta-baseline: submodule checkout has no changes to tracked files"
  else say "cetta-baseline: NOTE: submodule checkout has uncommitted changes:"; git -C "$CETTA" diff --stat HEAD | tee -a "$SUMMARY"; fi
fi
say "cetta-baseline: gcc $(gcc -dumpfullversion 2>/dev/null), $(make --version | head -1), $(python3 --version 2>&1)"
say "cetta-baseline: logs in $LOG"
say "cetta-baseline: extra make arguments (MDINC_MAKE_ARGS): ${MDINC_MAKE_ARGS:-none}"

run(){ # run <name> <cmd...>: log the command, its output and EXIT=<status>
  local n=$1; shift
  local s; s=$(date +%s)
  { echo "== $* =="; (cd "$CETTA" && "$@"); echo "EXIT=$? SECS=$(( $(date +%s) - s ))"; } > "$LOG/$n.log" 2>&1
  local e; e=$(sed -n 's/^EXIT=\([0-9]*\).*/\1/p' "$LOG/$n.log" | tail -1)
  say "$n: exit $e ($(( $(date +%s) - s )) s)"
  return "$e"
}

run 01_doctor_gmp make "${MK[@]}" BUILD=core doctor-gmp || die "GMP probe failed (see $LOG/01_doctor_gmp.log; set MDINC_GMP_PREFIX)"
run 02_build_core make "${MK[@]}" -j"$JOBS" BUILD=core || die "core build failed (see $LOG/02_build_core.log)"
run 03_version_core ./cetta --version; grep -q '(core)' "$LOG/03_version_core.log" || die "./cetta is not the core build"
run 04_test_rhocalc make "${MK[@]}" BUILD=core test-rhocalc
run 05_test_core_k make "${MK[@]}" -k BUILD=core test-correctness test-profiles
run 06_build_python make "${MK[@]}" -j"$JOBS" BUILD=python || die "python build failed (see $LOG/06_build_python.log)"
run 07_version_python ./cetta --version; grep -q '(python)' "$LOG/07_version_python.log" || die "./cetta is not the python build"
run 08_test_python_k make "${MK[@]}" -k BUILD=python test-correctness test-profiles

say "cetta-baseline: comparison with tools/cetta-baseline.expected"
python3 "$CHECK" compare "$EXPECTED" "$CETTA" rhocalc="$LOG/04_test_rhocalc.log" core="$LOG/05_test_core_k.log" \
  python="$LOG/08_test_python_k.log" | tee -a "$SUMMARY"
st=${PIPESTATUS[0]}
if [ "$st" -eq 0 ]; then say "RESULT: GREEN (no regression against E0's frozen baseline)"; exit 0; fi
say "RESULT: NOT GREEN (regression, exit 1)"
exit 1
