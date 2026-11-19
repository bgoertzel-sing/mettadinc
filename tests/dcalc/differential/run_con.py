#!/usr/bin/env python3
"""Differential runner for affine contracts: gen_con.py -> real CLI (dcalc --beyond-release) vs oracle.py
(CheckImplementation by spec 9.3 over all ordered audited pairs; ThenContracts by Prop 9.1, only from Checked inputs).
Compares status and the exact grade (L, eta).
usage: run_con.py --seed N --count K --out DIR [--dcalc PATH]"""
import argparse, json, os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_con, oracle, sx

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def expect(c):
    A = oracle.affine
    s1, g1 = oracle.check_implementation(A(c['f']), A(c['fh']), c['X'], *c['gr1'])
    s2, g2 = oracle.check_implementation(A(c['g']), A(c['gh']), c['Y'], *c['gr2'])
    e = {'C1': (s1, g1 if s1 == 'Checked' else None), 'C2': (s2, g2 if s2 == 'Checked' else None)}
    e['C12'] = ('Checked', oracle.then_contracts(g1, g2)) if s1 == s2 == 'Checked' else ('InvalidInput', None)
    return e


def got(res):
    st = sx.status(res)
    v = sx.find(res, 'Value')
    if st != 'Checked' or v is None:
        return (st, None)
    g = sx.find(v, 'Grade')
    return (st, (sx.num(g[1]), sx.num(g[2])) if g else None)


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
        name = 'CN%d_%d' % (a.seed, i)
        c, text = gen_con.rand_case(rng, name)
        fn = os.path.join(a.out, name + '.metta'); open(fn, 'w').write(text)
        try:
            out = subprocess.run([a.dcalc, '--beyond-release', fn], capture_output=True, text=True, timeout=60).stdout
        except subprocess.TimeoutExpired:
            out = ''
        ans = dict((r.split()[1], res) for r, res in sx.answers(out) if len(r.split()) == 2)
        e = expect(c)
        for k in ('C1', 'C2', 'C12'):
            g = got(ans[k]) if k in ans else ('NoAnswer', None)
            ok = g == e[k]
            t = tally.setdefault(k, [0, 0]); t[0 if ok else 1] += 1
            log.write(json.dumps({'case': name, 'kind': k, 'ok': ok, 'got': str(g), 'expect': str(e[k]),
                                  'clipped': any(abs(x - y) > 1 for x in c['X'] for y in c['X'])}) + '\n')
        log.flush()
    for k, (g, b) in sorted(tally.items()):
        print('%-4s agree %d disagree %d' % (k, g, b))
    json.dump(tally, open(os.path.join(a.out, 'tally.json'), 'w'))
    return 0 if all(b == 0 for _, b in tally.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
