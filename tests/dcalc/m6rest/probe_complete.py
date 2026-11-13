#!/usr/bin/env python3
"""M6-rest random probe for CompleteHive (beyond the fixtures).
Random small kernel hives with some correspondences Unmeasured/undeclared -> dcalc.  Every row is checked against an
independent brute-force (Floyd-Warshall closure over measured identifications): Unsupported exactly when a measured 0
is joined by a measured path; otherwise Checked with alignment cost = sum w_a w_b over filled ordered pairs.  Checked
rows are replayed (replay_m6rest.py) and tampered (first Fill row dropped) -> the replayer must reject every one.
usage: probe_complete.py N seed outdir"""
import os, random, re, subprocess, sys
from fractions import Fraction as Q
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
sys.path.insert(0, os.path.join(HERE, '..', 'm6')); import replay_m6 as R
N, seed, od = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; rnd = random.Random(seed); os.makedirs(od, exist_ok=True)
CAR = {'Bit': [0, 1], 'Tri': [0, 1, 2]}
def rs(q): return '(Rat %d %d)' % (q.numerator, q.denominator)
hdr = ['(DC.Module CompleteProbe', '  (Profile Graded)', '  (Use Hives)', '  (Carrier Bit (Of Nat) (Enum 0 1))', '  (Carrier Tri (Of Nat) (Enum 0 1 2))',
       '  (Tolerance SharpBit (On Bit) (Discrete))', '  (Tolerance SharpTri (On Tri) (Discrete))', '  (Tolerance CoarseBit (On Bit) (Trivial))',
       '  (Measure UBit (On Bit) (Uniform))', '  (Measure UTri (On Tri) (Uniform))']
body, reqs, truth = [], [], {}
for i in range(N):
    k = rnd.choice([3, 3, 4, 4, 5]); mem = []
    for j in range(k):
        c = rnd.choice(['Bit', 'Bit', 'Tri']); t = 'SharpTri' if c == 'Tri' else rnd.choice(['SharpBit', 'SharpBit', 'SharpBit', 'CoarseBit'])
        mem.append(('M%d' % (j + 1), c, t, 'UTri' if c == 'Tri' else 'UBit'))
    ws = [rnd.randint(1, 4) for _ in mem]; W = [Q(x, sum(ws)) for x in ws]
    nodes = [(m[0], v) for m in mem for v in CAR[m[1]]]; wt = {}; H = {}
    for m, w in zip(mem, W):
        for v in CAR[m[1]]: wt[(m[0], v)] = w / len(CAR[m[1]])
        for a in CAR[m[1]]:
            for b in CAR[m[1]]: H[((m[0], a), (m[0], b))] = 1 if a == b or m[2] == 'CoarseBit' else 0
    hv = ['  (KernelHive C%d' % i] + ['    (Member %s %s %s %s)' % m for m in mem]
    # review 1 F4: a hive whose pairs all draw 'none' has no Correspondence and the whole module is InvalidInput;
    # then add one Measured M1-M2 correspondence (extra draws happen only in that case, so other seeds are unchanged)
    pairs = [(a, b) for a in range(k) for b in range(a + 1, k)]; ncorr = 0; forced = None
    while True:
        for a, b in (pairs if forced is None else [forced]):
            ma, mb = mem[a], mem[b]; st = 'Measured' if forced else rnd.choice(['Measured', 'Measured', 'Unmeasured', 'none'])
            if st == 'none': continue
            ncorr += 1
            kn = 'K%d_%d_%d' % (i, a, b); ents = []
            # mostly partial bijections so that many hives are completable
            perm = list(CAR[mb[1]]); rnd.shuffle(perm); sparse = rnd.random() < 0.3
            for x in CAR[ma[1]]:
                for y in CAR[mb[1]]:
                    e = (1 if rnd.random() < 0.4 else 0) if sparse else (1 if x < len(perm) and perm[x] == y else 0)
                    ents.append('(%d %d %d)' % (x, y, e))
                    if st == 'Measured': H[((ma[0], x), (mb[0], y))] = H[((mb[0], y), (ma[0], x))] = e
            body.append('  (CrossKernel %s (Left %s) (Right %s) (Entries %s))' % (kn, ma[1], mb[1], ' '.join(ents)))
            hv.append('    (Correspondence %s %s %s %s)' % (ma[0], mb[0], kn, st))
        if ncorr or forced: break
        forced = (0, 1)
    hv.append('    (Weights %s))' % ' '.join('(%s %s)' % (m[0], rs(w)) for m, w in zip(mem, W)))
    body += hv; reqs.append('!(dc.run CompleteProbe (CompleteHive C%d))' % i); truth['C%d' % i] = (nodes, wt, H)
