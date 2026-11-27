#!/usr/bin/env python3
"""Gates for t-2026-11-24-mettadinc-families review 1: the Families elaborator's folds stay sound outside
Symbolic modules (finding 1), and forms it does not handle answer Unsupported with a Families reason."""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DC = os.environ.get('DCALC_FAMILIES_DC') or os.path.join(ROOT, 'build', 'dcalc', 'dcalc')
FXD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
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
        out[k.strip()] = (st.group(1) if st else None, rs.group(1) if rs else '')
    return out
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    r = rows(os.path.join(FXD, 'crisp_eq.metta'), mode)
    a = r.get('CE1 (CheckNow R)'); b = r.get('CE0 (CheckNow R)')
    report('F1 (%s): Crisp + Use Families, (Eq low low) in Cases folds to True/False -> not InvalidInput' % tag,
           a is not None and a[0] != 'InvalidInput', r)
    report('F1 (%s): same module without Use Families is unchanged (not InvalidInput)' % tag,
           b is not None and b[0] != 'InvalidInput', r)
# Review 1: a start word outside an inductive Invariant must fail Initiation, so induction must not certify the
# scope; the budget row is Refuted with Coverage at the start word (an Initiation-removed mutant answers Conditional).
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    o = subprocess.run([DC] + mode + [os.path.join(FXD, 'initiation.metta')], capture_output=True, text=True, timeout=120).stdout
    ln = [l for l in o.splitlines() if '(Budget (Unrollings 1))) => ' in l]
    ok = len(ln) == 1 and '(Status Refuted)' in ln[0] and '(Obligation Coverage)' in ln[0] and '(Witness 1)' in ln[0]
    report('Init (%s): start outside the Invariant -> Refuted, Coverage at word 1 (no induction certificate)' % tag, ok, ln)
    ln2 = [l for l in o.splitlines() if 'Low (Of OneReach)) => ' in l]
    report('Init (%s): unbudgeted row Refuted' % tag, len(ln2) == 1 and '(Status Refuted)' in ln2[0], ln2)
# Review 1 finding 4: Switch with an Any arm.  SwA's key has its own arm (sets bit 0): Refuted at word 1; an
# elaborator that always prefers Any reaches only word 2 and is not Refuted.  SwB's key has no arm and takes Any
# (sets bit 1): Refuted at word 2; a first-arm mutant reaches word 1, an Any-ignoring one answers Unsupported.
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    o = subprocess.run([DC] + mode + [os.path.join(FXD, 'switch_any.metta')], capture_output=True, text=True, timeout=120).stdout
    la = [l for l in o.splitlines() if l.startswith('SwA (CheckBlockPartition Bit0Low (Of MR)) => ')]
    report('Switch (%s): key with its own arm takes it, not Any -> Refuted, witness word 1' % tag,
           len(la) == 1 and '(Status Refuted)' in la[0] and '(Witness (Word 1)' in la[0], la)
    lb = [l for l in o.splitlines() if l.startswith('SwB (CheckBlockPartition Bit1Low (Of MR)) => ')]
    report('Switch (%s): key without an arm takes the Any arm -> Refuted, witness word 2' % tag,
           len(lb) == 1 and '(Status Refuted)' in lb[0] and '(Witness (Word 2)' in lb[0], lb)
# t-2026-11-26-mettadinc-families-followups-v2 step 2: exact verdicts for the Eq / And / Or folds (crisp_fold.metta).
# R merges all states into one code (Refuted iff the folded observation is not constant); RH splits mid off (Checked).
FOLD_EXP = {('FE', 'R'): 'Refuted', ('FE', 'RH'): 'Checked', ('FA', 'R'): 'Refuted', ('FA', 'RH'): 'Checked',
            ('FO', 'R'): 'Refuted', ('FO', 'RH'): 'Checked'}
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    o = subprocess.run([DC] + mode + [os.path.join(FXD, 'crisp_fold.metta')], capture_output=True, text=True, timeout=120).stdout
    for (mn, rep), st in sorted(FOLD_EXP.items()):
        ln = [l for l in o.splitlines() if l.startswith('%s (CheckNow %s) => ' % (mn, rep))]
        dfc = '(Defect (Interval 1 1))' if st == 'Refuted' else '(Defect (Interval 0 0))'
        report('Fold (%s): %s CheckNow %s -> %s %s' % (tag, mn, rep, st, dfc),
               len(ln) == 1 and ('(Status %s)' % st) in ln[0] and dfc in ln[0], ln)

# t-2026-11-26-mettadinc-families-gates-2 item 1: For expansion on a small fixture (for_small.metta), exact verdicts.
# FS needs the LAST element of the For (set.i2 sets bit 2): Refuted at word 4 on HEAD; a For that drops the last
# element never sets bit 2.  FT (bit 1, not the last element) is a control: Refuted at word 2 either way.
FOR_EXP = {'FS': ('Bit2Low', 4), 'FT': ('Bit1Low', 2)}
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    o = subprocess.run([DC] + mode + [os.path.join(FXD, 'for_small.metta')], capture_output=True, text=True, timeout=120).stdout
    for mn, (bp, w) in sorted(FOR_EXP.items()):
        ln = [l for l in o.splitlines() if l.startswith('%s (CheckBlockPartition %s (Of MR)) => ' % (mn, bp))]
        report('For/small (%s): %s CheckBlockPartition %s -> Refuted, Coverage, witness word %d' % (tag, mn, bp, w),
               len(ln) == 1 and '(Status Refuted)' in ln[0] and ('(Witness (Word %d) (Obligation Coverage)' % w) in ln[0], ln)

