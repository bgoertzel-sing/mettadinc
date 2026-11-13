# m5-rest review 2 F2: randomized differential check of CheckSafety (abstract transfer and the
# refinement loop under (Budget (Unrollings b))), with non-functional Via relations.
# Own generator and semantics (no dcalc code, no replay_m5 internals):
#   abstract violation  : on B from the images of Init
#   concrete violation  : on A from Init with the SOUND pullback, down(T) = states all of whose images lie in T;
#                         EnterFrom X (Not Y) pulls the from-side back as down(complement(X u Y)).
# Rules: Refuted <=> concrete violation is required of every Refuted; Checked => no concrete violation;
# no budget: abstract safe -> Checked, abstract+concrete violation -> Refuted, else Unknown.
# Every output is replayed by replay_m5.py; one Refuted row per file is tampered (path start moved
# outside Init) and must be rejected.  Usage: cs_random.py SEED N  (run from the repo root)
import random, re, subprocess, sys, tempfile
Rg = random.Random(int(sys.argv[1])); N = int(sys.argv[2]); D = tempfile.mkdtemp(prefix='csr') + '/'
DC = 'build/dcalc/dcalc'; RP = 'tests/dcalc/m5/replay_m5.py'
def reach(init, step):
    dep = {x: 0 for x in init}; q = list(init)
    while q:
        x = q.pop(0)
        for y in sorted(step(x)):
            if y not in dep: dep[y] = dep[x] + 1; q.append(y)
    return dep
