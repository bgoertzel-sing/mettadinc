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
print('run_families: ' + ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
