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


# ---- review 1 F2: independent replay of certificate data (exact Fractions, own S-expression reader) ----
from fractions import Fraction as Fr
def sx_parse(t):
    toks = re.findall(r'\(|\)|[^\s()]+', t); pos = 0
    def rd():
        nonlocal pos
        tk = toks[pos]; pos += 1
        if tk != '(': return tk
        out = []
        while toks[pos] != ')': out.append(rd())
        pos += 1; return out
    res = []
    while pos < len(toks): res.append(rd())
    return res
def sx_find(x, head):
    if isinstance(x, list):
        if x and x[0] == head: yield x
        for y in x: yield from sx_find(y, head)
def rat(x):
    if isinstance(x, list) and x[0] == 'Rat': return Fr(int(x[1]), int(x[2]))
    return Fr(int(x))
def chain_model(text, module=None):
    """kernels name -> {state: {state: Fr}}, maps name -> {state: value}, from the fixture source itself
    (restricted to the top-level form named `module` when given)"""
    K, M = {}, {}
    forms = sx_parse(text)
    if module: forms = [f for f in forms if isinstance(f, list) and len(f) > 1 and f[1] == module]
    for f in forms:
        for k in sx_find(f, 'TransitionKernel'):
            K[k[1]] = {r[1]: {ms[1]: rat(ms[2]) for ms in r[2:] if ms[0] == 'Mass'} for r in k if isinstance(r, list) and r[0] == 'Row'}
        for m_ in sx_find(f, 'Map'):
            cs = [c for c in m_ if isinstance(c, list) and c[0] == 'Cases']
            if cs: M[m_[1]] = {c[0]: c[1] for c in cs[0][1:]}
    return K, M
def mt_replay(line, text, actions, gamma):
    """Evaluate the ModalTestWitness Formula graph at every state; check the grammar (Definition 4.9),
    the discount on every Next node, and that Left/Right are the values at the Pair.  Returns (left, right) or None."""
    K, M = chain_model(text)
    try:
        w = next(sx_find(sx_parse(line), 'ModalTestWitness'))
        pair = next(sx_find(w, 'Pair')); fm = next(sx_find(w, 'Formula'))
        root = int(next(sx_find(fm, 'Root'))[1]); states = list(next(iter(K.values())).keys())
        val = {}
        for nd in fm[1:]:
            if nd[0] != 'Node': continue
            i, e = int(nd[1]), nd[2]; op = e[0]
            if op == 'Indicator': v = {z: Fr(int(M[e[1]][z] == e[2])) for z in states}
            elif op == 'Not': v = {z: 1 - val[int(e[1])][z] for z in states}
            elif op == 'Min': v = {z: min(val[int(e[1])][z], val[int(e[2])][z]) for z in states}
            elif op == 'Max': v = {z: max(val[int(e[1])][z], val[int(e[2])][z]) for z in states}
            elif op == 'Sub': v = {z: max(Fr(0), val[int(e[1])][z] - rat(e[2])) for z in states}
            elif op == 'Next':
                if rat(e[3]) != gamma or e[1] not in actions: return None
                Kr = K[actions[e[1]]]; a = val[int(e[2])]
                v = {z: gamma * sum(p * a[y] for y, p in Kr[z].items()) for z in states}
            else: return None
            if any(not (0 <= x <= 1) for x in v.values()): return None
            val[i] = v
        l, r = val[root][pair[1]], val[root][pair[2]]
        if l != rat(next(sx_find(w, 'Left'))[1]) or r != rat(next(sx_find(w, 'Right'))[1]): return None
        return l, r
    except (StopIteration, KeyError, IndexError, ValueError):
        return None


