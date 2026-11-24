#!/usr/bin/env python3
"""Gates for t-2026-11-24-mettadinc-m0-gap-g: a (To Bool) map used as an Observe port and declared with a type-form
From (repro g, tests/dcalc/examples_e2e/repro/m0_blocker_g_bool_typeform_from.metta; doc04 AnchorMigration
live-old/live-new).  The meaning combines the two existing lowerings: the type-form map is tabulated on the states of
the machine where it is used (t-2026-11-23-mettadinc-m0-typeform-maps) and its values lie in the implicit Bool carrier
{False, True} (t-2026-11-23-mettadinc-m0-bool-observe).  Every gate runs in release mode and with --beyond-release.
Expected answers come from:
  1. worked by hand (README.md), hard-coded below;
  2. Ben's reference evaluator (docs/e0 doc04 bundle: mg_eval.World + models/dclib, via
     ../m0_typeform_maps/reference_answers.py), run on the same fixture text;
  3. a twin GGnC of every module whose Bool maps name the declared state carrier in From (the bool-observe
     lowering), which must answer byte-for-byte the same (module and digest masked);
  4. doc04's own AnchorMigration answers (s6.4 l.1422, l.1425) on memory_goals.metta verbatim, and mg_results.json.
Near misses (fixtures/gapg_negative.metta) must answer as their declared-carrier twin and with the stated reason.
DCALC overrides the binary (used to show the gate fails on the base binary and on mutants)."""
import json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DC = os.environ.get('DCALC') or os.path.join(ROOT, 'build', 'dcalc', 'dcalc')
FX = os.path.join(HERE, 'fixtures')
BUNDLE = os.path.join(ROOT, 'docs', 'e0', 'docs', '04_omega_memory_goals_part1', 'validation_bundle')
PROBE = os.path.join(ROOT, 'tests', 'dcalc', 'examples_e2e', 'repro', 'm0_blocker_g_bool_typeform_from.metta')
REF = os.path.join(ROOT, 'tests', 'dcalc', 'm0_typeform_maps', 'reference_answers.py')
sys.path[:0] = [BUNDLE, os.path.join(BUNDLE, 'models')]
from mg_eval import World  # noqa: E402
from dclib import Machine, check_abstraction_map  # noqa: E402

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

def rows_text(text, args=()):
    with tempfile.NamedTemporaryFile('w', suffix='.metta', delete=False) as fh: fh.write(text)
    try: return rows(fh.name, args)
    finally: os.unlink(fh.name)

def norm(v):
    v = re.sub(r'\(Module [^()\s]+\)', '(Module _)', v)
    return re.sub(r'\(Digest "[0-9a-f]*"\)', '(Digest _)', v)

def meets(g, st, subs):
    return g is not None and g[0] == st and all(s in g[2] for s in subs)

def sx(v):
    if isinstance(v, tuple): return '(Tuple ' + ' '.join(sx(x) for x in v) + ')'
    if isinstance(v, bool): return 'True' if v else 'False'
    return str(v)

