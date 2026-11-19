"""Greedy shrinker for an M4 kant_disc disagreement (CLI status/value != oracle).

Usage: python3 shrink_stoch.py --seed S --index I --cli PATH --out FILE
Rebuilds the case from (seed, index) exactly as run_stoch.run_case does, then greedily
drops actions, states, zero-mass edges and support entries while the disagreement persists.
Standard library only.
"""
import argparse, os, random, subprocess, sys, tempfile
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_stoch import rand_machine, module_text
from run_stoch import requests, parse_line, oracle, rat
import oracle_stoch as O


def cli_answer(cli, M, g):
    req = '(MeasureBehavioral Merge (Discount %s))' % rat(g)
    text = module_text('Shrunk', M) + '!(dc.run Shrunk %s)\n' % req
    with tempfile.NamedTemporaryFile('w', suffix='.metta', delete=False) as fh:
        fh.write(text); path = fh.name
    try:
        p = subprocess.run([cli, '--beyond-release', path], capture_output=True, text=True, timeout=60)
        lines = [l for l in p.stdout.splitlines() if '=> (Result' in l]
        return (parse_line('kant_disc', lines[0]) if lines else ('NoOutput', None)), text
    finally:
        os.unlink(path)


def bad(cli, M, g):
    try:
        (cs, cv), _ = cli_answer(cli, M, g)
        os_, ov = oracle('kant_disc', g, M)
    except Exception:
        return False
    return (cs, cv) != (os_, ov) and os_ == 'Checked'


def valid(M):
    return all(sum(K[s].values()) == 1 and all(t in M['states'] for t in K[s]) for K in M['actions'].values() for s in M['states'])


def drop_state(M, s):
    if s in M['pair']:
        return None
    S = [t for t in M['states'] if t != s]
    acts = {}
    for a, K in M['actions'].items():
        NK = {}
        for x in S:
            r = {t: m for t, m in K[x].items() if t != s}
            tot = sum(r.values())
            NK[x] = {t: m / tot for t, m in r.items()} if tot != 0 else {x: F(1)}
        acts[a] = NK
    return dict(M, states=S, actions=acts, report={t: M['report'][t] for t in S},
                merge={t: M['merge'][t] for t in S})


def candidates(M):
    if len(M['actions']) > 1:
        for a in sorted(M['actions']):
            yield dict(M, actions={b: K for b, K in M['actions'].items() if b != a})
    for s in M['states']:
        c = drop_state(M, s)
        if c: yield c
    for a, K in sorted(M['actions'].items()):
        for x in M['states']:
            for t, m in list(K[x].items()):
                r = {u: v for u, v in K[x].items() if u != t}
                tot = sum(r.values())
                if m == 0 or tot != 0:
                    nr = {u: (v / tot if tot else v) for u, v in r.items()} if r else None
                    if nr:
                        yield dict(M, actions=dict(M['actions'], **{a: dict(K, **{x: nr})}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True); ap.add_argument('--index', type=int, required=True)
    ap.add_argument('--cli', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rng = random.Random(a.seed * 1000003 + a.index)
    M = rand_machine(rng)
    g = requests(rng, 'R')[3][1]
    assert bad(a.cli, M, g), 'case does not reproduce'
    changed = True
    while changed:
        changed = False
        for c in candidates(M):
            if valid(c) and bad(a.cli, c, g):
                M, changed = c, True
                break
    (cs, cv), text = cli_answer(a.cli, M, g)
    with open(a.out, 'w') as fh:
        fh.write(text)
    print('SHRUNK states=%d actions=%d discount=%s cli=%s oracle=%s' % (
        len(M['states']), len(M['actions']), g, [cs, cv], list(oracle('kant_disc', g, M))))


if __name__ == '__main__':
    main()
