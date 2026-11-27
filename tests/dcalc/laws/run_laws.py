#!/usr/bin/env python3
"""Laws gates (t-2026-11-27-mettadinc-laws): exact laws/means from dcalc vs hand-checked rationals and vs
the reference evaluator metta_eval.py (docs/e0 ex1 bundle) on every reward-law cell."""
import os, re, subprocess, sys
from fractions import Fraction as F
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build', 'dcalc', 'dcalc'))
sys.path.insert(0, os.path.join(ROOT, 'docs/e0/docs/03_four_worked_examples/validation_bundles/ex1_belief_memory'))
from metta_eval import World
fails = 0
def report(name, ok, detail=''):
    global fails
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else '  -- %r' % (detail,)))
    fails += 0 if ok else 1
def q(s):
    m = re.fullmatch(r'\(Rat (-?\d+) (\d+)\)', s.strip())
    return F(int(m.group(1)), int(m.group(2))) if m else F(int(s))
def results(path, beyond=True):
    p = subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [path], capture_output=True, text=True, timeout=60)
    out = []
    for chunk in p.stdout.split('(Status ')[1:]:
        st = chunk.split()[0].rstrip(')')
        law = {}
        m = re.search(r'\(Law ((?:\((?:\w+) (?:\(Rat -?\d+ \d+\)|-?\d+)\) ?)*)\) \(Mean ((?:\(Rat -?\d+ \d+\)|-?\d+))\)', chunk)
        if m:
            for v, w in re.findall(r'\((\w+) (\(Rat -?\d+ \d+\)|-?\d+)\)', m.group(1)):
                if q(w): law[int(v) if v.lstrip('-').isdigit() else v] = q(w)
        rs = re.search(r'\(Reason "([^"]*)"', chunk)
        out.append((st, law, q(m.group(2)) if m else None, rs.group(1) if rs else ''))
    return p.returncode, out
# ---- values: hand-checked
VAL = os.path.join(HERE, 'fixtures', 'laws_values.metta')
WANT = [({0: F(1, 3), 1: F(2, 3)}, F(2, 3)),       # Image (If (Eq $b 1) 0 1) (Coin 1/3)
        ({0: F(5, 6), 1: F(1, 6)}, F(1, 6)),       # Image (Mul ..) (Indep (Coin 1/2) (Coin 1/3))
        ({0: F(3, 5), 1: F(2, 5)}, F(2, 5)),       # Coin (Div (Add 1 1) 5)
        ({1: F(1)}, F(1)),                         # LawOf (Point 1)
        ({0: F(4, 5), 1: F(1, 5)}, F(1, 5)),       # Coin (Expect (Image (Mul $b 2/5) (Coin 1/2))) = Coin 1/5
        ({0: F(77, 150), 1: F(73, 150)}, F(73, 150))]  # uniform prior over A..E
rc, out = results(VAL)
report('values: dcalc exit 0, %d requests' % len(WANT), rc == 0 and len(out) == len(WANT), (rc, len(out)))
for i, (law, mean) in enumerate(WANT):
    got = out[i] if i < len(out) else ('?', {}, None, '')
    report('values: request %d Checked, law %s mean %s' % (i + 1, law, mean), got[0] == 'Checked' and got[1] == law and got[2] == mean, got)
# ---- reference-evaluator agreement: every cell of rl, and the prior averages
W = World(VAL); mod = 'LawsValues'; _, rl = W.lookup(mod, 'rl')
cells = {s: W.apply(mod, rl, [(s, 'K')]) for s in 'ABCDE'}
for i, (s, pr) in enumerate(zip('ABCDE', ['Pa', 'Pb', 'Pc', 'Pd', 'Pe'])):
    ref = {v: m for v, m in cells[s].items() if m}
    report('agree: ref evaluator law of rl(%s, K) = dcalc (Under %s)' % (s, pr), i < len(out) and ref == out[i][1], (ref, out[i][1] if i < len(out) else None))
mu = W.measure(mod, 'Pu'); avg = {}
for s, w in mu.items():
    for v, m in cells[s].items(): avg[v] = avg.get(v, F(0)) + w * m
avg = {v: m for v, m in avg.items() if m}
report('agree: ref evaluator prior average (Under Pu) = dcalc', len(out) > 5 and avg == out[5][1] and sum(v * m for v, m in avg.items()) == out[5][2], (avg, out[5] if len(out) > 5 else None))
# ---- negative gates: a bad law is InvalidInput naming the reason, never a value
NEG = [('Mp', 'the probability of a Coin is outside [0, 1]'),      # Coin (Add 1/2 1) = 3/2
       ('Mz', 'the probability of a Coin is not a rational'),      # Coin (Div 1 0): division by zero does not evaluate
       ('Mn', 'the probability of a Coin is outside [0, 1]'),      # Coin (Sub 0 1/3) = -1/3
       ('Mo', 'a law value is outside the target carrier')]        # Image (Add $b 1): value 2 not in Bit
