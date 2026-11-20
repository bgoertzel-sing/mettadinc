"""D6 runner (t-2026-11-20-mettadinc-d6-trace-check): horizon trace defect, real CLI vs a brute-force oracle.

run_stoch.py's check_trace kind is the unbounded crisp CheckTrace, which D6 does not affect, so this runner
measures MeasureTrace (Horizon (Steps h)) over fixed words. Machines come from gen_stoch.rand_machine
(fixed seed); the MergeXY encoding is widened to a 3-state class {x, y, z} -> x so that same-code pairs
other than the representative pairs exist. Oracle: spec Def 4.4(4) l.1044-1059, max over ALL same-code
pairs x, x' of max_w TV(P_x^w, P_x'^w); also the representative-only value (what D6 computes).
Usage: python3 run_trace_hor.py --seed S --count N --cli PATH --out DIR [--horizon H]
Standard library only.
"""
import argparse, json, os, random, re, subprocess, sys
from fractions import Fraction as F
from itertools import product
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_stoch


def path_law(M, x, w):
    law = {((M['report'][x],), x): F(1)}
    for a in w:
        K, nl = M['actions'][a], {}
        for (obs, s), p in law.items():
            for t, m in K[s].items():
                if m == 0:
                    continue
                k = (obs + (M['report'][t],), t)
                nl[k] = nl.get(k, F(0)) + p * m
        law = nl
    out = {}
    for (obs, s), p in law.items():
        out[obs] = out.get(obs, F(0)) + p
    return out


def tv(P, Q):
    return sum(abs(P.get(k, F(0)) - Q.get(k, F(0))) for k in set(P) | set(Q)) / 2


def oracle(M, h):
    S, code = M['states'], M['merge']
    spec, rep = F(0), F(0)
    for w in product(sorted(M['actions']), repeat=h):
        L = {x: path_law(M, x, w) for x in S}
        for i, x in enumerate(S):
            for y in S[i + 1:]:
                if code[x] == code[y]:
                    spec = max(spec, tv(L[x], L[y]))
            if code[x] != x:
                rep = max(rep, tv(L[x], L[code[x]]))
    return spec, rep


def parse_rat(s):
    m = re.search(r'\(TraceDefect (?:\(Rat (-?\d+) (\d+)\)|(-?\d+))\)', s)
    if not m:
        return None
    return F(int(m.group(1)), int(m.group(2))) if m.group(1) else F(int(m.group(3)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--count', type=int, default=50)
    ap.add_argument('--horizon', type=int, default=2)
    ap.add_argument('--cli', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    n = dis = errs = 0
    with open(os.path.join(a.out, 'results.jsonl'), 'w') as fh:
        for i in range(a.count):
            rng = random.Random(a.seed * 100003 + i)
            M = gen_stoch.rand_machine(rng, nmin=3, nmax=6)
            x, y, z = rng.sample(M['states'], 3)
            M['merge'] = {s: s for s in M['states']}
            M['merge'][y] = x
            M['merge'][z] = x
            name = 'TH%d_%d' % (a.seed, i)
            path = os.path.join(a.out, 'case_%d_%d.metta' % (a.seed, i))
            with open(path, 'w') as f:
                f.write(gen_stoch.module_text(name, M))
                f.write('!(dc.run %s (MeasureTrace Merge (Horizon (Steps %d))))\n' % (name, a.horizon))
            p = subprocess.run([a.cli, '--beyond-release', path], capture_output=True, text=True, timeout=120)
            cli = parse_rat(p.stdout)
            spec, rep = oracle(M, a.horizon)
            agree = cli == spec
            n += 1
            dis += 0 if agree else 1
            errs += 1 if cli is None else 0
            r = dict(case=i, cls=[x, y, z], cli=str(cli), spec=str(spec), rep_only=str(rep), agree=agree,
                     cli_is_rep_only=(cli == rep))
            fh.write(json.dumps(r) + '\n')
            if not agree:
                print('DISAGREE case %d class %s cli %s spec %s rep_only %s' % (i, [x, y, z], cli, spec, rep))
    print('trace_hor seed %d h %d: %d cases, %d disagree, %d no-parse' % (a.seed, a.horizon, n, dis, errs))


if __name__ == '__main__':
    main()
