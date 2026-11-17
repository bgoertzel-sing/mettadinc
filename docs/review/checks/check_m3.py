# Own M3 checker (no repo code). FortyBits on n-bit analogues (n=4..14, brute force) plus exact Reach(0) at n=40.
# Recomputes: ZeroQuotient / ParityQuotient class counts (bisimulation by refinement), Reach(0) size, and the
# coverage witness for the zero-tail-only partition (F05 word 4).
import sys
bad = 0
def chk(n, got, exp):
    global bad; ok = got == exp; bad += not ok; print(f'{n:45s} mine={got} expected={exp} {"OK" if ok else "MISMATCH"}')
def ops(n, kind):
    mask = (1 << n) - 1
    bit = lambda x, i: (x >> i) & 1
    def swap(x): return (x & ~3) | (bit(x,0) << 1) | bit(x,1)
    def rot(x):
        t = x >> 2; m = n - 2; t = ((t << 1) | (t >> (m-1))) & ((1 << m) - 1); return (x & 3) | (t << 2)
    def tailf(x): t = x >> 2; return bin(t).count('1') & 1 if kind == 'parity' else int(t == 0)
    def inj(x): return x ^ (tailf(x) << 1)
    return [swap, rot, inj]
def classes(n, kind):
    A = ops(n, kind); N = 1 << n; blk = [x & 1 for x in range(N)]
    while True:
        sig = [(blk[x],) + tuple(blk[f(x)] for f in A) for x in range(N)]
        ids = {s: i for i, s in enumerate(sorted(set(sig)))}; nb = [ids[s] for s in sig]
        if len(ids) == len(set(blk)): return len(ids)
        blk = nb
for n in (4, 6, 8, 10, 12, 14):
    chk(f'n={n} ZeroMachine bisim classes', classes(n, 'zero'), 8)
    chk(f'n={n} ParityMachine bisim classes', classes(n, 'parity'), 8)
A = ops(40, 'zero'); R = {0}; fr = [0]
while fr:
    x = fr.pop()
    for f in A:
        y = f(x)
        if y not in R: R.add(y); fr.append(y)
chk('F06 |Reach(0)| at n=40', sorted(R), [0, 1, 2, 3])
inblock = lambda x: (x >> 2) == 0
chk('F05 smallest word outside every zero-tail block', next(x for x in range(1 << 10) if not inblock(x)), 4)
print('CHECK_M3', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
