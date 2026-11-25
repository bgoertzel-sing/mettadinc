#!/usr/bin/env python3
"""Gates for t-2026-11-24-mettadinc-stoch-reach-reader: (Reach M (From s+)) carriers in the stochastic reader
(spec 5.3 l.1810-1812 "Reachability scopes": the forward closure of the starts under the actions of M; a
stochastic action moves x to every y it gives mass > 0).  Stochastic is beyond the first release, so the
answers are checked with --beyond-release and release mode must keep its Unsupported (profile) answer."""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DC = os.path.join(ROOT, 'build', 'dcalc', 'dcalc')
FXD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
RP = os.path.join(ROOT, 'tests', 'dcalc', 'examples_e2e', 'repro')
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
        dm = re.search(r'\(MinimalLinear \(Dimension (\d+)\)', v)
        out[k.strip()] = (st.group(1) if st else None, rs.group(1) if rs else '', dm.group(1) if dm else None, v)
    return out
B = ['--beyond-release']
# repro, worked by hand: S={a,b,c}, obs a,b->o c->p, K: a->b b->b c->c.
#   Seen = Reach M From a = {a,b}; on Seen obs is constant o and go is a->b,b->b: one class -> LS dimension 1.
#   M on S: classes {a,b},{c} (c is the only p state and go fixes it) -> LM dimension 2 (no Reach involved).
r = rows(os.path.join(RP, 'stoch_reach_carrier.metta'), B)
g = r.get('R LS'); report('repro LS: MinimalLinear on Seen = Reach M From a = {a,b} -> Checked, Dimension 1', g is not None and g[0] == 'Checked' and g[2] == '1', g)
g = r.get('R LM'); report('repro LM: MinimalLinear on M (parent S) -> Checked, Dimension 2', g is not None and g[0] == 'Checked' and g[2] == '2', g)
r = rows(os.path.join(RP, 'stoch_reach_carrier.metta'))
report('repro release mode: Stochastic stays outside the first release (Unsupported)', all(v[0] == 'Unsupported' and 'outside the first release' in v[1] for v in r.values()) and len(r) == 2, r)
# the zero-mass discriminator: a listed (Mass c 0) is not a successor (spec: support of the kernel)
r = rows(os.path.join(FXD, 'stoch_reach_gates.metta'), B)
g = r.get('Z LZ'); report('Z: (Mass c 0) is not a successor: Reach From a = {a,b}, not {a,b,c} -> Dimension 1 (2 if c were in)', g is not None and g[0] == 'Checked' and g[2] == '1', g)
r = rows(os.path.join(FXD, 'bad_reach_start.metta'), B)
report('negative: Reach start z outside the parent carrier -> InvalidInput', len(r) == 2 and all(v[0] == 'InvalidInput' and 'Reach start z is not a state of M' in v[1] for v in r.values()), r)
r = rows(os.path.join(FXD, 'mass_leaves.metta'), B)
g = r.get('X LX'); report('negative: an action on the Reach carrier whose mass leaves it -> InvalidInput', g is not None and g[0] == 'InvalidInput' and 'mass leaves the Reach carrier' in g[1], g)
print('run_stoch_reach: ' + ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
