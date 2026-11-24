#!/usr/bin/env python3
"""Hard D1 gate for run_stoch output (D1 fixed, t-2026-11-24-mettadinc-d1-exact-rationals).

The stochastic paths (Kantorovich, behavioral and trace distances, discounted fixed
points, lp_exact) now use exact arbitrary-precision rationals (src/dcalc/qrat.c), so no
overflow answer is accepted any more:
  * the log must have SUMMARY lines and no DISAGREE line at all (every one is NEW);
  * if CASEDIR is given, every case file in it is re-run through the CLI and any
    "rational overflow" in the output fails the gate;
  * --stored DIR re-runs the stored D1 inputs (stoch_runs/*/disagreements.txt) and
    requires the CLI's (status, defect) to equal the oracle value recorded there.
usage: known_d1.py LOG DCALC [CASEDIR]
       known_d1.py --stored STOCH_RUNS_DIR DCALC
exit 0 iff all checks pass."""
import ast, glob, os, re, subprocess, sys
from fractions import Fraction as F


def run(dc, case):
    p = subprocess.run([dc, '--beyond-release', case], capture_output=True, text=True, timeout=120)
    return p.stdout + p.stderr


def overflow_scan(dc, cases):
    bad = 0
    for c in cases:
        o = run(dc, c)
        if 'rational overflow' in o or 'exact rational limit' in o:
            bad += 1; print('OVERFLOW', c)
    return bad


def defect(line):
    m = re.search(r'\(BehavioralDefect (\(Rat (-?\d+) (\d+)\)|(-?\d+))\)', line)
    if not m:
        return None
    return str(F(int(m.group(2)), int(m.group(3)))) if m.group(2) else str(F(int(m.group(4))))


def stored(root, dc):
    here = os.path.dirname(os.path.abspath(__file__))
    n = bad = 0
    for dl in sorted(glob.glob(os.path.join(root, '*', 'disagreements.txt'))):
        for l in open(dl).read().splitlines():
            if not l.startswith('DISAGREE'):
                continue
            p = l.split(); kind, case = p[1], p[2]
            want = ast.literal_eval(l.split('oracle=', 1)[1].strip())
            path = case if os.path.exists(case) else os.path.join(here, case)
            out = run(dc, path)
            res = [x for x in out.splitlines() if '=> (Result' in x and 'MeasureBehavioral' in x and 'Discount' in x]
            got = None
            if res:
                st = re.search(r'\(Result \(Status (\w+)\)', res[0])
                got = [st.group(1) if st else 'NoResult', defect(res[0])]
            n += 1
            ok = kind == 'kant_disc' and got == want and 'rational overflow' not in out and 'exact rational limit' not in out
            if not ok:
                bad += 1; print('STORED-MISMATCH', case, 'cli=', got, 'oracle=', want)
            else:
                print('STORED-OK', case, want[1])
    print('known_d1 stored: CASES=%d MATCH=%d MISMATCH=%d' % (n, n - bad, bad))
    return 1 if (bad or n == 0) else 0


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--stored':
        sys.exit(stored(sys.argv[2], sys.argv[3]))
    log, dc = sys.argv[1], sys.argv[2]
    casedir = sys.argv[3] if len(sys.argv) > 3 else None
    lines = open(log).read().splitlines()
    if not any(l.startswith('SUMMARY') for l in lines):
        print('NO SUMMARY in', log); sys.exit(1)
    new = 0
    for l in lines:
        if l.startswith('DISAGREE'):
            new += 1; print('NEW', l)
    ovf = overflow_scan(dc, sorted(glob.glob(os.path.join(casedir, '*.metta')))) if casedir else 0
    print('known_d1: KNOWN-D1=0 NEW=%d OVERFLOW=%d' % (new, ovf))
    sys.exit(1 if (new or ovf) else 0)


if __name__ == '__main__':
    main()
