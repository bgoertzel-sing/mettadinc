import random, subprocess, sys, tempfile
from fractions import Fraction as F
sys.path.insert(0, 'tests/dcalc/m5'); import replay_m5 as R
Rg = random.Random(int(sys.argv[1])); N = int(sys.argv[2]); D = tempfile.mkdtemp(prefix='hr') + '/'
ok = bad = 0; cnt = {}
def dist(M, g, h):
    """Independent value iteration of the Hausdorff lifting (spec 951), Fractions."""
    S = M.states('M'); ob = M.mach['M']['obs']; ac = M.mach['M']['act']
    od = lambda x, y: any(M.map[ob[o]].get(x) != M.map[ob[o]].get(y) for o in ob)
    Dk = {(x, y): F(int(od(x, y))) for x in S for y in S}; k = 0
    while h is None or k < h:
        N2 = {}
        for x in S:
            for y in S:
                if od(x, y): N2[(x, y)] = F(1); continue
                v = F(0)
                for a in ac:
                    X, Y = M.img('M', a, x), M.img('M', a, y)
                    if not X and not Y: continue
                    if not X or not Y: hv = F(1)
                    else: hv = max(max(min(Dk[(u, w)] for w in Y) for u in X), max(min(Dk[(u, w)] for u in X) for w in Y))
                    v = max(v, g * hv)
                N2[(x, y)] = v
        k += 1
        if N2 == Dk and h is None: break
        Dk = N2
        if k > 200: break
    return Dk
for t in range(N):
    n = Rg.randint(1, 7); S = ['S%d' % i for i in range(n)]; na = Rg.randint(1, 2); no = Rg.randint(1, 2)
    L = ['(DC.Module RH', '  (Profile Nondeterministic)', '  (Use Simulation)', '  (Carrier St (Of Symbol) (Enum %s))' % ' '.join(S),
         '  (Carrier V (Of Symbol) (Enum V0 V1))', '  (Carrier K (Of Symbol) (Enum %s))' % ' '.join('K%d' % i for i in range(n))]
    for o in range(no): L.append('  (Map o%d (From St) (To V) (Cases %s))' % (o, ' '.join('(%s V%d)' % (x, Rg.randint(0, 1)) for x in S)))
    for a in range(na):
        L.append('  (Map m%d (From St) (To St) (Choice %s))' % (a, ' '.join('(%s %s)' % (x, ' '.join(Rg.sample(S, Rg.randint(1, min(3, n))))) for x in S)))
    nk = Rg.randint(1, n)
    L.append('  (Map e (From St) (To K) (Cases %s))' % ' '.join('(%s K%d)' % (x, Rg.randrange(nk)) for x in S))
    L.append('  (Machine M (States St) %s %s (Bag Set))' % (' '.join('(Observe o%d o%d)' % (o, o) for o in range(no)), ' '.join('(Action a%d m%d)' % (a, a) for a in range(na))))
    L.append('  (Representation P (Of M) (Encode e)))')
    gs = [F(1, 2), F(1), F(2, 3), F(1, 3)]; g = Rg.choice(gs); b = F(Rg.randint(0, 4), 4); h = Rg.randint(0, 4); bu = Rg.randint(0, 3)   # Discount 0 is rejected at admission: (0,1]
    gl = '(Discount (Rat %d %d))' % (g.numerator, g.denominator)
    reqs = [('(MeasureBehavioral P %s)' % gl, None, None, None), ('(MeasureBehavioral P %s (Horizon (Steps %d)))' % (gl, h), h, None, None),
            ('(CheckBehavioral P %s (Within (Rat %d %d)))' % (gl, b.numerator, b.denominator), None, b, None),
            ('(MeasureBehavioral P %s (Budget (Unrollings %d)))' % (gl, bu), None, None, bu)]
    L += ['!(dc.run RH %s)' % r[0] for r in reqs]
    f = D + 'r%d.metta' % t; o = D + 'r%d.out' % t; open(f, 'w').write('\n'.join(L) + '\n')
    out = subprocess.run(['build/dcalc/dcalc', '--beyond-release', f], capture_output=True, text=True).stdout; open(o, 'w').write(out)
    rows = [l for l in out.splitlines() if ' => ' in l]
    r = subprocess.run(['python3', 'tests/dcalc/m5/replay_m5.py', f, o], capture_output=True, text=True)
    good = r.returncode == 0 and len(rows) == 4
    M = R.Module([u for u in R.read_all(open(f).read()) if R.head(u) == 'DC.Module'][0])
    same = [(x, z) for i, x in enumerate(S) for z in S[i + 1:] if M.map['e'][x] == M.map['e'][z]]
    why = []
    for row, (rq, hh, bb, uu) in zip(rows, reqs):
        res = R.read_all(row.split(' => ', 1)[1])[0]; st = R.field(res, 'Status')[1]; cnt[st] = cnt.get(st, 0) + 1
        Dk = dist(M, g, hh); true = max([Dk[p] for p in same], default=F(0)); val = R.field(res, 'Value')
        if st == 'Unknown':
            iv = R.field(val, 'BehavioralInterval'); lo, up = R.rat(R.field(iv, 'Lower')[1]), R.rat(R.field(iv, 'Upper')[1])
            if not (lo <= true <= up): why.append('interval %s..%s misses %s' % (lo, up, true))
            continue
        if bb is not None and g == 1 and bb == 0 and st in ('Checked', 'Refuted') and not (val and R.field(val, 'BehavioralDefect')):
            if (st == 'Checked') != (true == 0): why.append('%s: crisp path status %s, true %s' % (rq, st, true))
            continue   # crisp default (Discount 1, Within 0) answers through the bisimulation path
        if st not in ('Checked', 'Refuted') or not val or not R.field(val, 'BehavioralDefect'):
            why.append('%s: status %s without BehavioralDefect: %s' % (rq, st, row.split(' => ', 1)[1][:300])); continue
        dv = R.rat(R.field(val, 'BehavioralDefect')[1])
        if dv != true: why.append('%s: defect %s, independent %s' % (rq, dv, true))
        if bb is not None and (st == 'Checked') != (true <= bb): why.append('%s: status %s, true %s' % (rq, st, true))
    if why: good = False
    if good: ok += 1
    else: bad += 1; print('BAD', t, f, why[:3], r.stdout.strip().splitlines()[-3:])
print('h_random: %d ok, %d bad, statuses %s -> %s' % (ok, bad, sorted(cnt.items()), 'PASS' if bad == 0 else 'FAIL'))