# ---- hand-worked answers (README.md) ----
PP, PQ, QP, QQ = '(Tuple p p)', '(Tuple p q)', '(Tuple q p)', '(Tuple q q)'
HAND = {
    # GG1: AA = {p,q}^2 in order pp pq qp qq; same = Eq a b: T F F T; swap; fst: p p q q; eqc = y n n y.
    'GG1 (CheckNow RF)': ('Refuted', ['(CurrentWitness (Pair %s %s) (Observe same) (Codes p p) (Left True) (Right False))' % (PP, PQ)]),
    'GG1 (CheckUpdates RF)': ('Refuted', ['(UpdateWitness (Pair %s %s) (Action swap) (Codes p p) (Left p) (Right q))' % (PP, PQ)]),
    'GG1 (CheckNow RE)': ('Checked', ['(Blocks (Block %s %s) (Block %s %s))' % (PP, QQ, PQ, QP)]),
    'GG1 (CheckUpdates RE)': ('Checked', ['(Blocks (Block %s %s) (Block %s %s))' % (PP, QQ, PQ, QP)]),
    'GG1 (CheckNow RI)': ('Checked', ['(Blocks (Block %s) (Block %s) (Block %s) (Block %s))' % (PP, PQ, QP, QQ)]),
    # GG2: S = {pq, qp} (Subset of AA by Not (Eq a b)); pfirst: pq T, qp F (no case for pp, qq); psecond = Eq b p:
    # pq F, qp T; pq = Eq a p: pq T, qp F; one = constant p; flip-s swaps.
    'GG2 (CheckNow R1)': ('Refuted', ['(CurrentWitness (Pair %s %s) (Observe live) (Codes p p) (Left True) (Right False))' % (PQ, QP)]),
    'GG2 (CheckUpdates R1)': ('Checked', ['(Blocks (Block %s %s))' % (PQ, QP)]),
    'GG2 (CheckAbstractionMap H12)': ('Checked', ['(Table (Row %s %s) (Row %s %s))' % (PQ, QP, QP, PQ)]),
    'GG2 (CheckAbstractionMap H13)': ('Refuted', ['(CommutationWitness (State %s) (Observe live) (Left True) (Right False))' % PQ]),
    'GG2 (CheckAbstractionMap H12I)': ('Refuted', ['(CommutationWitness (State %s) (Observe live) (Left True) (Right False))' % PQ]),
    'GG2 (CheckAbstractionMap H13I)': ('Checked', ['(Table (Row %s %s) (Row %s %s))' % (PQ, PQ, QP, QP)]),
    # GG3: yes = (Body ($x) True); one = constant p: one block.
    'GG3 (CheckNow R)': ('Checked', ['(Blocks (Block %s %s %s %s))' % (PP, PQ, QP, QQ)]),
    'GG3 (CheckUpdates R)': ('Checked', ['(Blocks (Block %s %s %s %s))' % (PP, PQ, QP, QQ)]),
}
# near misses: (status, reason substring); every one must also answer with the status of its declared-carrier twin
NEG = {
    'NT1': ('InvalidInput', 'NT1.live: undeclared name Truth'),
    'NF1': ('InvalidInput', 'NF1.live: undeclared name BB'),
    'NF2': ('InvalidInput', 'Map live: From type (Tuple Symbol Symbol Symbol) is not the element type of carrier AA, where the map is used, which is (Tuple Symbol Symbol)'),
    'NW1': ('InvalidInput', 'Map live: sends (Tuple p p) to p, which leaves carrier Bool'),
    'NW2': ('InvalidInput', 'Map live: not total on carrier AA; no value for (Tuple q q)'),
    'NW3': ('InvalidInput', 'Map live: input (Tuple p p) matches Cases rows 0 and 1; overlapping cases are rejected'),
    'NG1': ('Unsupported', 'Observe live: map live targets Bool; a (To Bool) Observe map is lowered only in a Crisp module'),
    'NA1': ('Unsupported', 'CheckNow: Representation R is outside the M0 fragment'),
    'NE1': ('Unsupported', 'Encode map live targets Bool; a (To Bool) map is lowered only as an Observe port'),
    'NU1': ('Unsupported', 'Observe live: Map live: Body uses Eq, an operator outside the M0 fragment'),
    'NU2': ('Unsupported', 'Observe live: Map live: Cases row 0 uses an operator outside the M0 fragment'),
}
# doc04 s6.4: NaiveMigration Refuted (l.1422), CellMigration Checked (l.1425); witness as mg_results.json records it
DOC04_AM = {'(CheckAbstractionMap NaiveMigration)': ('Refuted', ['(CommutationWitness (State (Tuple absent none)) (Action repair) (Left (Tuple present new)) (Right (Tuple present old)))']),
            '(CheckAbstractionMap CellMigration)': ('Checked', ['(Table (Row (Tuple present old) (Tuple present new)) (Row (Tuple absent none) (Tuple absent none)))'])}

# reference evaluator on the gate fixture
GATES = os.path.join(FX, 'gapg_gates.metta')
rp = subprocess.run([sys.executable, REF, GATES], capture_output=True, text=True, timeout=300)
ref = {}
for l in rp.stdout.splitlines():
    k, st, w = l.split('\t'); ref[k] = (st, w)
report('reference evaluator ran on gapg_gates.metta and answered all %d requests' % (2 * len(HAND)), rp.returncode == 0 and len(ref) == 2 * len(HAND), rp.stderr[-300:])
# reference evaluator on doc04 AnchorMigration verbatim
src_doc04 = os.path.join(BUNDLE, 'memory_goals.metta')
doc = open(src_doc04).read()
report('doc04 declares live-old/live-new as (To Bool) maps with type-form From (the form gated here)',
       all(re.search(r'\(Map %s \(From \(Tuple Symbol Symbol\)\) \(To Bool\)' % n, doc) for n in ('live-old', 'live-new')))
wd = World(src_doc04)
def mach(w, mod, name):
    st, acts, obs = w.machine(mod, name); return Machine(st, acts, obs)
