#!/bin/sh
# Run a dcalc binary on every tracked .metta (outside cetta/), each alone from its own directory,
# in release and --beyond-release mode.  Usage: run_all_metta.sh DCALC REPO OUTDIR
DC=$1; R=$2; O=$3
mkdir -p "$O"
cd "$R" || exit 2
git ls-files '*.metta' | grep -v '^cetta/' | while read -r f; do
  d=$(dirname "$f"); b=$(basename "$f"); k=$(echo "$f" | tr '/' '_')
  for mode in release beyond; do
    if [ $mode = beyond ]; then a=--beyond-release; else a=; fi
    (cd "$d" && timeout 300 "$DC" $a "$b" > "$O/$k.$mode.out" 2>&1; echo "exit=$?" >> "$O/$k.$mode.out")
  done
done
echo done
