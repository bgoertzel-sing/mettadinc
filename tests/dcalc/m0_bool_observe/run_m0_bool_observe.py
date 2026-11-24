#!/usr/bin/env python3
"""Gates for t-2026-11-23-mettadinc-m0-bool-observe: a (To Bool) map used as an Observe port in the Crisp M0
lowering (spec Def 3.1/3.2, txt l.676-700: query value types with crisp equality; Core builtin type Bool with the
constants True and False; 5.4, l.1851-1857: total, non-overlapping cases with outputs in the declared type).
Every gate runs in release mode and with --beyond-release.  Hand answers are in the fixture's header."""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DC = os.path.join(ROOT, 'build', 'dcalc', 'dcalc')
FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'bool_observe_gates.metta')
DSG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'doc04_desugared.metta')
GEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'desugar_doc04.py')
PROBE = os.path.join(ROOT, 'tests', 'dcalc', 'examples_e2e', 'repro', 'm0_blocker_a_bool_observe.metta')
fails = 0
def report(name, ok, det=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '  :: ' + str(det)[:300]))
    if not ok: fails += 1
def rows(path, args=()):
    o = subprocess.run([DC] + list(args) + [path], capture_output=True, text=True, timeout=120)
    out = {}
    for l in o.stdout.splitlines():
        if ' => ' not in l: continue
        k, v = l.split(' => ', 1)
        st = re.search(r'\(Status ([A-Za-z]+)\)', v); rs = re.search(r'\(Reason "([^"]*)"', v)
        out[k.strip()] = (st.group(1) if st else None, rs.group(1) if rs else '', v)
    return out
def status(r, key, want, name, needle=None):
    g = r.get(key)
    report(name, g is not None and g[0] == want and (needle is None or needle in g[2]), g)
def partition_blocks(v):
    i = v.find('(Partition ')
    if i < 0: return None
    depth, j = 0, i
    while j < len(v):
        depth += v[j] == '('; depth -= v[j] == ')'
        if depth == 0: break
        j += 1
    p = v[i:j + 1]
    return p.count('(Block '), p.count('(Tuple ')
gen = subprocess.run([sys.executable, GEN], capture_output=True, text=True).stdout
report('doc04_desugared.metta is the output of desugar_doc04.py', gen == open(DSG).read())
DOC04 = [  # doc04's stated answers (s6.4 l.1422/1425, s7.3 l.1518-1524) on the hand-desugared modules
    ('AnchorMigrationD (CheckAbstractionMap NaiveMigration)', 'Refuted'),
    ('AnchorMigrationD (CheckAbstractionMap CellMigration)', 'Checked'),
    ('TaskResumeD (CheckNow NoReadSets)', 'Checked'),
    ('TaskResumeD (CheckUpdates NoReadSets)', 'Refuted'),
    ('TaskResumeD (CheckBehavioral NoReadSets)', 'Refuted'),
    ('TaskResumeD (CheckBehavioral ReadSets)', 'Checked'),
]
HAND = [  # (request, status, text that must appear in the result), worked by hand in the fixture header
    ('(CheckNow R1)', 'Checked', None),
    ('(CheckUpdates R1)', 'Checked', None),
    ('(CheckBehavioral R1)', 'Checked', None),
    ('(CheckNow R2)', 'Refuted', '(CurrentWitness (Pair p q) (Observe live) (Codes k1 k1)'),
    ('(CheckNow R3)', 'Checked', None),
    ('(CheckUpdates R3)', 'Refuted', '(UpdateWitness (Pair p t) (Action step) (Codes k1 k1) (Left k2) (Right k1))'),
    ('(CheckBehavioral R3)', 'Refuted', '(WordWitness (Pair p t) (Codes k1 k1) (Word (Do step)) (Query live)'),
    ('Min', 'Checked', '(Partition (Block p r) (Block q s) (Block t))'),
]
for mode in ([], ['--beyond-release']):
    tag = ' [%s]' % (mode[0] if mode else 'release')
    p = rows(PROBE, mode)
    status(p, 'A1 (CheckNow R)', 'Checked', 'probe A1: Bool Observe port, Encode id injective -> Checked' + tag)
    status(p, 'A1C (CheckNow R)', 'Checked', 'probe A1C control: same into Enum O -> Checked' + tag)
    r = rows(FX, mode)
    for req, st, needle in HAND:
        status(r, 'BO ' + req, st, 'BO %s -> %s (hand)%s' % (req, st, tag), needle)
        g, e = r.get('BO ' + req), r.get('BOE ' + req)
        report('BOE %s: same status as BO (Enum control)%s' % (req, tag), g is not None and e is not None and g[0] == e[0], (g, e))
    status(r, 'BO (CheckNow R2)', 'Refuted', 'BO R2 witness values are the Bool constants True/False' + tag, '(Left True) (Right False)')
    status(r, 'BT (CheckNow R2)', 'Checked', 'BT: Reach scope {t}, Bool Observe restricted -> Checked' + tag)
    status(r, 'BX (CheckNow R1)', 'InvalidInput', 'BX: case value maybe is undeclared -> InvalidInput' + tag, 'undeclared name maybe')
    status(r, 'BX2 (CheckNow R1)', 'InvalidInput', 'BX2: case value yes is not a Bool -> InvalidInput' + tag, 'Map live: Cases row 1 gives a value outside carrier Bool')
    status(r, 'BY (CheckNow R1)', 'InvalidInput', 'BY: no case for q -> InvalidInput' + tag, 'Map live: not total; no value for q')
    status(r, 'BW (CheckNow R1)', 'InvalidInput', 'BW: overlapping cases -> InvalidInput' + tag, 'overlapping cases are rejected')
    status(r, 'BZ (CheckNow R)', 'InvalidInput', 'BZ: Bool map from another carrier -> InvalidInput' + tag, 'field Observe map live does not start at the state carrier')
    status(r, 'BU1 (CheckNow RB)', 'Unsupported', 'BU1: Encode into Bool -> Unsupported naming the form' + tag, 'a (To Bool) map is lowered only as an Observe port')
    status(r, 'BU2 (CheckNow R1)', 'Unsupported', 'BU2: Eq in a Bool Observe case -> Unsupported naming the form' + tag, 'Observe live: Map live: Cases row 0 uses an operator outside the M0 fragment')
    status(r, 'BU3 (CheckNow R1)', 'Unsupported', 'BU3: Bool Observe in a Graded module -> Unsupported naming the form' + tag, 'lowered only in a Crisp module')
    d = rows(DSG, mode)
    for key, st in DOC04: status(d, key, st, 'doc04 desugared %s -> %s (doc04)%s' % (key, st, tag))
    g = d.get('TaskResumeD ResumeMemory')
    report('doc04 desugared ResumeMemory -> Checked, 11 classes on 12 states (doc04 s7.3 l.1524)' + tag,
           g is not None and g[0] == 'Checked' and partition_blocks(g[2]) == (11, 12), (g and partition_blocks(g[2]), g))
print('m0_bool_observe: %s (%d failing)' % ('PASS' if not fails else 'FAIL', fails))
sys.exit(1 if fails else 0)
