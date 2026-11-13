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
# negative gate 6: the rhocalc script's depth is a cost budget, never a MeTTaDinC horizon.
# dcalc side: no Simulation request takes a horizon or depth argument, so admission refuses one.
for tag, req in (('neg6_horizon_sim', '(CheckSimulation StageSim (Horizon 2))'),
                 ('neg6_depth_sim', '(CheckSimulation StageSim (Depth 2))'),
                 ('neg6_horizon_safety', '(CheckSafety Abstract (Never (EnterFrom Admin (Not Auth))) (Via StageSim) (Init S0) (Horizon 2))')):
    l = mut('access_protocol.metta', tag, 'AccessProtocol', req)
    report('neg 6: script depth passed as a horizon (%s) -> InvalidInput' % tag, st(l) == 'InvalidInput' and has(l, r'unknown argument'), st(l))
# script side (recorded by weakbarbed_record.py when the CeTTa scratch exists): depth is ScriptCostBudget, never an oracle
WB = os.path.join(ROOT, 'build/m5_weakbarbed.tsv')
if os.path.exists(WB):
    rows = [l.rstrip('\n').split('\t') for l in open(WB) if l.strip() and not l.startswith('#')]
    report('neg 6: recorded script verdicts carry Horizon None, Oracle False', bool(rows) and all(r[4:6] == ['None', 'False'] for r in rows), '%d rows' % len(rows))
# review 2 F2: only lockstep matching is checked; a declared Stutter matching or Order answers Unsupported
SIMD = '(Simulation StageSim (Source Protocol) (Target Abstract) (Relation stage-of))'
l = mut('access_protocol.metta', 'r2f2_stutter_sim', 'AccessProtocol', '(CheckSimulation StageSim)', (SIMD, SIMD[:-1] + ' (Matching Stutter))'))
report('review 2 F2: (Matching Stutter) CheckSimulation -> Unsupported', st(l) == 'Unsupported' and has(l, r'only Lockstep'), st(l))
l = mut('access_protocol.metta', 'r2f2_stutter_safety', 'AccessProtocol', '(CheckSafety Abstract (Never (Shows stage Admin)) (Via StageSim) (Init S0))', (SIMD, SIMD[:-1] + ' (Matching Stutter))'))
report('review 2 F2: (Matching Stutter) CheckSafety -> Unsupported', st(l) == 'Unsupported' and has(l, r'only Lockstep'), st(l))
l = mut('access_protocol.metta', 'r2f2_order', 'AccessProtocol', '(CheckSimulation StageSim)', (SIMD, SIMD[:-1] + ' (Order Start))'))
report('review 2 F2: declared Order -> Unsupported', st(l) == 'Unsupported' and has(l, r'Order is declared'), st(l))
l = mut('access_protocol.metta', 'r2f2_lockstep', 'AccessProtocol', '(CheckSimulation StageSim)', (SIMD, SIMD[:-1] + ' (Matching Lockstep))'))
report('review 2 F2: explicit (Matching Lockstep) -> Checked as before', st(l) == 'Checked' and has(l, r'\(Kind Simulation\)'), st(l))
# review 2 F1: rows that reach the three evidence paths review 2 found unreplayed
# (ObserverMismatch, ConcreteCounterexample, ReachWithin SafetyTransfer).  Their .out files
# are picked up by the independent replay below, so a Replayed True claim there is re-checked.
l = mut('access_protocol.metta', 'r2f1_obsmismatch', 'AccessProtocol', '(CheckSimulation StageSim)',
        ('(Cases (Start Start) (Locked Locked) (Auth Auth) (Admin Admin)))', '(Cases (Start Locked) (Locked Locked) (Auth Auth) (Admin Admin)))'))
