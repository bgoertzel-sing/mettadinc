#!/usr/bin/env python3
"""M6-rest random probe for LeastCoherentRefinement (beyond the fixtures).
Random small kernel hives -> dcalc; every Checked row is (1) replayed by replay_m6rest.py (Fractions),
(2) compared with an independent exact LP (sympy lpmax over ALL ordered triples, not dcalc's reduced rows),
(3) tampered (one dual row dropped) and the replayer must reject every tampered row.
usage: probe_lcr.py N seed outdir"""
import os, random, subprocess, sys
from fractions import Fraction as Q
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
sys.path.insert(0, os.path.join(HERE, '..', 'm6')); import replay_m6 as R
N, seed, od = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; rnd = random.Random(seed); os.makedirs(od, exist_ok=True)
CAR = {'Bit': [0, 1], 'Tri': [0, 1, 2]}
def rs(q): return '(Rat %d %d)' % (q.numerator, q.denominator)
hdr = ['(DC.Module LcrProbe', '  (Profile Graded)', '  (Use Hives)', '  (Carrier Bit (Of Nat) (Enum 0 1))', '  (Carrier Tri (Of Nat) (Enum 0 1 2))',
       '  (Tolerance SharpBit (On Bit) (Discrete))', '  (Tolerance SharpTri (On Tri) (Discrete))', '  (Tolerance CoarseBit (On Bit) (Trivial))',
       '  (Measure UBit (On Bit) (Uniform))', '  (Measure UTri (On Tri) (Uniform))']
body, reqs, truth = [], [], {}
for i in range(N):
    k = rnd.choice([2, 3, 3, 3, 4]); mem = []
    for j in range(k):
        c = rnd.choice(['Bit', 'Bit', 'Tri']) if k < 4 else 'Bit'
        t = 'SharpTri' if c == 'Tri' else rnd.choice(['SharpBit', 'SharpBit', 'CoarseBit'])
        mem.append(('M%d' % (j + 1), c, t, 'UTri' if c == 'Tri' else 'UBit'))
    while True:
        ws = [rnd.randint(1, 4) for _ in mem]
        if len(set(ws)) > 1 or rnd.random() < 0.3: break
    W = [Q(x, sum(ws)) for x in ws]
    nodes = [(m[0], v) for m in mem for v in CAR[m[1]]]; wt = {}; H = {}
    for m, w in zip(mem, W):
        for v in CAR[m[1]]: wt[(m[0], v)] = w / len(CAR[m[1]])
        for a in CAR[m[1]]:
            for b in CAR[m[1]]: H[((m[0], a), (m[0], b))] = 1 if a == b or m[2] == 'CoarseBit' else 0
    hv = ['  (KernelHive P%d' % i] + ['    (Member %s %s %s %s)' % m for m in mem]
    for a in range(k):
        for b in range(a + 1, k):
            ma, mb = mem[a], mem[b]; kn = 'K%d_%d_%d' % (i, a, b); ents = []
            for x in CAR[ma[1]]:
                for y in CAR[mb[1]]:
                    e = 1 if rnd.random() < 0.45 else 0; ents.append('(%d %d %d)' % (x, y, e)); H[((ma[0], x), (mb[0], y))] = H[((mb[0], y), (ma[0], x))] = e
            body.append('  (CrossKernel %s (Left %s) (Right %s) (Entries %s))' % (kn, ma[1], mb[1], ' '.join(ents)))
            hv.append('    (Correspondence %s %s %s Measured)' % (ma[0], mb[0], kn))
    hv.append('    (Weights %s))' % ' '.join('(%s %s)' % (m[0], rs(w)) for m, w in zip(mem, W)))
    body += hv; reqs.append('!(dc.run LcrProbe (LeastCoherentRefinement P%d))' % i); truth['P%d' % i] = (nodes, wt, H)
fx = os.path.join(od, 'probe_lcr.metta'); open(fx, 'w').write('\n'.join(hdr + body) + ')\n' + '\n'.join(reqs) + '\n')
out = os.path.join(od, 'probe_lcr.out')
with open(out, 'w') as f: subprocess.run([os.path.join(ROOT, 'build/dcalc/dcalc'), '--beyond-release', fx], stdout=f, stderr=subprocess.STDOUT, timeout=600)
rp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), fx, out], capture_output=True, text=True)
print(rp.stdout.strip().splitlines()[-1])
from sympy import Rational, Symbol
from sympy.solvers.simplex import lpmax
st = {'Checked': 0, 'other': 0, 'lp': 0, 'chord': 0, 'agree': 0, 'disagree': 0}; tam = []
for line in open(out).read().splitlines():
    if ' => ' not in line: continue
    res = R.read_all(line.split(' => ', 1)[1])[0]; s = R.field(res, 'Status')[1]; nm = R.field(res, 'Claim')[1][1]
    if s != 'Checked': st['other'] += 1; print('NOT CHECKED', nm, line[:200]); continue
    st['Checked'] += 1
    if 'LinearProgram' in line: st['lp'] += 1
    if '(Chord ' in line: st['chord'] += 1
    nodes, wt, H = truth[nm]; X = {}; obj = 0; T = Q(0); cons = []
    for i, a in enumerate(nodes):
        X[(a, a)] = 1
        for b in nodes[i + 1:]:
            if H[(a, b)]:
                v = Symbol('x%d' % len(cons)); cons += [v >= 0, v <= 1]; X[(a, b)] = X[(b, a)] = v
                c = wt[a] * wt[b]; obj += Rational(c.numerator, c.denominator) * v; T += c
            else: X[(a, b)] = X[(b, a)] = 0
    for a in nodes:
        for b in nodes:
            for c in nodes:
                if len({a, b, c}) == 3:
                    e = X[(a, c)] - X[(a, b)] - X[(b, c)] + 1
                    if getattr(e, 'free_symbols', None): cons.append(e >= 0)
    P = lpmax(obj, cons)[0] if cons else Rational(0)
    ref = 2 * (Rational(T.numerator, T.denominator) - P); got = R.rat(R.field(res, 'Value')[1])
    ok = Rational(got.numerator, got.denominator) == ref; st['agree' if ok else 'disagree'] += 1
    if not ok: print('DISAGREE', nm, got, ref)
    i0 = line.find('(Dual (') + 6
    if i0 > 5:
        d, j = 0, i0
        while True:
            d += {'(': 1, ')': -1}.get(line[j], 0); j += 1
            if d == 0: break
        tam.append(line[:i0] + line[j:].lstrip(' '))
tf = out + '.tampered'; open(tf, 'w').write('\n'.join(tam) + '\n')
tp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), fx, tf], capture_output=True, text=True)
rej = sum(1 for l in tp.stdout.splitlines() if l.startswith('REJECT'))
print('stats', st, 'tampered', len(tam), 'rejected', rej)
good = 'PASS' in rp.stdout.splitlines()[-1] and st['disagree'] == 0 and st['other'] == 0 and rej == len(tam) and st['Checked'] == N
print('probe_lcr: %s' % ('PASS' if good else 'FAIL')); sys.exit(0 if good else 1)
