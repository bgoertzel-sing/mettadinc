#!/usr/bin/env python3
"""M5 gate 6 (t-2026-11-12-mettadinc-m5): record the verdicts of CeTTa's
scripts/rhocalc_bounded_bisimulation.py over tests/rhocalc_bisimulation.tsv.

MILESTONES.md M5: the script performs weak barbed matching with a cost-charged
depth (a successor reached at internal cost c is matched with depth - max(1, c)
left).  That depth is a work budget of the script, NOT a MeTTaDinC horizon.
Until a test suite establishes how the depth corresponds to the WeakBarbed
adapter's horizon, the verdicts are RECORDED here and never used as a
differential oracle.  Each record names the depth as (ScriptCostBudget d) and
carries (Horizon None) (Oracle False).

usage: weakbarbed_record.py CETTA_DIR CETTA_BIN OUT.tsv
"""
import os, subprocess, sys
def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr); return 2
    cdir, cbin, out = sys.argv[1:]
    tsv = os.path.join(cdir, 'tests/rhocalc_bisimulation.tsv')
    rows = []
    for line in open(tsv, encoding='utf-8'):
        if not line.strip() or line.startswith('#'): continue
        name, depth, ls, lf, rs, rf, expect = line.rstrip('\n').split('\t')
        verdict = {}
        for guess in ('yes', 'no'):   # the script only checks an expectation; ask both ways
            r = subprocess.run(['python3', 'scripts/rhocalc_bounded_bisimulation.py', cbin, depth, ls, lf, rs, rf, guess],
                               cwd=cdir, capture_output=True, text=True, timeout=300,
                               env=dict(os.environ, CETTA_BIN=cbin))
            verdict[guess] = r.returncode == 0
        v = 'bisimilar' if verdict['yes'] and not verdict['no'] else 'not-bisimilar' if verdict['no'] and not verdict['yes'] else 'error'
        rows.append((name, depth, v, expect))
    with open(out, 'w') as f:
        f.write('# name\tScriptCostBudget\tscript_verdict\ttsv_expect\tHorizon\tOracle\n')
        for name, depth, v, e in rows: f.write('%s\t%s\t%s\t%s\tNone\tFalse\n' % (name, depth, v, e))
    bad = [r for r in rows if r[2] == 'error']
    print('weakbarbed_record: %d rows recorded (%d errors); depth recorded as ScriptCostBudget, never a horizon' % (len(rows), len(bad)))
    return 1 if bad else 0
if __name__ == '__main__':
    sys.exit(main())
