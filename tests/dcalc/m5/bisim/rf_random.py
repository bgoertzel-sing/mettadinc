import random, subprocess, sys, tempfile
sys.path.insert(0, 'tests/dcalc/m5'); import replay_m5 as R
Rg = random.Random(int(sys.argv[1])); N = int(sys.argv[2]); D = tempfile.mkdtemp(prefix='rfr') + '/'
ok = bad = 0; cnt = {}
for t in range(N):
    n = Rg.randint(1, 9); S = ['S%d' % i for i in range(n)]; na = Rg.randint(1, 3); no = Rg.randint(1, 2)
    L = ['(DC.Module RF', '  (Profile Nondeterministic)', '  (Use Simulation)', '  (Carrier St (Of Symbol) (Enum %s))' % ' '.join(S),
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
    k = Rg.randint(0, 4); b = Rg.randint(0, 4)
    L += ['!(dc.run RF (Refine P (Preserve Encoding) (Until Stable)))', '!(dc.run RF (Refine P (Until (Steps %d))))' % k, '!(dc.run RF (Refine P (Budget (Unrollings %d))))' % b]
    f = D + 'r%d.metta' % t; o = D + 'r%d.out' % t; open(f, 'w').write('\n'.join(L) + '\n')
    out = subprocess.run(['build/dcalc/dcalc', '--beyond-release', f], capture_output=True, text=True).stdout; open(o, 'w').write(out)
    rows = [l for l in out.splitlines() if ' => ' in l]
    r = subprocess.run(['python3', 'tests/dcalc/m5/replay_m5.py', f, o], capture_output=True, text=True)
    sts = [R.field(R.read_all(l.split(' => ', 1)[1])[0], 'Status')[1] for l in rows]
    for s_ in sts: cnt[s_] = cnt.get(s_, 0) + 1
    # independent fixed point via coarsest_bisim restricted by code: refine from seed until stable
    M = R.Module([u for u in R.read_all(open(f).read()) if R.head(u) == 'DC.Module'][0])
    good = len(rows) == 3 and sts[0] == 'Checked' and sts[1] == 'Checked' and sts[2] in ('Checked', 'Unknown') and r.returncode == 0
    if good:
        seedk = {x: (M.map['e'][x] and tuple(sorted(M.map['e'][x])), tuple(tuple(sorted(M.map['o%d' % j].get(x, set()))) for j in range(no))) for x in S}
        ids = {kk: i for i, kk in enumerate(sorted(set(seedk.values()), key=repr))}; blk = {x: ids[seedk[x]] for x in S}; rounds = 0
        while True:
            nb = R.refine_step(M, 'M', blk)
            if R.same_part(nb, blk, S): break
            blk = nb; rounds += 1
        fin = R.blocks_of(R.field(R.field(R.read_all(rows[0].split(' => ', 1)[1])[0], 'Value')[1], 'Partition'), S)
        if not R.same_part(fin, blk, S): good = False
        # Budget (Unrollings b): rounds splitting + one confirming round must fit -> Checked iff b >= rounds + 1
        if sts[2] != ('Checked' if b >= rounds + 1 else 'Unknown'): good = False
        sk = R.blocks_of(R.field(R.field(R.read_all(rows[1].split(' => ', 1)[1])[0], 'Value')[1], 'Partition'), S)
        ref = {x: ids[seedk[x]] for x in S}
        for _ in range(k): ref = R.refine_step(M, 'M', ref)
        if not R.same_part(sk, ref, S): good = False
    if good: ok += 1
    else: bad += 1; print('BAD', t, f, sts, r.stdout.strip().splitlines()[-2:])
print('rf_random: %d ok, %d bad, statuses %s -> %s' % (ok, bad, sorted(cnt.items()), 'PASS' if bad == 0 else 'FAIL'))
