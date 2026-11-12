#!/usr/bin/env python3
"""M4 claim rows S01-S07 and negative gates (t-2026-11-11-mettadinc-m4).

Runs build/dcalc/dcalc on seven_state.metta, once by default (release 1: every
request must answer Unsupported) and once with --beyond-release (the M4
answers).  Negative cases are inline source mutations written to DCALC_OUT;
no fixture under tests/dcalc/mutations/ is named.  Exit 0 iff all pass."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FIX = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures/seven_state.metta')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m4'))
fails = 0
def report(name, ok, note=''):
    global fails
    fails += not ok; print('%-66s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
def run(src, tag, beyond=True):
    os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, tag + '.metta'); open(p, 'w').write(src)
    r = subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [p], capture_output=True, text=True, timeout=120)
    open(os.path.join(OUT, tag + '.out'), 'w').write(r.stdout)
    lines = {}
    for line in r.stdout.splitlines():
        if ' => ' in line: head = line.split(' => ', 1)[0]; mod, req = head.split(' ', 1); lines[(mod, req)] = line
    return lines
def st(line): m = re.search(r'\(Result \(Status (\w+)\)', line or ''); return m.group(1) if m else 'missing'
def has(line, pat): return re.search(pat, line or '') is not None

src = open(FIX, encoding='utf-8').read()
MB = '(MeasureBehavioral MergeXY (Discount (Rat 9 10)))'
REQS = ['Bisimulation', 'TraceClasses', 'Behavioral', MB, 'Trace', 'Linear', 'Positive']
# release 1 (default): the fixture header requires Unsupported for every request
D = run(src, 'default', beyond=False)
report('R1 default: all seven requests Unsupported', all(st(D.get(('SevenState', q))) == 'Unsupported' for q in REQS),
       ' '.join(st(D.get(('SevenState', q))) for q in REQS))
L = run(src, 'fixture')
POL = r'\(Policy M4-StochasticReplay\) \(Replayed True\)'
rows = [('S01', 'Bisimulation', 'Checked', r'\(Classes 7\).*\(Kind StrongLumping\)'),
        ('S02', 'TraceClasses', 'Checked', r'\(Block x y\).*\(Classes 6\)'),
        ('S03', 'Behavioral', 'Refuted', r'\(BehavioralDefect \(Rat 1 2\)\).*\(ModalTestWitness \(Pair y x\) \(Phi \(x \(Rat 1 2\)\) \(y 0\)\)\)'),
        ('S04', MB, 'Checked', r'\(BehavioralDefect \(Rat 81 200\)\).*\(Discount \(Rat 9 10\)\)'),
        ('S05', 'Trace', 'Checked', r'\(TraceEquivalent True\)'),
        ('S06', 'Linear', 'Checked', r'\(Dimension 5\).*\(Minor \(Columns( \w+){5}\) \(Determinant (?!0\))'),
        ('S07', 'Positive', 'Checked', r'\(Interval 5 5\).*\(SignedMinimum 5\).*\(Candidate Lpos Replayed \(States 5\)\)')]
for cid, req, want, pat in rows:
    line = L.get(('SevenState', req)); s = st(line)
    report('%s %s' % (cid, req[:40]), s == want and has(line, pat) and has(line, POL), s)
# neg 1 (S03, S05): the behavioral refutation carries a modal test witness, never a trace-event/word witness,
# and the trace check is not refuted because the behavioral one is
b3, t5 = L.get(('SevenState', 'Behavioral')), L.get(('SevenState', 'Trace'))
report('neg 1: behavioral refutation uses ModalTestWitness, trace stays Checked',
       has(b3, r'\(ModalTestWitness ') and not has(b3, r'TraceEventWitness|\(Word ') and st(t5) == 'Checked', st(t5))
# neg 2 (S07): the positive candidate is never reported as a minimum without the signed lower bound
p7 = L.get(('SevenState', 'Positive')); m = re.search(r'\(Interval (\d+) (\d+)\).*\(SignedMinimum (\d+)\)', p7 or '')
report('neg 2: positive interval lower bound = signed minimum', bool(m) and m.group(1) == m.group(3), m.groups() if m else 'no interval')
# neg 5: negative masses, wrong row sums, float probabilities and duplicate outcome keys are InvalidInput
ROW = '(Row y (Mass w 1))'; assert src.count(ROW) == 1
muts = {'negmass': '(Row y (Mass w 2) (Mass p -1))', 'rowsum': '(Row y (Mass w (Rat 1 2)))',
        'float': '(Row y (Mass w 1.0))', 'dupkey': '(Row y (Mass w (Rat 1 2)) (Mass w (Rat 1 2)))'}
for k, v in muts.items():
    V = run(src.replace(ROW, v), 'neg5-' + k); ss = [st(V.get(('SevenState', q))) for q in REQS]
    report('neg 5: %s -> InvalidInput on every request' % k, ss and all(x == 'InvalidInput' for x in ss), ' '.join(sorted(set(ss))))
# neg 8: unbounded trace equivalence is not Unsupported here, and the six-class trace partition is not the Markov quotient
b1 = L.get(('SevenState', 'Bisimulation'))
report('neg 8: trace answered (not Unsupported); bisimulation keeps 7 classes, not 6',
       st(t5) != 'Unsupported' and st(L.get(('SevenState', 'TraceClasses'))) != 'Unsupported' and has(b1, r'\(Classes 7\)') and not has(b1, r'\(Block x y\)'))


# ---- V01-V04: evolution_archive.metta (Use Search, beyond release) ----
EFIX = os.path.join(os.path.dirname(FIX), 'evolution_archive.metta')
esrc = open(EFIX, encoding='utf-8').read()
E = run(esrc, 'evolution')
vrows = [('V01', '(CheckUpdates FitnessOnly)', 'Refuted', r'\(UpdatesStable False\).*\(Kind UpdateWitness\) \(Pair G00 G01\) \(Action mutate\) \(Class \(score 1\)\) \(Masses 0 \(Rat 1 2\)\)'),
         ('V02', 'Repaired', 'Checked', r'\(Partition \(Block G00\) \(Block G01 G10\) \(Block G11\)\) \(Classes 3\)'),
         ('V03', 'ControlledClasses', 'Checked', r'\(Classes 4\)'),
         ('V04', 'Discovery', 'Checked', r'\(ExpectedProposals 5\) \(Until \(Hits G11\)\)')]
for cid, req, want, pat in vrows:
    line = E.get(('EvolutionArchive', req)); s_ = st(line)
    report('%s %s' % (cid, req[:40]), s_ == want and has(line, pat) and has(line, POL), s_)

# ---- R01-R06: regime_repair.metta (Use Decisions, beyond release) ----
RFIX = os.path.join(os.path.dirname(FIX), 'regime_repair.metta')
G = run(open(RFIX, encoding='utf-8').read(), 'regime')
rrows = [('R01', '(CheckEqual (AverageModel Old (Under Fair)) (AverageModel New (Under Fair)))', 'Checked', r'\(Equal True\).*\(Kind ExactLawEquality\)'),
         ('R02', '(AverageModel New (Under Skewed))', 'Checked', r'\(L \(Law \(0 \(Rat 1 4\)\) \(1 \(Rat 3 4\)\)\) \(Mean \(Rat 3 4\)\)\) \(R \(Law \(0 \(Rat 3 4\)\) \(1 \(Rat 1 4\)\)\) \(Mean \(Rat 1 4\)\)\)'),
         ('R03', '(InduceExact Coarse)', 'Refuted', r'\(Exact False\).*\(Kind ObservationWitness\) \(Pair Plus Minus\) \(Observation reward-law\)'),
         ('R04', '(OptimizePolicy New (Through Coarse) (Under Fair))', 'Checked', r'\(Optimum \(Rat 1 2\)\)'),
         ('R05', '(OptimizePolicy New (Under Fair))', 'Checked', r'\(Optimum 1\)'),
         ('R06', '(EvaluatePolicy New (With Sensor) (Under Fair))', 'Checked', r'\(NetValue \(Rat 17 20\)\).*\(GainOverUninformed \(Rat 7 20\)\)')]
for cid, req, want, pat in rrows:
    line = G.get(('RegimeRepair', req)); s_ = st(line)
    report('%s %s' % (cid, req[:48]), s_ == want and has(line, pat) and has(line, POL), s_)

# ---- O01-O04: certificate_limits.metta AdaptiveProbe (beyond release) ----
CFIX = os.path.join(os.path.dirname(FIX), 'certificate_limits.metta')
csrc = open(CFIX, encoding='utf-8').read()
CL = run(csrc, 'certlimits')
orows = [('O01', '(MeasureTrace MergeX (Horizon (Steps 2)))', 'Checked', r'\(TraceDefect \(Rat 1 2\)\).*\(Policies FixedWords\)'),
         ('O02', '(CheckTrace MergeX (Horizon (Steps 2)) (Within (Rat 3 4)))', 'Checked', r'\(WithinBound True\) \(TraceDefect \(Rat 1 2\)\)'),
         ('O03', '(CheckTrace MergeX (Horizon (Steps 2)) (Policies ObservationBased) (Within (Rat 3 4)))', 'Refuted',
          r'\(WithinBound False\).*\(PolicyTreeWitness \(Pair x x2\) \(Do a \(On 1 \(Do b\)\) \(On 2 \(Do c\)\)\) \(Event \(LastReport 3\)\) \(Probabilities 1 0\)\)'),
         ('O04', '(MeasureTrace MergeX (Horizon (Steps 2)) (Policies ObservationBased))', 'Checked', r'\(TraceDefect 1\).*\(Policies ObservationBased\)')]
for cid, req, want, pat in orows:
    line = next((l for (mo, rq), l in CL.items() if mo == 'AdaptiveProbe' and ' '.join(rq.split()) == req), None); s_ = st(line)
    report('%s %s' % (cid, req[:48]), s_ == want and has(line, pat) and has(line, POL), s_)

# ---- U01-U04: certificate_limits.metta UnattainedSupremum (beyond release) ----
UPOL = r'\(Policy M4-StochasticReplay\) \(Replayed False\)'
urows = [('U01', '(MeasureBehavioral JoinXY)', 'Unknown', r'\(BehavioralInterval \(Lower \(Rat (\d+) \1\d*\)\)|\(BehavioralInterval \(Lower \(Rat \d+ \d+\)\) \(Upper 1\)\).*\(Closed False\)', UPOL),
         ('U02', '(MeasureBehavioral JoinXY (Horizon (Steps 3)))', 'Checked', r'\(BehavioralDefect \(Rat 7 8\)\) \(Horizon \(Steps 3\)\).*\(Kind LayeredPrefixpoint\).*\(Depth 3\)', POL),
         ('U03', '(CheckBehavioral JoinXY (Within (Rat 99 100)))', 'Refuted', r'\(WithinBound False\) \(BehavioralDefect \(Rat 127 128\)\).*\(Depth 7\) \(Separation \(Rat 127 128\)\)', POL),
         ('U04', '(MeasureBehavioral JoinXY (Discount (Rat 1 2)))', 'Checked', r'\(BehavioralDefect \(Rat 1 3\)\) \(Discount \(Rat 1 2\)\).*\(Kind CouplingPrefixpoint\) \(DualPostfixpoint Replayed\)', POL)]
for cid, req, want, pat, pol in urows:
    line = next((l for (mo, rq), l in CL.items() if mo == 'UnattainedSupremum' and ' '.join(rq.split()) == req), None); s_ = st(line)
    ok = s_ == want and has(line, pat) and has(line, pol)
    if cid == 'U01':   # the lower bound is below 1 and the interval is reported open
        ok = ok and has(line, r'\(Upper 1\)') and has(line, r'\(Closed False\)') and not has(line, r'\(BehavioralDefect 1\)')
    report('%s %s' % (cid, req[:48]), ok, s_)

# ---- negative gates 3, 9, 10, 11 ----
# neg 3 (L03): composed residual carries the norm factor: (rA*lB + lA*rB) = 3/5, never the plain sum rA + rB = 1/5
LFIX = os.path.join(os.path.dirname(FIX), 'linear_composition.metta')
LC = run(open(LFIX, encoding='utf-8').read(), 'lincomp')
l3 = LC.get(('LinearComposition', 'LK'))   # requests are keyed by their Derive name; LK = (Then (Output LChecked Value) (Output KChecked Value))
report('neg 3: L03 residual uses the norm factor (Rho 3/5, not 1/5)',
       st(l3) == 'Checked' and has(l3, r'\(Grade \(Lambda 3\) \(Rho \(Rat 3 5\)\)\)') and not has(l3, r'\(Value .*\(Rho \(Rat 1 5\)\)\) \(Attained'), st(l3))
# neg 9: no answer anywhere uses a sampled successor (seed / sample / trajectory) as a witness
allout = [l for D_ in (L, E, G, CL, LC) for l in D_.values()]
report('neg 9: no sampled-successor witness in any M4 answer', not any(has(l, r'Sample|Seed|Trajectory') for l in allout), '%d answers' % len(allout))
# neg 10 (O03): the policy-class refutation carries a policy-tree witness, never a word witness
o3 = next((l for (mo, rq), l in CL.items() if mo == 'AdaptiveProbe' and 'ObservationBased' in rq and 'Within' in rq), None)
report('neg 10: O03 witness is PolicyTreeWitness, not WordWitness', st(o3) == 'Refuted' and has(o3, r'PolicyTreeWitness') and not has(o3, r'WordWitness'), st(o3))
# neg 11 (U01): a Precision-0 undiscounted measurement is never Checked from tests alone, nor certified by a post-fixpoint
u1 = next((l for (mo, rq), l in CL.items() if mo == 'UnattainedSupremum' and ' '.join(rq.split()) == '(MeasureBehavioral JoinXY)'), None)
report('neg 11: U01 not Checked, no post-fixpoint certificate', st(u1) == 'Unknown' and not has(u1, r'DualPostfixpoint|CouplingPrefixpoint'), st(u1))
sys.exit(1 if fails else 0)