def prefix_replay(line, text, actions, obsmaps, module=None):
    """Replay a Prefixpoint certificate: couplings have the two successor laws as marginals, every
    same-class pair x != y has a coupling per action, and D >= max(d0, gamma * E_theta D).  Returns D or None."""
    K, M = chain_model(text, module)
    try:
        c = next(x for x in sx_find(sx_parse(line), 'Certificate') if ['Kind', 'Prefixpoint'] in x)
        g = rat(next(sx_find(c, 'Discount'))[1]); states = list(next(iter(K.values())).keys())
        D = {(a, b): Fr(0) for a in states for b in states}
        for e in next(sx_find(c, 'Kernel'))[1:]: D[(e[1], e[2])] = rat(e[3])
        d0 = {(a, b): Fr(int(any(M[o][a] != M[o][b] for o in obsmaps))) for a in states for b in states}
        if any(not (max(d0[k], Fr(0)) <= D[k] <= 1) for k in D) or any(D[(a, b)] != D[(b, a)] for a, b in D): return None
        seen = set()
        for cp in next(sx_find(c, 'Couplings'))[1:]:
            x, y, act = cp[1], cp[2], cp[3]; Kr = K[actions[act]]; th = {}
            for ms in cp[4:]: th[(ms[1], ms[2])] = th.get((ms[1], ms[2]), Fr(0)) + rat(ms[3])
            if any(v < 0 for v in th.values()): return None
            for z in states:
                if sum(v for (i, j), v in th.items() if i == z) != Kr[x].get(z, 0): return None
                if sum(v for (i, j), v in th.items() if j == z) != Kr[y].get(z, 0): return None
            if D[(x, y)] < g * sum(v * D[k] for k, v in th.items()): return None
            seen.add((x, y, act)); seen.add((y, x, act))
        for a in states:
            for b in states:
                if a != b and d0[(a, b)] == 0 and any((a, b, act) not in seen for act in actions): return None
        return D
    except (StopIteration, KeyError, IndexError, ValueError):
        return None


def dual_replay(line, text, actions, obsmaps, module=None):
    """Replay a DualPostfixpoint certificate: for every same-class pair with D(x,y) > 0 a Dual names an action
    and potentials f on supp K(x), g on supp K(y) with f(u) - g(v) <= D(u,v) and gamma (E f - E g) >= D(x,y).
    D outside such pairs must equal d0.  Then D is a post-fixpoint, hence a lower bound.  Returns D or None."""
    K, M = chain_model(text, module)
    try:
        c = next(x for x in sx_find(sx_parse(line), 'Certificate') if ['Kind', 'DualPostfixpoint'] in x)
        g = rat(next(sx_find(c, 'Discount'))[1]); states = list(next(iter(K.values())).keys())
        D = {(a, b): Fr(0) for a in states for b in states}
        for e in next(sx_find(c, 'Kernel'))[1:]: D[(e[1], e[2])] = rat(e[3])
        d0 = {(a, b): Fr(int(any(M[o][a] != M[o][b] for o in obsmaps))) for a in states for b in states}
        if any(D[(a, b)] != D[(b, a)] for a, b in D) or any(not (0 <= v <= 1) for v in D.values()): return None
        ok = set()
        for du in next(sx_find(c, 'Duals'))[1:]:
            x, y, act = du[1], du[2], du[3]; Kr = K[actions[act]]
            f = {p_[1]: rat(p_[2]) for p_ in du[4][1:]}; gg = {p_[1]: rat(p_[2]) for p_ in du[5][1:]}
            if du[4][0] != 'F' or du[5][0] != 'G': return None
            if set(z for z, p in Kr[x].items() if p) - set(f) or set(z for z, p in Kr[y].items() if p) - set(gg): return None
            if any(f[u] - gg[v] > D[(u, v)] for u in f for v in gg): return None
            if g * (sum(p * f[z] for z, p in Kr[x].items() if p) - sum(p * gg[z] for z, p in Kr[y].items() if p)) < D[(x, y)]: return None
            ok.add((x, y)); ok.add((y, x))
        for k, v in D.items():
            if k[0] != k[1] and d0[k] == 0 and v > 0 and k not in ok: return None
            if d0[k] == 1 and v != 1: return None
        return D
    except (StopIteration, KeyError, IndexError, ValueError):
        return None


