#!/usr/bin/env bash
# Driver for t-2026-11-06-mettadinc-m0-prep-submodule reruns (not committed; build/ is ignored).
set -u
cd "$(dirname "$0")/.."
REPO=$PWD
E=$REPO/evidence/m0-prep-submodule
pkill -f 'cetta-baseline.sh' 2>/dev/null; rm -rf "$E"; mkdir -p "$E/registry" "$E/oracles" "$E/cetta-baseline"
export MDINC_GMP_PREFIX=$HOME/scratch/mettadinc-e0/deps/root/usr
rec(){ local f=$1; shift; { echo "\$ $*"; ( eval "$*" ) 2>&1; echo "exit $?"; } > "$f"; tail -2 "$f"; }
echo "HEAD $(git rev-parse HEAD)"
rec "$E/00_pin_check.out" "tools/check-vendored-cetta.sh"
rec "$E/00_submodule_status.out" "git submodule status; git ls-tree HEAD cetta; cat .gitmodules"
rec "$E/registry/03_adopt_check.out" "python3 tools/adopt_registry.py --supersede requests.Detect=wx --check"
rec "$E/registry/04_check_fixtures.out" "cd validation && python3 check_fixtures.py"
rec "$E/registry/05_check_bundles_detect.out" "python3 tools/check_bundles.py --request Detect"
rec "$E/registry/05b_check_bundles.out" "python3 tools/check_bundles.py"
rec "$E/registry/digest.out" "cat registry/DIGEST; sha256sum registry/mettadinc_registry.json"
# baseline: green, broken, reverted
B=$REPO/build/cetta-baseline
T=cetta/tests/rhocalc/translate_rho_to_mrho.expected
for run in sub-run1-green sub-run2-broken sub-run3-reverted; do
  rm -rf "$B/$run"; mkdir -p "$B/$run"
  if [ $run = sub-run2-broken ]; then
    echo "deliberately broken by the m0-prep-submodule break-a-test check" >> $T
    echo "echo \"deliberately broken by the m0-prep-submodule break-a-test check\" >> $T   (before run2, in the submodule checkout); git -C cetta checkout -- tests/rhocalc/translate_rho_to_mrho.expected   (after run2)" > "$E/cetta-baseline/BREAK.txt"
    tools/check-vendored-cetta.sh > "$E/cetta-baseline/pin_check_while_broken.out" 2>&1; echo "exit $?" >> "$E/cetta-baseline/pin_check_while_broken.out"
  fi
  MDINC_BASELINE_LOGDIR=$B/$run tools/cetta-baseline.sh > "$B/$run/../$run.harness.out" 2>&1; ex=$?
  echo "HARNESS_EXIT=$ex" >> "$B/$run/../$run.harness.out"
  mkdir -p "$E/cetta-baseline/$run"; cp "$B/$run"/*.log "$B/$run/summary.txt" "$E/cetta-baseline/$run/"; mv "$B/$run.harness.out" "$E/cetta-baseline/$run/harness.out"
  echo "$run: HARNESS_EXIT=$ex"
  if [ $run = sub-run2-broken ]; then
    git -C cetta checkout -- tests/rhocalc/translate_rho_to_mrho.expected
    rec "$E/cetta-baseline/pin_check_after_revert.out" "tools/check-vendored-cetta.sh"
  fi
done
rec "$E/00_pin_check_after_builds.out" "tools/check-vendored-cetta.sh"
# oracles
MDINC_PYTHON=$HOME/scratch/mettadinc-e0/venv/bin/python MDINC_TOOLS=$HOME/scratch/mettadinc-e0/tools MDINC_ORACLE_DIR=$REPO/build/oracles-sub tools/run-oracles.sh > "$E/oracles/run-oracles.summary.out" 2>&1; ox=$?
echo "ORACLES_EXIT=$ox" >> "$E/oracles/run-oracles.summary.out"; cp build/oracles-sub/*.out "$E/oracles/"
echo "ORACLES_EXIT=$ox"
echo DONE
