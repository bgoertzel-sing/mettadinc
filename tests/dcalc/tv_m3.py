#!/usr/bin/env python3
"""M3 translation-validation suite for the obligation generator
(t-2026-11-11-mettadinc-m3-tv-suite).

build/dcalc/tv_m3 writes the production CNF of each obligation kind (ops_sym.c:
sym_cnf_partition per obligation and All, sym_cnf_minimize, sym_cnf_now) without the
goal unit that sym_prove adds.  This script checks every such CNF F against an
independent semantics of the module (tests/dcalc/replay_sym.py SymM, which shares no
code with src/dcalc), over EVERY assignment x of the primary variables (the word bits):

  1. unit propagation from x and the constant-true unit assigns every variable of F
     with no conflict (so F has exactly one model extending x: no vacuous or
     contradictory encoding, no gate left undefined by a dropped clause);
  2. the goal literal's value in that model equals the reference obligation ref(x).

Together, 1 and 2 give: F + goal is UNSAT iff ref(x) = 0 for all x, so a checked
LRAT proof of the CNF really proves the obligation.  Re-checking proofs alone cannot
show this (a wrong but UNSAT CNF has a valid proof); see the mutation gate."""
import sys, os, glob, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay import find, Fail, need
from replay_sym import SymM

def parse_sx(src):
    toks = []
    for line in src.split('\n'):
        line = line.split(';', 1)[0]
        toks += line.replace('(', ' ( ').replace(')', ' ) ').split()
    out, st = [], [[]]
    for t in toks:
        if t == '(': st.append([])
        elif t == ')': x = st.pop(); st[-1].append(x)
        else: st[-1].append(t)
    return st[0]

def load_module(path):
    for f in parse_sx(open(path).read()):
        if isinstance(f, list) and f and f[0] == 'DC.Module': return SymM(f)
    raise Fail('no DC.Module in %s' % path)

def read_tv(path):
    hdr, kind, tests, cls, cur, p = {}, None, [], [], [], None
    for line in open(path):
        w = line.split()
        if not w: continue
        if w[0] == 'c':
            if w[1] in ('goal', 'prim', 'tru'): hdr[w[1]] = int(w[2])
            elif w[1] == 'kind': kind = w[2:]
            elif w[1] == 'test': tests.append((w[2], int(w[3]), w[4:]))
            continue
        if w[0] == 'p': p = (int(w[2]), int(w[3])); continue
        for t in w:
            v = int(t)
            if v == 0: cls.append(cur); cur = []
            else: cur.append(v)
    need(p is not None and not cur and len(cls) == p[1], '%s: malformed DIMACS' % path)
    return {'nv': p[0], 'cls': cls, 'kind': kind, 'tests': tests, **hdr}

# ---- independent reference semantics, one function per obligation kind ----
def ref_partition(sm, P, M, sel):
    d = sm.decl[P]; car = find(d, 'On')[1]; W = sm.car[car]['w']; mach = sm.mach[M]
    blocks = [b for b in d[2:] if isinstance(b, list) and b[0] == 'Block']
    byname = {b[1]: b for b in blocks}
    inb = lambda b, x: sm.block_has(b, x, W)
    obl = [('Coverage', lambda x: not any(inb(b, x) for b in blocks))]
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            obl.append(('Disjointness', lambda x, bi=blocks[i], bj=blocks[j]: inb(bi, x) and inb(bj, x)))
    for _, mp in mach['obs']:
        for b in blocks:
            obl.append(('Constancy', lambda x, b=b, mp=mp: inb(b, x) and sm.apply(mp, x) != sm.apply(mp, int(b[3]))))
    for lab, mp in mach['act']:
        for sc in d[2:]:
            if isinstance(sc, list) and sc[0] == 'Successor' and len(sc) == 4 and sc[1] == lab:
                obl.append(('Stability', lambda x, bi=byname[sc[2]], bj=byname[sc[3]], mp=mp: inb(bi, x) and not inb(bj, sm.apply(mp, x))))
    rc = sm.car[car]['reach']
    scope = set(sm.reach(rc[0], rc[1])) if rc else None
    chosen = obl if sel < 0 else [obl[sel]]
    name = 'All' if sel < 0 else obl[sel][0]
    return W, len(obl), name, lambda x: int((scope is None or x in scope) and any(f(x) for _, f in chosen))

