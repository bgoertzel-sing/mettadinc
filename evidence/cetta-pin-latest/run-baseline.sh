#!/usr/bin/env bash
# Driver for t-2026-11-06-mettadinc-cetta-pin-latest baseline runs (copied to evidence/cetta-pin-latest/).
# usage: run-baseline.sh <run-name> [MDINC_MAKE_ARGS]
set -u
cd "$(dirname "$0")/.."
REPO=$PWD; E=$REPO/evidence/cetta-pin-latest/cetta-baseline; B=$REPO/build/cetta-baseline
run=$1; export MDINC_MAKE_ARGS=${2:-}
export MDINC_GMP_PREFIX=$HOME/scratch/mettadinc-e0/deps/root/usr
git -C cetta clean -xfdq     # build outputs only (upstream-ignored); tracked files untouched
rm -rf "$B/$run"; mkdir -p "$B/$run"
MDINC_BASELINE_LOGDIR=$B/$run tools/cetta-baseline.sh > "$B/$run.harness.out" 2>&1; ex=$?
echo "HARNESS_EXIT=$ex" >> "$B/$run.harness.out"
mkdir -p "$E/$run"; cp "$B/$run"/*.log "$B/$run/summary.txt" "$E/$run/"; cp "$B/$run.harness.out" "$E/$run/harness.out"
echo "$run: HARNESS_EXIT=$ex" > "$B/$run.done"
