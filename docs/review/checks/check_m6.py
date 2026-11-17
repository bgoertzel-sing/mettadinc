# Own M6 checker (no repo code). ParityTriangle: kernel composition around the cycle -> holonomy, coherence.
# AffineContracts: exact rational evaluation of ideal vs actual, composite grade (L1*L2, e2 + L2*e1), direct check.
import sys
from fractions import Fraction as Q
bad = 0
def chk(n, got, exp):
    global bad; ok = got == exp; bad += not ok; print(f'{n:45s} mine={got} expected={exp} {"OK" if ok else "MISMATCH"}')
Equal = {(0,0):1,(0,1):0,(1,0):0,(1,1):1}; Opp = {(0,0):0,(0,1):1,(1,0):1,(1,1):0}
def comp(A, B): return {(i,k): sum(A[(i,j)]*B[(j,k)] for j in (0,1)) for i in (0,1) for k in (0,1)}
H = comp(comp(Equal, Equal), Opp)
chk('Triangle holonomy M1->M2->M3->M1', 'swap' if H == Opp else ('id' if H == Equal else H), 'swap')
chk('Triangle coherent (holonomy = id)', H == Equal, False)
# consensus: best global assignment per M1 value; fraction of the 3 correspondences violated, averaged
best = min(sum([a != b, b != c, c == a]) for a in (0,1) for b in (0,1) for c in (0,1))
chk('Triangle min violated correspondences', best, 1)
X = [Q(0), Q(1)]; Y = [Q(0), Q(2), Q(1,10), Q(21,10)]
f = lambda x: 2*x; fh = lambda x: 2*x + Q(1,10); g = lambda y: 3*y; gh = lambda y: 3*y + Q(1,5)
e1 = max(abs(fh(x)-f(x)) for x in X); e2 = max(abs(gh(y)-g(y)) for y in Y)
chk('First additive error', e1, Q(1,10)); chk('Second additive error', e2, Q(1,5))
L1, L2 = 2, 3; comp_grade = (L1*L2, e2 + L2*e1)
chk('Composite grade (L, eps)', comp_grade, (6, Q(1,2)))
ed = max(abs(gh(fh(x)) - g(f(x))) for x in X); worst = [x for x in X if abs(gh(fh(x)) - g(f(x))) > Q(3,10)]
chk('Direct error max', ed, Q(1,2))
chk('Direct (6,1/2) Checked', ed <= Q(1,2), True)
chk('Direct (6,3/10) Refuted at input 0', (ed <= Q(3,10), worst[0]), (False, Q(0)))
print('CHECK_M6', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
