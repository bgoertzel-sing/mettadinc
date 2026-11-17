# Independent recomputation of EightState (spec 6.1) claims; replays the kernel certificate itself.
import itertools, sys
from sx import envelopes, find, findall
OUT = sys.argv[1] if len(sys.argv)>1 else '/hive/protomega/work/cetta-src/mettadinc/build/dcalc/out/eight_state.out'
S = list(itertools.product((0,1),repeat=3))
obs = lambda s: s[0]; swap = lambda s: (s[1],s[0],s[2]); keepA = lambda s: s[0]
# behaviour class: observation sequence under swap^k, k>=0 (period 2) -> (a,b)
beh = {s: tuple(obs(t) for t in [s, swap(s)]) for s in S}
# my kernel: unordered pairs with different behaviour
mine = {frozenset((p,q)) for p,q in itertools.combinations(S,2) if beh[p]!=beh[q]}
# update defect: same code, successors different code
upd = max(int(keepA(p)==keepA(q) and keepA(swap(p))!=keepA(swap(q))) for p in S for q in S)
behd = max(int(keepA(p)==keepA(q) and beh[p]!=beh[q]) for p in S for q in S)
cur = 0  # KeepA = observation itself -> current defect 0
fails = 0
env = dict(envelopes(OUT,'EightState'))
e = env['(Defects KeepA)']
st = find(e,'Status')[1]
iv = {k: find(find(e,'Value'),k) for k in ('Current','Update','Behavioral')}
got = {k:(v[1][1],v[1][2]) for k,v in iv.items()}
exp = {'Current':(str(cur),str(cur)),'Update':(str(upd),str(upd)),'Behavioral':(str(behd),str(behd))}
print('status',st,'defects got',got,'mine',exp); fails += (got!=exp) + (st!='Checked')
def tup(x): return tuple(int(v) for v in x[1:])
ker = findall(find(e,'Kernel'),'Entry')
theirs = {frozenset((tup(x[1]),tup(x[2]))) for x in ker if x[3]=='1'}
print('kernel entries', len(theirs), 'mine', len(mine), 'equal', theirs==mine); fails += theirs!=mine
w = find(e,'WordWitness'); p,q = tup(w[1][1]), tup(w[1][2])
ok = keepA(p)==keepA(q) and obs(swap(p))!=obs(swap(q)); print('word witness replays', ok); fails += not ok
uw = find(e,'UpdateWitness'); p,q = tup(uw[1][1]), tup(uw[1][2])
ok = keepA(p)==keepA(q) and keepA(swap(p))!=keepA(swap(q)); print('update witness replays', ok); fails += not ok
for r in ['(CheckUpdates KeepA)','(CheckBehavioral KeepA)','(CheckBehavioral KeepA (Horizon (Steps 0)))','(InduceExact KeepA)']:
    print(r, find(env[r],'Status')[1])
print('FAILS', fails); sys.exit(1 if fails else 0)