# t-2026-11-26-mettadinc-families-gates-2 item 2: the ForAll / Exists unfolding (forall_exists.metta), exact verdicts.
# QE (Exists body) and QA (ForAll body) need the LAST element of Ix: Refuted at word 4 on HEAD; an unfolding that
# drops the last instance answers otherwise.  QF (ForAll, first element) is a control: Refuted at word 1 either way.
QF_EXP = {'QE': ('Quiet', 4), 'QA': ('Good', 4), 'QF': ('Good', 1)}
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    o = subprocess.run([DC] + mode + [os.path.join(FXD, 'forall_exists.metta')], capture_output=True, text=True, timeout=120).stdout
    for mn, (bp, w) in sorted(QF_EXP.items()):
        ln = [l for l in o.splitlines() if l.startswith('%s (CheckBlockPartition %s (Of MR)) => ' % (mn, bp))]
        report('ForAll/Exists (%s): %s CheckBlockPartition %s -> Refuted, Coverage, witness word %d' % (tag, mn, bp, w),
               len(ln) == 1 and '(Status Refuted)' in ln[0] and ('(Witness (Word %d) (Obligation Coverage)' % w) in ln[0], ln)

# t-2026-11-26-mettadinc-families-followups-v2 step 1: For expansion checked automatically.  ex2 (access policy) is
# built with For fields; replay.py re-elaborates it independently (replay_families.elaborate) and replays every
# Checked/Refuted answer.  Required: replay exit 0 with the exact summary, and the exact per-request status list.
EX2 = os.path.join(ROOT, 'docs', 'e0', 'docs', '03_four_worked_examples', 'validation_bundles', 'ex2_access_policy',
                   'access_policy.metta')
# Rows 4 and 6 are decision-diagram answers: Conditional without a proof backend, Checked once DCALC_CADICAL and
# DCALC_CAKE_LPR are configured (as dcalc-run-all does with the backend exports); the expectation is exact either way.
EX2_BK = bool(os.environ.get('DCALC_CADICAL')) and bool(os.environ.get('DCALC_CAKE_LPR'))
EX2_DD = 'Checked' if EX2_BK else 'Conditional'
EX2_ST = ['Refuted', 'Refuted', 'Refuted', EX2_DD, 'Unknown', EX2_DD] + ['Unsupported'] * 9
EX2_SUM = ('replay: 5 replayed, 10 not Checked/Refuted, 0 failed' if EX2_BK
           else 'replay: 3 replayed, 12 not Checked/Refuted, 0 failed')
# DCALC_FAMILIES_SKIP_EX2=1 (set only by run_families_mutants.py, t-2026-11-26-mettadinc-families-gates-2 item 1):
# skip ex2 for a mutant binary; a dropped-last-element For on ex2 peaked at about 4.2 GB RSS.  The unmutated
# families step always runs it.
SKIP_EX2 = os.environ.get('DCALC_FAMILIES_SKIP_EX2') == '1'
if SKIP_EX2: print('SKIP  For/ex2 (both modes): DCALC_FAMILIES_SKIP_EX2=1 (mutant run)')
for mode in ([] if SKIP_EX2 else [[], ['--beyond-release']]):
    tag = mode[0] if mode else 'release'
    o = subprocess.run([DC] + mode + [EX2], capture_output=True, text=True, timeout=300).stdout
    st = [re.sub(r'^.* => \(Result \(Status ([A-Za-z]+)\).*$', r'\1', l) for l in o.splitlines() if ' => ' in l]
    report('For/ex2 (%s, proof backend %s): 15 answers with the expected status list' % (tag, 'on' if EX2_BK else 'off'), st == EX2_ST, st)
    tf = os.path.join(ROOT, 'build', 'families_ex2_%s.out' % tag.strip('-'))
    with open(tf, 'w') as fh: fh.write(o)
    rp = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'replay.py'), EX2, tf],
                        capture_output=True, text=True, timeout=300)
    last = (rp.stdout.strip().splitlines() or [''])[-1]
    report('For/ex2 (%s): replay.py re-elaborates and replays, "%s"' % (tag, EX2_SUM),
           rp.returncode == 0 and last == EX2_SUM, [rp.returncode, last])

# t-2026-11-26-mettadinc-families-followups-v2 step 3: Families + M6/M7 expansion is elaborated, never silently skipped.
M67_EXP = {('release', 'FB0'): ('Refuted', '(Witness (Word 2)'),
           ('release', 'FB6'): ('Unsupported', '(Reason "library Contracts is outside the first release")'),
           ('release', 'FB7'): ('Unsupported', '(Reason "library Hyperseed is outside the first release")'),
           ('--beyond-release', 'FB0'): ('Refuted', '(Witness (Word 2)'),
           ('--beyond-release', 'FB6'): ('Refuted', '(Witness (Word 2)'),
           ('--beyond-release', 'FB7'): ('Refuted', '(Witness (Word 2)')}
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    o = subprocess.run([DC] + mode + [os.path.join(FXD, 'families_m6_m7.metta')], capture_output=True, text=True, timeout=120).stdout
    for mn in ('FB0', 'FB6', 'FB7'):
        st, frag = M67_EXP[(tag, mn)]
        ln = [l for l in o.splitlines() if l.startswith('%s (CheckBlockPartition Low (Of MR)) => ' % mn)]
        report('Families+M6/M7 (%s): %s -> %s %s' % (tag, mn, st, frag),
               len(ln) == 1 and ('(Status %s)' % st) in ln[0] and frag in ln[0], ln)

print('run_families: ' + ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
