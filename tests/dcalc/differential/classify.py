#!/usr/bin/env python3
"""Tag every disagreement of a run_diff.py / run_con.py output dir as a listed D-id or NEW.
Regenerates the cases from the seed (same rng order as the runner) and replays the CLI's known behaviour:
  run_con: no known bug (D4 fixed in t-2026-11-19-mettadinc-d4-contract-clip): every disagreement is NEW.
  D5 (run_diff kant_h): CLI defect = max_x d(x, rep(x))  -> must equal the CLI value.
usage: classify.py --runner diff|con --seed N --count K --out DIR   (exit 1 if any NEW)"""
import argparse, collections, json, os, random, sys
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runner', choices=['diff', 'con'], required=True)
    ap.add_argument('--seed', type=int, required=True); ap.add_argument('--count', type=int, required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(a.out, 'results.jsonl'))]
    got = {(r['case'], r['kind']): r for r in rows}
    rng = random.Random(a.seed)
    tags = collections.Counter()
    if a.runner == 'diff':
        import run_diff
        for i in range(a.count):
            name = 'D%d_%d' % (a.seed, i)
            m, enc, text, reqs, exp = run_diff.case(rng, i, name)
            for kind, req in reqs:
                r = got.get((name, kind))
                if r is None: tags['MISSING'] += 1; continue
                if r['ok']: tags['OK'] += 1; continue
                t = 'NEW'
                if kind == 'kant_h' and r['status'] == 'Checked':
                    h = int(req.split('Steps ')[1].split(')')[0])
                    d = oracle.horizon_distances(m, h)
                    rep = max([d.get((x, enc[x]), F(0)) for x in m['states']] + [F(0)])
                    if str(rep) == r['got']: t = 'KNOWN-D5'
                tags[t] += 1
                if t == 'NEW': print('NEW', name, kind, r['got'], r['expect'])
    else:
        import gen_con, run_con
        cases = [gen_con.rand_case(rng, 'CN%d_%d' % (a.seed, i))[0] for i in range(a.count)]
        for i, c in enumerate(cases):
            for k in ('C1', 'C2', 'C12'):
                r = got.get(('CN%d_%d' % (a.seed, i), k))
                if r is None: tags['MISSING'] += 1; continue
                if r['ok']: tags['OK'] += 1; continue
                t = 'NEW'  # D4 fixed: the CLI must agree with the clipped oracle
                tags[t] += 1
                if t == 'NEW': print('NEW', 'CN%d_%d' % (a.seed, i), k, r['got'], r['expect'])
    print('CLASSIFY', a.runner, dict(sorted(tags.items())))
    return 1 if tags['NEW'] or tags['MISSING'] else 0


if __name__ == '__main__':
    sys.exit(main())