def layered_replay(line, text, actions, obsmaps, module=None):
    """Replay a LayeredPrefixpoint: D_0 >= d0, and for every layer t < h, same-class pair x != y and action a
    coupling with the two successor laws as marginals and D_(t+1)(x,y) >= max(d0, gamma * E_theta D_t).
    Returns the list [D_0 .. D_h] or None."""
    K, M = chain_model(text, module)
    try:
        c = next(x for x in sx_find(sx_parse(line), 'Certificate') if ['Kind', 'LayeredPrefixpoint'] in x)
        g = rat(next(sx_find(c, 'Discount'))[1]); h = int(next(sx_find(c, 'Steps'))[1])
        states = list(next(iter(K.values())).keys())
        d0 = {(a, b): Fr(int(any(M[o][a] != M[o][b] for o in obsmaps))) for a in states for b in states}
        Ds = []
        for lay in next(sx_find(c, 'LayerKernels'))[1:]:
            D = {k: Fr(0) for k in d0}
            for e in lay[2:]: D[(e[1], e[2])] = rat(e[3])
            if any(not (d0[k] <= D[k] <= 1) or D[k] != D[(k[1], k[0])] for k in D): return None
            Ds.append(D)
        if len(Ds) != h + 1: return None
        CS = next(sx_find(c, 'LayerCouplings'))[1:]
        if len(CS) != h: return None
        for tt, lay in enumerate(CS):
            if int(lay[1]) != tt: return None
            seen = set()
            for cp in lay[2:]:
                x, y, act = cp[1], cp[2], cp[3]; Kr = K[actions[act]]; th = {}
                for ms in cp[4:]: th[(ms[1], ms[2])] = th.get((ms[1], ms[2]), Fr(0)) + rat(ms[3])
                if any(v < 0 for v in th.values()): return None
                for z in states:
                    if sum(v for (i, j), v in th.items() if i == z) != Kr[x].get(z, 0): return None
                    if sum(v for (i, j), v in th.items() if j == z) != Kr[y].get(z, 0): return None
                if Ds[tt + 1][(x, y)] < g * sum(v * Ds[tt][k] for k, v in th.items()): return None
                seen.add((x, y, act)); seen.add((y, x, act))
            for a in states:
                for b in states:
                    if a != b and d0[(a, b)] == 0 and any((a, b, act) not in seen for act in actions): return None
        return Ds
    except (StopIteration, KeyError, IndexError, ValueError):
        return None


