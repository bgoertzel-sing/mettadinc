#!/bin/sh
# AC1/AC7 CeTTa side: make a scratch copy of the pinned CeTTa submodule,
# apply upstream/cetta/*.patch with git am, build it, and run the MeTTa
# smoke tests in tests/dcalc/cetta/.  Nothing is written to cetta/ or src/dcalc:
# the scratch tree and a copy of the dcalc core live under build/ (gitignored).
#   tools/dcalc-cetta-smoke.sh            (reuses build/cetta-dcalc if present)
#   DCALC_CETTA_FRESH=1 tools/dcalc-cetta-smoke.sh   (recreate it)
# Env: MAKE_JOBS (default 1), CETTA_CFLAGS (extra -Wno-error flags for old gcc),
#      CETTA_MAKE_ARGS (extra make overrides; default PACK_RELATIVE_RELOCS= so the
#      build links on glibc 2.35 / Ubuntu 22.04 without GLIBC_ABI_DT_RELR, review 2 F3).
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 2
G="git -c submodule.recurse=false -c core.preloadIndex=false"
S=$ROOT/build/cetta-dcalc
PIN=$($G ls-tree HEAD cetta | awk '{print $3}')
[ -n "$PIN" ] || { echo "no cetta submodule pin"; exit 2; }
if [ "${DCALC_CETTA_FRESH:-0}" = 1 ]; then rm -rf "$S"; fi
if [ ! -d "$S/.git" ] && [ ! -f "$S/.git" ]; then
  mkdir -p build
  $G clone -q --no-checkout cetta "$S" || exit 2
  (cd "$S" && $G checkout -q --detach "$PIN" &&
   $G -c user.name=dcalc -c user.email=dcalc@local am -q "$ROOT"/upstream/cetta/*.patch) \
     || { echo "patch does not apply to $PIN"; exit 1; }
fi
# Private copy of the core so CeTTa's .o/.d files never land in src/dcalc.
rm -rf "$S/dcalc-core" && mkdir -p "$S/dcalc-core" && cp src/dcalc/*.c src/dcalc/*.h "$S/dcalc-core/"
CF="-O3 -Wall -Werror -std=c11 -pthread ${CETTA_CFLAGS:-}"
(cd "$S" && make -j"${MAKE_JOBS:-1}" BUILD=core DCALC_DIR=dcalc-core CFLAGS="$CF" ${CETTA_MAKE_ARGS-PACK_RELATIVE_RELOCS=}) > build/cetta-dcalc-build.log 2>&1 \
  || { echo "CeTTa build failed: build/cetta-dcalc-build.log"; exit 1; }
rc=0
for t in tests/dcalc/cetta/*.metta; do
  exp="${t%.metta}.expected"
  sed "s#@FIXTURES@#$ROOT/docs/e0/docs/01_language_specification/validation_package/fixtures#g; s#@ROOT@#$ROOT#g" "$t" > build/smoke-run.metta
  (cd "$S" && ./cetta "$ROOT/build/smoke-run.metta") > build/smoke-run.out 2>&1
  # *.expected holds either (Status S) lines (full envelopes) or bare result
  # symbols, one per !-line after the import! lines (which print true).
  if head -1 "$exp" | grep -q '^(Status'; then
    got=$(grep -o '(Status [A-Za-z]*)' build/smoke-run.out | tr '\n' ' ')
  else
    got=$(grep -v -x 'true' build/smoke-run.out | tr '\n' ' ')
  fi
  want=$(tr '\n' ' ' < "$exp")
  if [ "$got" = "$want" ]; then echo "PASS $t"; else echo "FAIL $t: got [$got] want [$want]"; rc=1; fi
done
exit $rc
