#!/usr/bin/env python3
"""Gates for t-2026-11-20-mettadinc-m0-subset-reach: Subset and Reach carriers in the Crisp M0 lowering
(spec 5.3, l.1774 Subset and l.1810 Reachability scopes).  Every gate runs in release mode and with --beyond-release."""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DC = os.path.join(ROOT, 'build', 'dcalc', 'dcalc')
FXD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
REPRO = os.path.join(ROOT, 'tests', 'dcalc', 'examples_e2e', 'repro', 'carrier_subset_reach.metta')
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
for mode in ([], ['--beyond-release']):
    tag = ' [%s]' % (mode[0] if mode else 'release')
    r = rows(REPRO, mode)
    for m in ('S', 'T', 'U'):
        g = r.get('%s (CheckNow R)' % m)
        report('repro %s: CheckNow R -> Checked%s' % (m, tag), g is not None and g[0] == 'Checked', g)
    r = rows(os.path.join(FXD, 'subset_reach_gates.metta'), mode)
    g = r.get('S2 (CheckNow R)'); report('S2: Subset {p,q} of {p,q,r}, enc injective on it -> Checked' + tag, g is not None and g[0] == 'Checked', g)
    g = r.get('S2C (CheckNow R)'); report('S2C control: same machine on {p,q,r} -> Refuted, witness (Pair p r)' + tag,
        g is not None and g[0] == 'Refuted' and '(Pair p r)' in g[2], g)
    g = r.get('T2 (CheckNow R)'); report('T2: Reach M0 From p = {p,q} -> Checked' + tag, g is not None and g[0] == 'Checked', g)
    g = r.get('SX (CheckNow R)'); report('SX: predicate without a case for r -> InvalidInput' + tag,
        g is not None and g[0] == 'InvalidInput' and 'Subset predicate keep has no case for r' in g[1], g)
    g = r.get('SY (CheckNow R)'); report('SY: action leaves the Subset -> InvalidInput' + tag,
        g is not None and g[0] == 'InvalidInput' and 'leaves carrier B' in g[1], g)
    r = rows(os.path.join(FXD, 'bad_reach_start.metta'), mode)
    g = r.get('TB (CheckNow R)'); report('TB: Reach start not a state -> InvalidInput' + tag,
        g is not None and g[0] == 'InvalidInput' and 'Reach start z is not a state of M0' in g[1], g)
    r = rows(os.path.join(FXD, 'subset_bound.metta'), mode)
    sb, pb = r.get('SB (CheckNow R)'), r.get('PB (CheckNow R)')
    report('SB: Subset of a 4225-element Product -> Unsupported, as the plain Product control PB' + tag,
        sb is not None and pb is not None and sb[0] == 'Unsupported' and pb[0] == 'Unsupported', (sb, pb))
print('m0_subset_reach: %s (%d failing)' % ('PASS' if not fails else 'FAIL', fails))
sys.exit(1 if fails else 0)
