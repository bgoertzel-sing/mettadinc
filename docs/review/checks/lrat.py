# Own LRAT (text) checker, independent of repo replayers/cake_lpr. RUP-only hints; RAT (negative hints) -> refuse.
import sys, hashlib, os
def check(cnf, lrat):
    cls = {}; n = 0
    for line in open(cnf):
        t = line.split()
        if not t or t[0] in ('c','p'): continue
        lits = [int(x) for x in t]; assert lits[-1] == 0
        n += 1; cls[n] = lits[:-1]
    empty = False
    for ln, line in enumerate(open(lrat), 1):
        t = line.split()
        if not t: continue
        cid = int(t[0])
        if t[1] == 'd':
            for x in t[2:-1]: cls.pop(int(x), None)
            continue
        v = [int(x) for x in t[1:]]; z = v.index(0)
        lits, hints = v[:z], v[z+1:]
        assert hints and hints[-1] == 0, f'line {ln}: missing hint terminator'; hints = hints[:-1]
        if any(h < 0 for h in hints): return f'line {ln}: RAT hint (unsupported)'
        asg = {-l for l in lits}; conflict = False
        for h in hints:
            c = cls.get(h)
            if c is None: return f'line {ln}: hint {h} unknown/deleted'
            un = [l for l in c if -l not in asg]
            if any(l in asg for l in un): return f'line {ln}: hint {h} satisfied (not unit)'
            if len(un) == 0: conflict = True; break
            if len(un) != 1: return f'line {ln}: hint {h} not unit ({len(un)} open)'
            asg.add(un[0])
        if not conflict: return f'line {ln}: no conflict after hints'
        if cid in cls or cid <= n: return f'line {ln}: id {cid} reused'
        cls[cid] = lits
        if not lits: empty = True; break
    return 'VERIFIED' if empty else 'no empty clause'
if __name__ == '__main__':
    d = sys.argv[1]; ok = bad = 0
    for f in sorted(os.listdir(d)):
        if not f.endswith('.cnf'): continue
        h = f[:-4]; c = os.path.join(d, f); l = os.path.join(d, h + '.lrat')
        dg = hashlib.sha256(open(c,'rb').read()).hexdigest()
        r = check(c, l) if os.path.exists(l) else 'missing lrat'
        good = r == 'VERIFIED' and dg == h
        print(h[:16], 'digest_ok' if dg == h else 'DIGEST_MISMATCH', r); ok += good; bad += not good
    print(f'LRAT_SUMMARY verified={ok} failed={bad}')
