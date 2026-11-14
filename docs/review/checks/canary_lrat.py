# Sanity-gate canary for my LRAT checker: tampered proofs/CNFs must be refused.
import os, shutil, sys
sys.path.insert(0, '.'); from lrat import check
S = '../proofstore'; h = sorted(f[:-4] for f in os.listdir(S) if f.endswith('.cnf'))[0]
cnf = open(f'{S}/{h}.cnf').read().split('\n'); lr = open(f'{S}/{h}.lrat').read().split('\n')
os.makedirs('canary', exist_ok=True)
def run(c, l):
    open('canary/x.cnf','w').write('\n'.join(c)); open('canary/x.lrat','w').write('\n'.join(l))
    return check('canary/x.cnf', 'canary/x.lrat')
print('baseline', run(cnf, lr))
add = [i for i,l in enumerate(lr) if l.split() and l.split()[1] != 'd' and len(l.split()) > 4]
m = {}
L = list(lr); t = L[add[0]].split(); L[add[0]] = ' '.join(t[:-2] + ['0']); m['drop_last_hint'] = run(cnf, L)
L = [l for l in lr if not (l.split() and l.split()[1] == '0')]; m['drop_empty_clause'] = run(cnf, L)
C = list(cnf); j = next(i for i,l in enumerate(C) if l and l[0] not in 'cp'); C[j] = ' '.join(x for x in C[j].split() if x != '0' ) ; C[j] = (C[j].split()[0] if C[j] else '1') + ' 0'
first = next(i for i,l in enumerate(cnf) if l and l[0] not in 'cp')
C = list(cnf); C[first] = str(int(cnf[first].split()[0]) * -1) + ' ' + ' '.join(cnf[first].split()[1:]); m['negate_cnf_literal'] = run(C, lr)
L = list(lr); t = L[add[1]].split(); z = t.index('0', 1); t[z+1], t[z+2] = t[z+2], t[z+1]; L[add[1]] = ' '.join(t); m['swap_hints'] = run(cnf, L)
bad = 0
for k, v in m.items(): print(k, '->', v); bad += v == 'VERIFIED'
print('CANARY', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
