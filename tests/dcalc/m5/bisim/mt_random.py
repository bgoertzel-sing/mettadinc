import random, subprocess, sys, os, tempfile, itertools
sys.path.insert(0, 'tests/dcalc/m5'); import replay_m5 as R
Rg = random.Random(int(sys.argv[1])); N = int(sys.argv[2]); D = tempfile.mkdtemp(prefix='mtr') + '/'
ok = bad = ref = chk = 0
def traces(M, m, x, L):
    out = set(); V = R.obs_vectors(M, m)
    def go(X, pre, k):
        for v in V:
            X1 = R.obs_filter(M, m, X, list(v))
            if not X1: continue
            out.add(pre + (v,))
            if k < L:
                for a in sorted(M.mach[m]['act']):
                    X2 = R.post(M, m, a, X1)
                    if X2: go(X2, pre + (v, a), k + 1)
    go({x}, (), 0); return out
for t in range(N):
    n = Rg.randint(1, 6); S = ['S%d' % i for i in range(n)]; na = Rg.randint(1, 2); no = Rg.randint(1, 2)
    L = ['(DC.Module RT', '  (Profile Nondeterministic)', '  (Use Simulation)', '  (Carrier St (Of Symbol) (Enum %s))' % ' '.join(S),
         '  (Carrier V (Of Symbol) (Enum V0 V1 V2))', '  (Carrier K (Of Symbol) (Enum %s))' % ' '.join('K%d' % i for i in range(n))]
    for o in range(no):
        if Rg.random() < 0.3: L.append('  (Map o%d (From St) (To V) (Choice %s))' % (o, ' '.join('(%s %s)' % (x, ' '.join(Rg.sample(['V0', 'V1', 'V2'], Rg.randint(1, 2)))) for x in S)))
        else: L.append('  (Map o%d (From St) (To V) (Cases %s))' % (o, ' '.join('(%s V%d)' % (x, Rg.randint(0, 1)) for x in S)))
    for a in range(na):
        L.append('  (Map m%d (From St) (To St) (Choice %s))' % (a, ' '.join('(%s %s)' % (x, ' '.join(Rg.sample(S, Rg.randint(1, min(3, n))))) for x in S)))
    nk = Rg.randint(1, n)
    L.append('  (Map e (From St) (To K) (Cases %s))' % ' '.join('(%s K%d)' % (x, Rg.randrange(nk)) for x in S))
    L.append('  (Machine M (States St) %s %s (Bag Set))' % (' '.join('(Observe o%d o%d)' % (o, o) for o in range(no)), ' '.join('(Action a%d m%d)' % (a, a) for a in range(na))))
    L.append('  (Representation P (Of M) (Encode e)))')
    L += ['!(dc.run RT (CheckTrace P))', '!(dc.run RT (CheckTrace P (Horizon (Steps 2))))']
    f = D + 'r%d.metta' % t; o = D + 'r%d.out' % t; open(f, 'w').write('\n'.join(L) + '\n')
    out = subprocess.run(['build/dcalc/dcalc', '--beyond-release', f], capture_output=True, text=True).stdout; open(o, 'w').write(out)
    rows = [l for l in out.splitlines() if ' => ' in l]
    r = subprocess.run(['python3', 'tests/dcalc/m5/replay_m5.py', f, o], capture_output=True, text=True)
    good = r.returncode == 0 and 'replay_m5: 2 rows, 0 not accepted' in r.stdout
    M = R.Module([u for u in R.read_all(open(f).read()) if R.head(u) == 'DC.Module'][0])
    same = [(x, z) for i, x in enumerate(S) for z in S[i + 1:] if M.map['e'][x] == M.map['e'][z]]
    for row, Lh in ((rows[0], 2 ** (2 * n)) , (rows[1], 2)):
        Lb = min(Lh, 6)
        diff = any(traces(M, 'M', x, Lb) != traces(M, 'M', z, Lb) for x, z in same)
        st = R.field(R.read_all(row.split(' => ', 1)[1])[0], 'Status')[1]
        ref += st == 'Refuted'; chk += st == 'Checked'
        if diff and st != 'Refuted': good = False
        if Lb == Lh and not diff and st != 'Checked': good = False
    if good: ok += 1
    else: bad += 1; print('BAD', t, f, r.stdout.strip().splitlines()[:3])
print('mt_random: %d ok, %d bad, %d refuted rows, %d checked rows -> %s' % (ok, bad, ref, chk, 'PASS' if bad == 0 else 'FAIL'))
