#!/usr/bin/env bash
# Registry and oracle checks for t-2026-11-06-mettadinc-cetta-pin-latest, unchanged from
# evidence/m0-prep-submodule/rerun-submodule.sh (the same commands; they do not use Cetta).
set -u
cd "$(dirname "$0")/../.."   # repo root
REPO=$PWD; E=$REPO/evidence/cetta-pin-latest
mkdir -p "$E/registry" "$E/oracles"
rec(){ local f=$1; shift; { echo "\$ $*"; ( eval "$*" ) 2>&1; echo "exit $?"; } > "$f"; echo "$(basename "$f"): $(tail -1 "$f")"; }
echo "HEAD $(git rev-parse HEAD)"
rec "$E/registry/03_adopt_check.out" "python3 tools/adopt_registry.py --supersede requests.Detect=wx --check"
rec "$E/registry/04_check_fixtures.out" "cd validation && python3 check_fixtures.py"
rec "$E/registry/05_check_bundles_detect.out" "python3 tools/check_bundles.py --request Detect"
rec "$E/registry/05b_check_bundles.out" "python3 tools/check_bundles.py"
rec "$E/registry/digest.out" "cat registry/DIGEST; sha256sum registry/mettadinc_registry.json"
MDINC_PYTHON=$HOME/scratch/mettadinc-e0/venv/bin/python MDINC_TOOLS=$HOME/scratch/mettadinc-e0/tools MDINC_ORACLE_DIR=$REPO/build/oracles-latest tools/run-oracles.sh > "$E/oracles/run-oracles.summary.out" 2>&1; ox=$?
echo "ORACLES_EXIT=$ox" >> "$E/oracles/run-oracles.summary.out"; cp build/oracles-latest/*.out "$E/oracles/"
echo "ORACLES_EXIT=$ox"
