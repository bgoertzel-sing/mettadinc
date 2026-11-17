#!/usr/bin/env python3
"""m6-graded random probe: graded kernel hives (rational degrees in {0, 1/4, 1/3, 1/2, 2/3, 3/4, 1}) through the
exact production path (build/dcalc/dcalc --beyond-release), checked three ways:
  1. replay_m6graded.py must ACCEPT every Checked/Refuted row;
  2. independent brute force (Fractions): coherence by triple scan, ConsensusCost / CompleteHive by (max, (x)) Floyd-
     Warshall closure, LeastCoherentRefinement by a separate sympy LP (lpmax, x_ab in [0, c_ab], transitivity rows);
  3. tamper canaries: every Value is perturbed by +1/97 and the replayer must REJECT every tampered row.
usage: probe_graded.py [N] [seed]"""
import os, random, subprocess, sys
from fractions import Fraction as Q
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'm6'))
import replay_m6 as R
N = int(sys.argv[1]) if len(sys.argv) > 1 else 24; SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
rnd = random.Random(SEED); od = os.path.join(ROOT, 'build', 'probe_graded'); os.makedirs(od, exist_ok=True)
CAR = {'Bit': [0, 1], 'Tri': [0, 1, 2]}; DEG = [Q(0), Q(0), Q(1, 4), Q(1, 3), Q(1, 2), Q(2, 3), Q(3, 4), Q(1), Q(1)]
def rs(q): return '(Rat %d %d)' % (q.numerator, q.denominator)
def lk(a, b): return max(Q(0), a + b - 1)
def closure(nodes, H):
    F = {(a, b): (Q(1) if a == b else H.get((a, b), Q(0))) for a in nodes for b in nodes}
    for k in nodes:
        for a in nodes:
            for b in nodes:
                t = lk(F[(a, k)], F[(k, b)])
                if t > F[(a, b)]: F[(a, b)] = t
    return F
hdr = ['(DC.Module GradedProbe', '  (Profile Graded)', '  (Use Hives)', '  (Carrier Bit (Of Nat) (Enum 0 1))', '  (Carrier Tri (Of Nat) (Enum 0 1 2))',
       '  (Tolerance SharpBit (On Bit) (Discrete))', '  (Tolerance SharpTri (On Tri) (Discrete))', '  (Tolerance CoarseBit (On Bit) (Trivial))',
       '  (Measure UBit (On Bit) (Uniform))', '  (Measure UTri (On Tri) (Uniform))']
body, reqs, truth = [], [], {}
for i in range(N):
    k = rnd.choice([2, 3, 3, 4]); mem = []; partial = i % 3 == 2
    for j in range(k):
        c = rnd.choice(['Bit', 'Bit', 'Tri']) if k < 4 else 'Bit'
        t = 'SharpTri' if c == 'Tri' else rnd.choice(['SharpBit', 'SharpBit', 'CoarseBit'])
        mem.append(('M%d' % (j + 1), c, t, 'UTri' if c == 'Tri' else 'UBit'))
    ws = [rnd.randint(1, 4) for _ in mem]; W = [Q(x, sum(ws)) for x in ws]
    # latent mode (odd i): c(a, b) = max(0, 1 - |p_a - p_b|) on a line is Lukasiewicz-transitive (triangle inequality),
    # so full hives are coherent (Checked) and partial ones have a completion (CompleteHive Checked)
    latent = i % 2 == 1; OFF = [Q(0), Q(1, 4), Q(1, 3), Q(1, 2), Q(2, 3), Q(3, 4), Q(1), Q(3, 2)]; pos = {}
    for m in mem:
        o = rnd.choice(OFF)
        for v in CAR[m[1]]: pos[(m[0], v)] = o if m[2] == 'CoarseBit' else o + 2 * v
    nodes = [(m[0], v) for m in mem for v in CAR[m[1]]]; wt = {}; H = {}
    for m, w in zip(mem, W):
        for v in CAR[m[1]]: wt[(m[0], v)] = w / len(CAR[m[1]])
        for a in CAR[m[1]]:
            for b in CAR[m[1]]: H[((m[0], a), (m[0], b))] = Q(1 if a == b or m[2] == 'CoarseBit' else 0)
    hv = ['  (KernelHive G%d' % i] + ['    (Member %s %s %s %s)' % m for m in mem]; forced = False
    pairs = [(a, b) for a in range(k) for b in range(a + 1, k)]; skip = rnd.choice(pairs) if partial else None
    for a, b in pairs:
        ma, mb = mem[a], mem[b]; kn = 'K%d_%d_%d' % (i, a, b); ents = []
        for x in CAR[ma[1]]:
            for y in CAR[mb[1]]:
                e = max(Q(0), 1 - abs(pos[(ma[0], x)] - pos[(mb[0], y)])) if latent else rnd.choice(DEG)
                if not latent and not forced and (a, b) != skip: e = Q(1, 2); forced = True   # at least one graded measured degree
                ents.append('(%d %d %s)' % (x, y, rs(e)))
                if (a, b) != skip: H[((ma[0], x), (mb[0], y))] = H[((mb[0], y), (ma[0], x))] = e
        body.append('  (CrossKernel %s (Left %s) (Right %s) (Entries %s))' % (kn, ma[1], mb[1], ' '.join(ents)))
        hv.append('    (Correspondence %s %s %s %s)' % (ma[0], mb[0], kn, 'Unmeasured' if (a, b) == skip else 'Measured'))
    hv.append('    (Weights %s))' % ' '.join('(%s %s)' % (m[0], rs(w)) for m, w in zip(mem, W)))
    body += hv; truth['G%d' % i] = (nodes, wt, H, partial)
    ops = ['CompleteHive'] if partial else ['CheckKernelCoherence', 'ConsensusCost', 'LeastCoherentRefinement', 'Holonomy']
    for op in ops:
        reqs.append('!(dc.run GradedProbe (%s G%d%s))' % (op, i, ' (Cycle %s)' % ' '.join(m[0] for m in mem) if op == 'Holonomy' else ''))
