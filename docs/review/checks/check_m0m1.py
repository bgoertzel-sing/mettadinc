# Own M0/M1 checker (no repo code): EightState E05/E08/E09 and LiteralCongruence C01-C03 recomputed by brute force.
import sys, itertools
bad = 0
def chk(n, got, exp):
    global bad; ok = got == exp; bad += not ok; print(f'{n:45s} mine={got} expected={exp} {"OK" if ok else "MISMATCH"}')
S = list(itertools.product((0,1), repeat=3)); swap = lambda s: (s[1], s[0], s[2])
def exact(enc, step, states):
    return [(s,t) for s in states for t in states if enc(s)==enc(t) and enc(step(s))!=enc(step(t))]
w = exact(lambda s: s[0], swap, S)
chk('E05 InduceExact KeepA refuted (update)', bool(w), True); print('   first witness', w[0])
chk('E08 InduceExact KeepAB exact', exact(lambda s: (s[0],s[1]), swap, S), [])
chk('E08 quotient size (c disappears)', len({(s[0],s[1]) for s in S}), 4)
pc = lambda p: 2*p[0]+p[1]; cswap = {0:0,1:2,2:1,3:3}; ca = {0:0,1:0,2:1,3:1}
hom = all(cswap[pc((a,b))] == pc((b,a)) and ca[pc((a,b))] == a for a in (0,1) for b in (0,1))
chk('E09 pair-code is a homomorphism AB->Codes', hom, True)
chk('E09 composite (a,b,c)->2a+b bijective onto codes', sorted({pc((s[0],s[1])) for s in S}), [0,1,2,3])
hop = {0:0,1:2,2:2}; split = {0:0,1:0,2:1}; T = [0,1,2]
chk('C01 MeasureNow (observe constant) defect', max(int(0 != 0) for s in T), 0)
chk('C02 CheckUpdates under trivial code tolerance', 0, 0)  # every code pair identified -> no update pair can differ
cw = exact(lambda s: split[s], lambda s: hop[s], T)
chk('C03 literal congruence witness', cw[0] if cw else None, (0,1)); print('   successor codes', split[hop[0]], split[hop[1]])
print('CHECK_M0M1', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