fx = os.path.join(od, 'probe_complete.metta'); open(fx, 'w').write('\n'.join(hdr + body) + ')\n' + '\n'.join(reqs) + '\n')
out = os.path.join(od, 'probe_complete.out')
with open(out, 'w') as f: subprocess.run([os.path.join(ROOT, 'build/dcalc/dcalc'), '--beyond-release', fx], stdout=f, stderr=subprocess.STDOUT, timeout=600)
st = {'Checked': 0, 'Unsupported': 0, 'other': 0, 'agree': 0, 'disagree': 0, 'fills': 0}; ok_lines, tam = [], []
for line in open(out).read().splitlines():
    if ' => ' not in line: continue
    res = R.read_all(line.split(' => ', 1)[1])[0]; s = R.field(res, 'Status')[1]; nm = re.search(r'\(CompleteHive (\w+)\)', line.split(' => ', 1)[0]).group(1)   # Unsupported rows carry an empty (Claim)
    nodes, wt, H = truth[nm]
    C = {(a, b): a == b or H.get((a, b)) == 1 for a in nodes for b in nodes}
    for m in nodes:
        for a in nodes:
            if C[(a, m)]:
                for b in nodes:
                    if C[(m, b)]: C[(a, b)] = True
    bad = any(H.get((a, b)) == 0 and C[(a, b)] for a in nodes for b in nodes)
    cost = sum((wt[a] * wt[b] for a in nodes for b in nodes if (a, b) not in H and C[(a, b)]), Q(0))
    if s == 'Checked':
        st['Checked'] += 1; good = not bad and R.rat(R.field(res, 'Value')[1]) == cost; ok_lines.append(line)
        if '(Fill ' in line:
            st['fills'] += 1; i0 = line.find('(Fill '); d, j = 0, i0
            while True:
                d += {'(': 1, ')': -1}.get(line[j], 0); j += 1
                if d == 0: break
            tam.append(line[:i0] + line[j:].lstrip(' '))
    elif s == 'Unsupported': st['Unsupported'] += 1; good = bad and 'not Lipschitz' in line
    else: st['other'] += 1; good = False
    st['agree' if good else 'disagree'] += 1
    if not good: print('DISAGREE', nm, s, cost, bad, line[:240])
ck = os.path.join(od, 'checked.out'); open(ck, 'w').write('\n'.join(ok_lines) + '\n')
rp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), fx, ck], capture_output=True, text=True)
print(rp.stdout.strip().splitlines()[-1] if rp.stdout.strip() else rp.stderr[-400:])
tf = os.path.join(od, 'tampered.out'); open(tf, 'w').write('\n'.join(tam) + '\n')
tp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), fx, tf], capture_output=True, text=True)
rej = sum(1 for l in tp.stdout.splitlines() if l.startswith('REJECT'))
print('stats', st, 'tampered', len(tam), 'rejected', rej)
good = rp.returncode == 0 and st['disagree'] == 0 and st['other'] == 0 and rej == len(tam) and st['Checked'] > 0 and st['Unsupported'] > 0 and st['fills'] > 0
print('probe_complete: %s' % ('PASS' if good else 'FAIL')); sys.exit(0 if good else 1)
