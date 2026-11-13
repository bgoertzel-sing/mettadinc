#!/usr/bin/env python3
"""M6-rest random probe for (Associator Hive Mi Mj Mk) beyond the fixtures.
Random fully measured crisp hives (3-4 members, Bit/Tri carriers) and random ordered member triples -> dcalc.
Each row is compared with an independent direct composition computed here (not via replay_m6), replayed by
replay_m6rest.py, and tampered (first Entry difference flipped) -> the replayer must reject every tampered row.
usage: probe_assoc.py N seed outdir"""
import os, random, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
N, seed, od = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; rnd = random.Random(seed); os.makedirs(od, exist_ok=True)
CAR = {'Bit': [0, 1], 'Tri': [0, 1, 2]}
hdr = ['(DC.Module AssocProbe', '  (Profile Graded)', '  (Use Hives)', '  (Carrier Bit (Of Nat) (Enum 0 1))', '  (Carrier Tri (Of Nat) (Enum 0 1 2))',
       '  (Tolerance SharpBit (On Bit) (Discrete))', '  (Tolerance SharpTri (On Tri) (Discrete))',
       '  (Measure UBit (On Bit) (Uniform))', '  (Measure UTri (On Tri) (Uniform))']
body, reqs, truth = [], [], []
for i in range(N):
    k = rnd.choice([3, 3, 4]); mem = []
    for j in range(k):
        c = rnd.choice(['Bit', 'Bit', 'Tri']); mem.append(('M%d' % (j + 1), c, 'SharpTri' if c == 'Tri' else 'SharpBit', 'UTri' if c == 'Tri' else 'UBit'))
    H = {}; hv = ['  (KernelHive A%d' % i] + ['    (Member %s %s %s %s)' % m for m in mem]
    for a in range(k):
        for b in range(a + 1, k):
            ma, mb = mem[a], mem[b]; kn = 'K%d_%d_%d' % (i, a, b); ents = []
            for x in CAR[ma[1]]:
                for y in CAR[mb[1]]:
                    e = 1 if rnd.random() < 0.45 else 0; ents.append('(%d %d %d)' % (x, y, e)); H[(ma[0], x, mb[0], y)] = H[(mb[0], y, ma[0], x)] = e
            body.append('  (CrossKernel %s (Left %s) (Right %s) (Entries %s))' % (kn, ma[1], mb[1], ' '.join(ents)))
            hv.append('    (Correspondence %s %s %s Measured)' % (ma[0], mb[0], kn))
    body += [h + (')' if n == len(hv) - 1 else '') for n, h in enumerate(hv)]
    for _ in range(2):
        t = rnd.sample(range(k), 3); I, J, K = (mem[x] for x in t)
        exp = {}
        for a in CAR[I[1]]:
            for c in CAR[K[1]]:
                d = H[(I[0], a, K[0], c)]; comp = 1 if any(H[(I[0], a, J[0], b)] and H[(J[0], b, K[0], c)] for b in CAR[J[1]]) else 0
                exp[(a, c)] = (d, comp, d - comp)
        reqs.append('!(dc.run AssocProbe (Associator A%d %s %s %s))' % (i, I[0], J[0], K[0])); truth.append(exp)
fx = os.path.join(od, 'probe_assoc.metta'); open(fx, 'w').write('\n'.join(hdr + body) + ')\n' + '\n'.join(reqs) + '\n')
out = os.path.join(od, 'probe_assoc.out')
with open(out, 'w') as f: subprocess.run([os.path.join(ROOT, 'build/dcalc/dcalc'), '--beyond-release', fx], stdout=f, stderr=subprocess.STDOUT, timeout=600)
lines = [l for l in open(out).read().splitlines() if ' => ' in l]
st = {'rows': len(lines), 'Checked': 0, 'agree': 0, 'disagree': 0, 'nonzero': 0}; tam = []
for line, exp in zip(lines, truth):
    if '(Status Checked)' not in line: st['disagree'] += 1; print('NOT CHECKED', line[:200]); continue
    st['Checked'] += 1
    got = {(int(a), int(c)): (int(d), int(p), int(x)) for a, c, d, p, x in re.findall(r'\(Entry (\d+) (\d+) (-?\d+) (-?\d+) (-?\d+)\)', line)}
    ok = got == exp and ('(Zero True)' in line) == all(v[2] == 0 for v in exp.values())
    st['agree' if ok else 'disagree'] += 1
    if not all(v[2] == 0 for v in exp.values()): st['nonzero'] += 1
    if not ok: print('DISAGREE', line[:200])
    m = re.search(r'\(Entry (\d+) (\d+) (-?\d+) (-?\d+) (-?\d+)\)', line)
    if m: tam.append(line[:m.start()] + '(Entry %s %s %s %s %d)' % (m.group(1), m.group(2), m.group(3), m.group(4), int(m.group(5)) + 1) + line[m.end():])
rp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), fx, out], capture_output=True, text=True)
print(rp.stdout.strip().splitlines()[-1] if rp.stdout.strip() else rp.stderr[-400:])
tf = out + '.tampered'; open(tf, 'w').write('\n'.join(tam) + '\n')
tp = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), fx, tf], capture_output=True, text=True)
rej = sum(1 for l in tp.stdout.splitlines() if l.startswith('REJECT'))
print('stats', st, 'tampered', len(tam), 'rejected', rej)
good = rp.returncode == 0 and st['disagree'] == 0 and st['Checked'] == len(truth) == st['rows'] and rej == len(tam) > 0 and st['nonzero'] > 0
print('probe_assoc: %s' % ('PASS' if good else 'FAIL')); sys.exit(0 if good else 1)