refam = {}
for req in DOC04_AM:
    src, tgt, h = wd.abstraction_map('AnchorMigration', req.strip('()').split()[1])
    r = check_abstraction_map(mach(wd, 'AnchorMigration', src), mach(wd, 'AnchorMigration', tgt), h)
    refam[req] = ('Checked', None) if r is None else ('Refuted', r)
res = json.load(open(os.path.join(BUNDLE, 'mg_results.json')))
def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r is not None: return r
    return None
naive = find_key(res, 'B AnchorMigration: NaiveMigration'); cell = find_key(res, 'B AnchorMigration: CellMigration')
report('reference evaluator on memory_goals.metta: NaiveMigration Refuted at (absent none) by repair, CellMigration Checked; as recorded in mg_results.json',
       refam['(CheckAbstractionMap NaiveMigration)'][0] == 'Refuted' and refam['(CheckAbstractionMap CellMigration)'][0] == 'Checked'
       and naive is not None and naive.get('ok') and naive['got']['state'] == ['absent', 'none'] and naive['got']['action'] == 'repair'
       and tuple(refam['(CheckAbstractionMap NaiveMigration)'][1]['state']) == ('absent', 'none')
       and cell is not None and cell.get('ok') and cell['got'] is None, (refam, naive, cell))

neg_text = open(os.path.join(FX, 'gapg_negative.metta')).read()
neg_twin = neg_text.replace('(From (Tuple Symbol Symbol))', '(From AA)')
for mode in ([], ['--beyond-release']):
    tag = ' [%s]' % (mode[0] if mode else 'release')
    # probe: repro g
    r = rows(PROBE, mode)
    g1, g1c = r.get('G1 (CheckNow R)'), r.get('G1C (CheckNow R)')
    blocks = '(Blocks (Block %s) (Block %s) (Block %s) (Block %s))' % (PP, PQ, QP, QQ)
    report('probe G1: (Map live (From (Tuple Symbol Symbol)) (To Bool) ...) as Observe -> Checked, four singleton blocks (by hand: Encode id)' + tag, meets(g1, 'Checked', [blocks]), g1)
    report('control G1C unchanged: Checked, four singleton blocks' + tag, meets(g1c, 'Checked', [blocks]), g1c)
    report('probe G1 == control G1C byte-for-byte (module, digest aside)' + tag, g1 is not None and g1c is not None and norm(g1[2]) == norm(g1c[2]), (g1, g1c))
    # hand-worked + reference + twins
    r = rows(GATES, mode)
    for key, (st, subs) in HAND.items():
        g = r.get(key); mod, req = key.split(' ', 1)
        report('%s -> %s (by hand)%s' % (key, st, tag), meets(g, st, subs), g)
        rs, rw = ref.get(key, (None, None))
        ok = g is not None and g[0] == rs
        if ok and rw != '-':
            ok = all(part in g[2] for part in re.findall(r'\((?:Pair|State|Action|Observe) (?:[^()]|\([^()]*\))*\)', rw))
        report('%s -> %s %s (reference evaluator)%s' % (key, rs, rw, tag), ok, (rs, rw, g))
        c = r.get('%sC %s' % (mod, req))
        report('%s == declared-carrier twin %sC%s' % (key, mod, tag), g is not None and c is not None and norm(g[2]) == norm(c[2]), (g, c))
    # doc04 AnchorMigration verbatim
    r = rows(src_doc04, mode)
    for req, (st, subs) in DOC04_AM.items():
        g = r.get('AnchorMigration %s' % req)
        report('doc04 AnchorMigration %s -> %s as doc04 s6.4 and the reference evaluator, memory_goals.metta verbatim%s' % (req, st, tag),
               meets(g, st, subs) and refam[req][0] == st, g)
    # near misses
    r = rows_text(neg_text, mode); rt = rows_text(neg_twin, mode)
    for mod, (st, why) in NEG.items():
        g, t = r.get('%s (CheckNow R)' % mod), rt.get('%s (CheckNow R)' % mod)
        report('%s -> %s "%s"%s' % (mod, st, why[:80], tag), g is not None and g[0] == st and why in g[1], g)
        report('%s answers with the status of its declared-carrier twin (%s)%s' % (mod, st, tag), g is not None and t is not None and g[0] == t[0], (g, t))
print('m0_gap_g: %s (%d failing)' % ('PASS' if not fails else 'FAIL', fails))
sys.exit(1 if fails else 0)