report('review 2 F1: observer disagreement -> Refuted with ObserverMismatch', st(l) == 'Refuted' and has(l, r'\(ObserverMismatch \(Pair '), st(l))
l = mut('access_protocol.metta', 'r2f1_reachwithin_checked', 'AccessProtocol', '(CheckSafety Abstract (Never (ReachWithin Admin 1)) (Via StageSim) (Init S0))')
report('review 2 F1: ReachWithin Admin 1 (Admin is 2 steps away) -> Checked SafetyTransfer', st(l) == 'Checked' and has(l, r'\(Kind SafetyTransfer\)'), st(l))
l = mut('access_protocol.metta', 'r2f1_concrete_reach', 'AccessProtocol', '(CheckSafety Abstract (Never (ReachWithin Auth 1)) (Via StageSim) (Init S0))')
report('review 2 F1: ReachWithin Auth 1 -> Refuted with a ConcreteCounterexample', st(l) == 'Refuted' and has(l, r'ConcreteCounterexample'), st(l))
l = mut('access_protocol.metta', 'r2f1_concrete_shows', 'AccessProtocol', '(CheckSafety Abstract (Never (Shows stage Admin)) (Via StageSim) (Init S0))')
report('review 2 F1: Shows stage Admin -> Refuted with a ConcreteCounterexample', st(l) == 'Refuted' and has(l, r'ConcreteCounterexample'), st(l))
# review 1 F1: Replayed True is not trusted from dcalc's own output.  Every M5 row that
# claims it is re-checked by tests/dcalc/m5/replay_m5.py (own reader, Fractions, no dcalc code).
REPLAY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'replay_m5.py')
outs = sorted(f[:-4] for f in os.listdir(OUT) if f.endswith('.out') and os.path.exists(os.path.join(OUT, f[:-4] + '.metta')))
args = [x for b in outs for x in (os.path.join(OUT, b + '.metta'), os.path.join(OUT, b + '.out'))]
r = subprocess.run([sys.executable, REPLAY] + args, capture_output=True, text=True, timeout=300)
open(os.path.join(OUT, 'replay_m5.log'), 'w').write(r.stdout + r.stderr)
last = (r.stdout.strip().splitlines() or ['no output'])[-1]
report('F1: independent replay of every Replayed True row (replay_m5.py)', r.returncode == 0 and last.endswith('PASS'), last)
# canary: tampered certificates must be rejected (one per evidence kind)
src_out = open(os.path.join(OUT, 'access_protocol_beyond.out'), encoding='utf-8').read()
TAMPER = (('wrong matching move', '(Step Auth) (To Auth)', '(Step Auth) (To Start)'),
          ('dropped Reachable state', '(Reachable Start Locked Auth Admin)', '(Reachable Start Locked Auth)'),
          ('wrong exactness codes', '(Codes Start) (Codes Locked)', '(Codes Start) (Codes Start)'))
for name, a, b in TAMPER:
    if a not in src_out: report('F1 canary: %s is rejected' % name, False, 'pattern absent'); continue
    tp = os.path.join(OUT, 'tamper_%s' % name.replace(' ', '_'))
    open(tp + '.out', 'w').write(src_out.replace(a, b, 1))
    open(tp + '.metta', 'w').write(open(os.path.join(OUT, 'access_protocol_beyond.metta'), encoding='utf-8').read())
    t = subprocess.run([sys.executable, REPLAY, tp + '.metta', tp + '.out'], capture_output=True, text=True, timeout=60)
    report('F1 canary: %s is rejected' % name, t.returncode == 1 and 'REJECT' in t.stdout, (t.stdout.strip().splitlines() or [''])[-1][:60])
    os.remove(tp + '.out'); os.remove(tp + '.metta')
# review 2 F1 canaries: one tamper per newly replayed evidence kind (edit the .out or the request)
TAMPER2 = (('ObserverMismatch on an unrelated pair', 'r2f1_obsmismatch', 'out', '(ObserverMismatch (Pair S0 Start)', '(ObserverMismatch (Pair S0 Auth)'),
           ('ConcreteCounterexample path that misses the property', 'r2f1_concrete_reach', 'out', '(Path S0 (Step ok Auth))', '(Path S0 (Step fail S1))'),
           ('ReachWithin bound that the target does reach', 'r2f1_reachwithin_checked', 'out', '(ReachWithin Admin 1)', '(ReachWithin Admin 2)'))
for name, base, which, a, b in TAMPER2:
    bp = os.path.join(OUT, base)
    if not os.path.exists(bp + '.out'): report('review 2 F1 canary: %s is rejected' % name, False, 'no %s.out' % base); continue
    txt = {k: open(bp + '.' + k, encoding='utf-8').read() for k in ('out', 'metta')}
    if a not in txt[which]: report('review 2 F1 canary: %s is rejected' % name, False, 'pattern absent'); continue
    txt[which] = txt[which].replace(a, b, 1)
    tp = os.path.join(OUT, 'tamper2_%s' % base)
    for k in ('out', 'metta'): open(tp + '.' + k, 'w').write(txt[k])
    t = subprocess.run([sys.executable, REPLAY, tp + '.metta', tp + '.out'], capture_output=True, text=True, timeout=60)
    report('review 2 F1 canary: %s is rejected' % name, t.returncode == 1 and 'REJECT' in t.stdout, (t.stdout.strip().splitlines() or [''])[-1][:60])
    os.remove(tp + '.out'); os.remove(tp + '.metta')
print('m5_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
