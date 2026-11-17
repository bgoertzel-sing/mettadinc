# Canary v2. v1 "FAIL" came from mutations that do not necessarily break the proof
# (negating a literal in a CNF clause the proof never uses; swapping two hints that are each unit anyway).
# The fix: (a) known-answer hand cases; (b) mutations checked against cake_lpr as an oracle. My verdict must
# agree with cake_lpr on every mutant, and at least one mutant per kind must be refused.
import os, sys, subprocess, random
sys.path.insert(0, '.'); from lrat import check
CAKE = sys.argv[1]; S = '../proofstore'; os.makedirs('canary', exist_ok=True)
def w(c, l, tag):
    cp, lp = f'canary/{tag}.cnf', f'canary/{tag}.lrat'
    open(cp,'w').write('\n'.join(c)+'\n'); open(lp,'w').write('\n'.join(l)+'\n'); return cp, lp
def cake(cp, lp):
    r = subprocess.run([CAKE, cp, lp], capture_output=True, text=True, timeout=60)
    return 's VERIFIED UNSAT' in r.stdout
bad = 0
# (a) known answers
ka = [('valid', ['p cnf 1 2','1 0','-1 0'], ['3 0 1 2 0'], True),
      ('no_conflict', ['p cnf 1 2','1 0','-1 0'], ['3 0 1 0'], False),
      ('sat_formula', ['p cnf 2 2','1 2 0','-1 0'], ['3 0 2 1 0'], False),
      ('unknown_hint', ['p cnf 1 2','1 0','-1 0'], ['3 0 1 7 0'], False)]
for name, c, l, exp in ka:
    cp, lp = w(c, l, 'ka'); mine = check(cp, lp) == 'VERIFIED'; ck = cake(cp, lp)
    ok = mine == exp == ck; bad += not ok; print('KA', name, 'mine', mine, 'cake', ck, 'expected', exp, 'OK' if ok else 'BAD')
# (b) differential mutations
random.seed(7); refused = {}; agree = dis = 0
hs = sorted(f[:-4] for f in os.listdir(S) if f.endswith('.cnf'))[:8]
for h in hs:
    cnf = open(f'{S}/{h}.cnf').read().strip().split('\n'); lr = open(f'{S}/{h}.lrat').read().strip().split('\n')
    adds = [i for i,l in enumerate(lr) if l.split()[1] != 'd']
    for kind in ('drop_hint','swap_hints','flip_used_cnf_lit','drop_used_cnf_clause'):
        L, C = list(lr), list(cnf)
        i = random.choice(adds); t = L[i].split(); z = t.index('0', 1); hints = t[z+1:-1]
        if kind == 'drop_hint' and hints:
            del hints[random.randrange(len(hints))]; L[i] = ' '.join(t[:z+1] + hints + ['0'])
        elif kind == 'swap_hints' and len(hints) > 1:
            a = random.randrange(len(hints)-1); hints[a], hints[a+1] = hints[a+1], hints[a]; L[i] = ' '.join(t[:z+1] + hints + ['0'])
        else:
            n = sum(1 for x in C if x and x[0] not in 'cp')
            used = [int(x) for x in hints if 0 < int(x) <= n]
            if not used: continue
            k = random.choice(used); idx = [j for j,x in enumerate(C) if x and x[0] not in 'cp'][k-1]
            lits = C[idx].split()[:-1]
            if kind == 'flip_used_cnf_lit':
                p = random.randrange(len(lits)); lits[p] = str(-int(lits[p])); C[idx] = ' '.join(lits + ['0'])
            else:
                C[idx] = 'c dropped'; C = [x if not x.startswith('p cnf') else x for x in C]
        cp, lp = w(C, L, 'mut'); mine = check(cp, lp) == 'VERIFIED'; ck = cake(cp, lp)
        if mine == ck: agree += 1
        else: dis += 1; print('DISAGREE', h[:12], kind, 'mine', mine, 'cake', ck)
        refused[kind] = refused.get(kind, 0) + (not mine)
print('refused per kind', refused, 'agree', agree, 'disagree', dis)
bad += dis + sum(1 for v in refused.values() if v == 0)
print('CANARY2', 'PASS' if not bad else 'FAIL'); sys.exit(1 if bad else 0)
