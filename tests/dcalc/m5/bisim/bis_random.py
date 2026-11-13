import random, subprocess, sys
R = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 7); N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
import os, tempfile; D = tempfile.mkdtemp(prefix='bisr') + '/'; ok = bad = 0; refuted = checked = 0
for t in range(N):
    n = R.randint(1, 9); S = ['S%d' % i for i in range(n)]; na = R.randint(1, 3); no = R.randint(1, 2)
    L = ['(DC.Module RB', '  (Profile Nondeterministic)', '  (Use Simulation)', '  (Carrier St (Of Symbol) (Enum %s))' % ' '.join(S),
         '  (Carrier V (Of Symbol) (Enum V0 V1 V2))', '  (Carrier K (Of Symbol) (Enum %s))' % ' '.join('K%d' % i for i in range(n))]
    for o in range(no):
        if R.random() < 0.3: L.append('  (Map o%d (From St) (To V) (Choice %s))' % (o, ' '.join('(%s %s)' % (x, ' '.join(R.sample(['V0', 'V1', 'V2'], R.randint(1, 2)))) for x in S)))
        else: L.append('  (Map o%d (From St) (To V) (Cases %s))' % (o, ' '.join('(%s V%d)' % (x, R.randint(0, 1)) for x in S)))
    for a in range(na):
        L.append('  (Map m%d (From St) (To St) (Choice %s))' % (a, ' '.join('(%s %s)' % (x, ' '.join(R.sample(S, R.randint(1, min(3, n))))) for x in S)))
    nk = R.randint(1, n)
    L.append('  (Map e (From St) (To K) (Cases %s))' % ' '.join('(%s K%d)' % (x, R.randrange(nk)) for x in S))
    L.append('  (Machine M (States St) %s %s (Bag Set))' % (' '.join('(Observe o%d o%d)' % (o, o) for o in range(no)), ' '.join('(Action a%d m%d)' % (a, a) for a in range(na))))
    L.append('  (Representation P (Of M) (Encode e)))')
    L += ['!(dc.run RB (BehavioralTolerance M))', '!(dc.run RB (CheckBehavioral P))']
    f = D + 'r%d.metta' % t; o = D + 'r%d.out' % t; open(f, 'w').write('\n'.join(L) + '\n')
    out = subprocess.run(['build/dcalc/dcalc', '--beyond-release', f], capture_output=True, text=True).stdout; open(o, 'w').write(out)
    refuted += '(Status Refuted)' in out; checked += out.count('(Status Checked)')
    r = subprocess.run(['python3', 'tests/dcalc/m5/replay_m5.py', f, o], capture_output=True, text=True)
    if r.returncode == 0 and 'replay_m5: 2 rows, 0 not accepted' in r.stdout: ok += 1
    else: bad += 1; print('BAD', t, r.stdout.strip().splitlines()[:3], out[:300])
print('bis_random: %d ok, %d bad, %d refuted rows, %d checked rows -> %s' % (ok, bad, refuted, checked, 'PASS' if bad == 0 else 'FAIL'))