def ref_minimize(sm, M, tests):
    W = sm.W(M); obsmap = dict(sm.mach[M]['obs']); acts = [l for l, _ in sm.mach[M]['act']]
    tb = lambda t, x, pre: (sm.apply(obsmap[t[0]], sm.run(M, x, pre + t[2])) >> t[1]) & 1
    def f(v):
        x, y = v & ((1 << W) - 1), v >> W
        same = all(tb(t, x, []) == tb(t, y, []) for t in tests)
        viol = sm.obs(M, x) != sm.obs(M, y) or any(tb(t, x, [a]) != tb(t, y, [a]) for t in tests for a in acts)
        return int(same and viol)
    return 2 * W, f

def ref_now(sm, R, M, E):
    W = sm.W(M)
    def f(v):
        x, y = v & ((1 << W) - 1), v >> W
        return int(sm.apply(E, x) == sm.apply(E, y) and sm.obs(M, x) != sm.obs(M, y))
    return 2 * W, f

def propagate(nv, cls, fixed):
    a = [0] * (nv + 1)
    for v, b in fixed: a[v] = b
    changed = True
    while changed:
        changed = False
        for c in cls:
            un, sat = None, False
            for l in c:
                s = a[abs(l)]
                if s == 0:
                    if un is not None: un = 0; break
                    un = l
                elif (s > 0) == (l > 0): sat = True; break
            if sat or un == 0: continue
            if un is None: return None, c            # every literal false: conflict
            a[abs(un)] = 1 if un > 0 else -1; changed = True
    return a, None

def check_tv(sm, path):
    """Return (ok, message, number of x with ref(x) = 1)."""
    t = read_tv(path); k = t['kind']
    if k[0] == 'partition':
        W, nob, name, ref = ref_partition(sm, k[1], k[2], int(k[3])); np = W
        if int(k[3]) >= 0 and name != k[4]: return False, 'obligation %s is %s in the reference' % (k[3], name), 0
    elif k[0] == 'minimize': np, ref = ref_minimize(sm, k[1], t['tests'])
    elif k[0] == 'now':
        d = sm.decl[k[1]]; np, ref = ref_now(sm, k[1], find(d, 'Of')[1], find(d, 'Encode')[1])
    else: return False, 'unknown kind %s' % k, 0
    if t.get('prim') != np: return False, 'primary count %s, reference says %d' % (t.get('prim'), np), 0
    g, tru = t['goal'], t['tru']
    if not (0 < abs(g) <= t['nv']) or not (np < tru <= t['nv']): return False, 'goal/tru variable out of range', 0
    if [tru] not in t['cls']: return False, 'no constant-true unit clause', 0
    nsat = 0
    for v in range(1 << np):
        fixed = [(i + 1, 1 if (v >> i) & 1 else -1) for i in range(np)] + [(tru, 1)]
        a, bad = propagate(t['nv'], t['cls'], fixed)
        if a is None: return False, 'x=%d: clause %s is false under propagation (contradictory/vacuous encoding)' % (v, bad), nsat
        if 0 in a[1:]: return False, 'x=%d: variable %d not determined (gate definition incomplete)' % (v, a[1:].index(0) + 1), nsat
        got = int((a[abs(g)] > 0) == (g > 0)); want = ref(v); nsat += want
        if got != want: return False, 'x=%d: goal is %d, reference obligation is %d' % (v, got, want), nsat
    return True, '%d of %d assignments violate (%s)' % (nsat, 1 << np, 'SAT' if nsat else 'UNSAT'), nsat

def check_dir(module, d, quiet=False):
    sm = load_module(module); res = []
    for p in sorted(glob.glob(os.path.join(d, '*.tv'))):
        try: ok, msg, ns = check_tv(sm, p)
        except Fail as e: ok, msg, ns = False, 'reference: %s' % e, 0
        res.append((os.path.basename(p), ok, msg, ns))
        if not quiet: print('%-36s %s  %s' % (os.path.basename(p), 'PASS' if ok else 'FAIL', msg))
    return res

if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'check':
        r = check_dir(sys.argv[2], sys.argv[3])
        sys.exit(0 if r and all(ok for _, ok, _, _ in r) else 1)
    print('usage: tv_m3.py check MODULE DIR'); sys.exit(2)
