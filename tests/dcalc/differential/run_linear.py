"""M4 linear-arrow differential runner: random arrows -> real CLI (--beyond-release) vs oracle_linear.

Usage: python3 run_linear.py --seed S --count N --cli PATH --out DIR [--family random|exact]
Requests per case: CheckLinearArrow L, CheckLinearArrow K, Then(L, K).
Oracle status rule (Def 3.8, Section 7.3 bullet 2): Refuted iff L eta' != eta (row sums != 1) or a
declared Positive arrow has a negative entry; otherwise Checked with grade (lam, rho), rho including
the projector residuals S_y.  Then: grade by Prop 3.9 from the two oracle grades.
Records rho_actions separately so a disagreement can say which residual differs.
Standard library only.
"""
import argparse, json, os, random, re, subprocess, sys
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_linear import rand_case, module_text
import oracle_linear as OL


def parse_num(s):
    m = re.match(r'\(Rat (-?\d+) (\d+)\)', s)
    return F(int(m.group(1)), int(m.group(2))) if m else F(int(s))


def parse_line(line):
    st = re.search(r'\(Result \(Status (\w+)\)', line)
    status = st.group(1) if st else 'NoResult'
    m = re.search(r'\(Grade \(Lambda (\(Rat -?\d+ \d+\)|-?\d+)\) \(Rho (\(Rat -?\d+ \d+\)|-?\d+)\)\)', line)
    val = [str(parse_num(m.group(1))), str(parse_num(m.group(2)))] if m and status == 'Checked' else None
    return status, val


def oracle_arrow(src, tgt, L, kind):
    g = OL.arrow_grade(src, tgt, L)
    ok = g['valid'] and (kind != 'Positive' or all(v >= 0 for r in L for v in r))
    return ('Checked' if ok else 'Refuted'), g


def run_case(args, seed, i):
    rng = random.Random(seed * 1000003 + i)
    c = rand_case(rng, args.family)
    name = 'Lin%d' % i
    path = os.path.join(args.out, 'lin_%s_%d_%d.metta' % (args.family, seed, i))
    with open(path, 'w') as fh:
        fh.write(module_text(name, c))
    try:
        p = subprocess.run([args.cli, '--beyond-release', path], capture_output=True, text=True, timeout=60)
        lines = [l for l in p.stdout.splitlines() if '=> (Result' in l]
    except subprocess.TimeoutExpired:
        lines = []
    sL, gL = oracle_arrow(c['A'], c['B'], c['L'], c['kL'])
    sK, gK = oracle_arrow(c['B'], c['C'], c['K'], c['kK'])
    exp = [(sL, [str(gL['lam']), str(gL['rho'])] if sL == 'Checked' else None, gL),
           (sK, [str(gK['lam']), str(gK['rho'])] if sK == 'Checked' else None, gK)]
    if sL == 'Checked' and sK == 'Checked':
        lam, rho = OL.compose_grade((gL['lam'], gL['rho']), (gK['lam'], gK['rho']))
        exp.append(('Checked', [str(lam), str(rho)], None))
    else:
        exp.append(('InvalidInput', None, None))
    out = []
    for k, kind in enumerate(['arrow_L', 'arrow_K', 'then_LK']):
        cs, cv = parse_line(lines[k]) if k < len(lines) else ('NoOutput', None)
        os_, ov, g = exp[k]
        extra = {} if g is None else dict(rho_actions=str(g['rho_actions']), rho_projectors=str(g['rho_projectors']), valid=g['valid'])
        out.append(dict(case=path, kind=kind, cli=[cs, cv], oracle=[os_, ov], agree=(cs == os_ and cv == ov), **extra))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--count', type=int, default=20)
    ap.add_argument('--family', choices=['random', 'exact', 'obs'], default='random')
    ap.add_argument('--cli', required=True); ap.add_argument('--out', required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    tally = {}
    with open(os.path.join(args.out, 'results.jsonl'), 'w') as fh:
        for i in range(args.count):
            for r in run_case(args, args.seed, i):
                fh.write(json.dumps(r) + '\n')
                t = tally.setdefault(r['kind'], [0, 0]); t[0] += 1; t[1] += 0 if r['agree'] else 1
                if not r['agree']:
                    print('DISAGREE', r['kind'], r['case'], 'cli=', r['cli'], 'oracle=', r['oracle'], flush=True)
    for k, (n, bad) in sorted(tally.items()):
        print('SUMMARY %-14s cases=%d disagree=%d' % (k, n, bad))
    return 1 if any(b for _, b in tally.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