rc, out = results(os.path.join(HERE, 'fixtures', 'laws_neg.metta'))
report('neg: dcalc exit 0, %d requests' % len(NEG), rc == 0 and len(out) == len(NEG), (rc, len(out)))
for i, (m, why) in enumerate(NEG):
    got = out[i] if i < len(out) else ('?', {}, None, '')
    report('neg: %s InvalidInput, no law, reason names %r' % (m, why), got[0] == 'InvalidInput' and not got[1] and got[2] is None and m in got[3] and why in got[3], got)
rc, out = results(os.path.join(HERE, 'fixtures', 'laws_neg_var.metta'))
got = out[0] if out else ('?', {}, None, '')
report('neg: free variable in an Image body is InvalidInput at admission (unbound variable $q)', len(out) == 1 and got[0] == 'InvalidInput' and not got[1] and 'unbound variable $q' in got[3], (rc, out))
# ---- review 1: LawOf of a declared measure (doc03 l.2174), Expect over zero-mass outcomes, a failing Indep
R1 = os.path.join(HERE, 'fixtures', 'laws_review1.metta')
WANT1 = [({0: F(1, 4), 1: F(3, 4)}, F(3, 4)),   # (LawOf Half): the masses of measure Half
         ({0: F(1)}, F(0)),                     # (Coin (Expect (Coin 0))): outcome 1 has mass 0
         ({1: F(1)}, F(1)),                     # (Coin (Expect (LawOf Z))): Z has a zero-mass outcome 0
         ({0: F(1, 2), 1: F(1, 2)}, F(1, 2))]   # (Coin (Expect (Image $b (Mul $b 1/2) (Coin 1))))
rc, out = results(R1)
report('review1: dcalc exit 0, 5 requests', rc == 0 and len(out) == 5, (rc, len(out)))
for i, (law, mean) in enumerate(WANT1):
    got = out[i] if i < len(out) else ('?', {}, None, '')
    report('review1: request %d Checked, law %s mean %s' % (i + 1, law, mean), got[0] == 'Checked' and got[1] == law and got[2] == mean, got)
W1 = World(R1); _, rl1 = W1.lookup('LawsR1', 'rl')
for i, s_ in enumerate('ABCD'):
    ref = {v: m for v, m in W1.apply('LawsR1', rl1, [(s_, 'K')]).items() if m}
    report('review1: ref evaluator law of rl(%s, K) = dcalc' % s_, i < len(out) and ref == out[i][1], (ref, out[i][1] if i < len(out) else None))
got = out[4] if len(out) > 4 else ('?', {}, None, '')
report('review1: failing Indep (non-law argument) is InvalidInput, no law', got[0] == 'InvalidInput' and not got[1] and 'not a law' in got[3], got)
# ---- review 1: a map call inside a law term is Unsupported with a reason, never InvalidInput or a value
rc, out = results(os.path.join(HERE, 'fixtures', 'laws_mapcall.metta'))
report('mapcall: dcalc exit 0, 4 requests', rc == 0 and len(out) == 4, (rc, len(out)))
for i, form in enumerate(['Coin (pr A)', 'Image (inc $b)', 'Indep (lw A)', 'bare (lw A)']):
    got = out[i] if i < len(out) else ('?', {}, None, '')
    report('mapcall: %s is Unsupported, reason names the map call' % form, got[0] == 'Unsupported' and not got[1] and 'map call inside a law term' in got[3], got)
# ---- review 2: computed Point values, map calls in a Point, admitted library forms in a law leaf, bare Expect
rc, out = results(os.path.join(HERE, 'fixtures', 'laws_review2.metta'))
report('review2: dcalc exit 0, 6 requests', rc == 0 and len(out) == 6, (rc, len(out)))
for i, form in enumerate(['Point (Add 0 1)', 'Point (If (Eq 1 1) 1 0)']):
    got = out[i] if i < len(out) else ('?', {}, None, '')
    report('review2: %s is Checked, law {1:1} mean 1' % form, got[0] == 'Checked' and got[1] == {1: F(1)} and got[2] == F(1), got)
for i, (form, why) in enumerate([('Point (pr A)', 'map call inside a law term'), ('Image (Switch ..) under Families', '(Switch ..) inside a law term'), ('Image (Quot ..) under NatArith', '(Quot ..) inside a law term')]):
    got = out[i + 2] if i + 2 < len(out) else ('?', {}, None, '')
    report('review2: %s is Unsupported, reason names %r' % (form, why), got[0] == 'Unsupported' and not got[1] and why in got[3], got)
got = out[5] if len(out) > 5 else ('?', {}, None, '')
report('review2: bare (Expect L) case body is InvalidInput with a sub-reason', got[0] == 'InvalidInput' and not got[1] and '(Expect L) is a number, not a law' in got[3], got)
print('run_laws: %s' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
