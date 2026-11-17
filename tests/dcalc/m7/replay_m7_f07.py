#!/usr/bin/env python3
"""M7 F07 independent replay (t-2026-11-14-mettadinc-m7, review 1 finding 5).
Does not use the C code.  (1) Brute force: for k-bit analogs of forty_bits (k=4..12) build ZeroMachine and
ParityMachine on all 2^k states, compute the coarsest stable refinement (Moore partition refinement from the
observation read0 under actions swap01 / rotate(2..k-1) / inject-*), and the exact mean clock rate
r_i = |{x : class(x) != class(x xor e_i)}| / 2^k under the uniform law.  Check the brute-force table equals the
closed form  Zero: r0=r1=1, r_i=1/2^(k-3) (i>=2);  Parity: all 1.  (2) Check the dcalc 40-bit output rows
ZeroRates / ParityRates are Checked and equal the closed form at k=40, and their Binding Digest is the sha256 of
the FortyBitsScreens module text (same rule as replay_m7.py).
usage: replay_m7_f07.py forty_bits.metta forty_bits.out"""
import re, sys, os
from fractions import Fraction as Fr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def expand(fm, mod):
    """Mirror of the documented M7 Import rule (no dcalc code): the digest is over the module with each
    (Import M (Only ..)) followed by M's declarations other than Profile/Use/Import/Derive and other than
    names the importer declares itself."""
    if not any(head(d) == 'Use' and ('Discovery' in d[1:] or 'Hyperseed' in d[1:]) for d in mod[2:]): return mod
    own = {(d[0], d[1]) for d in mod[2:] if isinstance(d, list) and len(d) > 1 and isinstance(d[1], str)}
    out, any_ = [], False
    for i, d in enumerate(mod):
        if i >= 2 and head(d) in ('Schema', 'Method'): any_ = True; continue
        out.append(d)
        if i < 2 or head(d) != 'Import' or len(d) < 3 or not isinstance(d[1], str): continue
        only = field(d, 'Only'); src = fm.get(d[1])
        if not only or src is None or src is mod: continue
        if not all(any(isinstance(e, list) and len(e) > 1 and e[1] == n for e in src[2:]) for n in only[1:]): continue
        for e in src[2:]:
            if head(e) in ('Profile', 'Use', 'Import', 'Derive'): continue
            if isinstance(e, list) and len(e) > 1 and isinstance(e[1], str) and (e[0], e[1]) in own: continue
            out.append(e); any_ = True
    return out if any_ else mod

def machine(k, kind):
    n = 1 << k; tm = (n - 1) & ~3
    def swap(x): b0, b1 = x & 1, (x >> 1) & 1; return (x & ~3) | (b0 << 1) | b1
    def rot(x):
        t = (x >> 2) & ((1 << (k - 2)) - 1); t = ((t << 1) | (t >> (k - 3))) & ((1 << (k - 2)) - 1)
        return (x & 3) | (t << 2)
    def inj(x):
        t = x & tm
        f = (bin(t).count('1') & 1) if kind == 'parity' else int(t == 0)
        return x ^ (f << 1)
    return n, [swap, rot, inj]

def classes(k, kind):
    n, acts = machine(k, kind)
    succ = [[a(x) for a in acts] for x in range(n)]
    blk = [x & 1 for x in range(n)]
    while True:
        sig = {}; nb = [sig.setdefault((blk[x],) + tuple(blk[y] for y in succ[x]), len(sig)) for x in range(n)]
        if len(sig) == len(set(blk)): return blk
        blk = nb

def rates(k, kind):
    blk = classes(k, kind); n = 1 << k
    return [Fr(sum(blk[x] != blk[x ^ (1 << i)] for x in range(n)), n) for i in range(k)]

def closed(k, kind):
    return [Fr(1)] * k if kind == 'parity' else [Fr(1), Fr(1)] + [Fr(1, 2 ** (k - 3))] * (k - 2)

ok = True
for k in range(4, 13):
    for kind in ('zero', 'parity'):
        if rates(k, kind) != closed(k, kind):
            ok = False; print('REJECT brute force k=%d %s: %s != closed form' % (k, kind, rates(k, kind)[:4]))
print('brute force k=4..12 equals closed form:', ok)

if len(sys.argv) == 3:
    import hashlib
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'm6'))
    from replay_m6 import read_all, head
    def show(t): return t if isinstance(t, str) else '(' + ' '.join(show(x) for x in t) + ')'   # same rule as replay_m7.py
    src, out = open(sys.argv[1], encoding='utf-8').read(), open(sys.argv[2], encoding='utf-8').read()
    forms = read_all(src)
    def named(raw, h, n): return any(isinstance(d, list) and len(d) >= 2 and d[0] == h and d[1] == n for d in raw[2:])
    def expand(raw):
        # Independent mirror of the M7 import inlining (api.c m7_expand): the Binding Digest of an importing module
        # is the sha256 of its form with the imported declarations (Only list) appended, importer's own decls winning.
        out = []
        for i, d in enumerate(raw):
            if i >= 2 and isinstance(d, list) and d and d[0] in ('Schema', 'Method'): continue
            out.append(d)
            if i < 2 or not (isinstance(d, list) and d and d[0] == 'Import' and len(d) >= 3 and isinstance(d[1], str)): continue
            only = next((x for x in d[2:] if isinstance(x, list) and x and x[0] == 'Only'), None)
            sm = next((f for f in forms if head(f) == 'DC.Module' and f[1] == d[1]), None)
            if not only or not sm or sm is raw: continue
            if not all(any(isinstance(e, list) and len(e) >= 2 and e[1] == o for e in sm[2:]) for o in only[1:]): continue
            for e in sm[2:]:
                if isinstance(e, list) and e and e[0] in ('Profile', 'Use', 'Import', 'Derive'): continue
                if isinstance(e, list) and len(e) >= 2 and isinstance(e[1], str) and named(raw, e[0] if isinstance(e[0], str) else '', e[1]): continue
                out.append(e)
        return out
    mod = next((f for f in forms if head(f) == 'DC.Module' and f[1] == 'FortyBitsScreens'), None)
    want = hashlib.sha256(show(expand(mod)).encode()).hexdigest() if mod else None
    for name, kind in (('ZeroRates', 'zero'), ('ParityRates', 'parity')):
        line = next((l for l in out.splitlines() if l.startswith('FortyBitsScreens %s =>' % name)), '')
        got = [Fr(int(p), int(q)) for i, p, q in re.findall(r'\(Rate \(Coordinate (\d+)\) \(Rat (\d+) (\d+)\)\)', line)]
        dg = re.search(r'\(Digest "([0-9a-f]{64})"\)', line)
        good = '(Status Checked)' in line and got == closed(40, kind) and dg is not None and dg.group(1) == want
        ok &= good
        print('%s %s: 40 rates vs closed form %s, digest %s' % ('ACCEPT' if good else 'REJECT', name,
              got == closed(40, kind), dg and dg.group(1) == want))
print('replay_m7_f07 -> %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
