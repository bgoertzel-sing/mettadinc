# Own M4 checker (no repo code): SevenState S01-S06, LinearComposition L01-L03, AdaptiveProbe O01/O04, UnattainedSupremum U01-U04.
import sys, itertools
from fractions import Fraction as Q
bad = 0
def chk(n, got, exp):
    global bad; ok = got == exp; bad += not ok; print(f'{n:45s} mine={got} expected={exp} {"OK" if ok else "MISMATCH"}')
h = Q(1,2)
S = ['x','y','u','v','w','p','q']; rep = dict(x=0,y=0,u=0,v=0,w=0,p=1,q=2)
K = dict(x={'u':h,'v':h}, y={'w':1}, u={'p':1}, v={'q':1}, w={'p':h,'q':h}, p={'p':1}, q={'q':1})
def law(s, n):  # distribution over report sequences of length n
    d = {((rep[s],), s): Q(1)}
    for _ in range(n-1):
        nd = {}
        for (seq, t), m in d.items():
            for t2, m2 in K[t].items(): nd[(seq+(rep[t2],), t2)] = nd.get((seq+(rep[t2],), t2), 0) + m*m2
        d = nd
    o = {}
    for (seq, _), m in d.items(): o[seq] = o.get(seq, 0) + m
    return o
chk('S02 trace classes', len({tuple(sorted(law(s,4).items())) for s in S}), 6)
# bisimulation by partition refinement on (report, lifted successor distribution)
part = {s: rep[s] for s in S}
for _ in range(10):
    sig = {s: (part[s], tuple(sorted({part[t]: 0 for t in K[s]}.items()))) for s in S}
    sig = {s: (part[s], tuple(sorted((c, sum(m for t,m in K[s].items() if part[t]==c)) for c in set(part[t] for t in K[s])))) for s in S}
    ids = {v:i for i,v in enumerate(sorted(set(sig.values()), key=str))}; part = {s: ids[sig[s]] for s in S}
chk('S01 bisimulation classes', len(set(part.values())), 7)
def dist(g):  # Kantorovich fixpoint; supports here force the couplings except x vs y
    d = {(a,b): Q(int(rep[a]!=rep[b])) for a in S for b in S}
    for _ in range(60):
        nd = dict(d)
        for a in S:
            for b in S:
                if rep[a]!=rep[b] or a==b: continue
                # all relevant pairs have a point mass on one side -> unique coupling
                if len(K[a])==1 or len(K[b])==1:
                    nd[(a,b)] = g*sum(ma*mb*d[(ta,tb)] for ta,ma in K[a].items() for tb,mb in K[b].items())
                else:
                    nd[(a,b)] = g*min(sum(m*d[(ta,tb)] for (ta,tb),m in zip(itertools.product(K[a],K[b]), c)) for c in ([h,0,0,h],[0,h,h,0]))
        d = nd
    return d
chk('S03 behavioral defect d(x,y) undiscounted', dist(Q(1))[('x','y')], h)
chk('S04 d(x,y) gamma 9/10', dist(Q(9,10))[('x','y')], Q(81,200))
chk('S05 trace laws x,y agree', all(law('x',n)==law('y',n) for n in range(1,6)), True)
seqs = sorted({k for s in S for n in range(1,5) for k in law(s,n)})
M = [[law(s,len(k)).get(k,0) for k in seqs] for s in S]
def rank(M):
    M = [r[:] for r in M]; r = 0
    for c in range(len(M[0])):
        piv = next((i for i in range(r,len(M)) if M[i][c]!=0), None)
        if piv is None: continue
        M[r], M[piv] = M[piv], M[r]
        for i in range(len(M)):
            if i!=r and M[i][c]!=0: f = M[i][c]/M[r][c]; M[i] = [a-f*b for a,b in zip(M[i],M[r])]
        r += 1
    return r
chk('S06 minimal signed linear dimension (Hankel rank)', rank(M), 5)
# LinearComposition: defect ||S A - A T||_inf, amplification ||A||_inf
mm = lambda A,B: [[sum(A[i][k]*B[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
nrm = lambda A: max(sum(abs(x) for x in r) for r in A); sub = lambda A,B: [[a-b for a,b in zip(r,s)] for r,s in zip(A,B)]
I = [[Q(1),Q(0)],[Q(0),Q(1)]]; Leak = [[Q(9,10),Q(1,10)],[Q(1,10),Q(9,10)]]; L = [[Q(2),Q(-1)],[Q(-1),Q(2)]]
gL = (nrm(L), nrm(sub(mm(I,L), mm(L,I)))); gK = (nrm(I), nrm(sub(mm(I,I), mm(I,Leak))))
chk('L01 grade L', gL, (3, 0)); chk('L02 grade K', gK, (1, Q(1,5)))
LK = mm(L, I); chk('L03 composite rho (bound, attained)', (gL[1]*gK[0] + gL[0]*gK[1], nrm(sub(mm(I,LK), mm(LK,Leak)))), (Q(3,5), Q(3,5)))
# AdaptiveProbe
R = dict(x=0,x2=0,r1=1,r2=2,s1=1,s2=2,A=3,B=4,C=5)
A_ = dict(a=dict(x={'r1':h,'r2':h},x2={'s1':h,'s2':h}), b=dict(r1='A',s1='B',r2='C',s2='C'), c=dict(r2='A',s2='B',r1='C',s1='C'))
def step(act, s): t = A_[act].get(s, s); return t if isinstance(t, dict) else {t: 1}
def run(s, pol):  # pol: function(report history)->action; 2 steps; returns law of last report
    d = {(s,(R[s],)): Q(1)}
    for _ in range(2):
        nd = {}
        for (t,hist),m in d.items():
            for t2,m2 in step(pol(hist), t).items(): k=(t2,hist+(R[t2],)); nd[k]=nd.get(k,0)+m*m2
        d = nd
    o = {}
    for (t,hist),m in d.items(): o[hist] = o.get(hist,0)+m
    return o
tv = lambda P,Qd: sum(abs(P.get(k,0)-Qd.get(k,0)) for k in set(P)|set(Qd))/2
fixed = max(tv(run('x', lambda hh, w=w: w[len(hh)-1]), run('x2', lambda hh, w=w: w[len(hh)-1])) for w in itertools.product('abc', repeat=2))
chk('O01 trace defect fixed words h=2', fixed, h)
pols = [lambda hh, f=f: ('a' if len(hh)==1 else f[hh[-1]]) for f in [dict(zip(range(6), c)) for c in itertools.product('abc', repeat=6)][:729]]
adap = max(tv(run('x',p), run('x2',p)) for p in pols)
chk('O04 trace defect observation-based h=2', adap, 1); chk('O03 1 > 3/4 so Refuted', adap > Q(3,4), True)
# UnattainedSupremum: d = g*(d/2 + 1/2) iterated from 0
def us(g, n):
    d = Q(0)
    for _ in range(n): d = g*(d/2 + h)
    return d
chk('U01 20-layer lower bound', us(Q(1),20), Q(1048575,1048576))
chk('U02 horizon 3', us(Q(1),3), Q(7,8))
chk('U03 first depth > 99/100', next((n, us(Q(1),n)) for n in range(1,50) if us(Q(1),n) > Q(99,100)), (7, Q(127,128)))
chk('U04 discount 1/2 fixpoint (d = d/4 + 1/4)', Q(1,4)/(1-Q(1,4)), Q(1,3))
print('CHECK_M4', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
