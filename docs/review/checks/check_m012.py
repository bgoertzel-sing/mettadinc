# Independent M0-M2 recomputation: Staged (H06-H08), DescentConverse (H09/H10), LiteralCongruence (C01-C03), Surjectivity (H12).
import re, sys, itertools
D = sys.argv[1] if len(sys.argv) > 1 else 'out'
def st(f):
    r = {}
    for l in open(f):
        if ' => ' in l:
            h, e = l.split(' => ', 1); r[(h.split(' ',1)[0], h.split(' ', 1)[1].strip())] = (re.search(r'\(Status (\w+)\)', e).group(1), e)
    return r
fails = 0
def rep(n, ok, note=''):
    global fails; fails += not ok; print(('PASS ' if ok else 'FAIL ') + n, note)
H = st(f'{D}/hypotheses.r1.out')
# Staged
last = {0:0,1:0,2:0,3:1}; climb = {0:1,1:2,2:3,3:3}; stage = {0:0,1:0,2:1,3:2}
def seq(s, h):
    o = []
    for _ in range(h+1): o.append(last[s]); s = climb[s]
    return tuple(o)
for h in (0,1,2):
    ker = {(p,q) for p,q in itertools.combinations(range(4),2) if seq(p,h)!=seq(q,h)}
    defect = int(any(stage[p]==stage[q] for p,q in ker))
    s, e = H[('Staged', f'(CheckBehavioral Merge01 (Horizon (Steps {h})))')]
    theirs = {(int(a),int(b)) for a,b in re.findall(r'\(Entry (\d) (\d) 1\)', e)}
    ok = s == ('Refuted' if defect else 'Checked') and (defect or theirs == ker)
    rep(f'Staged horizon {h}', ok, f'mine defect {defect} kernel {sorted(ker)}; theirs {sorted(theirs) if not defect else "-"}')
upw = [(p,q) for p,q in itertools.combinations(range(4),2) if stage[p]==stage[q] and stage[climb[p]]!=stage[climb[q]]]
s, e = H[('Staged','(InduceExact Merge01)')]
rep('H08 Staged InduceExact', s=='Refuted' and bool(upw) and '(UpdateWitness (Pair 0 1) (Action climb)' in e, f'my update witnesses {upw}')
# DescentConverse / LiteralCongruence share M
hop = {0:0,1:2,2:2}; split = {0:0,1:0,2:1}
upd = [(p,q) for p,q in itertools.combinations(range(3),2) if split[p]==split[q] and split[hop[p]]!=split[hop[q]]]
rep('H09 DescentConverse behavioral (obs constant)', H[('DescentConverse','(CheckBehavioral Q)')][0]=='Checked')
s, e = H[('DescentConverse','(CheckUpdates Q)')]
rep('H10 DescentConverse updates', s=='Refuted' and upd==[(0,1)] and '(UpdateWitness (Pair 0 1) (Action hop) (Codes 0 0) (Left 0) (Right 1))' in e, f'mine {upd}')
rep('C01 Blurred now (trivial tolerance)', H[('LiteralCongruence','(MeasureNow Blurred)')][0]=='Checked')
rep('C02 Blurred updates (trivial tolerance)', H[('LiteralCongruence','(CheckUpdates Blurred)')][0]=='Checked')
s, e = H[('LiteralCongruence','(InduceExact Blurred)')]
rep('C03 literal congruence refuted', s=='Refuted' and '(CongruenceWitness (Pair 0 1) (Action hop) (Codes 0' in e, f'mine {upd}')
# Surjectivity
zero = {'s':0}; hold = {'s':'s'}; which = {'z0':0,'z1':1}; keep = {'z0':'z0','z1':'z1'}; f = {'s':'z0'}
hom = all(zero[x]==which[f[x]] and keep[f[x]]==f[hold[x]] for x in zero); sur = set(f.values())=={'z0','z1'}
s, e = H[('Surjectivity','(CheckAbstractionMap Embed)')]
rep('H12 homomorphism, not surjective', s=='Checked' and hom and not sur and '(Kind Homomorphism) (Surjective False)' in e)
print('FAILS', fails); sys.exit(1 if fails else 0)
