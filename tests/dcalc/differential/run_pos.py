#!/usr/bin/env python3
"""Differential runner for PositiveRealization M (Candidate L) (spec l.2469-2486).
Candidates: exact permutation copy, exact bisimulation quotient (lumping), or a random positive
arrow (usually not exact).  Oracle: oracle.positive_realization -> Checked (Interval signed_min k)
or Refuted.  usage: run_pos.py --seed N --count K --out DIR [--dcalc PATH]"""
import argparse, json, os, random, re, subprocess, sys
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_lin, oracle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def quotient(rng, m):
    B = oracle.bisim_partition(m)
    T = ['q%d' % i for i in range(len(B))]
    blk = {s: i for i, b in enumerate(B) for s in b}
    acts = {}
    for a, K in m['actions'].items():
        acts[a] = {}
        for i, b in enumerate(B):
            r = {}
            for t, p in K[b[0]].items():
                if p:
                    r[T[blk[t]]] = r.get(T[blk[t]], F(0)) + p
            acts[a][T[i]] = r
    q = {'states': T, 'obs': {T[i]: m['obs'][b[0]] for i, b in enumerate(B)}, 'actions': acts}
    L = [[F(int(blk[s] == j)) for j in range(len(T))] for s in m['states']]
    return q, L


def rand_case(rng, name):
    acts = ['a%d' % i for i in range(rng.randint(1, 2))]
    nobs = rng.randint(1, 3)
    ms = gen_lin.rand_machine(rng, 's', rng.randint(2, 6), nobs, acts)
    mode = rng.choice(['perm', 'quot', 'quot', 'rand'])
    if mode == 'perm':
        mt, L = gen_lin.permuted(rng, ms, 't')
    elif mode == 'quot':
        mt, L = quotient(rng, ms)
    else:
        mt = gen_lin.rand_machine(rng, 't', rng.randint(1, 4), nobs, acts)
        L = gen_lin.rand_arrow(rng, ms, mt, False, respect=rng.random() < 0.8)
    txt = '\n'.join(['(DC.Module %s' % name, '  (Profile Stochastic)', '  (Use Linear)',
                     '  (Carrier Report (Of Nat) (Enum %s))' % ' '.join(str(i) for i in range(nobs)),
                     gen_lin.machine_text('S', 'MS', ms, nobs), gen_lin.machine_text('T', 'MT', mt, nobs),
                     gen_lin.arrow_text('L', 'MS', 'MT', ms, mt, L, False),
                     '  (Derive P (PositiveRealization MS (Candidate L))))']) + '\n!(dc.run %s P)\n' % name
    return ms, mt, L, mode, txt


def expect(ms, mt, L):
    """Spec l.2469-2486: interval [signed minimum, upper]. The bisimulation (lumped) quotient is itself a
    positive realization, so a sound upper bound is min(k, lumped) when the candidate replays, and
    lumped when it does not (spec is silent on a rejected candidate; the CLI keeps the lumped bound)."""
    g = oracle.linear_arrow(ms, mt, L)
    replayed = bool(g['valid'] and g['positive'] and g['rho'] == 0)
    lumped = len(oracle.bisim_partition(ms))
    lo = oracle.minimal_linear_dim(ms)
    up = min(len(mt['states']), lumped) if replayed else lumped
    return 'Checked', (lo, up), ('Replayed' if replayed else 'Rejected')


def parse(line):
    st = re.search(r'\(Result \(Status (\w+)\)', line)
    st = st.group(1) if st else 'NoResult'
    iv = re.search(r'\(PositiveDimension \(Interval (\d+) (\d+)\)\)', line)
    return st, ((int(iv.group(1)), int(iv.group(2))) if (iv and st == 'Checked') else None)


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
            name = 'PR%d_%d' % (a.seed, i)
            ms, mt, L, mode, text = rand_case(rng, name)
            fn = os.path.join(a.out, name + '.metta'); open(fn, 'w').write(text)
            try:
                out = subprocess.run([a.dcalc, '--beyond-release', fn], capture_output=True, text=True, timeout=60).stdout
            except subprocess.TimeoutExpired:
                out = ''
            lines = [l for l in out.splitlines() if '=> (Result' in l]
            cli = parse(lines[0]) if lines else ('NoOutput', None)
            e = expect(ms, mt, L)
            exp = (e[0], e[1])
            rep = re.search(r'\(Candidate \S+ (Replayed|Rejected)', lines[0]) if lines else None
            ok = (cli[0], cli[1]) == exp and (rep.group(1) if rep else None) == e[2]
            t = tally.setdefault(mode, [0, 0]); t[0 if ok else 1] += 1
            log.write(json.dumps({'case': name, 'mode': mode, 'ok': ok, 'cli': [cli[0], cli[1]], 'oracle': [exp[0], exp[1]]}) + '\n')
            if not ok:
                print('DISAGREE', name, mode, 'cli=', cli, 'oracle=', exp, flush=True)
    for k, (g, b) in sorted(tally.items()):
        print('SUMMARY %-5s agree %d disagree %d' % (k, g, b))
    return 1 if any(b for _, b in tally.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
