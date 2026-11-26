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
# review 1 F1: the restriction cache must not key on names cut to 30 chars (two kernels sharing a 30-char prefix)
r = rows(os.path.join(FXD, 'e7_long_names.metta'), B)
g, h = r.get('E7 (TracePartition MR)'), r.get('E7Short (TracePartition MR)')
cl = lambda v: (re.search(r'\(Classes (\d+)\)', v[3]) or [None, None])[1] if v else None
report('F1: long kernel names sharing 30 chars -> same answer as short names (Checked, 3 classes)', g is not None and h is not None and g[0] == h[0] == 'Checked' and cl(g) == cl(h) == '3', (g and g[:2], cl(g), h and h[:2], cl(h)))
# review 1 F2: one parent map as both Observe port and Action on the Reach carrier, both declaration orders
r = rows(os.path.join(FXD, 'e3b_obs_action_same_map.metta'), B)
g, h = r.get('E3B (TracePartition MS)'), r.get('E3B (TracePartition MS2)')
report('F2: map used as Observe and Action -> Checked, 1 class, in either order', g is not None and h is not None and g[0] == h[0] == 'Checked' and cl(g) == cl(h) == '1', (g and g[:2], cl(g), h and h[:2], cl(h)))
# review 2: the V03 0/1 kernel of a Map used as an Action is keyed by (map, carrier), not by the bare map name.
#   f: a->b b->a c->c, observed by f. Seen = Reach M From a = {a,b}: f separates a,b -> 2 classes; on S: 3 classes;
#   Seen2 = Reach M From c = {c}: 1 class. Declaration order must not change any answer.
r1 = rows(os.path.join(FXD, 'rv2_f1_reach_first.metta'), B); r2 = rows(os.path.join(FXD, 'rv2_f2_parent_first.metta'), B)
a1, b1, a2, b2 = r1.get('RV2F1 (TracePartition MS)'), r1.get('RV2F1 (TracePartition MC)'), r2.get('RV2F2 (TracePartition MS)'), r2.get('RV2F2 (TracePartition MC)')
ok = all(v is not None and v[0] == 'Checked' for v in (a1, b1, a2, b2)) and cl(a1) == cl(a2) == '2' and cl(b1) == cl(b2) == '3'
report('R2a: map as Action on a Reach carrier and on its parent -> Checked 2 / 3 classes in either declaration order', ok, [v and (v[0], cl(v)) for v in (a1, b1, a2, b2)])
r = rows(os.path.join(FXD, 'rv2_f3_two_reach.metta'), B)
g, h = r.get('RV2F3 (TracePartition MS1)'), r.get('RV2F3 (TracePartition MS2)')
report('R2b: one map as Action on two Reach carriers of one parent -> Checked, 2 and 1 classes', g is not None and h is not None and g[0] == h[0] == 'Checked' and cl(g) == '2' and cl(h) == '1', (g and (g[0], cl(g)), h and (h[0], cl(h))))
print('run_stoch_reach: ' + ('PASS' if fails == 0 else 'FAIL (%d)' % fails))
sys.exit(1 if fails else 0)
