#!/usr/bin/env python3
"""M7 M01 cross-file independent replay (t-2026-11-14-mettadinc-m7, review 1 finding 5).
Does not use the C code.  hyperseed_methods.metta imports HyperseedMemory from receipt_packets.metta.
Recomputes RepairMemory PosteriorOnly = Refine PosteriorOnly (Preserve Encoding) (Until Stable): start from the
classes of the posterior code, split by successor classes under every action until stable; checks the dcalc row
is Checked, ExactAbstraction with Defect 0, the same partition and state count, and its Binding Digest equals the
sha256 of the import-inlined HyperseedMethods form.
usage: replay_m7_m01.py hyperseed_methods.metta hyperseed_methods.out receipt_packets.metta"""
import re, sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'm6'))
from replay_m6 import read_all, head, field

def show(t): return t if isinstance(t, str) else '(' + ' '.join(show(x) for x in t) + ')'
def need(c, msg):
    if not c: print('REJECT ' + msg); print('replay_m7_m01 -> FAIL'); sys.exit(1)

src, out, lib = (open(p, encoding='utf-8').read() for p in sys.argv[1:4])
forms = read_all(src) + [f for f in read_all(lib) if head(f) == 'DC.Module']
mods = {f[1]: f for f in forms if head(f) == 'DC.Module'}
need('HyperseedMemory' in mods and 'HyperseedMethods' in mods, 'modules missing')
mem = mods['HyperseedMemory']
def decl(h, n): return next((d for d in mem[2:] if isinstance(d, list) and len(d) >= 2 and d[0] == h and d[1] == n), None)
mach = decl('Machine', 'Memory'); states = decl('Carrier', 'Packet'); states = field(states, 'Enum')[1:]
def cases(name): return {k: v for k, v in field(decl('Map', name), 'Cases')[1:]}
obs = field(mach, 'Observe'); post = cases(obs[2])
acts = [cases(a[2]) for a in mach[2:] if isinstance(a, list) and a and a[0] == 'Action']
need(field(decl('Representation', 'PosteriorOnly'), 'Encode')[1] == obs[2], 'PosteriorOnly does not encode the observation')
blk = {s: show(post[s]) for s in states}
while True:
    sig = {s: (blk[s],) + tuple(blk[a[s]] for a in acts) for s in states}
    if len(set(sig.values())) == len(set(blk.values())): break
    blk = {s: show(sig[s]) for s in states}
want = sorted(sorted(s for s in states if blk[s] == b) for b in set(blk.values()))

def subst(x, env):
    if isinstance(x, str):
        for v, a in reversed(env):
            if x == v: return a
        return x
    return [subst(y, env) for y in x]
def unfold(o, dn, b, env, depth):   # mirror of api.c m7_body: (LetResult $v E B) -> (Derive dn__v E), B with $v := dn__v
    if depth <= 8 and isinstance(b, list) and len(b) == 4 and b[0] == 'LetResult' and isinstance(b[1], str) and b[1].startswith('$'):
        nm = '%s__%s' % (dn, b[1][1:]); o.append(['Derive', nm, subst(b[2], env)])
        return unfold(o, dn, b[3], env + [(b[1], nm)], depth + 1)
    o.append(['Derive', dn, subst(b, env)])
def named(raw, h, n): return any(isinstance(d, list) and len(d) >= 2 and d[0] == h and d[1] == n for d in raw[2:])
def expand(raw):   # independent mirror of api.c m7_expand import inlining (same as replay_m7_f07.py)
    o = []
    for i, d in enumerate(raw):
        if i >= 2 and isinstance(d, list) and d and d[0] in ('Schema', 'Method'): continue
        if i >= 2 and isinstance(d, list) and len(d) == 3 and d[0] == 'Derive' and isinstance(d[1], str) and isinstance(d[2], list) and d[2] and isinstance(d[2][0], str):
            mt = next((m for m in raw[2:] if isinstance(m, list) and len(m) >= 2 and m[0] == 'Method' and m[1] == d[2][0]), None)
            pa = next((x for x in mt[2:] if isinstance(x, list) and x and x[0] == 'Parameters'), None) if mt else None
            bo = next((x for x in mt[2:] if isinstance(x, list) and x and x[0] == 'Body'), None) if mt else None
            if mt and pa and bo and len(bo) == 2 and len(pa) == len(d[2]) and all(isinstance(p, list) and p and isinstance(p[0], str) and p[0].startswith('$') for p in pa[1:]):
                env = [(p[0], a) for p, a in zip(pa[1:], d[2][1:])]
                unfold(o, d[1], bo[1], env, 0); continue
        o.append(d)
        if i < 2 or not (isinstance(d, list) and d and d[0] == 'Import' and len(d) >= 3 and isinstance(d[1], str)): continue
        only = next((x for x in d[2:] if isinstance(x, list) and x and x[0] == 'Only'), None)
        sm = mods.get(d[1])
        if not only or not sm or sm is raw: continue
        if not all(any(isinstance(e, list) and len(e) >= 2 and e[1] == q for e in sm[2:]) for q in only[1:]): continue
        for e in sm[2:]:
            if isinstance(e, list) and e and e[0] in ('Profile', 'Use', 'Import', 'Derive'): continue
            if isinstance(e, list) and len(e) >= 2 and isinstance(e[1], str) and named(raw, e[0] if isinstance(e[0], str) else '', e[1]): continue
            o.append(e)
    return o
dg_want = hashlib.sha256(show(expand(mods['HyperseedMethods'])).encode()).hexdigest()

line = next((l for l in out.splitlines() if l.startswith('HyperseedMethods Repaired =>')), '')
need(line, 'no HyperseedMethods Repaired row')
res = read_all(line.split('=>', 1)[1])[0]
need(field(res, 'Status') == ['Status', 'Checked'], 'not Checked: ' + show(field(res, 'Status')))
v = field(field(res, 'Value'), 'ExactAbstraction')
need(v is not None and show(field(v, 'Defect')) == '(Defect (Interval 0 0))', 'not an exact abstraction with defect 0')
need(show(field(v, 'States')) == '(States %d)' % len(states), 'state count')
part = field(field(field(res, 'Evidence'), 'Certificate'), 'Partition')
got = sorted(sorted(b[1:]) for b in part[1:]) if part else None
need(got == want, 'partition %s != recomputed %s' % (got, want))
dg = field(field(res, 'Binding'), 'Digest')
need(dg is not None and dg[1].strip('"') == dg_want, 'stale certificate: Binding Digest %s != %s' % (dg and dg[1], dg_want))
print('ACCEPT M01 HyperseedMethods Repaired: %d blocks %s, digest ok' % (len(want), want))
print('replay_m7_m01 -> PASS')
