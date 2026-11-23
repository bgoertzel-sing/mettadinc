#!/usr/bin/env python3
"""Gates for t-2026-11-23-mettadinc-m0-like-machines: (Machine M (States S) (Like N)) in the Crisp M0 lowering
(registry field Machine.Like, normative by spec 5.1; scopes by spec 5.3 and Table 7).  Probe X2 is
tests/dcalc/examples_e2e/repro/m0_blocker_d_like.metta (D1).  Every gate runs in release mode and with
--beyond-release.  Expected answers come from three independent places:
  1. worked by hand (README.md), hard-coded below;
  2. Ben's reference evaluator (docs/e0/.../04_omega_memory_goals_part1/validation_bundle/mg_eval.py, which
     resolves Like itself, entry_exprs l.350-357) with models/dclib.py, run on the same fixture text;
  3. for TaskResume, doc04's own answers (s7.3 l.1518-1524) and the reference evaluator on the original
     memory_goals.metta module.
Each Like module must also answer byte-for-byte like its written-out control (module name and digest aside).
"""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DC = os.environ.get('DCALC', os.path.join(ROOT, 'build', 'dcalc', 'dcalc'))
FX = os.path.join(HERE, 'fixtures')
BUNDLE = os.path.join(ROOT, 'docs', 'e0', 'docs', '04_omega_memory_goals_part1', 'validation_bundle')
sys.path[:0] = [BUNDLE, os.path.join(BUNDLE, 'models')]
from mg_eval import World  # noqa: E402
from dclib import Machine, check_now, check_updates, check_behavioral, minimize_for_queries  # noqa: E402

fails = 0
def report(name, ok, det=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '  :: ' + str(det)[:400]))
    if not ok: fails += 1

def rows(path, args=()):
    o = subprocess.run([DC] + list(args) + [path], capture_output=True, text=True, timeout=300)
    out = {}
    for l in o.stdout.splitlines():
        if ' => ' not in l: continue
        k, v = l.split(' => ', 1)
        st = re.search(r'\(Status ([A-Za-z]+)\)', v); rs = re.search(r'\(Reason "([^"]*)"', v)
        out[k.strip()] = (st.group(1) if st else None, rs.group(1) if rs else '', v)
    return out

def norm(v, mod):
    v = re.sub(r'\(Digest "[0-9a-f]+"\)', '(Digest _)', v)
    return v.replace('(Module %s)' % mod, '(Module _)')

def fmt(v):
    if isinstance(v, bool): return 'True' if v else 'False'
    if isinstance(v, tuple): return '(Tuple ' + ' '.join(fmt(x) for x in v) + ')'
    return str(v)

def word(ws): return '(Word)' if not ws else '(Word ' + ' '.join('(Do %s)' % a for a in ws) + ')'

def ref_expect(w, mod, req):
    """(status, list of substrings) from the reference evaluator for one request."""
    head, arg = req.strip('()').split() if req.startswith('(') else ('Derive', req)
    if head == 'Derive':
        d = w.decl(mod, arg); mname = d[2][1]
        st, acts, obs = w.machine(mod, mname)
        cls, _ = minimize_for_queries(Machine(st, acts, obs))
        return 'Checked', ['(Block %s)' % ' '.join(fmt(x) for x in c) for c in cls] + ['#blocks=%d' % len(cls)]
    of, enc = w.representation(mod, arg)
    st, acts, obs = w.machine(mod, of); m = Machine(st, acts, obs)
    if head == 'CheckNow':
        r = check_now(m, enc)
        return ('Checked', []) if r is None else ('Refuted', ['(CurrentWitness (Pair %s %s) (Observe %s)' % (fmt(r['pair'][0]), fmt(r['pair'][1]), r['query'])])
    if head == 'CheckUpdates':
        r = check_updates(m, enc)
        return ('Checked', []) if r is None else ('Refuted', ['(UpdateWitness (Pair %s %s) (Action %s)' % (fmt(r['pair'][0]), fmt(r['pair'][1]), r['action'])])
    if head == 'CheckBehavioral':
        r = check_behavioral(m, enc)
        return ('Checked', []) if r is None else ('Refuted', ['(WordWitness (Pair %s %s)' % (fmt(r['pair'][0]), fmt(r['pair'][1])), word(r['word']), '(Query %s)' % r['query']])
    raise ValueError(req)

