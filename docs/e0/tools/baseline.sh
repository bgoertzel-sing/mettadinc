#!/bin/bash
source ~/scratch/mettadinc-e0/env.sh
cd ~/research-agent/projects/mettadinc/repos/cetta
L=~/scratch/mettadinc-e0/baseline
mkdir -p $L
cp ~/scratch/mettadinc-e0/build.log $L/00_make_python_default.log
run(){ n=$1; shift; echo "== $* ==" > $L/$n.log; s=$(date +%s); "$@" >> $L/$n.log 2>&1; e=$?; echo "EXIT=$e SECS=$(( $(date +%s)-s ))" >> $L/$n.log; echo "$n EXIT=$e" >> $L/summary.txt; }
: > $L/summary.txt
git rev-parse HEAD > $L/commit.txt
run 01_doctor_gmp make BUILD=core doctor-gmp
run 02_make_core make -j8 BUILD=core
run 03_version ./cetta --version
run 04_langs ./cetta --list-languages
run 05_profiles ./cetta --list-profiles
run 06_test_correctness_profiles make BUILD=core test-correctness test-profiles
run 07_test_rhocalc make BUILD=core test-rhocalc
echo DONE >> $L/summary.txt
