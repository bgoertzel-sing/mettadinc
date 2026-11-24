#!/usr/bin/env python3
"""Gates for t-2026-11-24-mettadinc-m0-body-maps: (Body ($v) expr) maps in the Crisp M0 lowering
(spec 5.1 l.1721 map-body grammar; 5.4 l.1856 "Body binds its single argument lexically"; 5.3 l.1784-1786
admission obligations by enumeration).  Probe: tests/dcalc/examples_e2e/repro/m0_blocker_f_crisp_body.metta (F1,
control F1C).  Every gate runs in release mode and with --beyond-release.  Expected answers come from:
  1. worked by hand (README.md), hard-coded below;
  2. Ben's reference evaluator (docs/e0/.../04_omega_memory_goals_part1/validation_bundle/mg_eval.py, World.call
     evaluates a Body as ev(expr, {$v: arg})) with models/dclib.py, run on the same fixture text;
  3. a written-out twin of every Body module (Table / literal Cases), which must answer byte-for-byte the same;
  4. for doc04, doc04's own answers (s6.4 l.1422-1425, s7.3 l.1518-1524) with the doc04 Body maps verbatim and
     every other M0 gap desugared, and the reference evaluator on the original memory_goals.metta.
"""
import os, re, subprocess, sys, tempfile
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

def rows_text(text, args=()):
    with tempfile.NamedTemporaryFile('w', suffix='.metta', delete=False) as fh: fh.write(text)
    try: return rows(fh.name, args)
    finally: os.unlink(fh.name)

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

# ---- hand-worked answers (README.md) ----
# BG1: X = -2 -1 0 1 2; neg x = -x; sq x = x*x; pron x = x*x + x = 2 0 0 2 6; id.  M: Observe sq, Action neg; MI: Observe id.
BG1 = {'(CheckNow RSq)': ('Checked', ['(Blocks (Block -2 2) (Block -1 1) (Block 0))']),
       '(CheckUpdates RSq)': ('Checked', ['(Blocks (Block -2 2) (Block -1 1) (Block 0))']),
       '(CheckBehavioral RSq)': ('Checked', []),
       '(CheckNow RQ)': ('Refuted', ['(CurrentWitness (Pair -2 1) (Observe sq) (Codes 2 2) (Left 4) (Right 1))']),
       '(CheckUpdates RQ)': ('Refuted', ['(UpdateWitness (Pair -2 1) (Action neg) (Codes 2 2) (Left 6) (Right 0))']),
       '(CheckBehavioral RQ)': ('Refuted', ['(WordWitness (Pair -2 1) (Codes 2 2) (Word) (Query sq) (Left 4) (Right 1)']),
       '(CheckNow RI)': ('Refuted', ['(CurrentWitness (Pair -2 2) (Observe id) (Codes 4 4) (Left -2) (Right 2))']),
       '(CheckBehavioral RI)': ('Refuted', ['(WordWitness (Pair -2 2) (Codes 4 4) (Word) (Query id) (Left -2) (Right 2)']),
       'MMin': ('Checked', ['(Leaf (Block -2 2)) (Leaf (Block -1 1)) (Leaf (Block 0))', '#blocks=3'])}
# BT1: All = (present old) (present none) (absent old) (absent none); lesion = const (absent none); live = link;
# keep = id (injective); forget = const (Tuple none); wrap x = (Tuple x old) (injective).
PO, PN, AO, AN = '(Tuple present old)', '(Tuple present none)', '(Tuple absent old)', '(Tuple absent none)'
ALLB = '(Blocks (Block %s) (Block %s) (Block %s) (Block %s))' % (PO, PN, AO, AN)
BT1 = {'(CheckNow RK)': ('Checked', [ALLB]), '(CheckUpdates RK)': ('Checked', [ALLB]), '(CheckBehavioral RK)': ('Checked', []),
       '(CheckNow RF)': ('Refuted', ['(CurrentWitness (Pair %s %s) (Observe live) (Codes (Tuple none) (Tuple none)) (Left old) (Right none))' % (PO, PN)]),
       '(CheckUpdates RF)': ('Checked', ['(Blocks (Block %s %s %s %s))' % (PO, PN, AO, AN)]),
       '(CheckBehavioral RF)': ('Refuted', ['(WordWitness (Pair %s %s) (Codes (Tuple none) (Tuple none)) (Word) (Query live) (Left old) (Right none)' % (PO, PN)]),
       '(CheckNow RW)': ('Checked', [ALLB]), '(CheckBehavioral RW)': ('Checked', [])}
