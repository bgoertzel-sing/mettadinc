#!/usr/bin/env python3
"""Review 4 F1: replay.py must recompute every envelope field.

Runs build/dcalc/dcalc on envelope.metta, checks each real row replays, then
applies one forgery at a time (per field: Status, Claim, Binding.*, Scope.*,
Assumptions, Assurance.*, field order/extra/missing) and requires replay.py
to refuse every one.  Exit 0 iff all real rows replay and all forgeries fail."""
import copy, importlib.util, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
spec = importlib.util.spec_from_file_location('replay', os.path.join(ROOT, 'tests/dcalc/replay.py'))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
FIX = os.path.join(HERE, 'envelope.metta')

def sub(env, *path):
    x = env
    for h in path: x = R.find(x, h)
    return x
def setf(*path):
    def f(e, v): sub(e, *path)[1] = v
    return f

def other_request(q):
    # a different request over the same subject, so the forgery is never a no-op
    return ['CheckUpdates' if q[0] == 'CheckNow' else 'CheckNow', 'Full', ['Within', '0']]

def flip_checks(e):
    # review 4 F5: a certificate must name the obligation it checks; on rows
    # without a certificate, swap the witness head instead
    ev = sub(e, 'Evidence'); c = R.find(ev, 'Certificate')
    if c is not None and R.find(c, 'Checks'): k = R.find(c, 'Checks'); k[1] = 'Current' if k[1] == 'Update' else 'Update'
    else:
        w = R.find(ev, 'Witness')
        if w is None or not isinstance(w[1], list) or w[1][0] not in ('CurrentWitness', 'UpdateWitness'):
            return False   # not applicable (abstraction-map rows): skipped, not counted
        w[1][0] = 'UpdateWitness' if w[1][0] == 'CurrentWitness' else 'CurrentWitness'

def forgeries(env):
    st = sub(env, 'Status')[1]
    F = [
     ('Status', lambda e: setf('Status')(e, 'Refuted' if st == 'Checked' else 'Checked')),
     ('Claim request', lambda e: setf('Claim')(e, other_request(sub(e, 'Claim')[1]))),
     ('Claim equality', lambda e: sub(e, 'Claim').__setitem__(2, ['Equality', 'Tolerant'])),
     ('Binding.Module', lambda e: setf('Binding', 'Module')(e, 'Other')),
     ('Binding.Digest', lambda e: setf('Binding', 'Digest')(e, ('str', '0' * 64))),
     ('Binding.Subject', lambda e: sub(e, 'Binding', 'Subject').append(['Extra', 'X'])),
     ('Binding.Source', lambda e: setf('Binding', 'Source')(e, 'UnrelatedMachine')),
     ('Binding.Target', lambda e: setf('Binding', 'Target')(e, 'UnrelatedCarrier')),
     ('Binding.Interface', lambda e: setf('Binding', 'Interface', 'Tolerance')(e, 'AllCodes')),
     ('Scope.Profile', lambda e: setf('Scope', 'Profile')(e, 'Stochastic')),
     ('Scope.Fragment', lambda e: setf('Scope', 'Fragment')(e, 'M1-Anything')),
     ('Scope.InitialStates', lambda e: setf('Scope', 'InitialStates')(e, 'Some')),
     ('Scope.ReachableStates', lambda e: setf('Scope', 'ReachableStates')(e, 'Some')),
     ('Scope.Horizon', lambda e: setf('Scope', 'Horizon')(e, '3')),
     ('Scope.Discount', lambda e: setf('Scope', 'Discount')(e, '0.9')),
     ('Scope.PolicyClass', lambda e: setf('Scope', 'PolicyClass')(e, 'Any')),
     ('Evidence.Checks', flip_checks),
     ('Assumptions', lambda e: sub(e, 'Assumptions').append(['TrustedBackend', 'UnprovedBackend'])),
     ('Assurance.Policy', lambda e: setf('Assurance', 'Policy')(e, 'Trusted')),
     ('Assurance.Replayed', lambda e: setf('Assurance', 'Replayed')(e, 'False')),
     ('Assurance.Ground', lambda e: setf('Assurance', 'Ground')(e, 'None')),
     ('extra field', lambda e: e.append(['Note', 'x'])),
     ('missing Assumptions', lambda e: e.remove(sub(e, 'Assumptions'))),
     ('field order', lambda e: e.__setitem__(slice(1, 3), [e[2], e[1]])),
    ]
    return F

def main():
    form = [f for f in R.parse(open(FIX).read()) if isinstance(f, list) and f and f[0] == 'DC.Module'][0]
    M, D = R.Module(form), R.derives(None, form)
    cp = subprocess.run([DCALC, FIX], capture_output=True, text=True)
    if cp.returncode != 0: print('FAIL dcalc rc=%d' % cp.returncode); return 1
    rows = [l.split(' => ', 1) for l in cp.stdout.splitlines() if ' => ' in l]
    rc = 0; n = 0
    if len(rows) != 9: print('FAIL expected 9 rows, got %d' % len(rows)); rc = 1
    for head, env_s in rows:
        req = R.parse(head.split(' ', 1)[1])[0]; env = R.parse(env_s)[0]
        try: R.replay(M, D, req, env); print('PASS real %s replays' % R.show(req))
        except Exception as ex: print('FAIL real %s: %s' % (R.show(req), ex)); rc = 1
        for name, f in forgeries(env):
            e = copy.deepcopy(env)
            if f(e) is False: continue
            n += 1
            try: got = R.replay(M, D, req, e)
            except Exception: got = 'refused'
            if got == 'ok': print('FAIL %s: forged %s replayed' % (R.show(req), name)); rc = 1
    print('envelope: %d forgeries checked, %s' % (n, 'PASS' if rc == 0 else 'FAIL'))
    return rc

if __name__ == '__main__': sys.exit(main())
