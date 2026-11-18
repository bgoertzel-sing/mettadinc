#!/usr/bin/env python3
"""Gate filter for run_stoch output (review 1 F6): every DISAGREE line must be D1, i.e. kind kant_disc,
CLI status Unsupported, and re-running that case through the CLI prints "rational overflow".
usage: known_d1.py LOG DCALC   exit 0 iff the log has SUMMARY lines and every disagreement is D1."""
import re, subprocess, sys
log, dc = sys.argv[1], sys.argv[2]
lines = open(log).read().splitlines()
if not any(l.startswith('SUMMARY') for l in lines):
    print('NO SUMMARY in', log); sys.exit(1)
new = 0; known = 0
for l in lines:
    if not l.startswith('DISAGREE'):
        continue
    p = l.split(); kind, case = p[1], p[2]
    out = subprocess.run([dc, '--beyond-release', case], capture_output=True, text=True, timeout=60)
    if kind == 'kant_disc' and "'Unsupported'" in l and 'rational overflow' in out.stdout + out.stderr:
        known += 1
    else:
        new += 1; print('NEW', l)
print('known_d1: KNOWN-D1=%d NEW=%d' % (known, new)); sys.exit(1 if new else 0)