def meets(got, status, subs):
    if got is None or got[0] != status: return False
    for s in subs:
        if s.startswith('#blocks='):
            part = got[2].split('(Partition', 1)[1].split('(Evidence', 1)[0] if '(Partition' in got[2] else ''
            if part.count('(Block ') != int(s[8:]): return False
        elif s not in got[2]: return False
    return True

# hand-worked answers (README.md): A={a,b,c,d}, step a<->b c<->d, obs a,c:o1 b,d:o2, Live={a,b}
FULL = {'(CheckNow R1)': ('Refuted', ['(Pair a d) (Observe obs)']),
        '(CheckUpdates R1)': ('Refuted', ['(Pair a c) (Action step)']),
        '(CheckBehavioral R1)': ('Refuted', ['(WordWitness (Pair a d)', '(Word)', '(Query obs)']),
        '(CheckNow R2)': ('Refuted', ['(Pair a b) (Observe obs)']),
        '(CheckBehavioral R2)': ('Refuted', ['(WordWitness (Pair a b)', '(Word)'])}
SCOPE = {'(CheckNow R1)': ('Checked', []), '(CheckUpdates R1)': ('Checked', []), '(CheckBehavioral R1)': ('Checked', []),
         '(CheckNow R2)': ('Refuted', ['(Pair a b) (Observe obs)']),
         '(CheckBehavioral R2)': ('Refuted', ['(WordWitness (Pair a b)', '(Word)'])}
HAND = {'LB': FULL, 'LA': FULL, 'LS': dict(SCOPE, ScopedMin=('Checked', ['(Partition (Block a) (Block b))'])),
        'LW': dict(SCOPE, ScopedMin=('Checked', ['(Partition (Block a) (Block b))'])), 'LC': SCOPE}
SAME = [('LS', 'LW', {}), ('LC', 'LS', {}), ('LA', 'LB', {'Copy': 'Base'})]   # (Like module, written-out control, machine renames)

DOC04 = {'(CheckNow NoReadSets)': 'Checked', '(CheckUpdates NoReadSets)': 'Refuted', '(CheckBehavioral NoReadSets)': 'Refuted',
         '(CheckBehavioral ReadSets)': 'Checked', 'ResumeMemory': 'Checked'}   # doc04 s7.3 l.1518-1524; ResumeMemory: 11 classes on 12 states

INVALID = {'LN1': 'undeclared name Nope (expected Machine)', 'LN2': 'field Like names the machine itself',
           'LN3': 'field Like takes one value', 'LN4': 'duplicate field Like',
           'LN5': 'the update sends a to b, which leaves carrier Sub; the entry is taken from machine Base by field Like',
           'LN6': 'field Observe map obs does not start at the state carrier; the entry is taken from machine Base by field Like',
           'LN7': 'expected a reference to Machine, found (Base)'}
UNSUP = {'LU1': "Machine M: field Like together with the machine's own Observe field is outside the M0 lowering",
         'LU2': 'Machine M: field Like names machine Later, declared after it',
         'LU3': 'Machine M: field Like names machine N, which is outside the M0 fragment',
         'LU4': 'Machine M: field Like is lowered only in a Crisp module'}