def realization_replay(line, text, actions, obs, depth=4):
    """Replay the S06 realization: for every word y0 a1 y1 .. am ym with m < depth, the value
    Final(s) . T_(a1,y0) .. T_(am,y(m-1)) Projector(ym) must equal the chain's exact probability
    Pr_s[o(X0)=y0, .., o(Xm)=ym] under the actions, at every state s.  Returns the dimension or None."""
    K, M = chain_model(text)
    try:
        R = next(sx_find(sx_parse(line), 'Realization'))
        k = int(next(sx_find(R, 'Dimension'))[1]); O = M[obs]; states = list(O.keys()); ys = sorted(set(O.values()))
        T, P, F = {}, {}, {}
        for e in R[2:]:
            if e[0] == 'Operator':
                cols = {int(c[1]): [rat(v) for v in c[2:]] for c in e[3:]}
                T[(e[1], e[2][1][1])] = [[cols[j][i] for j in range(k)] for i in range(k)]
            elif e[0] == 'Projector': P[e[1][1][1]] = [rat(v) for v in e[2:]]
            elif e[0] == 'Final': F = {r[1]: [rat(v) for v in r[2:]] for r in e[1:]}
        if set(F) != set(states) or any(len(v) != k for v in list(F.values()) + list(P.values())): return None
        def direct(word):   # word = [y0, a1, y1, ..]
            f = {s: Fr(int(O[s] == word[-1])) for s in states}
            for i in range(len(word) - 3, -1, -2):
                Kr = K[actions[word[i + 1]]]
                f = {s: Fr(int(O[s] == word[i])) * sum(p * f[u] for u, p in Kr[s].items()) for s in states}
            return f
        def viaR(word):
            c = P[word[-1]]
            for i in range(len(word) - 3, -1, -2):
                A = T[(word[i + 1], word[i])]; c = [sum(A[r][j] * c[j] for j in range(k)) for r in range(k)]
            return {s: sum(F[s][i] * c[i] for i in range(k)) for s in states}
        words = [[y] for y in ys]; allw = list(words)
        for _ in range(depth - 1):
            words = [w + [a, y] for w in words for a in actions for y in ys]; allw += words
        for w in allw:
            if direct(w) != viaR(w): return None
        return k
    except (StopIteration, KeyError, IndexError, ValueError):
        return None

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
        ('S03', 'Behavioral', 'Refuted', r'\(BehavioralDefect \(Rat 1 2\)\).*\(ModalTestWitness \(Pair y x\) \(Formula \(Root \d+\)'),
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
# review 1 F2: the S03/S04 modal tests replay independently and certify the defect as a lower bound
ACT = {'step': 'Step'}
rp3 = mt_replay(b3, src, ACT, Fr(1)); rp4 = mt_replay(L.get(('SevenState', MB)), src, ACT, Fr(9, 10))
report('F2: S03 ModalTestWitness formula replays, |Left - Right| = 1/2', bool(rp3) and abs(rp3[0] - rp3[1]) == Fr(1, 2), rp3)
report('F2: S04 ModalTestWitness formula replays at discount 9/10, gap 81/200', bool(rp4) and abs(rp4[0] - rp4[1]) == Fr(81, 200), rp4)
# invariant 18: the upper certificate (Prefixpoint) replays and meets the lower one (modal test) at the value
pp3 = prefix_replay(b3, src, ACT, ['report']); pp4 = prefix_replay(L.get(('SevenState', MB)), src, ACT, ['report'])
report('F2: S03 Prefixpoint replays (marginals, D >= max(d0, E_theta D)), D(x,y) = 1/2 = test gap', bool(pp3) and pp3[('x', 'y')] == Fr(1, 2), pp3 and pp3[('x', 'y')])
report('F2: S04 Prefixpoint replays at 9/10, D(x,y) = 81/200 = test gap', bool(pp4) and pp4[('x', 'y')] == Fr(81, 200), pp4 and pp4[('x', 'y')])
# review 1 F2: the S06 signed minimum carries its realization (Table 1); every word up to length 4 replays exactly
rz6 = realization_replay(L.get(('SevenState', 'Linear')), src, ACT, 'report')
report('F2: S06 Realization (dimension 5) reproduces every word probability up to length 4', rz6 == 5, rz6)
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
         ('U04', '(MeasureBehavioral JoinXY (Discount (Rat 1 2)))', 'Checked', r'\(BehavioralDefect \(Rat 1 3\)\) \(Discount \(Rat 1 2\)\).*\(Kind Prefixpoint\).*\(Kind DualPostfixpoint\)', POL)]
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
# L01-L03 rows (linear_composition.metta): release 1 answers Unsupported; --beyond-release gives the graded arrows
LD = run(open(LFIX, encoding='utf-8').read(), 'lincomp-default', beyond=False)
report('R1 default: L01-L03 requests Unsupported', all(st(LD.get(('LinearComposition', q))) == 'Unsupported' for q in ('LChecked', 'KChecked', 'LK')),
       ' '.join(st(LD.get(('LinearComposition', q))) for q in ('LChecked', 'KChecked', 'LK')))
lrows = [('L01', 'LChecked', 'Checked', r'\(LinearArrow Signed \(Valid True\) \(Grade \(Lambda 3\) \(Rho 0\)\)\).*\(Kind GradedIntertwining\)'),
         ('L02', 'KChecked', 'Checked', r'\(LinearArrow Positive \(Valid True\) \(Grade \(Lambda 1\) \(Rho \(Rat 1 5\)\)\)\).*\(Kind GradedIntertwining\)'),
         ('L03', 'LK', 'Checked', r'\(Grade \(Lambda 3\) \(Rho \(Rat 3 5\)\)\) \(Attained True\).*\(Kind GradedComposition\)')]
for cid, req, want, pat in lrows:
    line = LC.get(('LinearComposition', req)); s_ = st(line)
    report('%s %s' % (cid, req), s_ == want and has(line, pat) and has(line, r'\(Policy M4-StochasticReplay\)'), s_)
l3 = LC.get(('LinearComposition', 'LK'))   # requests are keyed by their Derive name; LK = (Then (Output LChecked Value) (Output KChecked Value))
report('neg 3: L03 residual uses the norm factor (Rho 3/5, not 1/5)',
       st(l3) == 'Checked' and has(l3, r'\(Grade \(Lambda 3\) \(Rho \(Rat 3 5\)\)\)') and not has(l3, r'\(Value .*\(Rho \(Rat 1 5\)\)\) \(Attained'), st(l3))