ok = bad = tam = und64 = 0; cnt = {}
for t in range(N):
    n = Rg.randint(1, 8); S = ['S%d' % i for i in range(n)]; na = Rg.randint(1, 2)
    co = {x: Rg.randint(0, 1) for x in S}
    m = Rg.randint(2, 5); T = ['T%d' % i for i in range(m)]; to = {T[i]: (i if i < 2 else Rg.randint(0, 1)) for i in range(m)}
    rel = {}
    for x in S:
        c = [u for u in T if to[u] == co[x]]; rel[x] = sorted(Rg.sample(c, Rg.randint(1, min(2, len(c)))))
    cm = {(a, x): sorted(Rg.sample(S, Rg.randint(1, min(2, n)))) for a in range(na) for x in S}
    tm = {}
    for a in range(na):
        for u in T:
            img = set()
            for x in S:
                if u in rel[x]:
                    for y in cm[(a, x)]: img |= set(rel[y])
            if Rg.random() < 0.3 or not img: img.add(Rg.choice(T))
            tm[(a, u)] = sorted(img)
    kind = Rg.choice(['Shows', 'EnterFrom', 'ReachWithin']); X, Y = Rg.sample(T, 2); pv = Rg.randint(0, 1); k = Rg.randint(0, 3)
    prop = {'Shows': '(Shows o V%d)' % pv, 'EnterFrom': '(EnterFrom %s (Not %s))' % (X, Y), 'ReachWithin': '(ReachWithin %s %d)' % (X, k)}[kind]
    I = sorted(Rg.sample(S, Rg.randint(1, min(2, n))))
    ch = lambda f, dom: ' '.join('(%s %s)' % (x, ' '.join(f(x))) for x in dom)
    L = ['(DC.Module CS', '  (Profile Nondeterministic)', '  (Use Simulation)',
         '  (Carrier C (Of Symbol) (Enum %s))' % ' '.join(S), '  (Carrier T (Of Symbol) (Enum %s))' % ' '.join(T),
         '  (Carrier O (Of Symbol) (Enum V0 V1))',
         '  (Map cobs (From C) (To O) (Cases %s))' % ' '.join('(%s V%d)' % (x, co[x]) for x in S),
         '  (Map tobs (From T) (To O) (Cases %s))' % ' '.join('(%s V%d)' % (u, to[u]) for u in T)]
    for a in range(na):
        L.append('  (Map ca%d (From C) (To C) (Choice %s))' % (a, ch(lambda x: cm[(a, x)], S)))
        L.append('  (Map ta%d (From T) (To T) (Choice %s))' % (a, ch(lambda u: tm[(a, u)], T)))
    acts = lambda p: ' '.join('(Action a%d %s%d)' % (a, p, a) for a in range(na))
    L += ['  (Machine A (States C) (Observe o cobs) %s (Bag Set))' % acts('ca'), '  (Machine B (States T) (Observe o tobs) %s (Bag Set))' % acts('ta'),
          '  (Map rel (From C) (To T) (Choice %s))' % ch(lambda x: rel[x], S), '  (Simulation H (Source A) (Target B) (Relation rel)))',
          '!(dc.run CS (CheckSimulation H))']
    BUD = (None, 0, 1, 64)
    for b in BUD:
        L.append('!(dc.run CS (CheckSafety B (Never %s) (Via H) (Init %s)%s))' % (prop, ' '.join(I), '' if b is None else ' (Budget (Unrollings %d))' % b))
    f = D + 'c%d.metta' % t; o = D + 'c%d.out' % t; open(f, 'w').write('\n'.join(L) + '\n')
    out = subprocess.run([DC, '--beyond-release', f], capture_output=True, text=True).stdout; open(o, 'w').write(out)
    rows = [l for l in out.splitlines() if ' => ' in l]
    sts = [(re.search(r'\(Status (\w+)\)', l) or [None, '?'])[1] for l in rows]
    for s_ in sts[1:]: cnt[s_] = cnt.get(s_, 0) + 1
    cstep = lambda x: {y for a in range(na) for y in cm[(a, x)]}
    tstep = lambda u: {v for a in range(na) for v in tm[(a, u)]}
    down = lambda Ts: {x for x in S if set(rel[x]) <= Ts}
    def viol(init, step, obs, Xs, Fs):
        dep = reach(init, step)
        if kind == 'Shows': return any(obs[x] == pv for x in dep)
        if kind == 'ReachWithin': return any(x in Xs and d <= k for x, d in dep.items())
        return any(x in Fs and step(x) & Xs for x in dep)
    abad = viol(set().union(*(rel[x] for x in I)), tstep, to, {X}, set(T) - {X, Y})
    cbad = viol(set(I), cstep, co, down({X}), down(set(T) - {X, Y}))
    why = []
    if len(rows) != 1 + len(BUD) or sts[0] != 'Checked': why.append('simulation row/rows %s' % sts)
    else:
        if cbad and not abad: why.append('generator: concrete violation without abstract one')
        want0 = 'Checked' if not abad else ('Refuted' if cbad else 'Unknown')
        if sts[1] != want0: why.append('no budget: %s, want %s' % (sts[1], want0))
        for b, s_ in zip(BUD[1:], sts[2:]):
            if s_ not in (('Refuted', 'Unknown') if cbad else ('Checked', 'Unknown')): why.append('Unrollings %d: %s (concrete violation %s)' % (b, s_, cbad))
        if sts[-1] == 'Unknown': und64 += 1
    r = subprocess.run([sys.executable, RP, f, o], capture_output=True, text=True)
    if r.returncode != 0: why.append('replay: ' + (r.stdout.strip().splitlines() or [''])[-1])
    nonI = [x for x in S if x not in I]
    ri = next((i for i, l in enumerate(out.splitlines()) if '(Status Refuted)' in l and 'ConcreteCounterexample (Path' in l), None)
    if ri is not None and nonI:
        ls = out.splitlines(); ls[ri] = re.sub(r'\(ConcreteCounterexample \(Path (\w+)', '(ConcreteCounterexample (Path ' + nonI[0], ls[ri], count=1)
        tp = D + 'c%d_t.out' % t; open(tp, 'w').write('\n'.join(ls) + '\n')
        rt = subprocess.run([sys.executable, RP, f, tp], capture_output=True, text=True)
        if rt.returncode == 0 or 'REJECT' not in rt.stdout: why.append('tamper accepted')
        else: tam += 1
    if why: bad += 1; print('BAD', t, f, kind, 'abad', abad, 'cbad', cbad, sts, why[:3])
    else: ok += 1
print('cs_random: %d ok, %d bad, statuses %s, tampers rejected %d, Unrollings-64 undecided %d -> %s' % (ok, bad, sorted(cnt.items()), tam, und64, 'PASS' if bad == 0 else 'FAIL'))
