#!/bin/sh
# AC1/AC7 CeTTa side: make a scratch copy of the pinned CeTTa submodule,
# apply upstream/cetta/*.patch with git am, build it, and run the MeTTa
# smoke tests in tests/dcalc/cetta/.  Nothing is written to cetta/ or src/dcalc:
# the scratch tree and a copy of the dcalc core live under build/ (gitignored).
#   tools/dcalc-cetta-smoke.sh            (reuses the cached build when its key matches)
#   DCALC_CETTA_FRESH=1 tools/dcalc-cetta-smoke.sh   (force a rebuild)
#   DCALC_CETTA_PLAN=1 tools/dcalc-cetta-smoke.sh    (print the cache decision, build and run nothing)
# Build cache: the patched, built scratch tree build/cetta-dcalc is reused only when its build key
# (build/cetta-dcalc/.dcalc-buildkey, written after a successful build) equals the key of this run:
#   pin (git ls-tree HEAD cetta), name + sha256 of each upstream/cetta/*.patch in git-am order,
#   sha256 of the dcalc core sources copied in (src/dcalc/*.c *.h), the compiler (path, sha256 of
#   the program, gcc --version, -dumpfullversion, -dumpmachine), CFLAGS and the make arguments.
# A hit also re-checks that the scratch HEAD is pin + one commit per patch and that the cetta binary
# still has the sha256 recorded at build time.  Any difference, or DCALC_CETTA_FRESH=1, deletes the
# tree and rebuilds from a fresh clone, so a build from another pin or patch set is never served.
# Env: MAKE_JOBS (default 1; not part of the key, it does not change the build),
#      CETTA_CFLAGS (extra CFLAGS; default "-Wno-error=stringop-overflow
#      -Wno-error=maybe-uninitialized", which gcc 11.4 on the reference host
#      Ubuntu 22.04 needs for src/tensor.c, review 3 F1; set CETTA_CFLAGS= to drop),
#      CETTA_MAKE_ARGS (extra make overrides; default PACK_RELATIVE_RELOCS= so the
#      build links on glibc 2.35 / Ubuntu 22.04 without GLIBC_ABI_DT_RELR, review 2 F3).
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 2
G="git -c submodule.recurse=false -c core.preloadIndex=false"
S=$ROOT/build/cetta-dcalc
PIN=$($G ls-tree HEAD cetta | awk '$2=="commit"{print $3}')
[ -n "$PIN" ] || { echo "no cetta submodule pin"; exit 2; }
CF="-O3 -Wall -Werror -std=c11 -pthread ${CETTA_CFLAGS--Wno-error=stringop-overflow -Wno-error=maybe-uninitialized}"
MKARGS=${CETTA_MAKE_ARGS-PACK_RELATIVE_RELOCS=}
sha(){ sha256sum | awk '{print $1}'; }
NPATCH=0
for p in "$ROOT"/upstream/cetta/*.patch; do [ -f "$p" ] && NPATCH=$((NPATCH+1)); done
build_key(){
  echo "format 1"
  echo "pin $PIN"
  for p in "$ROOT"/upstream/cetta/*.patch; do [ -f "$p" ] && echo "patch $(basename "$p") $(sha < "$p")"; done
  echo "dcalc-core $( (cd "$ROOT/src/dcalc" && sha256sum *.c *.h) | sha)"
  CCP=$(command -v gcc || echo none)
  echo "compiler $CCP $( [ -f "$CCP" ] && sha < "$CCP")"
  echo "compiler-version $(gcc --version 2>/dev/null | head -1) / $(gcc -dumpfullversion 2>/dev/null) / $(gcc -dumpmachine 2>/dev/null)"
  echo "cflags $CF"
  echo "make-args BUILD=core DCALC_DIR=dcalc-core $MKARGS"
}
KEY=$(build_key)
KEYSUM=$(printf '%s\n' "$KEY" | sha)
KF=$S/.dcalc-buildkey
WHY=
if [ "${DCALC_CETTA_FRESH:-0}" = 1 ]; then WHY="forced by DCALC_CETTA_FRESH=1"
elif [ ! -f "$KF" ]; then WHY="no cached build"
elif [ "$(cat "$KF")" != "$KEY" ]; then
  printf '%s\n' "$KEY" > "$S/.key-now"
  WHY="key changed in: $( { grep -vxF -f "$KF" "$S/.key-now"; grep -vxF -f "$S/.key-now" "$KF"; } | awk '{print $1}' | sort -u | tr '\n' ' ')"
  rm -f "$S/.key-now"
elif [ ! -x "$S/cetta" ]; then WHY="cached binary missing"
elif [ "$(sha < "$S/cetta")" != "$(cat "$S/.dcalc-binsha" 2>/dev/null)" ]; then WHY="cached binary differs from the one built"
elif ! (cd "$S" && $G merge-base --is-ancestor "$PIN" HEAD 2>/dev/null) \
  || [ "$(cd "$S" && $G rev-list --count "$PIN"..HEAD 2>/dev/null)" != "$NPATCH" ]; then WHY="scratch tree is not pin + $NPATCH patches"
fi
if [ -z "$WHY" ]; then echo "cetta build cache: HIT key $KEYSUM (pin $PIN, $NPATCH patches)"
else echo "cetta build cache: MISS ($WHY): rebuilding, key $KEYSUM"; fi
[ "${DCALC_CETTA_PLAN:-0}" = 1 ] && exit 0
if [ -n "$WHY" ]; then
  rm -rf "$S"; mkdir -p build
  $G clone -q --no-checkout cetta "$S" || exit 2
  (cd "$S" && $G checkout -q --detach "$PIN" &&
   $G -c user.name=dcalc -c user.email=dcalc@local am -q "$ROOT"/upstream/cetta/*.patch) \
     || { echo "patch does not apply to $PIN"; exit 1; }
  # Private copy of the core so CeTTa's .o/.d files never land in src/dcalc.
  mkdir -p "$S/dcalc-core" && cp src/dcalc/*.c src/dcalc/*.h "$S/dcalc-core/"
  (cd "$S" && make -j"${MAKE_JOBS:-1}" BUILD=core DCALC_DIR=dcalc-core CFLAGS="$CF" $MKARGS) > build/cetta-dcalc-build.log 2>&1 \
    || { echo "CeTTa build failed: build/cetta-dcalc-build.log"; exit 1; }
  # The key is written last, only after a successful build: an interrupted build is never a hit.
  sha < "$S/cetta" > "$S/.dcalc-binsha"
  printf '%s\n' "$KEY" > "$KF"
fi
rc=0
for t in tests/dcalc/cetta/*.metta; do
  exp="${t%.metta}.expected"
  sed "s#@FIXTURES@#$ROOT/docs/e0/docs/01_language_specification/validation_package/fixtures#g; s#@ROOT@#$ROOT#g" "$t" > build/smoke-run.metta
  (cd "$S" && ./cetta "$ROOT/build/smoke-run.metta") > build/smoke-run.out 2>&1
  # *.expected holds either (Status S) lines (full envelopes) or bare result
  # symbols, one per !-line after the import! lines (which print true).
  if head -1 "$exp" | grep -q '^(Status'; then
    got=$(grep -o '^(Result (Status [A-Za-z]*)' build/smoke-run.out | sed 's/^(Result //' | tr '\n' ' ')
  else
    got=$(grep -v -x 'true' build/smoke-run.out | tr '\n' ' ')
  fi
  want=$(tr '\n' ' ' < "$exp")
  # M1 acceptance 4: a held declaration or request must never run its host code.
  # (a Reason that quotes the source is not a run: match a printed line only)
  if grep -qx -e 'HELD-DECLARATION-RAN' -e '"HELD-DECLARATION-RAN"' build/smoke-run.out; then echo "FAIL $t: a held host side effect ran"; rc=1; continue; fi
  if [ "$got" = "$want" ]; then echo "PASS $t"; else echo "FAIL $t: got [$got] want [$want]"; rc=1; fi
done
exit $rc