# neg 9: no answer anywhere uses a sampled successor (seed / sample / trajectory) as a witness
allout = [l for D_ in (L, E, G, CL, LC) for l in D_.values()]
report('neg 9: no sampled-successor witness in any M4 answer', not any(has(l, r'Sample|Seed|Trajectory') for l in allout), '%d answers' % len(allout))
# neg 10 (O03): the policy-class refutation carries a policy-tree witness, never a word witness
o3 = next((l for (mo, rq), l in CL.items() if mo == 'AdaptiveProbe' and 'ObservationBased' in rq and 'Within' in rq), None)
report('neg 10: O03 witness is PolicyTreeWitness, not WordWitness', st(o3) == 'Refuted' and has(o3, r'PolicyTreeWitness') and not has(o3, r'WordWitness'), st(o3))
# review 1 F3: a stochastic fixed-word refutation carries a TraceEventWitness (spec table), never the deterministic WordWitness
f3src = csrc.replace('(CheckTrace MergeX (Horizon (Steps 2)) (Within (Rat 3 4))))', '(CheckTrace MergeX (Horizon (Steps 2)) (Within (Rat 1 4))))', 1)
assert f3src != csrc
F3 = run(f3src, 'f3-words')
o2b = next((l for (mo, rq), l in F3.items() if mo == 'AdaptiveProbe' and 'Rat 1 4' in rq and 'ObservationBased' not in rq), None)
report('F3: fixed-word refutation (Within 1/4) is TraceEventWitness, not WordWitness', st(o2b) == 'Refuted' and has(o2b, r'\(TraceEventWitness \(Pair x x2\) \(Word a b\)') and not has(o2b, r'WordWitness \('), st(o2b))
# neg 11 (U01): a Precision-0 undiscounted measurement is never Checked from tests alone, nor certified by a post-fixpoint
u1 = next((l for (mo, rq), l in CL.items() if mo == 'UnattainedSupremum' and ' '.join(rq.split()) == '(MeasureBehavioral JoinXY)'), None)
report('neg 11: U01 not Checked, no post-fixpoint certificate', st(u1) == 'Unknown' and not has(u1, r'DualPostfixpoint|CouplingPrefixpoint'), st(u1))
# review 1 F2 (invariant 18): U04 upper Prefixpoint and lower DualPostfixpoint both replay and meet at 1/3
u4 = next((l for (mo, rq), l in CL.items() if mo == 'UnattainedSupremum' and ' '.join(rq.split()) == '(MeasureBehavioral JoinXY (Discount (Rat 1 2)))'), None)
UA = {'step': 'Step'}
pu4 = prefix_replay(u4, csrc, UA, ['report'], 'UnattainedSupremum'); du4 = dual_replay(u4, csrc, UA, ['report'], 'UnattainedSupremum')
report('F2: U04 Prefixpoint (upper) replays, D(x,y) = 1/3', bool(pu4) and pu4[('x', 'y')] == Fr(1, 3), pu4 and pu4[('x', 'y')])
report('F2: U04 DualPostfixpoint (lower) replays, D(x,y) = 1/3, bounds meet', bool(du4) and du4[('x', 'y')] == Fr(1, 3) and bool(pu4) and du4 == pu4, du4 and du4[('x', 'y')])
u2 = next((l for (mo, rq), l in CL.items() if mo == 'UnattainedSupremum' and ' '.join(rq.split()) == '(MeasureBehavioral JoinXY (Horizon (Steps 3)))'), None)
lu2 = layered_replay(u2, csrc, UA, ['report'], 'UnattainedSupremum')
report('F2: U02 LayeredPrefixpoint replays (4 layer kernels, couplings per layer), D_3(y,x) = 7/8', bool(lu2) and len(lu2) == 4 and lu2[3][('y', 'x')] == Fr(7, 8), lu2 and lu2[-1][('y', 'x')])