wg = World(os.path.join(FX, 'like_gates.metta'))
wd = World(os.path.join(BUNDLE, 'memory_goals.metta'))
for mode in ([], ['--beyond-release']):
    tag = ' [%s]' % (mode[0] if mode else 'release')
    # probe X2 (repro d): D1 now answers as its written-out control D1C
    r = rows(os.path.join(ROOT, 'tests', 'dcalc', 'examples_e2e', 'repro', 'm0_blocker_d_like.metta'), mode)
    d1, d1c = r.get('D1 (CheckNow R)'), r.get('D1C (CheckNow R)')
    report('probe X2 D1: (Machine M (States A) (Like M0)) CheckNow R -> Checked, Blocks p q' + tag,
           meets(d1, 'Checked', ['(Blocks (Block p) (Block q))']), d1)
    report('probe X2 D1 == control D1C (written out)' + tag, d1 is not None and d1c is not None and norm(d1[2], 'D1') == norm(d1c[2], 'D1C'), (d1, d1c))
    # hand-worked + reference evaluator
    r = rows(os.path.join(FX, 'like_gates.metta'), mode)
    for mod, exp in HAND.items():
        for req, (st, subs) in exp.items():
            g = r.get('%s %s' % (mod, req))
            report('%s %s -> %s (by hand)%s' % (mod, req, st, tag), meets(g, st, subs), g)
            rst, rsubs = ref_expect(wg, mod, req)
            report('%s %s -> %s (reference evaluator)%s' % (mod, req, rst, tag), meets(g, rst, rsubs), (rst, rsubs, g))
    for a, b, ren in SAME:
        keys = [k.split(' ', 1)[1] for k in r if k.startswith(a + ' ')]
        def na(v):
            v = norm(v, a)
            for x, y in ren.items(): v = re.sub(r'\b%s\b' % x, y, v)
            return v
        ok = bool(keys) and all(r.get('%s %s' % (b, k)) and na(r['%s %s' % (a, k)][2]) == norm(r['%s %s' % (b, k)][2], b) for k in keys)
        report('%s answers byte-for-byte as %s (%d requests)%s' % (a, b, len(keys), tag), ok)
    # TaskResume with only Like left (desugared by the reference evaluator)
    r = rows(os.path.join(FX, 'taskresume_like.metta'), mode)
    for req, st in DOC04.items():
        g = r.get('TRL %s' % req)
        rst, rsubs = ref_expect(wd, 'TaskResume', req)
        report('TaskResume/Like %s -> %s as doc04 s7.3%s' % (req, st, tag), g is not None and g[0] == st == rst, (st, rst, g))
        report('TaskResume/Like %s: witness / partition as the reference evaluator on memory_goals.metta%s' % (req, tag), meets(g, rst, rsubs), (rsubs, g))
        w = r.get('TRW %s' % req)
        report('TaskResume/Like %s == written-out control TRW%s' % (req, tag), g is not None and w is not None and norm(g[2], 'TRL') == norm(w[2], 'TRW'), (g, w))
    g = r.get('TRL ResumeMemory')
    report('TaskResume/Like ResumeMemory: 11 classes on 12 states (doc04 s7.3 l.1524)' + tag,
           meets(g, 'Checked', ['#blocks=11']) and g[2].split('(Partition', 1)[1].split('(Evidence', 1)[0].count('(Tuple ') == 12, g)
    # negatives
    r = rows(os.path.join(FX, 'like_invalid.metta'), mode)
    for mod, why in INVALID.items():
        g = r.get('%s (CheckNow R1)' % mod)
        report('%s -> InvalidInput "%s"%s' % (mod, why[:60], tag), g is not None and g[0] == 'InvalidInput' and why in g[1], g)
    r = rows(os.path.join(FX, 'like_unsupported.metta'), mode)
    for mod, why in UNSUP.items():
        g = r.get('%s (CheckNow R1)' % mod)
        report('%s -> Unsupported naming Like%s' % (mod, tag), g is not None and g[0] == 'Unsupported' and why in g[1], g)
chk = subprocess.run([sys.executable, os.path.join(HERE, 'desugar_taskresume.py'), '--check'], capture_output=True, text=True)
report('fixtures/taskresume_like.metta is what desugar_taskresume.py generates', chk.returncode == 0, chk.stdout + chk.stderr)
print('m0_like: %s (%d failing)' % ('PASS' if not fails else 'FAIL', fails))
sys.exit(1 if fails else 0)
