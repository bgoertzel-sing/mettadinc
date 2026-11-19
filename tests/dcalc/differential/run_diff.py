#!/usr/bin/env python3
"""Differential runner: random chains (gen.py) -> real CLI (dcalc --beyond-release) vs oracle.py.
Compares exact values (partitions as sets of blocks, dimensions, rational defects) and statuses.
usage: run_diff.py --seed N --count K --out DIR [--dcalc PATH]"""
import argparse, json, os, random, subprocess, sys
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen, oracle, sx

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def blocks_of(v):
    p = sx.find(v, 'Partition')
    return sorted(sorted(b[1:]) for b in p[1:]) if p else None


def norm(bs):
    return sorted(sorted(b) for b in bs)


def case(rng, i, name):
    m = gen.rand_chain(rng)
    enc = gen.rand_encode(rng, m)
    h = rng.randint(1, 4)
    reqs = [('trace', '(TracePartition Chain)'), ('lindim', '(MinimalLinear Chain)'),
            ('bisim', '(MinimizeForQueries Chain)'),
            ('kant_h', '(MeasureBehavioral Rep (Horizon (Steps %d)))' % h)]
    text = gen.chain_module(name, m, enc) + ''.join('!(dc.run %s %s)\n' % (name, r) for _, r in reqs)
    exp = {'trace': ('Checked', norm(oracle.trace_partition(m))),
           'lindim': ('Checked', F(oracle.minimal_linear_dim(m))),
           'bisim': ('Checked', norm(oracle.bisim_partition(m))),
           'kant_h': ('Checked', oracle.defect(m, oracle.horizon_distances(m, h), enc))}
    return m, enc, text, reqs, exp


def got_value(kind, res):
    v = sx.find(res, 'Value')
    if v is None:
        return None
    if kind in ('trace', 'bisim'):
        return blocks_of(v)
    if kind == 'lindim':
        d = sx.find(v, 'Dimension'); return sx.num(d[1]) if d else None
    if kind == 'kant_h':
        d = sx.find(v, 'BehavioralDefect'); return sx.num(d[1]) if d else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--count', type=int, default=10)
    ap.add_argument('--out', required=True); ap.add_argument('--dcalc', default=os.path.join(ROOT, 'build/dcalc/dcalc'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    log = open(os.path.join(a.out, 'results.jsonl'), 'w')
    tally = {}
    for i in range(a.count):
        name = 'D%d_%d' % (a.seed, i)
        m, enc, text, reqs, exp = case(rng, i, name)
        fn = os.path.join(a.out, name + '.metta')
        open(fn, 'w').write(text)
        try:
            out = subprocess.run([a.dcalc, '--beyond-release', fn], capture_output=True, text=True, timeout=60).stdout
        except subprocess.TimeoutExpired:
            out = ''
        ans = sx.answers(out)
        for (kind, req), (_, res) in zip(reqs, ans + [(None, None)] * (len(reqs) - len(ans))):
            st = sx.status(res) if res is not None else 'NoAnswer'
            gv = got_value(kind, res) if res is not None else None
            es, ev = exp[kind]
            ok = st == es and gv == ev
            t = tally.setdefault(kind, [0, 0]); t[0 if ok else 1] += 1
            log.write(json.dumps({'case': name, 'kind': kind, 'req': req, 'ok': ok, 'status': st, 'expect_status': es,
                                  'got': str(gv), 'expect': str(ev)}) + '\n')
        log.flush()
    for k, (g, b) in sorted(tally.items()):
        print('%-8s agree %d disagree %d' % (k, g, b))
    json.dump(tally, open(os.path.join(a.out, 'tally.json'), 'w'))
    return 0 if all(b == 0 for _, b in tally.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