# neg 12: a Positive arrow from an unnormalized realization (K rows sum to 2) is not valid, so no composite is formed from it.
lsrc = open(LFIX, encoding='utf-8').read()
m12 = lsrc.replace('(Matrix (Rows (e1 (e1 1)) (e2 (e2 1))))', '(Matrix (Rows (e1 (e1 2)) (e2 (e2 2))))', 1)
assert m12 != lsrc
U12 = run(m12, 'neg12-unnorm')
k12, c12 = U12.get(('LinearComposition', 'KChecked')), U12.get(('LinearComposition', 'LK'))
report('neg 12: unnormalized Positive arrow K is Refuted (row sum)', st(k12) == 'Refuted' and has(k12, r'\(Valid False\)') and has(k12, r'does not sum to 1'), st(k12))
# review 1 F4: registry Output rule -- Then projects only from Checked results, so the composite of a Refuted K is InvalidInput
# (never a Checked/Refuted composite carrying the additive shortcut grade 2/5).
report('neg 12: composite of unnormalized K is InvalidInput (Output only from Checked), no grade 2/5', st(c12) == 'InvalidInput'
       and has(c12, r'Output projects only from Checked results') and not has(c12, r'\(Rho \(Rat 2 5\)\)'), st(c12))

# neg 6 (R01): equal expected rewards with different reward laws are not equal.  Mutation of regime_repair:
# Bit gains outcome 2; Old pays 1 surely, New pays 2 or 0 with probability 1/2 each under Fair (mean 1 for both actions).
rsrc = open(RFIX, encoding='utf-8').read()
m6 = re.sub(r'\(Carrier Bit +\(Of Nat\) \(Enum 0 1\)\)', '(Carrier Bit (Of Nat) (Enum 0 1 2))', rsrc, count=1)
m6 = m6.replace('(Body ($sa) (Coin (Rat 1 2)))', '(Body ($sa) (Point 1))', 1)
m6 = m6.replace('((Tuple Plus L) (Point 1))', '((Tuple Plus L) (Point 2))', 1).replace('((Tuple Minus R) (Point 1))', '((Tuple Minus R) (Point 2))', 1)
assert m6.count('(Point 2)') == 2 and '(Enum 0 1 2)' in m6 and '(Point 1))' in m6
V6 = run(m6, 'neg6-equal-means')
r6 = V6.get(('RegimeRepair', '(CheckEqual (AverageModel Old (Under Fair)) (AverageModel New (Under Fair)))'))
report('neg 6: equal means, different laws -> CheckEqual Refuted', st(r6) == 'Refuted' and has(r6, r'\(Equal False\)') and has(r6, r'\(Kind LawDifference\)')
       and has(r6, r'\(Mean 1\).*\(Mean 1\).*\(Mean 1\).*\(Mean 1\)'), st(r6))

# neg 7 (V02; spec 13.2): equality concerns laws, not couplings -- the three-block quotient is certified by
# strong lumping of the laws and is never rejected by (or certified with) a same-seed trajectory comparison
v2 = E.get(('EvolutionArchive', 'Repaired'))
report('neg 7: three-block quotient Checked by law lumping, no same-seed comparison',
       st(v2) == 'Checked' and has(v2, r'\(Classes 3\)') and has(v2, r'\(Kind StrongLumping\)') and not has(v2, r'Seed|Trajectory|Sample'), st(v2))
# neg 4 (R03/R04; worked examples 4): an induced bound is never applied without current adequacy --
# InduceExact Coarse is Refuted on current adequacy (observation witness), and optimizing through Coarse
# reports the coarse optimum 1/2, not the refined optimum 1 carried over as if the abstraction were exact
r3 = G.get(('RegimeRepair', '(InduceExact Coarse)')); r4 = G.get(('RegimeRepair', '(OptimizePolicy New (Through Coarse) (Under Fair))'))
report('neg 4: no induced bound without current adequacy (R03 Refuted, R04 = 1/2 not 1)',
       st(r3) == 'Refuted' and has(r3, r'\(Kind ObservationWitness\)') and not has(r3, r'\(Exact True\)')
       and has(r4, r'\(Optimum \(Rat 1 2\)\)') and not has(r4, r'\(Optimum 1\)'), '%s / %s' % (st(r3), st(r4)))
print('m4_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
