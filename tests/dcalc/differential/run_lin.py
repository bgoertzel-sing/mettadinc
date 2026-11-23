#!/usr/bin/env python3
"""Differential runner for linear arrows: gen_lin cases -> real CLI (--beyond-release) vs oracle.linear_arrow.
Requests per case: CheckLinearArrow L, CheckLinearArrow K, Then(L, K).
Oracle rule (spec Def 3.8, l.2465; Prop 3.9): valid iff L eta' = eta (rows sum to 1, both machines
stochastic) and, when Kind Positive, L >= 0. Grade (||L||, max(max_a ||R_a||, max_y ||S_y||)).
Then: Checked with the Prop 3.9 grade when both parts are Checked, else InvalidInput.
Each disagreement is tagged KNOWN-D3 (see disagreements/README.md) or NEW. KNOWN-D2 was removed when D2 was fixed (t-2026-11-19).
usage: run_lin.py --seed N --count K --out DIR [--dcalc PATH]"""
import argparse, json, os, random, re, subprocess, sys
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_lin, oracle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def num(s):
    m = re.match(r'\(Rat (-?\d+) (\d+)\)', s)
    return F(int(m.group(1)), int(m.group(2))) if m else F(int(s))


def parse(line):
    st = re.search(r'\(Result \(Status (\w+)\)', line)
    lam = re.search(r'\(Lambda (\(Rat -?\d+ \d+\)|-?\d+)\)', line)
    rho = re.search(r'\(Rho (\(Rat -?\d+ \d+\)|-?\d+)\)', line)
    st = st.group(1) if st else 'NoResult'
    if st != 'Checked':
        return st, None
    return st, (str(num(lam.group(1))) if lam else None, str(num(rho.group(1))) if rho else None)


def arrow_expect(src, tgt, L, signed):
    g = oracle.linear_arrow(src, tgt, L)
    ok = g['valid'] and (signed or g['positive'])
    return ('Checked', (str(g['lam']), str(g['rho']))) if ok else ('Refuted', None), g


def tag(kind, cli, exp, g, signed, raw=''):
    if kind in ('LC', 'KC'):
        # t-2026-11-19 D2 fixed: a nonzero observation residual is graded (rho includes max_y ||S_y||), so a
        # Refuted-with-'observation report differs' answer is no longer a known bug; it is tagged NEW.
        if cli[0] == 'Checked' and exp[0] == 'Refuted' and signed and not g['valid']:
            return 'KNOWN-D3'
    if kind == 'LK':
        return 'DOWNSTREAM'      # Then disagreements are tagged downstream if LC/KC already differ
    return 'NEW'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--count', type=int, default=20)
    ap.add_argument('--out', required=True); ap.add_argument('--dcalc', default=os.path.join(ROOT, 'build/dcalc/dcalc'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    tally = {}
    with open(os.path.join(a.out, 'results.jsonl'), 'w') as log:
        for i in range(a.count):
            name = 'LN%d_%d' % (a.seed, i)
            (ms, mt, mu, L, K, sL, sK), text = gen_lin.rand_case(rng, name)
            fn = os.path.join(a.out, name + '.metta')
            open(fn, 'w').write(text)
            try:
                out = subprocess.run([a.dcalc, '--beyond-release', fn], capture_output=True, text=True, timeout=60).stdout
            except subprocess.TimeoutExpired:
                out = ''
            lines = [l for l in out.splitlines() if '=> (Result' in l]
            eL, gL = arrow_expect(ms, mt, L, sL)
            eK, gK = arrow_expect(mt, mu, K, sK)
            if eL[0] == 'Checked' and eK[0] == 'Checked':
                lam, rho = oracle.compose_grade(gL, gK); eLK = ('Checked', (str(lam), str(rho)))
            else:
                eLK = ('InvalidInput', None)
            first_bad = False
            for k, (kind, exp, g, signed) in enumerate([('LC', eL, gL, sL), ('KC', eK, gK, sK), ('LK', eLK, None, None)]):
                cli = parse(lines[k]) if k < len(lines) else ('NoOutput', None)
                ok = cli == exp
                t = 'OK'
                if not ok:
                    t = tag(kind, cli, exp, g, signed, lines[k] if k < len(lines) else '') if (kind != 'LK' or first_bad) else 'NEW'
                    first_bad = True
                tally.setdefault(kind, {}).setdefault(t, 0); tally[kind][t] += 1
                log.write(json.dumps({'case': name, 'kind': kind, 'tag': t, 'cli': [cli[0], cli[1]], 'oracle': [exp[0], exp[1]]}) + '\n')
                if t == 'NEW':
                    print('NEW', name, kind, 'cli=', cli, 'oracle=', exp, flush=True)
    for k, d in sorted(tally.items()):
        print('SUMMARY', k, json.dumps(d, sort_keys=True))
    json.dump(tally, open(os.path.join(a.out, 'tally.json'), 'w'))
    return 1 if any(d.get('NEW') for d in tally.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