# BB1: A = p q; yes = const True (Bool Observe port); swap; one = const p.  One class of observations: Checked, Blocks (p q).
BB1 = {'(CheckNow R)': ('Checked', ['(Blocks (Block p q))']), '(CheckBehavioral R)': ('Checked', [])}
# BT2: BG1's RQ with codes and observations as one-element tuples.
BT2 = {'(CheckNow RQ)': ('Refuted', ['(CurrentWitness (Pair -2 1) (Observe sq) (Codes (Tuple 2) (Tuple 2)) (Left (Tuple 4)) (Right (Tuple 1)))']),
       '(CheckUpdates RQ)': ('Refuted', ['(UpdateWitness (Pair -2 1) (Action neg) (Codes (Tuple 2) (Tuple 2)) (Left (Tuple 6)) (Right (Tuple 0)))']),
       '(CheckBehavioral RQ)': ('Refuted', ['(WordWitness (Pair -2 1) (Codes (Tuple 2) (Tuple 2)) (Word) (Query sq) (Left (Tuple 4)) (Right (Tuple 1))'])}
HAND = {'BG1': BG1, 'BT1': BT1, 'BT2': BT2, 'BB1': BB1}

INVALID = {'BN1': 'Map inc: Body sends 2 to 3, which is not in carrier N',
           'BN2': 'Map inc: Body on 9223372036854775807: integer overflow',
           'BN3': 'Map dup: Body gives (Tuple (Tuple present old) (Tuple present old)) on (Tuple present old), which is not of the To type (Tuple Symbol Symbol)',
           'BN4': 'Map bump: Body has no value on (Tuple present old), so the map is not total on carrier All',
           'BN5': 'Map lesion: sends (Tuple present old) to (Tuple absent none), which leaves carrier Up',
           'BN6': 'Map yes: Body sends p to p, which is not in carrier Bool',
           'BN7': 'unbound variable $y',
           'BN8': 'unbound variable $x',
           'BN9': 'Map f: a Body must be (Body ($v) expr)'}
UNSUP = {'BU1': 'Map flip: Body uses If, an operator outside the M0 fragment',
         'BU2': 'Map link: Body uses GetTuple, an operator outside the M0 fragment',
         'BU3': 'Map dec: Body uses Sub, an operator outside the M0 fragment'}

DOC04_TR = {'(CheckNow NoReadSets)': 'Checked', '(CheckUpdates NoReadSets)': 'Refuted', '(CheckBehavioral NoReadSets)': 'Refuted',
            '(CheckBehavioral ReadSets)': 'Checked', 'ResumeMemory': 'Checked'}   # doc04 s7.3 l.1518-1524
DOC04_AM = {'(CheckAbstractionMap NaiveMigration)': 'Refuted', '(CheckAbstractionMap CellMigration)': 'Checked'}   # doc04 s6.4 l.1422, l.1425

# doc04 TaskResume with every gap but the Body map desugared: TRL of tests/dcalc/m0_like/fixtures/taskresume_like.metta
# (generated there from memory_goals.metta by the reference evaluator), with checkpoint-with-reads put back as
# doc04 writes it (memory_goals.metta l.423-424): a type-form To and (Body ($x) $x).
tl = open(os.path.join(ROOT, 'tests', 'dcalc', 'm0_like', 'fixtures', 'taskresume_like.metta')).read()
trl = tl[tl.index('(DC.Module TRL'):tl.index('(DC.Module TRW')]
cwr = re.search(r'  \(Map checkpoint-with-reads \(From Task\) \(To [^)]*\)\n    \(Table [^\n]*\)\)\n', trl).group(0)
DOC04_CWR = '  (Map checkpoint-with-reads (From Task) (To (Tuple Symbol Symbol Symbol Symbol))\n    (Body ($x) $x))\n'
trb = trl.replace(cwr, DOC04_CWR).replace('TRL', 'TRB')
assert '(Body ($x) $x)' in trb
# doc04 AnchorMigration with every gap but the Body map desugared: AnchorMigrationD of
# tests/dcalc/m0_bool_observe/fixtures/doc04_desugared.metta, with doc04's lesion (memory_goals.metta l.356-357) in
# place of its two tabulated copies lesion-o / lesion-n.
dd = open(os.path.join(ROOT, 'tests', 'dcalc', 'm0_bool_observe', 'fixtures', 'doc04_desugared.metta')).read()
amd = dd[dd.index('(DC.Module AnchorMigrationD'):dd.index('(DC.Module TaskResumeD')]
amd_mod = amd[:amd.index('!(dc.run')]
DOC04_LESION = '  (Map lesion (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol))\n    (Body ($x) (Tuple absent none)))\n'
amb = re.sub(r'  \(Map lesion-o [^\n]*\n', DOC04_LESION, amd_mod)
amb = re.sub(r'  \(Map lesion-n [^\n]*\n', '', amb).replace('(Action lesion lesion-o)', '(Action lesion lesion)').replace('(Action lesion lesion-n)', '(Action lesion lesion)')
amb = amb.replace('AnchorMigrationD', 'AnchorMigrationB') + ''.join('!(dc.run AnchorMigrationB %s)\n' % q for q in DOC04_AM)
assert 'lesion-' not in amb

src_doc04 = open(os.path.join(BUNDLE, 'memory_goals.metta')).read()
report('doc04 writes checkpoint-with-reads as (Body ($x) $x) with a type-form To (the form gated here)',
       re.search(r'\(Map checkpoint-with-reads \(From Task\) \(To \(Tuple Symbol Symbol Symbol Symbol\)\)\s+\(Body \(\$x\) \$x\)\)', src_doc04) is not None)
