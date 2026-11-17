# Own M7 checker (no repo code): Availability W01-W02 and NeuralAudit N01-N06 recomputed by brute force.
import sys, itertools
from fractions import Fraction as Q
bad = 0
def chk(n, got, exp):
    global bad; ok = got == exp; bad += not ok; print(f'{n:45s} mine={got} expected={exp} {"OK" if ok else "MISMATCH"}')
C = ['Absent','Neither','Support','Oppose','Both']
rep = {'Absent':'Missing','Neither':(0,0),'Support':(1,0),'Oppose':(0,1),'Both':(1,1)}
dz = {'Absent':(0,0),'Neither':(0,0),'Support':(1,0),'Oppose':(0,1),'Both':(1,1)}
bias = {'Absent':0,'Neither':0,'Support':1,'Oppose':-1,'Both':0}
def merges(enc): return sorted(sorted([a,b]) for a,b in itertools.combinations(C,2) if enc[a]==enc[b] and rep[a]!=rep[b])
chk('W01 DefaultZero merged pairs', merges(dz), [['Absent','Neither']])
chk('W02 Bias merged pairs', merges(bias), [['Absent','Both'],['Absent','Neither'],['Both','Neither']])
I = [(a,b) for a in (0,1) for b in (0,1)]; xor = lambda x: x[0]^x[1]; fb = lambda x: x[0]
def check_now(enc): return [(x,y) for x,y in itertools.combinations(I,2) if enc(x)==enc(y) and xor(x)!=xor(y)]
chk('N01 SymbolicOld CheckNow refuting pairs', check_now(xor), [])
chk('N02 SymbolicNew first refuting pair', check_now(fb)[0], ((0,0),(0,1)))
P = Q(1,16); pairs = [(x,y) for x in I for y in I]
m_old = sum(P for x,y in pairs if xor(x)!=xor(y)); m_new = sum(P for x,y in pairs if fb(x)!=fb(y))
cr = sum(P for x,y in pairs if fb(x)!=fb(y) and xor(x)==xor(y)); er = sum(P for x,y in pairs if xor(x)!=xor(y) and fb(x)==fb(y))
chk('N03 masses old/new', (m_old, m_new), (Q(1,2), Q(1,2))); chk('N03 creation/erasure/turnover', (cr, er, cr+er), (Q(1,4), Q(1,4), Q(1,2)))
acc_old = Q(sum(1 for x in I if 0 == xor(x)), 4); acc_new = Q(sum(1 for x in I if xor(x) == xor(x)), 4)  # use-report reads forced 0; bypass recomputes xor
chk('N04 accuracy after SetReport 0 old/new', (acc_old, acc_new), (Q(1,2), Q(1)))
classes = lambda key: sorted({tuple(sorted(x for x in I if key(x)==key(y))) for y in I})
chk('N05 Refine(Preserve Encoding) #classes', len(classes(lambda x: x)), 4)
chk('N06 MinimizeForQueries Task classes', classes(xor), [((0,0),(1,1)), ((0,1),(1,0))])
print('CHECK_M7', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
