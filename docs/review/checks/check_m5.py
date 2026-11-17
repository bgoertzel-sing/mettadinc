# Own M5 checker (no repo code): parses fixtures with a tiny s-expr reader and recomputes
# Reads outcome sets / uniform probabilities and AccessProtocol simulation, exactness, Safe, Lockout.
import re, sys
from fractions import Fraction
def parse(s):
    s = re.sub(r';[^\n]*', '', s); toks = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', s); out = []; st = [out]
    for t in toks:
        if t == '(': n = []; st[-1].append(n); st.append(n)
        elif t == ')': st.pop()
        else: st[-1].append(t)
    return out
def module(path):
    m = next(x for x in parse(open(path).read()) if isinstance(x, list) and x and x[0] == 'DC.Module')
    maps = {}
    for f in m[2:]:
        if f[0] == 'Map':
            body = f[4]
            maps[f[1]] = {r[0]: (set(r[1:]) if body[0] == 'Choice' else {r[1]}) for r in body[1:]}
    return m, maps
F = sys.argv[1]; bad = 0
def chk(name, got, exp):
    global bad; ok = got == exp; bad += not ok; print(f'{name:45s} mine={got} envelope={exp} {"OK" if ok else "MISMATCH"}')
m, M = module(F + '/reads.metta')
for mach, act in (('Shared','shared-read'), ('Fresh','fresh-read')):
    succ = M[act]['Start']; obs = {next(iter(M['agree'][s])) for s in succ}
    p = Fraction(sum(1 for s in succ if M['agree'][s] == {'Agree'}), len(succ))
    chk(f'Reads Outcomes {mach}', sorted(obs), {'Shared':['Agree'],'Fresh':['Agree','Differ']}[mach])
    chk(f'Reads P(Agree) {mach}', p, {'Shared':Fraction(1),'Fresh':Fraction(1,2)}[mach])
m, M = module(F + '/access_protocol.metta')
al = lambda m_: {'fail':'afail','ok':'aok','escalate':'aescalate'}
h = lambda s: next(iter(M['stage-of'][s])); C = list(M['fail'])
sim_bad = [(s,a) for s in C for a in ('fail','ok','escalate') if h(next(iter(M[a][s]))) not in M[al(0)[a]][h(s)]]
chk('Access CheckSimulation StageSim', 'Checked' if not sim_bad else ('Refuted', sim_bad), 'Checked')
ex_bad = [(a,s,t) for a in ('fail','ok','escalate') for s in C for t in C if h(s)==h(t) and h(next(iter(M[a][s])))!=h(next(iter(M[a][t])))]
chk('Access InduceExact StageQuotient', 'Refuted' if ex_bad else 'Checked', 'Refuted'); print('  exactness witness', ex_bad[0])
# Safe on abstract: no transition into Admin from a state other than Auth/Admin, from reachable states of h(S0)
reach = {h('S0')}; fr = [h('S0')]
while fr:
    x = fr.pop()
    for a in al(0).values():
        for y in M[a][x]:
            if y not in reach: reach.add(y); fr.append(y)
viol = [(x,a) for x in reach for a in al(0).values() if 'Admin' in M[a][x] and x not in ('Auth','Admin')]
chk('Access Safe (abstract)', 'Checked' if not viol else 'Refuted', 'Checked')
# Lockout: abstract reaches Locked within 2 -> abstract counterexample; concrete within 2?
def within(step, start, k):
    lv = {start}
    for _ in range(k): lv |= {y for x in lv for a in step for y in step[a](x)}
    return lv
absr = within({a: (lambda x, a=a: M[a][x]) for a in al(0).values()}, 'Start', 2)
conc = within({a: (lambda x, a=a: M[a][x]) for a in ('fail','ok','escalate')}, 'S0', 2)
lk = 'Unknown' if ('Locked' in absr and 'Locked' not in conc) else ('Refuted' if 'Locked' in conc else 'Checked')
chk('Access Lockout (spurious abstract cex)', lk, 'Unknown'); print('  abstract within2', sorted(absr), 'concrete within2', sorted(conc))
print('CHECK_M5', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
