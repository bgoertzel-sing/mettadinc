"""M4 differential runner: random machines -> real CLI (--beyond-release) vs oracle_stoch.

Usage: python3 run_stoch.py --seed S --count N --cli PATH --out DIR [--expect-fail FILE]
Writes each case module to DIR/case_<seed>_<i>.metta and a JSON line per case to DIR/results.jsonl.
Compares exact values AND statuses per request.  Standard library only.
"""
import argparse, json, os, random, re, subprocess, sys
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_stoch import rand_machine, rand_mixture_machine, module_text
import oracle_stoch as O

DISCOUNTS = [F(1, 2), F(9, 10), F(2, 3)]


def requests(rng, name):
    g = rng.choice(DISCOUNTS)
    h = rng.randint(0, 4)
    return [('bisim', None, '(MinimizeForQueries Chain)'),
            ('trace_classes', None, '(TracePartition Chain)'),
            ('linear_dim', None, '(MinimalLinear Chain)'),
            ('kant_disc', g, '(MeasureBehavioral Merge (Discount %s))' % rat(g)),
            ('kant_hor', h, '(MeasureBehavioral Merge (Horizon (Steps %d)))' % h),
            ('check_trace', None, '(CheckTrace Merge)')]


def rat(q):
    return str(q.numerator) if q.denominator == 1 else '(Rat %d %d)' % (q.numerator, q.denominator)


def parse_num(s):
    m = re.match(r'\(Rat (-?\d+) (\d+)\)', s)
    return F(int(m.group(1)), int(m.group(2))) if m else F(int(s))


def parse_line(kind, line):
    st = re.search(r'\(Result \(Status (\w+)\)', line)
    status = st.group(1) if st else 'NoResult'
    val = None
    if kind in ('bisim', 'trace_classes'):
        m = re.search(r'\(Partition ((?:\(Block [^)]*\) ?)+)\)', line)
        if m:
            val = sorted(sorted(b.split()) for b in re.findall(r'\(Block ([^)]*)\)', m.group(1)))
    elif kind == 'linear_dim':
        m = re.search(r'\(MinimalLinear \(Dimension (\d+)\)\)', line)
        val = int(m.group(1)) if m else None
    elif kind.startswith('kant'):
        m = re.search(r'\(BehavioralDefect (\(Rat -?\d+ \d+\)|-?\d+)\)', line)
        val = str(parse_num(m.group(1))) if m else None
    elif kind == 'check_trace':
        m = re.search(r'\(TraceEquivalent (True|False)\)', line)
        val = m.group(1) if m else None
    return status, val


def oracle(kind, arg, M):
    x, y = M['pair']
    if kind == 'bisim':
        return 'Checked', sorted(sorted(b) for b in O.bisim_partition(M))
    if kind == 'trace_classes':
        return 'Checked', sorted(sorted(b) for b in O.trace_partition(M))
    if kind == 'linear_dim':
        return 'Checked', O.linear_dimension(M)
    if kind == 'kant_disc':
        d = O.exact_distance(M, arg)
        return ('Checked', str(d[x, y])) if d is not None else ('OracleGaveUp', None)
    if kind == 'kant_hor':
        return 'Checked', str(O.horizon_distance(M, F(1), arg)[x, y])
    if kind == 'check_trace':
        same = any(x in b and y in b for b in O.trace_partition(M))
        return ('Checked' if same else 'Refuted'), str(same)


def run_case(args, seed, i):
    rng = random.Random(seed * 1000003 + i)
    M = rand_mixture_machine(rng) if args.family == 'mixture' else rand_machine(rng)
    name = 'R%d' % i
    reqs = requests(rng, name)
    text = module_text(name, M) + ''.join('!(dc.run %s %s)\n' % (name, r[2]) for r in reqs)
    path = os.path.join(args.out, 'case_%s_%d_%d.metta' % (args.family, seed, i))
    with open(path, 'w') as fh:
        fh.write(text)
    try:
        p = subprocess.run([args.cli, '--beyond-release', path], capture_output=True, text=True, timeout=60)
        lines = [l for l in p.stdout.splitlines() if '=> (Result' in l]
    except subprocess.TimeoutExpired:
        lines = []
    out = []
    for k, (kind, arg, req) in enumerate(reqs):
        cs, cv = parse_line(kind, lines[k]) if k < len(lines) else ('NoOutput', None)
        os_, ov = oracle(kind, arg, M)
        agree = (cs == os_ and cv == ov)
        out.append(dict(case=path, kind=kind, arg=str(arg), cli=[cs, cv], oracle=[os_, ov], agree=agree))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--count', type=int, default=20)
    ap.add_argument('--family', choices=['random', 'mixture'], default='random')
    ap.add_argument('--cli', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    tally = {}
    with open(os.path.join(args.out, 'results.jsonl'), 'w') as fh:
        for i in range(args.count):
            for r in run_case(args, args.seed, i):
                fh.write(json.dumps(r) + '\n')
                t = tally.setdefault(r['kind'], [0, 0])
                t[0] += 1
                t[1] += 0 if r['agree'] else 1
                if not r['agree']:
                    print('DISAGREE', r['kind'], r['case'], 'cli=', r['cli'], 'oracle=', r['oracle'], flush=True)
    for k, (n, bad) in sorted(tally.items()):
        print('SUMMARY %-14s cases=%d disagree=%d' % (k, n, bad))
    return 1 if any(b for _, b in tally.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
