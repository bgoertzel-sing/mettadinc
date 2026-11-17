# Own M2 checker (no repo code): GradedClosure G01-G04 (Lukasiewicz path closure, brackets, thresholds)
# and Staged H05-H08 (horizon adequacy by explicit word unrolling, exactness of the block partition).
import sys
from fractions import Fraction as Q
bad = 0
def chk(n, got, exp):
    global bad; ok = got == exp; bad += not ok; print(f'{n:45s} mine={got} expected={exp} {"OK" if ok else "MISMATCH"}')
P = ['A','B','C']; K = {}
for p in P: K[(p,p)] = Q(1)
for a,b,v in (('A','B',Q(9,10)),('B','C',Q(9,10)),('A','C',Q(1,10))): K[(a,b)] = K[(b,a)] = v
T = lambda x, y: max(Q(0), x + y - 1)
def closure(K):
    C = dict(K)
    for m in P:
        for i in P:
            for j in P: C[(i,j)] = max(C[(i,j)], T(C[(i,m)], C[(m,j)]))
    return C
Cl = closure(K); br = lambda K: sum(K.values()) / 9
chk('G01 brackets before/after/increase', (br(K), br(Cl), br(Cl)-br(K)), (Q(34,45), Q(41,45), Q(7,45)))
chk('G03 closed A-C entry', Cl[('A','C')], Q(4,5))
metric = lambda K: all(K[(i,k)] >= T(K[(i,j)], K[(j,k)]) for i in P for j in P for k in P)
chk('G03 closed kernel Lukasiewicz-transitive', metric(Cl), True)
chk('G04 Alpha transitive', metric(K), False)
R = {k: v >= Q(9,10) for k, v in Cl.items()}
chk('G02 threshold 9/10 Boolean-transitive', all(R[(i,k)] or not (R[(i,j)] and R[(j,k)]) for i in P for j in P for k in P), False)
last = {0:0,1:0,2:0,3:1}; climb = {0:1,1:2,2:3,3:3}; stage = {0:0,1:0,2:1,3:2}
def trace(s, h):
    out = []
    for _ in range(h+1): out.append(last[s]); s = climb[s]
    return out
adequate = lambda h: all(trace(s,h) == trace(t,h) for s in range(4) for t in range(4) if stage[s] == stage[t])
chk('H05-H07 adequate at horizon 0/1/2', [adequate(h) for h in (0,1,2)], [True, True, False])
exact = all(stage[climb[s]] == stage[climb[t]] for s in range(4) for t in range(4) if stage[s] == stage[t])
chk('H08 InduceExact', exact, False)
print('CHECK_M2', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
