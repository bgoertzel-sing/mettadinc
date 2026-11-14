#!/usr/bin/env python3
"""M7 Z01 replayer (independent of the C code): CheckNow on a keyed snapshot carrier ((Carriers Snapshot) profile).
Re-derives from the fixture declarations alone that the check is content-independent: the state carrier is
(Query S pattern (Key $k)), the Encode map queries the same snapshot/pattern/key, every observation is the Encode
map (or the same query), every action is the identity body, and the digest is "sha256:<64 lowercase hex>".  The
snapshot content is never read.  The Value must be (SymbolicCheck (Holds ForAllContent)) and the certificate must
record the snapshot, digest, revision, the observations and the identity actions exactly."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'm6'))
from replay_m6 import read_all, field, head, need

def decl(mod, h, name):
    for d in mod[2:]:
        if head(d) == h and len(d) > 1 and d[1] == name: return d
    return None
def fld(d, h, start=2):
    for x in (d or [])[start:]:
        if head(x) == h: return x
    return None
def show(t): return t if isinstance(t, str) else '(' + ' '.join(show(x) for x in t) + ')'

def z_row(mod, req, res):
    need(req[0] == 'CheckNow' and len(req) == 2, 'not (CheckNow R)')
    rep = decl(mod, 'Representation', req[1]); need(rep, 'no Representation %s' % req[1])
    mn, en = fld(rep, 'Of')[1], fld(rep, 'Encode')[1]
    mach = decl(mod, 'Machine', mn); cn = fld(mach, 'States')[1]; car = decl(mod, 'Carrier', cn)
    cq = fld(car, 'Query'); need(cq and isinstance(cq[2], list) and fld(cq, 'Key', 3), 'state carrier is not keyed (Query S pattern (Key $k))')
    snap = decl(mod, 'Snapshot', cq[1]); need(snap and fld(snap, 'Space'), 'snapshot %s not declared' % cq[1])
    dg = fld(snap, 'Digest'); dv = dg[1].strip('"') if dg else ''
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', dv), 'digest %r is not sha256:<64 lowercase hex>' % dv)
    em = decl(mod, 'Map', en); eq = fld(em, 'Query')
    need(em and eq and fld(em, 'From')[1] == cn and fld(eq, 'Value', 3), 'Encode is not a keyed snapshot map from the states')
    need(eq[1] == cq[1] and show(eq[2]) == show(cq[2]) and show(fld(eq, 'Key', 3)) == show(fld(cq, 'Key', 3)), 'Encode does not query the carrier snapshot/pattern/key')
    obs, acts = [], []
    for o in mach[2:]:
        if head(o) not in ('Observe', 'Action'): continue
        for k in range(1, len(o) - 1, 2):
            mp = decl(mod, 'Map', o[k + 1]); need(mp, 'map %s not declared' % o[k + 1])
            if head(o) == 'Observe':
                need(o[k + 1] == en or show(fld(mp, 'Query')) == show(eq), 'observation %s is not the Encode query' % o[k])
                obs.append([o[k], o[k + 1]])
            else:
                b = fld(mp, 'Body'); need(b and isinstance(b[1], list) and len(b[1]) == 1 and b[2] == b[1][0], 'action %s is not the identity' % o[k])
                acts.append([o[k], o[k + 1]])
    need(obs, 'no observation')
    need(field(res, 'Status')[1] == 'Checked', 'status not Checked')
    need(show(field(res, 'Value')) == '(Value (SymbolicCheck (Holds ForAllContent)))', 'Value differs')
    ce = field(field(res, 'Evidence'), 'Certificate'); need(ce is not None, 'no certificate')
    need(show(field(ce, 'Kind')) == '(Kind SymbolicSnapshot)', 'certificate kind differs')
    rv = fld(snap, 'Revision')
    want_s = ['Snapshot', cq[1], dg, rv if rv else ['Revision', 'None']]
    need(show(field(ce, 'Snapshot')) == show(want_s), 'certificate snapshot/digest/revision differs')
    need([x[1:] for x in ce[1:] if head(x) == 'CodeIsObservation'] == obs, 'certificate observations differ')
    need([x[1:] for x in ce[1:] if head(x) == 'IdentityAction'] == acts, 'certificate actions differ')
    need(show(field(ce, 'Assumptions')) == '(Assumptions (DigestCheckedBeforeMaterialization) (FunctionalMap %s))' % en, 'certificate assumptions differ')
    return 'CheckNow %s: content-independent (%d obs, %d identity actions, digest %s...)' % (req[1], len(obs), len(acts), dv[:15])

def main(fx, out):
    forms = read_all(open(fx, encoding='utf-8').read()); fm = {f[1]: f for f in forms if head(f) == 'DC.Module'}
    bad = rows = 0
    for line in open(out, encoding='utf-8').read().splitlines():
        if ' => ' not in line: continue
        res = read_all(line.split(' => ', 1)[1])[0]; st = field(res, 'Status')[1]
        sc = field(res, 'Scope'); fr = field(sc, 'Fragment') if sc else None
        if not fr or fr[1] != 'M7-Snapshot' or st not in ('Checked', 'Refuted'): continue
        rows += 1
        try:
            asr = field(res, 'Assurance'); rp = field(asr, 'Replayed') if asr else None
            need(rp and rp[1] == 'True', 'verdict without Replayed True')
            print('ACCEPT    %s' % z_row(fm[line.split(' ', 1)[0]], field(res, 'Claim')[1], res))
        except (AssertionError, ValueError, KeyError, IndexError, TypeError) as e:
            bad += 1; print('REJECT    %s: %s' % (line.split(' => ')[0][:80], e))
    print('replay_m7_snapshot: %d rows, %d not accepted -> %s' % (rows, bad, 'PASS' if rows and not bad else 'FAIL'))
    return 1 if bad or not rows else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1], sys.argv[2]))
