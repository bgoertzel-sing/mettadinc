#!/bin/bash
# Runs every oracle and static checker of the MeTTaDinC package on copies (oracles rewrite their results JSON).
set -u
E=~/scratch/mettadinc-e0
PY=$E/venv/bin/python
export MDINC_TOOLS=$E/tools/mdinc_tools
R=$E/runs/oracles
rm -rf $R; mkdir -p $R
cp -r $E/raw $R/pkg
P=$R/pkg
S=$R/summary.tsv
echo -e "name\texit\tok_lines\tfail_lines\tsecs\tresults_json_identical" > $S
run(){ name=$1; dir=$2; shift 2; cd $dir; s=$(date +%s); "$@" > $R/$name.out 2>&1; e=$?; t=$(( $(date +%s)-s ));
  ok=$(grep -c -E '^\s*\[?(ok|OK|PASS|pass)' $R/$name.out); bad=$(grep -c -E '^\s*\[?(FAIL|fail|bad|BAD)' $R/$name.out);
  echo -e "$name\t$e\t$ok\t$bad\t$t\t-" >> $S; }
run spec_oracle $P/01_language_specification/validation_package/oracle $PY verify_mettadinc.py
run spec_check_fixtures $P/01_language_specification/validation_package $PY check_fixtures.py
B=$P/03_four_worked_examples/validation_bundles
export MDINC_PACKAGE=$P/01_language_specification/validation_package
run ex1_oracle $B/ex1_belief_memory $PY ex1_oracle.py
run ex2_oracle $B/ex2_access_policy $PY ex2_oracle.py
run ex3_oracle $B/ex3_skill_share $PY ex3_oracle.py
run ex4_oracle $B/ex4_market_maker $PY ex4_oracle.py
run ex1_check $B/ex1_belief_memory $PY ex_check.py ex1_registry_patch.json -- belief_memory.metta
run ex2_check $B/ex2_access_policy $PY ex_check.py ex2_registry_patch.json -- access_policy.metta
run ex3_check $B/ex3_skill_share $PY ex_check.py ex1_registry_patch.json ex3_registry_patch.json -- skill_share.metta
run ex4_check $B/ex4_market_maker $PY ex_check.py ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json -- market_maker.metta
run ex1_replay_proofs $B/ex1_belief_memory bash -c "ls; $PY replay_proofs.py --help 2>&1 | head -5"
run mg_oracle $P/04_omega_memory_goals_part1/validation_bundle $PY mg_oracle.py
run mg_check $P/04_omega_memory_goals_part1/validation_bundle $PY ex_check.py ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json mg_registry_patch.json -- memory_goals.metta
run ls_oracle $P/05_live_memory_part2/validation_bundle $PY ls_oracle.py
run ls_check $P/05_live_memory_part2/validation_bundle $PY ex_check.py ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json mg_registry_patch.json ls_registry_patch.json -- memory_goals.metta live_memory.metta
run wx_oracle $P/06_wmtm_worked_example/validation_bundle $PY wx_oracle.py
run wx_check $P/06_wmtm_worked_example/validation_bundle $PY ex_check.py ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json mg_registry_patch.json ls_registry_patch.json wx_registry_patch.json -- memory_goals.metta live_memory.metta wmtm_example.metta
cd $R; diff -rq $E/raw $P > $R/diff_vs_shipped.txt 2>&1
$PY --version > $R/python_version.txt; $PY -m pip list 2>/dev/null > $R/pip_list.txt || /opt/hive/uv pip list --python $PY > $R/pip_list.txt
echo DONE >> $S
