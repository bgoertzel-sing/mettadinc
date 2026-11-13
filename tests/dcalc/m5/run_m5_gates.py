#!/usr/bin/env python3
"""M5 claim rows H13-H14, Y01-Y04, D01-D04 and negative gates (t-2026-11-12-mettadinc-m5).

Runs build/dcalc/dcalc on the three validation-package fixtures, once in release
mode (every M5 request must answer Unsupported) and once with --beyond-release
(the M5 answers), then on mutations for the negative gates.  Exit 0 iff all pass."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FIXD = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m5'))
fails = 0
def report(name, ok, note=''):
    global fails
    fails += not ok; print('%-70s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
def norm(s): return re.sub(r'\s+', ' ', s.strip())
def run(src, tag, beyond=True):
    os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, tag + '.metta'); open(p, 'w').write(src)
    r = subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [p], capture_output=True, text=True, timeout=120)
    open(os.path.join(OUT, tag + '.out'), 'w').write(r.stdout)
    lines = {}
    for line in r.stdout.splitlines():
        if ' => ' in line:
            head = line.split(' => ', 1)[0]; mod, req = head.split(' ', 1); lines[(mod, norm(req))] = line
    return lines
def st(line): m = re.search(r'\(Result \(Status (\w+)\)', line or ''); return m.group(1) if m else 'missing'
def has(line, pat): return re.search(pat, line or '') is not None
def fx(name): return open(os.path.join(FIXD, name), encoding='utf-8').read()

ROWS = [
    ('H13', 'hypotheses.metta', 'SimulationScope', '(CheckSimulation Empty)', 'Checked', [r'\(Kind Simulation\)']),
    ('H14', 'hypotheses.metta', 'SimulationScope', '(CheckSafety Abstract (Never (Shows flag Bad)) (Via Empty) (Init c0))', 'Unknown', [r'\(UncoveredInit c0\)', r'\(Coverage Vacuous\)']),
    ('Y01', 'access_protocol.metta', 'AccessProtocol', '(InduceExact StageQuotient)', 'Refuted', [r'\(ExactnessFailure \(States S0 S2\) \(Action fail\) \(Codes Start\) \(Codes Locked\)\)']),
    ('Y02', 'access_protocol.metta', 'AccessProtocol', '(CheckSimulation StageSim)', 'Checked', [r'\(Kind Simulation\)']),
    ('Y03', 'access_protocol.metta', 'AccessProtocol', 'Safe', 'Checked', [r'\(Kind SafetyTransfer\)', r'\(InitCovered True\)']),
    ('Y04', 'access_protocol.metta', 'AccessProtocol', 'Lockout', 'Unknown', [r'\(Spurious True\)', r'\(Split Start\)', r'\(ConcreteSteps 3\)']),
    ('D01', 'reads.metta', 'Reads', '(Outcomes Shared (From Start) (After (Do read)) (Observe agree))', 'Checked', [r'\(OutcomeSet Agree\)']),
    ('D02', 'reads.metta', 'Reads', '(Outcomes Fresh (From Start) (After (Do read)) (Observe agree))', 'Checked', [r'\(OutcomeSet Agree Differ\)']),
    ('D03', 'reads.metta', 'Reads', '(OutcomeProbability Shared (From Start) (After (Do read)) (Event (Shows agree Agree)) (Scheduler Fair))', 'Checked', [r'\(Probability \(Rat 1 1\)\)']),
    ('D04', 'reads.metta', 'Reads', '(OutcomeProbability Fresh (From Start) (After (Do read)) (Event (Shows agree Agree)) (Scheduler Fair))', 'Checked', [r'\(Probability \(Rat 1 2\)\)']),
]
cache = {}
for beyond in (False, True):
    for cid, f, mod, req, want, pats in ROWS:
        key = (f, beyond)
        if key not in cache: cache[key] = run(fx(f), f.split('.')[0] + ('_beyond' if beyond else '_release'), beyond)
        line = cache[key].get((mod, norm(req))); s = st(line)
        if not beyond: report('%s release 1: Unsupported' % cid, s == 'Unsupported', s)
        else:
            ok = s == want and all(has(line, p) for p in pats)
            report('%s %s %s' % (cid, req[:40], want), ok, s)
# a Checked or Refuted M5 answer is replayed by the M5 policy
for cid, f, mod, req, want, pats in ROWS:
    if want in ('Checked', 'Refuted'):
        line = cache[(f, True)].get((mod, norm(req)))
        report('%s assurance M5-NondeterministicReplay, Replayed True' % cid, has(line, r'\(Policy M5-NondeterministicReplay\) \(Replayed True\)'))

# negative gates (MILESTONES.md M5, negative tests 1-5)
def mut(f, tag, mod, req, edit=None):
    src = fx(f)
    if edit:
        a, b = edit; assert src.count(a) == 1, (tag, a); src = src.replace(a, b)
    L = run(src + '\n!(dc.run %s %s)\n' % (mod, req), tag)
    return L.get((mod, norm(req)))
l = mut('reads.metta', 'neg1_no_scheduler', 'Reads', '(OutcomeProbability Fresh (From Start) (After (Do read)) (Event (Shows agree Agree)))')
report('neg 1: result bag as a law without a scheduler -> InvalidInput', st(l) == 'InvalidInput', st(l))
l = mut('access_protocol.metta', 'neg2_liveness', 'AccessProtocol', '(CheckSafety Abstract (Never (Eventually (Shows stage Admin))) (Via StageSim) (Init S0))')
report('neg 2: liveness through a simulation -> Unsupported', st(l) == 'Unsupported' and has(l, r'liveness or existential'), st(l))
l = mut('access_protocol.metta', 'neg2_existential', 'AccessProtocol', '(CheckSafety Abstract (Never (Exists (Shows stage Admin))) (Via StageSim) (Init S0))')
report('neg 2: existential through a simulation -> Unsupported', st(l) == 'Unsupported' and has(l, r'liveness or existential'), st(l))
l = mut('access_protocol.metta', 'neg3_missed_move', 'AccessProtocol', '(CheckSimulation StageSim)', ('(Start Start Locked)', '(Start Start)'))
report('neg 3: relation missing one matching move -> Refuted with that move', st(l) == 'Refuted' and has(l, r'\(UnmatchedMove \(Pair S2 Start\) \(Action fail\) \(Step Locked\)\)'), st(l))
l = mut('hypotheses.metta', 'neg4_uncovered', 'SimulationScope', '(CheckSafety Abstract (Never (Shows flag Bad)) (Via Empty) (Init c0))')
report('neg 4: simulation missing an initial state is never Checked (H14)', st(l) not in ('Checked', 'Refuted') and has(l, r'UncoveredInit c0'), st(l))
l = mut('access_protocol.metta', 'neg5_wrong_target', 'AccessProtocol', '(CheckSafety Protocol (Never (EnterFrom Admin (Not Auth))) (Via StageSim) (Init S0))')
report('neg 5: safety along a simulation whose target is not the request target -> InvalidInput', st(l) == 'InvalidInput', st(l))
print('m5_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
