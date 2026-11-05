#!/usr/bin/env bash
# Run the package's reference oracles (docs/e0/ORACLES.md commands) on a copy of docs/e0/docs, since the oracles
# rewrite their results JSON and ex1/ex2 write obligations/.  The oracles do not read the registry; this is the
# check that adopting the patches left the expected values alone: 157 / 305 (92+69+57+87) / 195 / 94 / 99, 0 failures.
#
# Environment: MDINC_PYTHON (default python3): a Python with numpy, scipy, z3-solver, cvc5, networkx, python-sat and
# dd as in docs/e0/ORACLES.md; MDINC_TOOLS: directory with drat-trim/drat-trim and cake_lpr/cake_lpr (pinned commits
# in DEPENDENCIES.json); MDINC_ORACLE_DIR (default build/oracles).  Exit 0 if every oracle exits 0 and its result
# file reports the expected count with no failures.
set -u
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PY=${MDINC_PYTHON:-python3}
: "${MDINC_TOOLS:?set MDINC_TOOLS (drat-trim, cake_lpr)}"
O=${MDINC_ORACLE_DIR:-$REPO/build/oracles}
rm -rf "$O"; mkdir -p "$O"; cp -r "$REPO/docs/e0/docs" "$O/pkg"
P=$O/pkg
export MDINC_TOOLS
export MDINC_PACKAGE=$P/01_language_specification/validation_package
B=$P/03_four_worked_examples/validation_bundles
st=0
run(){ local n=$1 d=$2; shift 2; local s; s=$(date +%s)
  (cd "$d" && "$PY" "$@") > "$O/$n.out" 2>&1; local e=$?
  echo "$n: exit $e ($(( $(date +%s) - s )) s)"; [ $e -eq 0 ] || st=1; }
run spec_oracle "$MDINC_PACKAGE/oracle" verify_mettadinc.py
run ex1_oracle "$B/ex1_belief_memory" ex1_oracle.py
run ex2_oracle "$B/ex2_access_policy" ex2_oracle.py
run ex3_oracle "$B/ex3_skill_share" ex3_oracle.py
run ex4_oracle "$B/ex4_market_maker" ex4_oracle.py
run mg_oracle "$P/04_omega_memory_goals_part1/validation_bundle" mg_oracle.py
run ls_oracle "$P/05_live_memory_part2/validation_bundle" ls_oracle.py
run wx_oracle "$P/06_wmtm_worked_example/validation_bundle" wx_oracle.py
for n in spec_oracle ex1_oracle ex2_oracle ex3_oracle ex4_oracle mg_oracle ls_oracle wx_oracle; do
  echo "--- $n (last lines)"; tail -n 3 "$O/$n.out"; done
# counts: the spec oracle prints one "[ok ]" line per check and "All checks passed."; the others end with
# "<n> checks passed, <m> failed" or "<n> checks, <m> failures"
"$PY" - "$O" <<'EOF' || st=1
import re, sys
O = sys.argv[1]
want = {"spec_oracle": 157, "ex1_oracle": 92, "ex2_oracle": 69, "ex3_oracle": 57, "ex4_oracle": 87,
        "mg_oracle": 195, "ls_oracle": 94, "wx_oracle": 99}
bad = 0
got = {}
for n, w in want.items():
    t = open(f"{O}/{n}.out").read()
    if n == "spec_oracle":
        ok = len(re.findall(r"^\s*\[ok \]", t, re.M)); fail = len(re.findall(r"^\s*\[(?:FAIL|fail|bad)", t, re.M))
        fine = "All checks passed." in t
    else:
        m = re.findall(r"^(\d+) checks(?: passed)?, (\d+) fail(?:ed|ures)", t, re.M)
        ok, fail = (int(m[-1][0]), int(m[-1][1])) if m else (None, None)
        fine = m != []
    got[n] = ok
    flag = fine and ok == w and fail == 0
    bad |= not flag
    print(f"{'OK ' if flag else 'BAD'} {n}: {ok} checks, {fail} failures (expected {w}, 0)")
print(f"totals: spec {got['spec_oracle']} / four examples {sum(got[k] or 0 for k in ('ex1_oracle','ex2_oracle','ex3_oracle','ex4_oracle'))} "
      f"/ mg {got['mg_oracle']} / ls {got['ls_oracle']} / wx {got['wx_oracle']} (expected 157 / 305 / 195 / 94 / 99)")
sys.exit(1 if bad else 0)
EOF
echo "run-oracles: exit $st"
exit $st