report('doc04 writes lesion as (Body ($x) (Tuple absent none)) with type-form From/To (the form gated here)',
       re.search(r'\(Map lesion \(From \(Tuple Symbol Symbol\)\) \(To \(Tuple Symbol Symbol\)\)\s+\(Body \(\$x\) \(Tuple absent none\)\)\)', src_doc04) is not None)

wg = World(os.path.join(FX, 'body_gates.metta'))
wd = World(os.path.join(BUNDLE, 'memory_goals.metta'))
for mode in ([], ['--beyond-release']):
    tag = ' [%s]' % (mode[0] if mode else 'release')
    # probe: repro f
    r = rows(os.path.join(ROOT, 'tests', 'dcalc', 'examples_e2e', 'repro', 'm0_blocker_f_crisp_body.metta'), mode)
    f1, f1c = r.get('F1 (CheckNow R)'), r.get('F1C (CheckNow R)')
    report('probe F1: (Map reset (From A) (To A) (Body ($x) p)) CheckNow R -> Checked, Blocks p q (by hand)' + tag,
           meets(f1, 'Checked', ['(Blocks (Block p) (Block q))']), f1)
    report('control F1C unchanged: Checked, Blocks p q' + tag, meets(f1c, 'Checked', ['(Blocks (Block p) (Block q))']), f1c)
    report('probe F1 == control F1C byte-for-byte (module, digest aside)' + tag,
           f1 is not None and f1c is not None and norm(f1[2], 'F1') == norm(f1c[2], 'F1C'), (f1, f1c))
    # hand-worked + reference evaluator + written-out twins
    r = rows(os.path.join(FX, 'body_gates.metta'), mode)
    for mod, exp in HAND.items():
        for req, (st, subs) in exp.items():
            g = r.get('%s %s' % (mod, req))
            report('%s %s -> %s (by hand)%s' % (mod, req, st, tag), meets(g, st, subs), g)
            rst, rsubs = ref_expect(wg, mod, req)
            report('%s %s -> %s (reference evaluator)%s' % (mod, req, rst, tag), meets(g, rst, rsubs), (rst, rsubs, g))
            c = r.get('%sC %s' % (mod, req))
            report('%s %s == written-out twin %sC%s' % (mod, req, mod, tag), g is not None and c is not None and norm(g[2], mod) == norm(c[2], mod + 'C'), (g, c))
    # doc04 TaskResume, Body map verbatim, the rest desugared
    r = rows_text(trb, mode)
    for req, st in DOC04_TR.items():
        g = r.get('TRB %s' % req)
        rst, rsubs = ref_expect(wd, 'TaskResume', req)
        report('TaskResume/Body %s -> %s as doc04 s7.3%s' % (req, st, tag), g is not None and g[0] == st == rst, (st, rst, g))
        report('TaskResume/Body %s: witness / partition as the reference evaluator on memory_goals.metta%s' % (req, tag), meets(g, rst, rsubs), (rsubs, g))
    g = r.get('TRB ResumeMemory')
    report('TaskResume/Body ResumeMemory: 11 classes on 12 states (doc04 s7.3 l.1524)' + tag,
           meets(g, 'Checked', ['#blocks=11']) and g[2].split('(Partition', 1)[1].split('(Evidence', 1)[0].count('(Tuple ') == 12, g)
    # doc04 AnchorMigration, lesion verbatim, the rest desugared; must answer as the fully desugared AnchorMigrationD
    r = rows_text(amb, mode); rd = rows(os.path.join(ROOT, 'tests', 'dcalc', 'm0_bool_observe', 'fixtures', 'doc04_desugared.metta'), mode)
    for req, st in DOC04_AM.items():
        g, d = r.get('AnchorMigrationB %s' % req), rd.get('AnchorMigrationD %s' % req)
        report('AnchorMigration/Body %s -> %s as doc04 s6.4%s' % (req, st, tag), g is not None and g[0] == st, g)
        report('AnchorMigration/Body %s == AnchorMigrationD (lesion tabulated by hand)%s' % (req, tag),
               g is not None and d is not None and norm(g[2], 'AnchorMigrationB') == norm(d[2], 'AnchorMigrationD'), (g, d))
    # negatives
    r = rows(os.path.join(FX, 'body_invalid.metta'), mode)
    for mod, why in INVALID.items():
        g = r.get('%s (CheckNow R)' % mod)
        report('%s -> InvalidInput "%s"%s' % (mod, why[:70], tag), g is not None and g[0] == 'InvalidInput' and why in g[1], g)
    r = rows(os.path.join(FX, 'body_unsupported.metta'), mode)
    for mod, why in UNSUP.items():
        g = r.get('%s (CheckNow R)' % mod)
        report('%s -> Unsupported naming the form%s' % (mod, tag), g is not None and g[0] == 'Unsupported' and why in g[1], g)
print('m0_body_maps: %s (%d failing)' % ('PASS' if not fails else 'FAIL', fails))
sys.exit(1 if fails else 0)
