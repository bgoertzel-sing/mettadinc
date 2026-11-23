#!/usr/bin/env bash
# Test for the drift guard in tools/cetta-baseline.sh (hive t-2026-11-24-mettadinc-tooling-leftovers).
# Builds a throwaway superproject in a temp dir: a copy of tools/cetta-baseline.sh, a stub expected file, and a
# tiny "cetta" repository with two commits, the first recorded as the gitlink (the pin).  Runs the script with
# --check-pin (guard only, nothing built) in three states:
#   1. cetta/ at the pin              -> exit 0, "drift guard OK"
#   2. cetta/ moved to the other commit -> exit 2, the message names both commits
#   3. cetta/ not initialised (empty)   -> exit 2, refuses (git -C cetta would answer for the superproject)
# Touches nothing in this repository.  Needs bash, git, python3.  Exit 0 = all cases pass.
set -u
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/drift-test.XXXXXX") || exit 2
trap 'rm -rf "$TMP"' EXIT
G="git -c user.name=t -c user.email=t@local -c init.defaultBranch=main -c protocol.file.allow=always"
rc=0
mkdir -p "$TMP/cetta-src" && cd "$TMP/cetta-src" && $G init -q . \
  && echo 'all:' > Makefile && $G add Makefile && $G commit -q -m pin \
  && echo '# moved' >> Makefile && $G commit -q -am moved || exit 2
PIN=$($G rev-parse HEAD~1); OTHER=$($G rev-parse HEAD)
SP="$TMP/super"; mkdir -p "$SP/tools" && cd "$SP" && $G init -q . || exit 2
cp "$ROOT/tools/cetta-baseline.sh" tools/ && : > tools/cetta-baseline.expected && : > tools/cetta_baseline_check.py
$G clone -q "$TMP/cetta-src" cetta && $G -C cetta checkout -q --detach "$PIN" || exit 2
$G update-index --add --cacheinfo 160000,"$PIN",cetta && $G add tools && $G commit -q -m super || exit 2
run(){ MDINC_BASELINE_LOGDIR="$TMP/log-$1" bash "$SP/tools/cetta-baseline.sh" --check-pin > "$TMP/$1.out" 2>&1; echo $?; }
check(){ # name, expected exit, grep patterns...
  n=$1; want=$2; shift 2; got=$(run "$n"); ok=1
  [ "$got" = "$want" ] || ok=0
  for p in "$@"; do grep -qF -- "$p" "$TMP/$n.out" || ok=0; done
  if [ $ok = 1 ]; then echo "PASS $n (exit $got)"; else echo "FAIL $n (exit $got, want $want):"; sed 's/^/  | /' "$TMP/$n.out"; rc=1; fi
  grep -F 'drift guard' "$TMP/$n.out" | sed 's/^/  > /'
}
check at_pin 0 "drift guard OK" "$PIN"
$G -C cetta checkout -q --detach "$OTHER"
check moved 2 "refusing" "$OTHER" "$PIN"
$G -C cetta checkout -q --detach "$PIN"
check back_at_pin 0 "drift guard OK"
rm -rf cetta && mkdir cetta && echo 'all:' > cetta/Makefile
check uninitialised 2 "not a checked-out submodule" "$PIN"
[ $rc = 0 ] && echo "drift guard test: PASS" || echo "drift guard test: FAIL"
exit $rc
