#!/usr/bin/env bash
# Test for the build cache in tools/dcalc-cetta-smoke.sh (hive t-2026-11-24-mettadinc-tooling-leftovers).
# Runs a copy of the script in a throwaway superproject: a tiny "cetta" repository whose Makefile counts its builds
# and writes a stub cetta binary, one upstream/cetta patch made with git format-patch, a stub src/dcalc and one
# smoke test.  Every case checks the cache decision line (HIT/MISS), the build count and the smoke result.
# Real-build timings (cold vs warm) are measured separately on the real tree; this test checks the key logic fast.
# Touches nothing in this repository.  Needs bash, git, make, gcc on PATH, python3 not needed.  Exit 0 = all pass.
set -u
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/smoke-cache-test.XXXXXX") || exit 2
trap 'rm -rf "$TMP"' EXIT
G="git -c user.name=t -c user.email=t@local -c init.defaultBranch=main -c protocol.file.allow=always"
export BUILDS_FILE="$TMP/builds"; echo 0 > "$BUILDS_FILE"
rc=0
# --- fake CeTTa: commit A (the pin), commit B (another pin), and a patch on top of A
mkdir -p "$TMP/cetta-src" && cd "$TMP/cetta-src" && $G init -q . || exit 2
printf 'all:\n\t@n=$$(cat $(BUILDS_FILE)); echo $$((n+1)) > $(BUILDS_FILE)\n\t@printf %s "#!/bin/sh" > cetta; printf "\\necho \\"(Result (Status Ok))\\"\\n" >> cetta; chmod +x cetta\n' '' > Makefile
$G add Makefile && $G commit -q -m A || exit 2
PIN_A=$($G rev-parse HEAD)
echo one > patched.txt && $G add patched.txt && $G commit -q -m "dcalc patch" || exit 2
mkdir -p "$TMP/patches" && $G format-patch -q -1 -o "$TMP/patches" HEAD || exit 2
$G reset -q --hard "$PIN_A" && echo '# B' >> Makefile && $G commit -q -am B || exit 2
PIN_B=$($G rev-parse HEAD)
# --- fake superproject
SP="$TMP/super"; mkdir -p "$SP/tools" "$SP/upstream/cetta" "$SP/src/dcalc" "$SP/tests/dcalc/cetta" && cd "$SP" && $G init -q . || exit 2
cp "$ROOT/tools/dcalc-cetta-smoke.sh" tools/ && cp "$TMP"/patches/*.patch upstream/cetta/
echo 'int x;' > src/dcalc/x.c && echo '/* h */' > src/dcalc/x.h && echo '!(x)' > tests/dcalc/cetta/s.metta && echo '(Status Ok)' > tests/dcalc/cetta/s.expected
printf 'build/\n' > .gitignore
$G clone -q "$TMP/cetta-src" cetta && $G -C cetta checkout -q --detach "$PIN_A" || exit 2
setpin(){ $G -C cetta checkout -q --detach "$1" && $G update-index --add --cacheinfo 160000,"$1",cetta && $G commit -q --allow-empty -m "pin $1"; }
$G add tools upstream src tests .gitignore && setpin "$PIN_A" || exit 2
N=0
case_(){ # name, HIT|MISS, reason substring ("" for HIT), extra env assignments...
  name=$1; want=$2; why=$3; shift 3
  before=$(cat "$BUILDS_FILE")
  env "$@" sh tools/dcalc-cetta-smoke.sh > "$TMP/$name.out" 2>&1; ex=$?
  after=$(cat "$BUILDS_FILE"); ok=1
  line=$(grep '^cetta build cache:' "$TMP/$name.out")
  case "$line" in *": $want"*) ;; *) ok=0;; esac
  [ -z "$why" ] || case "$line" in *"$why"*) ;; *) ok=0;; esac
  if [ "$want" = HIT ]; then [ "$after" = "$before" ] || ok=0; else [ "$after" = $((before+1)) ] || ok=0; fi
  [ $ex = 0 ] && grep -qx 'PASS tests/dcalc/cetta/s.metta' "$TMP/$name.out" || ok=0
  if [ $ok = 1 ]; then echo "PASS $name: builds $before->$after | $line"
  else echo "FAIL $name (exit $ex, builds $before->$after, want $want $why):"; sed 's/^/  | /' "$TMP/$name.out"; rc=1; fi
}
case_ cold          MISS "no cached build"
case_ warm          HIT  ""
grep -v '^cetta build cache' "$TMP/cold.out" > "$TMP/c"; grep -v '^cetta build cache' "$TMP/warm.out" > "$TMP/w"
cmp -s "$TMP/c" "$TMP/w" && echo "PASS warm_equals_cold: smoke results identical" || { echo "FAIL warm_equals_cold"; rc=1; }
P=$(ls upstream/cetta/*.patch); sed -i 's/^Subject: \[PATCH\] dcalc patch/Subject: [PATCH] dcalc patch (edited)/' "$P"
case_ changed_patch MISS "patch"
case_ warm2         HIT  ""
setpin "$PIN_B"
case_ changed_pin   MISS "pin"
setpin "$PIN_A"
case_ pin_back      MISS "pin"
case_ forced        MISS "forced by DCALC_CETTA_FRESH=1" DCALC_CETTA_FRESH=1
case_ cflags        MISS "cflags" CETTA_CFLAGS=-Wno-error
case_ cflags_warm   HIT  "" CETTA_CFLAGS=-Wno-error
case_ make_args     MISS "make-args" CETTA_MAKE_ARGS=
mkdir -p "$TMP/bin" && printf '#!/bin/sh\nexec %s "$@"\n' "$(command -v gcc)" > "$TMP/bin/gcc" && chmod +x "$TMP/bin/gcc"
case_ compiler      MISS "compiler" CETTA_MAKE_ARGS= PATH="$TMP/bin:$PATH"
case_ compiler_back MISS "compiler" CETTA_MAKE_ARGS=
echo 'int y;' >> src/dcalc/x.c
case_ dcalc_core    MISS "dcalc-core" CETTA_MAKE_ARGS=
(cd build/cetta-dcalc && $G reset -q --hard "$PIN_A")
case_ tree_not_pin_plus_patches MISS "not pin + 1 patches" CETTA_MAKE_ARGS=
echo '# tampered' >> build/cetta-dcalc/cetta
case_ binary_changed MISS "binary differs" CETTA_MAKE_ARGS=
case_ final_warm    HIT  "" CETTA_MAKE_ARGS=
[ $rc = 0 ] && echo "smoke cache test: PASS" || echo "smoke cache test: FAIL"
exit $rc
