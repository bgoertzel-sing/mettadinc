#!/usr/bin/env python3
"""M6-rest random probe: registered composition law of the Linear arrow kind (arrow_kinds, spec Table 4 l.893-912)
beyond the fixture.  Random signed / positive 2x2 and 3x3 matrices between machines with identity kernels -> dcalc
CheckLinearArrow L, K and Then L K.  The Then grade must equal the law (lL lK, rL lK + lL rK) recomputed here
(Fractions) from the two premises' own grades; a tampered Then grade must not satisfy it.
usage: probe_arrows.py N seed outdir"""
import os, random, subprocess, sys
from fractions import Fraction as Q
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
sys.path.insert(0, os.path.join(HERE, '..', 'm6')); import replay_m6 as R
N, seed, od = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; rnd = random.Random(seed); os.makedirs(od, exist_ok=True)
fx = os.path.join(od, 'probe_arrows.metta'); out = os.path.join(od, 'probe_arrows.out'); src, runs = [], []
for i in range(N):
    n = rnd.choice([2, 3]); S = ['s%d' % k for k in range(n)]
    def mat(pos):
        rows = []
        for a in S:
            # rows sum to 1 (CheckLinearArrow refutes otherwise); Positive rows are nonnegative
            if pos:
                k = [rnd.randint(0, 3) for _ in S]
                if not any(k): k[rnd.randrange(n)] = 1
                v = [Q(x, sum(k)) for x in k]
            else:
                v = [Q(rnd.randint(-3, 3)) for _ in S[:-1]]; v.append(1 - sum(v))
            ents = ' '.join('(%s %s)' % (b, str(x.numerator) if x.denominator == 1 else '(Rat %d %d)' % (x.numerator, x.denominator)) for b, x in zip(S, v))
            rows.append('(%s %s)' % (a, ents))
        return '(Matrix (Rows %s))' % ' '.join(rows)
        
    kl, kk = rnd.choice(['Signed', 'Positive']), rnd.choice(['Signed', 'Positive'])
    src.append('''(DC.Module Lin%d
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum %s))
  (Carrier Unit (Of Nat) (Enum 0))
  (Map blank (From S) (To Unit) (Cases %s))
  (TransitionKernel Stay (From S) (To S) %s)
  (Machine M (States S) (Observe blank blank) (Action step Stay))
  (Machine N (States S) (Observe blank blank) (Action step Stay))
  (Machine P (States S) (Observe blank blank) (Action step Stay))
  (LinearArrow L (Source M) (Target N) (Kind %s) %s)
  (LinearArrow K (Source N) (Target P) (Kind %s) %s)
  (Derive LChecked (CheckLinearArrow L))
  (Derive KChecked (CheckLinearArrow K))
  (Derive LK (Then (Output LChecked Value) (Output KChecked Value))))''' % (i, ' '.join(S), ' '.join('(%s 0)' % a for a in S),
        ' '.join('(Row %s (Mass %s 1))' % (a, a) for a in S), kl, mat(kl == 'Positive'), kk, mat(kk == 'Positive')))
    runs += ['!(dc.run Lin%d LChecked)' % i, '!(dc.run Lin%d KChecked)' % i, '!(dc.run Lin%d LK)' % i]
open(fx, 'w').write('\n'.join(src) + '\n' + '\n'.join(runs) + '\n')
with open(out, 'w') as f: subprocess.run([os.path.join(ROOT, 'build/dcalc/dcalc'), '--beyond-release', fx], stdout=f, stderr=subprocess.STDOUT, timeout=600)
L = [l for l in open(out).read().splitlines() if ' => ' in l]
def grade(line):
    res = R.read_all(line.split(' => ', 1)[1])[0]; st = R.field(res, 'Status')[1]
    v = R.field(res, 'Value'); la = R.field(v[1], 'Grade') if v and len(v) > 1 and isinstance(v[1], list) else None   # non-Checked rows carry an empty (Value)
    return st, (R.rat(R.field(la, 'Lambda')[1]), R.rat(R.field(la, 'Rho')[1])) if la else None
st = {'triples': 0, 'composed': 0, 'agree': 0, 'disagree': 0, 'premise_not_checked': 0, 'tamper_caught': 0}
for t in range(0, len(L) - 2, 3):
    st['triples'] += 1; (s1, g1), (s2, g2), (s3, g3) = grade(L[t]), grade(L[t + 1]), grade(L[t + 2])
    if s1 != 'Checked' or s2 != 'Checked' or not g1 or not g2:
        st['premise_not_checked'] += 1
        if s3 == 'Checked': st['disagree'] += 1; print('THEN CHECKED WITHOUT PREMISES', L[t + 2][:200])
        continue
    st['composed'] += 1; law = (g1[0] * g2[0], g1[1] * g2[0] + g1[0] * g2[1])
    ok = s3 == 'Checked' and g3 == law; st['agree' if ok else 'disagree'] += 1
    if not ok: print('DISAGREE', g1, g2, g3, law, L[t + 2][:200])
    if (g3[0], g3[1] + Q(1, 7)) != law: st['tamper_caught'] += 1
print('stats', st)
good = len(L) == 3 * N and st['disagree'] == 0 and st['composed'] > N // 2 and st['tamper_caught'] == st['composed']
print('probe_arrows: %s' % ('PASS' if good else 'FAIL')); sys.exit(0 if good else 1)