fx = os.path.join(od, 'probe_graded.metta'); open(fx, 'w').write('\n'.join(hdr + body) + ')\n' + '\n'.join(reqs) + '\n')
out = os.path.join(od, 'probe_graded.out')
with open(out, 'w') as f: subprocess.run([os.path.join(ROOT, 'build/dcalc/dcalc'), '--beyond-release', fx], stdout=f, stderr=subprocess.STDOUT, timeout=600)
rp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6graded.py'), fx, out], capture_output=True, text=True)
print(rp.stdout.strip().splitlines()[-1])
try:
    from sympy import Rational, Symbol
    from sympy.solvers.simplex import lpmax
    HAVE_SYMPY = True
except ImportError:
    HAVE_SYMPY = False
    print('SKIP  sympy LP cross-check of LeastCoherentRefinement: sympy not installed (pip install sympy); LCR rows still checked by the replayer LP certificate')
def S(q): return Rational(q.numerator, q.denominator)
st = {'rows': 0, 'agree': 0, 'disagree': 0, 'unsupported_ok': 0, 'refuted': 0, 'checked': 0, 'complete_checked': 0, 'graded_checked': 0}; tam = []
for line in open(out).read().splitlines():
    if ' => ' not in line: continue
    st['rows'] += 1; lq = R.read_all(line.split(' => ', 1)[0].split(' ', 1)[1])[0]; op, nm = lq[0], lq[1]
    res = R.read_all(line.split(' => ', 1)[1])[0]; s = R.field(res, 'Status')[1]
    nodes, wt, H, partial = truth[nm]; F = closure(nodes, H); ok = False
    if op == 'CheckKernelCoherence':
        bad = any(H[(a, c)] < lk(H[(a, b)], H[(b, c)]) for a in nodes for b in nodes for c in nodes)
        ok = s == ('Refuted' if bad else 'Checked'); st['refuted' if bad else 'checked'] += 1
    elif op == 'ConsensusCost':
        ok = s == 'Checked' and R.rat(R.field(res, 'Value')[1]) == sum(wt[a] * wt[b] * (F[(a, b)] - H[(a, b)]) for a in nodes for b in nodes if a != b)
    elif op == 'Holonomy':
        ok = s == 'Checked'
    elif op == 'CompleteHive':
        if any(H[kk] < F[kk] for kk in H): ok = s == 'Unsupported'; st['unsupported_ok'] += ok
        else: ok = s == 'Checked' and R.rat(R.field(res, 'Value')[1]) == sum(wt[a] * wt[b] * F[(a, b)] for a in nodes for b in nodes if (a, b) not in H)
    elif op == 'LeastCoherentRefinement' and not HAVE_SYMPY:
        ok = s == 'Checked'; st['lp_skipped'] = st.get('lp_skipped', 0) + 1
    elif op == 'LeastCoherentRefinement':
        X = {}; obj = 0; T = Q(0); cons = []
        for i2, a in enumerate(nodes):
            X[(a, a)] = 1
            for b in nodes[i2 + 1:]:
                if H[(a, b)] > 0:
                    v = Symbol('x%d' % len(cons)); cons += [v >= 0, v <= S(H[(a, b)])]; X[(a, b)] = X[(b, a)] = v
                    obj += S(wt[a] * wt[b]) * v; T += wt[a] * wt[b] * H[(a, b)]
                else: X[(a, b)] = X[(b, a)] = 0
        for a in nodes:
            for b in nodes:
                for c in nodes:
                    if len({a, b, c}) == 3:
                        e = X[(a, c)] - X[(a, b)] - X[(b, c)] + 1
                        if getattr(e, 'free_symbols', None): cons.append(e >= 0)
        P = lpmax(obj, cons)[0] if cons else Rational(0)
        ok = s == 'Checked' and S(R.rat(R.field(res, 'Value')[1])) == 2 * (S(T) - P)
    if op == 'CompleteHive' and s == 'Checked': st['complete_checked'] += 1
    if s == 'Checked' and any(v not in (0, 1) for v in H.values()): st['graded_checked'] += 1
    st['agree' if ok else 'disagree'] += 1
    if not ok: print('DISAGREE', op, nm, s, line[:300])
    if s == 'Checked' and '(Value (Rat ' in line:
        j = line.index('(Value (Rat ') + 12; p, q = line[j:line.index(')', j)].split(); v = Q(int(p), int(q)) + Q(1, 97)
        tam.append(line[:j - 5] + '(Rat %d %d)' % (v.numerator, v.denominator) + line[line.index(')', j) + 1:])
tf = out + '.tampered'; open(tf, 'w').write('\n'.join(tam) + '\n')
tp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6graded.py'), fx, tf], capture_output=True, text=True)
rej = sum(1 for l in tp.stdout.splitlines() if l.startswith('REJECT'))
print('stats', st, 'tampered', len(tam), 'rejected', rej)
good = 'PASS' in rp.stdout.splitlines()[-1] and st['disagree'] == 0 and st['rows'] == len(reqs) and rej == len(tam) and tam and st['checked'] and st['refuted'] and st['complete_checked'] and st['unsupported_ok']
print('probe_graded: %s' % ('PASS' if good else 'FAIL')); sys.exit(0 if good else 1)
