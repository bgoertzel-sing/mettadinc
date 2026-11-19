#!/usr/bin/env python3
"""t-2026-11-18-mettadinc-examples-e2e: run every request of Ben's worked examples (docs/e0/docs 03-06) through the
real CLI, unedited, in release mode and with --beyond-release, and write one per-request table per document.

usage: python3 tests/dcalc/examples_e2e/run_e2e.py [--dcalc build/dcalc/dcalc] [--out tests/dcalc/examples_e2e/out]
Modules are run from their bundle directory exactly as published. Imported module files are passed as LIBS
arguments (dcalc MODULE [LIBS...]); main.c loads LIBS only with --beyond-release.
Document answers are in doc_expected.tsv (hand-transcribed; used by make_tables.py)."""
import argparse, collections, csv, os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
E = os.path.join(ROOT, 'docs/e0/docs')
W = '03_four_worked_examples/validation_bundles/'
RUNS = [  # (id, document, bundle dir, module, libs)
    ('ex1', '03', W + 'ex1_belief_memory', 'belief_memory.metta', []),
    ('ex2', '03', W + 'ex2_access_policy', 'access_policy.metta', []),
    ('ex3', '03', W + 'ex3_skill_share', 'skill_share.metta', []),
    ('ex4', '03', W + 'ex4_market_maker', 'market_maker.metta', []),
    ('mg', '04', '04_omega_memory_goals_part1/validation_bundle', 'memory_goals.metta', []),
    ('ls', '05', '05_live_memory_part2/validation_bundle', 'live_memory.metta', ['memory_goals.metta']),
    ('wx', '06', '06_wmtm_worked_example/validation_bundle', 'wmtm_example.metta', ['live_memory.metta', 'memory_goals.metta']),
]
LINE = re.compile(r'^(\S+) (.*?) => \(Result \(Status (\w+)\)')
REASON = re.compile(r'\(Reason "((?:[^"\\]|\\.)*)"\)')

def run(dc, d, mod, libs, beyond):
    cmd = [dc] + (['--beyond-release'] if beyond else []) + [mod] + (libs if beyond else [])
    p = subprocess.run(cmd, cwd=os.path.join(E, d), capture_output=True, text=True, timeout=900)
    rows = []
    for l in p.stdout.splitlines():
        m = LINE.match(l)
        if m:
            r = REASON.search(l)
            rows.append((m.group(1), m.group(2), m.group(3), r.group(1) if r else ''))
    return cmd, p.returncode, rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dcalc', default=os.path.join(ROOT, 'build/dcalc/dcalc'))
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    dc = os.path.abspath(a.dcalc)
    for rid, doc, d, mod, libs in RUNS:
        for beyond in (0, 1):
            cmd, rc, rows = run(dc, d, mod, libs, beyond)
            tag = '%s_%s' % (rid, 'beyond' if beyond else 'release')
            with open(os.path.join(a.out, tag + '.tsv'), 'w', newline='') as fh:
                w = csv.writer(fh, delimiter='\t'); w.writerow(['module', 'request', 'status', 'reason'])
                w.writerows(rows)
            c = collections.Counter(r[2] for r in rows)
            print('%-12s rc=%d requests=%d %s' % (tag, rc, len(rows), dict(sorted(c.items()))))
            if not rows: print('NO RESULTS for', tag, cmd); sys.exit(1)

if __name__ == '__main__':
    main()
