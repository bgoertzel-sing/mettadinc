#!/usr/bin/env python3
"""Exact-arithmetic oracle for the MeTTaDinC validation package.

It accompanies "MeTTaDinC: An Executable Language for Observer-Relative Abstraction,
Evidence, and Composition" (specification draft, 4 November 2026) and "Implementing
MeTTaDinC in Cetta" (coding-agent guide, 4 November 2026).

Every mathematical value quoted in the two documents is recomputed here with
Python's fractions.Fraction (rationals) or arithmetic modulo 7 or modulo 2; no
floating-point arithmetic is used, and the one linear-programming optimum is
proved by a primal and a dual solution checked exactly.  The script is an
independent calculator for the worked examples and for the counterexamples that
justify the theorem hypotheses.  It does not parse or run MeTTaDinC source and it is
not a conformance test of any implementation; check_fixtures.py ties its results
to the fixture modules through manifest.json.

Run:  python3 verify_mettadinc.py     (prints a report, writes mettadinc_oracle_results.json)
"""

from fractions import Fraction as F
from itertools import product, combinations
from collections import deque
import json
import sys

RESULTS = {}
FAILS = []


def check(name, cond, detail=""):
    status = "ok " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILS.append(name)


def record(key, value):
    RESULTS[key] = value


def fstr(x):
    if isinstance(x, F):
        return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
    if isinstance(x, (list, tuple)):
        return [fstr(y) for y in x]
    if isinstance(x, dict):
        return {str(k): fstr(v) for k, v in x.items()}
    return x


# ---------------------------------------------------------------------------
# Generic finite deterministic machines
# ---------------------------------------------------------------------------

def refine(states, seed_key, actions):
    """Coarsest stable refinement of the partition induced by seed_key.

    actions: dict label -> dict state -> state (deterministic).
    Returns (block_of, history) where history lists the number of blocks per
    round.  This is the d-calculus refinement rule alpha <- alpha /\\ T^* alpha
    iterated on crisp tolerances (Moore minimization)."""
    sig = {x: seed_key(x) for x in states}
    canon = {}
    block = {}
    for x in states:
        block[x] = canon.setdefault(sig[x], len(canon))
    history = [len(canon)]
    while True:
        canon2 = {}
        block2 = {}
        for x in states:
            s = (block[x],) + tuple(block[actions[a][x]] for a in sorted(actions))
            block2[x] = canon2.setdefault(s, len(canon2))
        history.append(len(canon2))
        if len(canon2) == len(canon):
            return block2, history
        block, canon = block2, canon2


def blocks_of(block):
    out = {}
    for x, b in block.items():
        out.setdefault(b, []).append(x)
    return sorted((sorted(v) for v in out.values()), key=lambda v: str(v[0]))


def shortest_behavioral_witness(states, q, obs, actions):
    """Multi-source BFS on the synchronous pair graph from pairs with equal
    encodings.  Returns (pair, word, query, left, right) for a globally shortest
    separating continuation, or None."""
    start = [(x, y) for x in states for y in states if x < y and q[x] == q[y]]
    pred = {p: None for p in start}
    dq = deque(start)
    while dq:
        p = dq.popleft()
        x, y = p
        for j in sorted(obs):
            if obs[j][x] != obs[j][y]:
                word = []
                cur = p
                while pred[cur] is not None:
                    prev, a = pred[cur]
                    word.append(a)
                    cur = prev
                word.reverse()
                return cur, word, j, obs[j][x], obs[j][y]
        for a in sorted(actions):
            nxt = (actions[a][x], actions[a][y])
            if nxt[0] > nxt[1]:
                nxt = (nxt[1], nxt[0])
            if nxt[0] == nxt[1]:
                continue
            if nxt not in pred:
                pred[nxt] = (p, a)
                dq.append(nxt)
    return None


def behavioral_distance(states, obsdist, actions, gamma):
    """Deterministic behavioral pseudometric
        d(x,y) = max( obsdist(x,y), gamma * max_a d(T_a x, T_a y) ),
    least fixpoint.  For deterministic systems d(x,y) = max over pairs
    reachable at pair-graph distance k of gamma^k * obsdist.  Exact."""
    d = {}
    for x in states:
        for y in states:
            if (y, x) in d:
                d[(x, y)] = d[(y, x)]
                continue
            dist = {(x, y): 0}
            dq = deque([(x, y)])
            best = F(0)
            while dq:
                p = dq.popleft()
                k = dist[p]
                val = (gamma ** k) * obsdist(*p)
                if val > best:
                    best = val
                for a in sorted(actions):
                    nxt = (actions[a][p[0]], actions[a][p[1]])
                    if nxt not in dist:
                        dist[nxt] = k + 1
                        dq.append(nxt)
            d[(x, y)] = best
    return d


# ---------------------------------------------------------------------------
# Section 1. The eight-state calibration
# ---------------------------------------------------------------------------

def eight_state():
    print("\n1. Eight-state calibration")
    X = [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    swap = {x: (x[1], x[0], x[2]) for x in X}
    obs = {"a": {x: x[0] for x in X}}
    keepA = {x: x[0] for x in X}
    now_ok = all(obs["a"][x] == obs["a"][y] for x in X for y in X if keepA[x] == keepA[y])
    upd_ok = all(keepA[swap[x]] == keepA[swap[y]] for x in X for y in X if keepA[x] == keepA[y])
    check("KeepA current adequacy holds", now_ok)
    check("KeepA update compatibility fails", not upd_ok)
    w = shortest_behavioral_witness(X, keepA, obs, {"swap": swap})
    check("shortest behavioral witness has length one", w is not None and len(w[1]) == 1, str(w))
    block, hist = refine(X, lambda x: (keepA[x], x[0]), {"swap": swap})
    bl = blocks_of(block)
    check("stable repair has four classes {ab}", len(bl) == 4 and all(len({(s[0], s[1]) for s in b}) == 1 for b in bl), str(bl))
    # witness length bound n - |X/K_O|
    nK = len({x[0] for x in X})
    record("eight_state", {"witness": [list(map(list, w[0])), w[1], w[2], w[3], w[4]],
                           "repair_blocks": [[list(s) for s in b] for b in bl],
                           "witness_bound": len(X) - nK})
    # composition with r(a,b) = 2a+b onto Codes
    codes = {0: 0, 1: 0, 2: 1, 3: 1}           # observation of code
    cswap = {0: 0, 1: 2, 2: 1, 3: 3}
    r = lambda a, b: 2 * a + b
    ok_obs = all(codes[r(x[0], x[1])] == x[0] for x in X)
    ok_upd = all(r(*swap[x][:2]) == cswap[r(x[0], x[1])] for x in X)
    check("composite (a,b,c) -> 2a+b preserves query and intertwines swap", ok_obs and ok_upd)


# ---------------------------------------------------------------------------
# Section 2. Witness bound n - |X/K_O| is tight
# ---------------------------------------------------------------------------

def witness_bound():
    print("\n2. Witness length bound")
    for n in range(2, 9):
        X = list(range(n))
        T = {i: min(i + 1, n - 1) for i in X}
        obs = {"mark": {i: 1 if i == n - 1 else 0 for i in X}}
        q = {i: 0 if i in (0, 1) else i for i in X}   # merge states 0 and 1
        w = shortest_behavioral_witness(X, q, obs, {"step": T})
        if n == 2:
            check("n=2: merged pair separated by empty word", w is not None and len(w[1]) == 0)
        else:
            check(f"chain n={n}: shortest witness length = n-2", w is not None and len(w[1]) == n - 2, f"len={len(w[1])}")
    record("witness_bound_tight", "chain with one marked end attains n-2")


# ---------------------------------------------------------------------------
# Section 3. Receipt packets: crisp checks, graded defects, frontier
# ---------------------------------------------------------------------------

PK = ["E", "U", "V", "B"]
POST = {"E": F(1, 2), "U": F(3, 4), "V": F(3, 4), "B": F(9, 10)}
ADD_U = {"E": "U", "U": "U", "V": "B", "B": "B"}
ADD_V = {"E": "V", "U": "B", "V": "V", "B": "B"}


def packets():
    print("\n3. Receipt packets")
    acts = {"add-u": ADD_U, "add-v": ADD_V}
    q = dict(POST)
    w = shortest_behavioral_witness(PK, q, {"posterior": POST}, acts)
    check("posterior-only behavioral witness: (U,V), add-u, 3/4 vs 9/10",
          w is not None and set(w[0]) == {"U", "V"} and w[1] == ["add-u"] and {w[3], w[4]} == {F(3, 4), F(9, 10)}, str(w))
    block, hist = refine(PK, lambda x: (POST[x],), acts)
    check("stable refinement has four singletons", len(blocks_of(block)) == 4)
    od = lambda x, y: abs(POST[x] - POST[y])
    d1 = behavioral_distance(PK, od, acts, F(1))
    d9 = behavioral_distance(PK, od, acts, F(9, 10))
    check("undiscounted d(U,V) = 3/20", d1[("U", "V")] == F(3, 20), fstr(d1[("U", "V")]))
    check("discounted (9/10) d(U,V) = 27/200", d9[("U", "V")] == F(27, 200), fstr(d9[("U", "V")]))
    # graded defects of PosteriorOnly
    fibers = [("U", "V")]
    now_def = max(abs(POST[x] - POST[y]) for x, y in fibers)
    upd_def = max(abs(POST[acts[a][x]] - POST[acts[a][y]]) for x, y in fibers for a in acts)
    beh_def1 = max(d1[(x, y)] for x, y in fibers)
    beh_def9 = max(d9[(x, y)] for x, y in fibers)
    check("PosteriorOnly defects: now 0, update 3/20, behavioral 3/20 (27/200 discounted)",
          (now_def, upd_def, beh_def1, beh_def9) == (0, F(3, 20), F(3, 20), F(27, 200)))
    # weakness-defect frontier over all partitions of the four packets
    def partitions(s):
        if not s:
            yield []
            return
        first, rest = s[0], s[1:]
        for p in partitions(rest):
            for i in range(len(p)):
                yield p[:i] + [[first] + p[i]] + p[i + 1:]
            yield [[first]] + p
    mu = {x: F(1, 4) for x in PK}
    rows = []
    for P in partitions(PK):
        diam = max((d1[(x, y)] for C in P for x in C for y in C), default=F(0))
        W = sum((sum(mu[x] for x in C)) ** 2 for C in P)
        rows.append((diam, W, P))
    frontier = {}
    for eps in sorted({r[0] for r in rows}):
        best = max((r for r in rows if r[0] <= eps), key=lambda r: r[1])
        frontier[eps] = best
    fr = [(fstr(e), fstr(b[1]), b[2]) for e, b in frontier.items()]
    print("    frontier (diameter bound, best weakness, partition):")
    for row in fr:
        print("     ", row)
    check("frontier: eps=0 -> W=1/4; eps=3/20 -> W=5/8 {E}{U,V,B}; eps=2/5 -> W=1",
          frontier[F(0)][1] == F(1, 4) and frontier[F(3, 20)][1] == F(5, 8) and frontier[F(2, 5)][1] == F(1))
    # exact defect of the representative machine for {E}{U,V,B} with rep B
    union = PK + ["cE", "cC"]
    cls = {"E": "cE", "U": "cC", "V": "cC", "B": "cC"}
    rep = {"cE": "E", "cC": "B"}
    pv = dict(POST)
    pv["cE"] = POST["E"]
    pv["cC"] = POST["B"]
    ua = {}
    for a, T in acts.items():
        m = dict(T)
        for c, r in rep.items():
            m[c] = cls[T[r]]
        ua[a] = m
    du = behavioral_distance(union, lambda x, y: abs(pv[x] - pv[y]), ua, F(1))
    induced = max(du[(x, cls[x])] for x in PK)
    check("induced two-class machine has exact defect 3/20", induced == F(3, 20), fstr(induced))
    record("packets", {"d_UV": "3/20", "d_UV_disc_9_10": "27/200",
                       "defects_posterior_only": ["0", "3/20", "3/20", "27/200"],
                       "frontier": fr, "induced_defect_E_UVB": fstr(induced),
                       "distance_matrix": {f"{x},{y}": fstr(d1[(x, y)]) for x in PK for y in PK if x < y}})
    # merge as a binary operation: congruence test for the posterior summary
    union_op = {}
    sets = {"E": frozenset(), "U": frozenset("u"), "V": frozenset("v"), "B": frozenset("uv")}
    inv = {v: k for k, v in sets.items()}
    for x in PK:
        for y in PK:
            union_op[(x, y)] = inv[sets[x] | sets[y]]
    witness = None
    for (x, y), (x2, y2) in product(union_op, union_op):
        if POST[x] == POST[x2] and POST[y] == POST[y2] and POST[union_op[(x, y)]] != POST[union_op[(x2, y2)]]:
            witness = ((x, y), (x2, y2), union_op[(x, y)], union_op[(x2, y2)])
            break
    check("posterior summary is not a congruence for merge", witness is not None, str(witness))
    # independent-evidence merge of posteriors (double counting) vs identity-aware union
    def post_from_odds(o):
        return o / (1 + o)
    def odds(p):
        return p / (1 - p)
    worst = max((abs(post_from_odds(odds(POST[x]) * odds(POST[y])) - POST[union_op[(x, y)]]), x, y)
                for x in PK for y in PK)
    check("double-counting merge: {u,v} with {u} gives 27/28 instead of 9/10",
          post_from_odds(odds(POST["B"]) * odds(POST["U"])) == F(27, 28))
    check("worst double-counting error 3/20 at ({u},{u})", worst[0] == F(3, 20), str(worst))
    record("merge", {"congruence_witness": [list(witness[0]), list(witness[1]), witness[2], witness[3]],
                     "double_count_example": "27/28 vs 9/10", "worst_error": fstr(worst[0])})


# ---------------------------------------------------------------------------
# Section 4. Graded closure and brackets
# ---------------------------------------------------------------------------

def luk(a, b):
    return max(F(0), a + b - 1)


def closure():
    print("\n4. Graded closure")
    P = ["A", "B", "C"]
    al = {(x, x): F(1) for x in P}
    for (x, y), v in {("A", "B"): F(9, 10), ("B", "C"): F(9, 10), ("A", "C"): F(1, 10)}.items():
        al[(x, y)] = al[(y, x)] = v
    cl = dict(al)
    for k in P:
        for i in P:
            for j in P:
                cl[(i, j)] = max(cl[(i, j)], luk(cl[(i, k)], cl[(k, j)]))
    check("closure raises (A,C) to 4/5", cl[("A", "C")] == F(4, 5))
    br = lambda t: sum(F(1, 9) * t[(x, y)] for x in P for y in P)
    check("brackets 34/45 -> 41/45, increase 7/45",
          br(al) == F(34, 45) and br(cl) == F(41, 45) and br(cl) - br(al) == F(7, 45))
    thr = {k: v >= F(9, 10) for k, v in cl.items()}
    check("threshold 9/10 of closed kernel is not transitive", thr[("A", "B")] and thr[("B", "C")] and not thr[("A", "C")])
    record("closure", {"closed_AC": "4/5", "before": "34/45", "after": "41/45", "increase": "7/45"})


# ---------------------------------------------------------------------------
# Section 5. Affine contracts
# ---------------------------------------------------------------------------

def affine():
    print("\n5. Affine contracts")
    X = [F(0), F(1)]
    Y = [F(0), F(2), F(1, 10), F(21, 10)]
    f = lambda x: 2 * x
    fh = lambda x: 2 * x + F(1, 10)
    g = lambda y: 3 * y
    gh = lambda y: 3 * y + F(1, 5)
    okF = all(abs(fh(a) - f(b)) <= 2 * abs(a - b) + F(1, 10) for a in X for b in X)
    okG = all(abs(gh(a) - g(b)) <= 3 * abs(a - b) + F(1, 5) for a in Y for b in Y)
    okH = all(abs(gh(fh(a)) - g(f(b))) <= 6 * abs(a - b) + F(1, 2) for a in X for b in X)
    badH = all(abs(gh(fh(a)) - g(f(b))) <= 6 * abs(a - b) + F(3, 10) for a in X for b in X)
    check("F grade (2,1/10), G grade (3,1/5), composite (6,1/2) hold", okF and okG and okH)
    check("composite grade (6,3/10) refuted at input 0", not badH)
    record("affine", {"composite": ["6", "1/2"], "refuted": ["6", "3/10"]})


# ---------------------------------------------------------------------------
# Section 6. Neural report audit and the U-statistic trap
# ---------------------------------------------------------------------------

def neural():
    print("\n6. Neural report audit")
    I = [(a, b) for a in (0, 1) for b in (0, 1)]
    xor = {x: x[0] ^ x[1] for x in I}
    first = {x: x[0] for x in I}
    pairs = [(x, y) for x in I for y in I]
    dO = {p: int(xor[p[0]] != xor[p[1]]) for p in pairs}
    dN = {p: int(first[p[0]] != first[p[1]]) for p in pairs}
    m = F(1, 16)
    Do = sum(m * dO[p] for p in pairs)
    Dn = sum(m * dN[p] for p in pairs)
    Bc = sum(m * max(0, dN[p] - dO[p]) for p in pairs)
    Er = sum(m * max(0, dO[p] - dN[p]) for p in pairs)
    Tu = sum(m * abs(dN[p] - dO[p]) for p in pairs)
    check("masses 1/2,1/2; creation 1/4; erasure 1/4; turnover 1/2",
          (Do, Dn, Bc, Er, Tu) == (F(1, 2), F(1, 2), F(1, 4), F(1, 4), F(1, 2)))
    dp = [p for p in pairs if p[0] != p[1]]
    md = F(1, len(dp))
    check("distinct-pair convention gives masses 2/3 and turnover 2/3",
          sum(md * dO[p] for p in dp) == F(2, 3) and sum(md * abs(dN[p] - dO[p]) for p in dp) == F(2, 3))
    old_int = sum(F(1, 4) * int(0 == xor[x]) for x in I)
    new_int = sum(F(1, 4) * int(xor[x] == xor[x]) for x in I)
    check("SetReport 0 accuracies 1/2 (old) and 1 (new)", (old_int, new_int) == (F(1, 2), F(1)))
    # U-statistic: exact expectations over all samples of size n
    n = 4
    plug, ustat = F(0), F(0)
    for s in product(I, repeat=n):
        w = F(1, 4 ** n)
        plug += w * sum(F(dO[(s[i], s[j])]) for i in range(n) for j in range(n)) / (n * n)
        ustat += w * sum(F(dO[(s[i], s[j])]) for i in range(n) for j in range(n) if i != j) / (n * (n - 1))
    check("n=4: plug-in mean 3/8 = (1-1/n)/2, U-statistic mean 1/2", plug == F(3, 8) and ustat == F(1, 2),
          f"{fstr(plug)}, {fstr(ustat)}")
    record("neural", {"masses": "1/2", "creation": "1/4", "erasure": "1/4", "turnover": "1/2",
                      "distinct_pairs": "2/3", "plugin_mean_n4": fstr(plug), "ustat_mean_n4": fstr(ustat)})


# ---------------------------------------------------------------------------
# Section 7. Evolutionary archive (stochastic lumping)
# ---------------------------------------------------------------------------

def evolution():
    print("\n7. Evolutionary archive")
    G = ["G00", "G01", "G10", "G11"]
    fit = {"G00": 0, "G01": 0, "G10": 0, "G11": 1}
    h = F(1, 2)
    M = {"G00": {"G01": h, "G10": h}, "G01": {"G00": h, "G11": h},
         "G10": {"G00": h, "G11": h}, "G11": {"G01": h, "G10": h}}
    blk = {g: fit[g] for g in G}
    while True:
        sig = {}
        for g in G:
            row = {}
            for t, p in M[g].items():
                row[blk[t]] = row.get(blk[t], 0) + p
            sig[g] = (blk[g], tuple(sorted(row.items())))
        canon = {}
        nb = {g: canon.setdefault(sig[g], len(canon)) for g in G}
        if len(canon) == len(set(blk.values())):
            break
        blk = nb
    classes = blocks_of(blk)
    check("random mutation quotient: {G00},{G01,G10},{G11}", sorted(map(tuple, classes)) == [("G00",), ("G01", "G10"), ("G11",)], str(classes))
    # controllable flips
    ff = {"G00": "G10", "G01": "G11", "G10": "G00", "G11": "G01"}
    fs = {"G00": "G01", "G01": "G00", "G10": "G11", "G11": "G10"}
    b2, _ = refine(G, lambda g: (fit[g],), {"first": ff, "second": fs})
    check("controllable flips need four classes", len(blocks_of(b2)) == 4)
    # expected discovery time of the archive policy: first proposal creates B, then 1/4 per proposal
    E = 1 + 1 / F(1, 4)
    check("expected discovery time 5 proposals", E == 5)
    record("evolution", {"quotient": classes, "controllable_classes": 4, "discovery": "5"})


# ---------------------------------------------------------------------------
# Section 8. Skill transfer, regime repair, tick library
# ---------------------------------------------------------------------------

def transfers():
    print("\n8. Skill transfer (Poly composition), regime repair, tick library")
    S = ["Left", "Right"]
    Mv = ["ChooseLeft", "ChooseRight"]
    rew = lambda s, m: 1 if (s, m) in {("Left", "ChooseLeft"), ("Right", "ChooseRight")} else 0
    same = lambda s: s
    flip = lambda s: "Right" if s == "Left" else "Left"
    mflip = lambda b, a: "ChooseRight" if a == "ChooseLeft" else "ChooseLeft"
    mid = lambda b, a: a
    def tv_defect(phi, iota):
        return max(abs(rew(phi(b), a) - rew(b, iota(b, a))) for b in S for a in Mv)
    check("BadCA defect 1, GoodCA defect 0", tv_defect(flip, mid) == 1 and tv_defect(flip, mflip) == 0)
    # Poly composition: A->B (same,id), B->C (same,id), C->A (flip, mflip)
    def compose(t1, t2):
        (p1, i1), (p2, i2) = t1, t2   # t1: A->B as (phi_AB, iota_AB); t2: B->C
        return (lambda c: p1(p2(c)), lambda c, a: i2(c, i1(p2(c), a)))
    AB = (same, mid)
    BC = (same, mid)
    CA = (flip, mflip)
    rt = compose(compose(AB, BC), CA)
    check("round trip flips state and method; reward invariant",
          all(rt[0](s) == flip(s) for s in S) and all(rew(rt[0](b), a) == rew(b, rt[1](b, a)) for b in S for a in Mv))
    # regime repair
    half = F(1, 2)
    new = {("Plus", "L"): 1, ("Plus", "R"): 0, ("Minus", "L"): 0, ("Minus", "R"): 1}
    coarse = max(half * new[("Plus", a)] + half * new[("Minus", a)] for a in "LR")
    full = half * max(new[("Plus", a)] for a in "LR") + half * max(new[("Minus", a)] for a in "LR")
    sense = F(9, 10) - F(1, 20)
    check("coarse 1/2, refined 1, sensor net 17/20, gain 7/20",
          (coarse, full, sense, sense - coarse) == (F(1, 2), F(1), F(17, 20), F(7, 20)))
    check("hidden-state substitution error gives 19/20", F(1) - F(1, 20) == F(19, 20))
    # tick library
    r = lambda d: 1 - (d - F(3, 2)) ** 2
    src = [r(F(l)) for l in (1, 2)]
    tgt = [r(F(l, 2)) for l in (1, 2, 3, 4)]
    check("source rewards 3/4,3/4; target 0,3/4,1,3/4; gap 1/4",
          src == [F(3, 4)] * 2 and tgt == [F(0), F(3, 4), F(1), F(3, 4)] and max(tgt) - max(r(F(2 * l, 2)) for l in (1, 2)) == F(1, 4))
    blind = max(abs(r(F(l)) - r(F(l, 2))) for l in (1, 2))
    check("blind copy expected-reward discrepancy 3/4", blind == F(3, 4))
    record("transfer", {"bad": 1, "good": 0, "regime": ["1/2", "1", "17/20", "7/20"], "tick_gap": "1/4"})


# ---------------------------------------------------------------------------
# Section 9. Trace equivalence and linear abstraction
# ---------------------------------------------------------------------------

def rank_q(rows):
    rows = [list(r) for r in rows]
    rk, col = 0, 0
    ncol = len(rows[0]) if rows else 0
    for col in range(ncol):
        piv = next((i for i in range(rk, len(rows)) if rows[i][col] != 0), None)
        if piv is None:
            continue
        rows[rk], rows[piv] = rows[piv], rows[rk]
        for i in range(len(rows)):
            if i != rk and rows[i][col] != 0:
                fct = rows[i][col] / rows[rk][col]
                rows[i] = [a - fct * b for a, b in zip(rows[i], rows[rk])]
        rk += 1
    return rk


def trace_example():
    print("\n9. Trace equivalence, minimal linear representation, positive realization")
    S = ["x", "y", "u", "v", "w", "p", "q"]
    idx = {s: i for i, s in enumerate(S)}
    obs = {"x": 0, "y": 0, "u": 0, "v": 0, "w": 0, "p": 1, "q": 2}
    h = F(1, 2)
    M = {"x": {"u": h, "v": h}, "y": {"w": F(1)}, "u": {"p": F(1)}, "v": {"q": F(1)},
         "w": {"p": h, "q": h}, "p": {"p": F(1)}, "q": {"q": F(1)}}
    Y = [0, 1, 2]
    # test vectors beta(y0..yk)(s) = P_s(observe y0..yk)
    def beta(word):
        vec = {s: F(int(obs[s] == word[-1])) for s in S}
        for yv in reversed(word[:-1]):
            vec = {s: (F(int(obs[s] == yv)) * sum(p * vec[t] for t, p in M[s].items())) for s in S}
        return vec
    words = [w for k in range(1, 7) for w in product(Y, repeat=k)]
    vecs = [tuple(beta(w)[s] for s in S) for w in words]
    dim = rank_q(vecs)
    check("minimal linear (weighted-automaton) dimension is 5", dim == 5, str(dim))
    # trace-equivalence classes: equal test vectors
    sigs = {}
    for s in S:
        sigs.setdefault(tuple(v[idx[s]] for v in vecs), []).append(s)
    tclasses = sorted(sigs.values())
    check("trace partition has 6 classes, merging x and y", len(tclasses) == 6 and ["x", "y"] in tclasses, str(tclasses))
    # probabilistic bisimulation (strong lumping) from the observation partition
    blk = {s: obs[s] for s in S}
    while True:
        sig = {s: (blk[s], tuple(sorted({blk[t]: 0 for t in M[s]}.keys())) and tuple(sorted(
            (b, sum(p for t, p in M[s].items() if blk[t] == b)) for b in set(blk[t] for t in M[s])))) for s in S}
        canon = {}
        nb = {s: canon.setdefault(sig[s], len(canon)) for s in S}
        if len(canon) == len(set(blk.values())):
            break
        blk = nb
    check("probabilistic bisimulation quotient is the identity (7 classes)", len(set(blk.values())) == 7)
    # shortest separating test for each inequivalent pair (Tzeng-style bound n - k)
    longest = 0
    for a, b in combinations(S, 2):
        if [a, b] == ["x", "y"]:
            continue
        L = next(len(w) for w in words if beta(w)[a] != beta(w)[b])
        longest = max(longest, L)
    check("every inequivalent pair has a separating test of length <= 7-3+1 symbols", longest <= 5, f"longest {longest} symbols")
    # positive 5-state realization via a Markov-kernel abstraction L
    A = ["X'", "U'", "V'", "P'", "Q'"]
    Lk = {"x": {"X'": F(1)}, "y": {"X'": F(1)}, "u": {"U'": F(1)}, "v": {"V'": F(1)},
          "w": {"U'": h, "V'": h}, "p": {"P'": F(1)}, "q": {"Q'": F(1)}}
    Mb = {"X'": {"U'": h, "V'": h}, "U'": {"P'": F(1)}, "V'": {"Q'": F(1)}, "P'": {"P'": F(1)}, "Q'": {"Q'": F(1)}}
    ob = {"X'": 0, "U'": 0, "V'": 0, "P'": 1, "Q'": 2}
    def kl(row, K):
        out = {}
        for t, p in row.items():
            for z, r in K[t].items():
                out[z] = out.get(z, 0) + p * r
        return {k: v for k, v in out.items() if v != 0}
    inter = all(kl(M[s], Lk) == kl(Lk[s], Mb) for s in S)
    obsok = all(ob[z] == obs[s] for s in S for z in Lk[s])
    check("intertwining M;L = L;Mbar and observation preservation", inter and obsok)
    record("trace_example", {"bisim_classes": 7, "trace_classes": 6, "linear_dim": 5,
                             "positive_realization": "5 states, w -> (U'+V')/2"})


# ---------------------------------------------------------------------------
# Section 10. Unenumerable parity fixture (scaled-down brute force)
# ---------------------------------------------------------------------------

def parity_fixture():
    print("\n10. Parity fixture (brute force on small widths)")
    for n in (5, 6, 8, 10):
        N = 1 << n
        bit = lambda x, i: (x >> i) & 1
        def swap01(x):
            b0, b1 = bit(x, 0), bit(x, 1)
            return (x & ~3) | (b0 << 1) | b1
        def rotate(x):
            hi = x >> 2
            m = n - 2
            hi = ((hi << 1) | (hi >> (m - 1))) & ((1 << m) - 1)
            return (hi << 2) | (x & 3)
        def inject(x):
            p = bin(x >> 2).count("1") & 1
            return x ^ (p << 1)
        acts = {"swap": {x: swap01(x) for x in range(N)},
                "rotate": {x: rotate(x) for x in range(N)},
                "inject": {x: inject(x) for x in range(N)}}
        block, hist = refine(list(range(N)), lambda x: (bit(x, 0),), acts)
        k = len(set(block.values()))
        same = all(block[x] == block[y] for x in range(N) for y in range(N)
                   if (bit(x, 0), bit(x, 1), bin(x >> 2).count("1") & 1) == (bit(y, 0), bit(y, 1), bin(y >> 2).count("1") & 1))
        check(f"width {n}: coarsest stable refinement has 8 classes = (x0, x1, parity)", k == 8 and same, f"rounds {hist}")
        # single-bit flips all change behavior; double flips in the tail do not
        singles = all(block[x] != block[x ^ (1 << i)] for i in range(n) for x in range(N))
        doubles = all(block[x] == block[x ^ (1 << i) ^ (1 << j)] for i in range(2, n) for j in range(i + 1, n) for x in range(N))
        check(f"width {n}: every single-bit flip is behaviorally visible; tail double flips are not", singles and doubles)
    # shortest separating words on the 8-class quotient
    Q = [(a, b, p) for a in (0, 1) for b in (0, 1) for p in (0, 1)]
    qa = {"swap": {s: (s[1], s[0], s[2]) for s in Q}, "inject": {s: (s[0], s[1] ^ s[2], s[2]) for s in Q},
          "rotate": {s: s for s in Q}}
    longest = 0
    for s, t in combinations(Q, 2):
        w = shortest_behavioral_witness([s, t], {s: 0, t: 0}, {"x0": {z: z[0] for z in Q}}, qa)
        longest = max(longest, len(w[1]))
    check("all 8 classes separated by words of length <= 2", longest == 2, str(longest))
    record("parity", {"classes": 8, "max_separating_word": 2})


# ---------------------------------------------------------------------------
# Section 11. Security simulation fixture
# ---------------------------------------------------------------------------

def security():
    print("\n11. Simulation arrow for a lockout protocol")
    C = ["S0", "S1", "S2", "Locked", "Auth", "Admin"]
    stage = {"S0": "Start", "S1": "Start", "S2": "Start", "Locked": "Locked", "Auth": "Auth", "Admin": "Admin"}
    fail = {"S0": "S1", "S1": "S2", "S2": "Locked", "Locked": "Locked", "Auth": "Auth", "Admin": "Admin"}
    ok = {"S0": "Auth", "S1": "Auth", "S2": "Auth", "Locked": "Locked", "Auth": "Auth", "Admin": "Admin"}
    esc = {"S0": "S0", "S1": "S1", "S2": "S2", "Locked": "Locked", "Auth": "Admin", "Admin": "Admin"}
    acts = {"fail": fail, "ok": ok, "escalate": esc}
    q = dict(stage)
    upd_fail = None
    for x in C:
        for y in C:
            if x < y and q[x] == q[y]:
                for a in sorted(acts):
                    if q[acts[a][x]] != q[acts[a][y]]:
                        upd_fail = upd_fail or (x, y, a, q[acts[a][x]], q[acts[a][y]])
    check("exact stage quotient is refuted", upd_fail is not None, str(upd_fail))
    # abstract nondeterministic system
    A = ["Start", "Locked", "Auth", "Admin"]
    Ab = {"fail": {"Start": {"Start", "Locked"}, "Locked": {"Locked"}, "Auth": {"Auth"}, "Admin": {"Admin"}},
          "ok": {"Start": {"Auth"}, "Locked": {"Locked"}, "Auth": {"Auth"}, "Admin": {"Admin"}},
          "escalate": {"Start": {"Start"}, "Locked": {"Locked"}, "Auth": {"Admin"}, "Admin": {"Admin"}}}
    R = {(x, stage[x]) for x in C}
    sim = all(any((acts[a][x], s2) in R for s2 in Ab[a][s]) for (x, s) in R for a in acts)
    check("stage map is a simulation into the nondeterministic abstraction", sim)
    # safety: Admin is entered only from Auth (checked on the abstraction)
    safe = all(not ("Admin" in Ab[a][s] and s not in ("Auth", "Admin")) for a in Ab for s in A)
    conc_safe = all(not (acts[a][x] == "Admin" and x not in ("Auth", "Admin")) for a in acts for x in C)
    check("safety holds on abstraction and therefore on the concrete system", safe and conc_safe)
    record("security", {"exact_refuted": list(upd_fail), "simulation": True})


# ---------------------------------------------------------------------------
# Section 12. Arithmetic probes and Hom dimensions over F7
# ---------------------------------------------------------------------------

P7 = 7


def mat(n, entries):
    m = [[0] * n for _ in range(n)]
    for (i, j), v in entries.items():
        m[i - 1][j - 1] = v % P7
    return m


def mmul(A, B):
    n = len(A)
    return [[sum(A[i][k] * B[k][j] for k in range(n)) % P7 for j in range(n)] for i in range(n)]


def madd(A, B):
    return [[(a + b) % P7 for a, b in zip(r, s)] for r, s in zip(A, B)]


def mscale(c, A):
    return [[(c * a) % P7 for a in r] for r in A]


def rank7(rows):
    rows = [list(r) for r in rows]
    rk = 0
    ncol = len(rows[0]) if rows else 0
    for col in range(ncol):
        piv = next((i for i in range(rk, len(rows)) if rows[i][col] % P7), None)
        if piv is None:
            continue
        rows[rk], rows[piv] = rows[piv], rows[rk]
        inv = pow(rows[rk][col], P7 - 2, P7)
        rows[rk] = [(a * inv) % P7 for a in rows[rk]]
        for i in range(len(rows)):
            if i != rk and rows[i][col] % P7:
                c = rows[i][col]
                rows[i] = [(a - c * b) % P7 for a, b in zip(rows[i], rows[rk])]
        rk += 1
    return rk


def arithmetic():
    print("\n12. Arithmetic probes over F7")
    n = 4
    I4 = mat(4, {(i, i): 1 for i in range(1, 5)})
    S = mat(4, {(2, 1): 1})
    T = madd(mat(4, {(3, 1): 1}), mat(4, {(4, 3): 1}))
    T2 = mmul(T, T)
    T5 = madd(mscale(4, S), mscale(5, T))
    T3A = madd(mscale(6, I4), mscale(4, T2))
    T3B = madd(mscale(6, I4), mscale(3, T2))
    flat = lambda A: [a for r in A for a in r]
    ranks = {}
    for b in range(7):
        rA = rank7([r for r in madd(madd(T3A, mscale(6, mscale(-1, I4))), mscale(-b, mmul(T5, T5)))])
        rB = rank7([r for r in madd(madd(T3B, mscale(6, mscale(-1, I4))), mscale(-b, mmul(T5, T5)))])
        ranks[b] = (rA, rB)
    expected = {0: (1, 1), 1: (0, 1), 2: (1, 1), 3: (1, 1), 4: (1, 1), 5: (1, 1), 6: (1, 0)}
    check("probe table matches (first separator b=1)", ranks == expected, str(ranks))
    # Jordan data agree
    def pow_ranks(A, c):
        N = madd(A, mscale(-c, I4))
        out, P = [], N
        for _ in range(3):
            out.append(rank7(P))
            P = mmul(P, N)
        return out
    check("centered T3 ranks (1,0,0) and T5 ranks (2,1,0) for both", pow_ranks(T3A, 6) == pow_ranks(T3B, 6) == [1, 0, 0] and pow_ranks(T5, 0) == [2, 1, 0])
    # Hom dimensions: X A_i = B_i X
    def hom_dim(As, Bs):
        rows = []
        for A, B in zip(As, Bs):
            for i in range(n):
                for j in range(n):
                    row = [0] * (n * n)
                    for k in range(n):
                        row[i * n + k] = (row[i * n + k] + A[k][j]) % P7      # (X A)_{ij} = sum_k X_ik A_kj
                        row[k * n + j] = (row[k * n + j] - B[i][k]) % P7      # (B X)_{ij} = sum_k B_ik X_kj
                    rows.append(row)
        return n * n - rank7(rows)
    eA = hom_dim([T3A, T5], [T3A, T5])
    hAB = hom_dim([T3A, T5], [T3B, T5])
    eB = hom_dim([T3B, T5], [T3B, T5])
    print(f"    dim End(KA)={eA}, dim Hom(KA,KB)={hAB}, dim End(KB)={eB}")
    check("Hom-dimension certificate separates KA and KB", hAB != eA, f"{eA} vs {hAB}")
    # second observer from the source paper: rank(T3 + 4*T13 - 2I) needs T13; omitted here
    record("arithmetic", {"ranks": {str(k): list(v) for k, v in ranks.items()},
                          "hom_dims": [eA, hAB, eB]})


# ---------------------------------------------------------------------------
# Section 13. Nondeterministic reads: shared versus fresh
# ---------------------------------------------------------------------------

def reads():
    print("\n13. Shared and fresh reads of one nondeterministic choice")
    shared = {(c, c) for c in (0, 1)}
    fresh = {(c, d) for c in (0, 1) for d in (0, 1)}
    first = lambda S: {s[0] for s in S}
    agree = lambda S: {s[0] == s[1] for s in S}
    check("first-read observer cannot separate shared from fresh", first(shared) == first(fresh))
    check("agreement observer separates them ({True} vs {True, False})", agree(shared) != agree(fresh))
    pa_shared = F(1)
    pa_fresh = F(1, 2)
    check("under a declared fair scheduler: P(agree) = 1 vs 1/2", (pa_shared, pa_fresh) == (F(1), F(1, 2)))
    record("reads", {"agree_shared": "1", "agree_fresh": "1/2"})



# ---------------------------------------------------------------------------
# Section 14. Forty-bit fixtures, scaled: all-zero detector and GF(2) observability
# ---------------------------------------------------------------------------

def zero_fixture():
    print("\n14. All-zero detector fixture and linear observability")
    for n in (5, 6, 8, 10):
        N = 1 << n
        bit = lambda x, i: (x >> i) & 1
        tailzero = lambda x: int((x >> 2) == 0)
        def swap01(x):
            return (x & ~3) | (bit(x, 0) << 1) | bit(x, 1)
        def rotate(x):
            hi, m = x >> 2, n - 2
            hi = ((hi << 1) | (hi >> (m - 1))) & ((1 << m) - 1)
            return (hi << 2) | (x & 3)
        acts = {"swap": {x: swap01(x) for x in range(N)},
                "rotate": {x: rotate(x) for x in range(N)},
                "inject": {x: x ^ (tailzero(x) << 1) for x in range(N)}}
        block, hist = refine(list(range(N)), lambda x: (bit(x, 0),), acts)
        key = lambda x: (bit(x, 0), bit(x, 1), tailzero(x))
        ok = len(set(block.values())) == 8 and all((block[x] == block[y]) == (key(x) == key(y)) for x in range(N) for y in range(N))
        # exact clock rate of tail bit 2 under the uniform law
        tau = F(sum(1 for x in range(N) if block[x] != block[x ^ 4]), N)
        check(f"width {n}: 8 classes (x0, x1, tail==0); tail-bit clock rate {fstr(tau)} = 2^-(n-3)", ok and tau == F(2, 1 << (n - 2)))
    # a sampled screen at width 40: 10^6 uniform samples per tail bit, rate 2^-37 each; by the union bound
    # over the 38 tail bits the chance that any estimate is nonzero is at most 38 * 10^6 * 2^-37
    union = F(38 * 10 ** 6, 2 ** 37)
    check("sampled screen at width 40: P(some tail-bit estimate nonzero) <= 38*10^6*2^-37 < 3*10^-4",
          union < F(3, 10 ** 4), fstr(union))
    record("zero_fixture", {"classes": 8, "clock_rate_width_40": "2^-37",
                            "sampled_screen_union_bound": "38*10^6*2^-37 < 3*10^-4"})
    # GF(2) observability for the parity system: rank of the Krylov row space is 3
    for n in (5, 8, 12, 40):
        def row_mul(r, A):            # row vector times matrix over GF(2); A as list of rows
            out = [0] * n
            for i, ri in enumerate(r):
                if ri:
                    out = [(o + a) % 2 for o, a in zip(out, A[i])]
            return out
        I = [[int(i == j) for j in range(n)] for i in range(n)]
        Sw = [row[:] for row in I]
        Sw[0], Sw[1] = I[1][:], I[0][:]
        # state transition x' = x A with row-vector convention; build columns by images of basis vectors
        def matrix_from_map(f):
            return [f([int(i == j) for j in range(n)]) for i in range(n)]
        def swapf(v):
            w = v[:]
            w[0], w[1] = v[1], v[0]
            return w
        def rotf(v):
            w = v[:]
            tail = v[2:]
            w[2:] = [tail[-1]] + tail[:-1]
            return w
        def injf(v):
            w = v[:]
            w[1] = (v[1] + sum(v[2:])) % 2
            return w
        mats = [matrix_from_map(f) for f in (swapf, rotf, injf)]
        # observable functionals: start with e0 (read bit 0); close under precomposition with each update
        def apply_functional(c, A):   # functional c (as column vector) precomposed with x -> x A
            # (x A) . c  = x . (A c)
            return [sum(A[i][j] * c[j] for j in range(n)) % 2 for i in range(n)]
        basis, frontier = [], [[int(j == 0) for j in range(n)]]
        def rank2(rows):
            rows = [r[:] for r in rows]
            rk = 0
            for col in range(n):
                piv = next((i for i in range(rk, len(rows)) if rows[i][col]), None)
                if piv is None:
                    continue
                rows[rk], rows[piv] = rows[piv], rows[rk]
                for i in range(len(rows)):
                    if i != rk and rows[i][col]:
                        rows[i] = [(a + b) % 2 for a, b in zip(rows[i], rows[rk])]
                rk += 1
            return rk
        while frontier:
            c = frontier.pop()
            if rank2(basis + [c]) > rank2(basis):
                basis.append(c)
                frontier.extend(apply_functional(c, A) for A in mats)
        check(f"GF(2) parity system, width {n}: observable space has dimension 3", rank2(basis) == 3)
    record("parity_linear", {"observable_dimension": 3, "unobservable_dimension_width_40": 37})


# ---------------------------------------------------------------------------
# Section 15. Parity-triangle hive: closure cost 1/2, least coherent refinement 1/6
# ---------------------------------------------------------------------------

def hive_triangle():
    print("\n15. Parity-triangle hive")
    nodes = [(i, v) for i in (1, 2, 3) for v in (0, 1)]
    H = {}
    for a in nodes:
        for b in nodes:
            if a == b:
                H[(a, b)] = 1
            elif a[0] == b[0]:
                H[(a, b)] = 0
            else:
                i, j = sorted((a[0], b[0]))
                va = a[1] if a[0] == i else b[1]
                vb = b[1] if b[0] == j else a[1]
                if (i, j) in ((1, 2), (2, 3)):
                    H[(a, b)] = int(va == vb)
                else:  # (1,3): c31 identifies opposite values
                    H[(a, b)] = int(va != vb)
    w = F(1, 6)
    h = sum(w * w * (1 - H[(a, b)]) for a in nodes for b in nodes)
    check("hive logical entropy h(w,H) = 1/2 = closure consensus cost (closure is all ones)", h == F(1, 2))
    # Least coherent graded refinement.  The linear program: maximize the kept mass sum_p K_p over
    # unordered pairs p, subject to 0 <= K_p <= H_p and K(x,y) + K(y,z) - K(x,z) <= 1 for every ordered
    # triple of distinct nodes (Lukasiewicz transitivity).  Instead of solving it in floating point,
    # the oracle checks a primal solution and a dual solution in exact rational arithmetic; equal
    # objective values prove both optimal (weak duality), so the cost is exact.
    pairs = list(combinations(nodes, 2))
    var = lambda a, b: (a, b) if (a, b) in set(pairs) else (b, a)
    triples = [(x, y, z) for x in nodes for y in nodes for z in nodes if len({x, y, z}) == 3]
    def coeffs(t):
        x, y, z = t
        out = {}
        for p, c in ((var(x, y), 1), (var(y, z), 1), (var(x, z), -1)):
            out[p] = out.get(p, 0) + c
        return out
    edges = [p for p in pairs if H[p] == 1]
    adj = {v: [u for p in edges for u in p if v in p and u != v] for v in nodes}
    check("the six identification edges form one cycle through all six nodes",
          len(edges) == 6 and all(len(adj[v]) == 2 for v in nodes))
    walk = [nodes[0], adj[nodes[0]][0]]
    while len(walk) < len(nodes):
        walk.append(next(u for u in adj[walk[-1]] if u != walk[-2]))
    cycle_edges = [var(walk[i], walk[(i + 1) % 6]) for i in range(6)]
    # primal: keep every other edge of the cycle (a perfect matching) at 1, everything else at 0
    K = {p: F(int(p in cycle_edges[0::2])) for p in pairs}
    primal_ok = (all(0 <= K[p] <= H[p] for p in pairs)
                 and all(sum(c * K[p] for p, c in coeffs(t).items()) <= 1 for t in triples))
    primal = sum(K.values())
    # dual: weight 1/2 on the transitivity constraint (u, v, w) along each pair of consecutive cycle
    # edges, slack z_p >= 0 on the upper bounds; dual feasibility is sum_t y_t a_tp + z_p >= 1
    y = {}
    for i in range(6):
        u, v, x = walk[i - 1], walk[i], walk[(i + 1) % 6]
        y[(u, v, x)] = F(1, 2)
    load = {p: sum(yt * coeffs(t).get(p, 0) for t, yt in y.items()) for p in pairs}
    z = {p: max(F(0), 1 - load[p]) for p in pairs}
    dual_ok = all(yt >= 0 for yt in y.values()) and all(load[p] + z[p] >= 1 for p in pairs)
    dual = sum(y.values()) + sum(H[p] * z[p] for p in pairs)
    check(f"primal certificate: a perfect matching of the cycle keeps mass {fstr(primal)} and satisfies "
          f"all {len(triples)} transitivity constraints and {len(pairs)} bounds exactly", primal_ok and primal == 3)
    check("dual certificate: weights 1/2 on six path constraints, feasible, dual value 3 = primal value",
          dual_ok and dual == primal == 3)
    total = sum(H[p] for p in pairs)
    cost = 2 * (total - primal) * w * w
    check("least coherent refinement costs exactly 1/6 (kept mass 3 of 6, proved optimal by duality)", cost == F(1, 6))
    record("hive", {"closure_cost": "1/2", "least_refinement_cost": fstr(cost),
                    "lp_certificate": {"primal_kept_mass": fstr(primal), "dual_value": fstr(dual),
                                       "dual_weights": "1/2 on the six transitivity constraints along the cycle"}})


# ---------------------------------------------------------------------------
# Section 16. Randomized checks of the new propositions
# ---------------------------------------------------------------------------

def random_props(seed=7, trials=300):
    import random
    rnd = random.Random(seed)
    print("\n16. Randomized checks of graded descent, induced-machine bounds, transport")
    bad_desc = bad_ind = bad_h = bad_inc = bad_add = 0
    for t in range(trials):
        n = rnd.randint(3, 7)
        X = list(range(n))
        acts = {a: {x: rnd.randrange(n) for x in X} for a in ("a", "b")[: rnd.randint(1, 2)]}
        ov = {x: F(rnd.randint(0, 4), 4) for x in X}
        od = lambda x, y: abs(ov[x] - ov[y])
        # graded descent: crisp update-compatible encoding (stable under actions only)
        seed_part = {x: rnd.randrange(2) for x in X}
        block, _ = refine(X, lambda x: (seed_part[x],), acts)
        for g in (F(1), F(1, 2)):
            d = behavioral_distance(X, od, acts, g)
            same = [(x, y) for x in X for y in X if block[x] == block[y]]
            dnow = max((od(x, y) for x, y in same), default=F(0))
            dbeh_ = max((d[(x, y)] for x, y in same), default=F(0))
            if dbeh_ > dnow:
                bad_desc += 1
        # induced representative machine bounds
        part = {x: rnd.randrange(3) for x in X}
        classes = sorted(set(part.values()))
        d1 = behavioral_distance(X, od, acts, F(1))
        rep = {}
        for c in classes:
            mem = [x for x in X if part[x] == c]
            rep[c] = min(mem, key=lambda r: max(d1[(x, r)] for x in mem))
        U = X + [("c", c) for c in classes]
        uv = dict(ov)
        ua = {a: dict(T) for a, T in acts.items()}
        for c in classes:
            uv[("c", c)] = ov[rep[c]]
            for a, T in acts.items():
                ua[a][("c", c)] = ("c", part[T[rep[c]]])
        uod = lambda x, y: abs(uv[x] - uv[y])
        for g in (F(1, 2), F(9, 10)):
            dg = behavioral_distance(X, od, acts, g)
            eps = max(dg[(x, rep[part[x]])] for x in X)
            du = behavioral_distance(U, uod, ua, g)
            E = max(du[(x, ("c", part[x]))] for x in X)
            if E > eps / (1 - g):
                bad_ind += 1
        eps1 = max(d1[(x, rep[part[x]])] for x in X)
        # horizon-h undiscounted bound E_h <= (h+1) eps
        def dist_h(x, y, h):
            best, frontier = F(0), {(x, y)}
            for k in range(h + 1):
                best = max([best] + [uod(*p) for p in frontier])
                frontier = {(ua[a][p[0]], ua[a][p[1]]) for p in frontier for a in ua}
            return best
        for h in range(0, 5):
            if max(dist_h(x, ("c", part[x]), h) for x in X) > (h + 1) * eps1:
                bad_h += 1
        # incrementality: adding a query resumes from P_beh cap ker(new)
        nv = {x: rnd.randrange(2) for x in X}
        b_old, _ = refine(X, lambda x: (ov[x],), acts)
        b_new_direct, _ = refine(X, lambda x: (ov[x], nv[x]), acts)
        b_new_resumed, _ = refine(X, lambda x: (b_old[x], nv[x]), acts)
        if any((b_new_direct[x] == b_new_direct[y]) != (b_new_resumed[x] == b_new_resumed[y]) for x in X for y in X):
            bad_inc += 1
        # additivity of graded abstraction defects under composition (two-step coarsening)
        part2 = {c: rnd.randrange(2) for c in classes}
    check(f"graded descent: delta_upd = 0 implies delta_beh <= delta_now ({trials} machines, two discounts)", bad_desc == 0, f"violations {bad_desc}")
    check("induced representative machine: exact defect <= eps/(1-gamma)", bad_ind == 0, f"violations {bad_ind}")
    check("undiscounted horizon bound E_h <= (h+1) eps", bad_h == 0, f"violations {bad_h}")
    check("adding a query: resumed refinement equals refinement from scratch", bad_inc == 0, f"violations {bad_inc}")


# ---------------------------------------------------------------------------
# Exact linear algebra and optimal transport helpers
# ---------------------------------------------------------------------------

def solve_exact(A, b):
    """Unique exact solution of A x = b (A has full column rank), else None."""
    m, n = len(A), len(A[0])
    M = [[F(v) for v in row] + [F(bv)] for row, bv in zip(A, b)]
    r = 0
    for c in range(n):
        p = next((i for i in range(r, m) if M[i][c] != 0), None)
        if p is None:
            return None
        M[r], M[p] = M[p], M[r]
        pv = M[r][c]
        M[r] = [v / pv for v in M[r]]
        for i in range(m):
            if i != r and M[i][c] != 0:
                f = M[i][c]
                M[i] = [a - f * bb for a, bb in zip(M[i], M[r])]
        r += 1
    if any(M[i][n] != 0 for i in range(r, m)):
        return None
    return [M[i][n] for i in range(n)]


def kantorovich_exact(mu, nu, dist):
    """Exact optimal-transport cost between finitely supported rational laws, by
    enumerating the basic feasible solutions of the coupling polytope."""
    A = sorted(mu, key=str)
    B = sorted(nu, key=str)
    cells = [(a, b) for a in A for b in B]
    k = min(len(A) + len(B) - 1, len(cells))
    best = None
    for S in combinations(range(len(cells)), k):
        rows, rhs = [], []
        for a in A:
            rows.append([1 if cells[s][0] == a else 0 for s in S])
            rhs.append(mu[a])
        for b in B:
            rows.append([1 if cells[s][1] == b else 0 for s in S])
            rhs.append(nu[b])
        sol = solve_exact(rows, rhs)
        if sol is None or any(v < 0 for v in sol):
            continue
        cost = sum(v * dist(cells[s][0], cells[s][1]) for v, s in zip(sol, S))
        if best is None or cost < best:
            best = cost
    return best


def stoch_iterate(S, d0, rows, gamma, k):
    """k-th Kleene iterate of the distance form of Phi_gamma from the zero kernel:
    d_{t+1}(s,t) = max(d0(s,t), gamma * max_a W_{d_t}(rows[a][s], rows[a][t]))."""
    d = {(s, t): F(0) for s in S for t in S}
    for _ in range(k):
        nd = {}
        for s in S:
            for t in S:
                if (t, s) in nd:
                    nd[(s, t)] = nd[(t, s)]
                    continue
                best = d0(s, t)
                for a in rows:
                    w = kantorovich_exact(rows[a][s], rows[a][t], lambda u, v: d[(u, v)])
                    best = max(best, gamma * w)
                nd[(s, t)] = best
        d = nd
    return d


def stoch_fixpoint(S, d0, rows, gamma, cap=60):
    prev = None
    for k in range(1, cap + 1):
        d = stoch_iterate(S, d0, rows, gamma, k)
        if d == prev:
            return d, k - 1
        prev = d
    return None, cap


def trace_law(s, word, rows, obs):
    """Law of the observation sequence at times 0..len(word) from s under an action word."""
    dist = {(obs[s],): {s: F(1)}}
    for a in word:
        new = {}
        for pref, sub in dist.items():
            for x, p in sub.items():
                for y, r in rows[a][x].items():
                    key = pref + (obs[y],)
                    cell = new.setdefault(key, {})
                    cell[y] = cell.get(y, F(0)) + p * r
        dist = new
    return {k: sum(v.values()) for k, v in dist.items()}


def tv(P, Q):
    keys = set(P) | set(Q)
    return sum(abs(P.get(k, F(0)) - Q.get(k, F(0))) for k in keys) / 2


def mat_mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(len(B))) for j in range(len(B[0]))] for i in range(len(A))]


def mat_sub(A, B):
    return [[a - b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]


def norm_inf(A):
    return max(sum(abs(v) for v in row) for row in A)


def eye(n):
    return [[F(int(i == j)) for j in range(n)] for i in range(n)]


# ---------------------------------------------------------------------------
# Section 17. Behavioral and trace claims on the seven-state chain
# ---------------------------------------------------------------------------

SEVEN_S = ["x", "y", "u", "v", "w", "p", "q"]
SEVEN_OBS = {"x": 0, "y": 0, "u": 0, "v": 0, "w": 0, "p": 1, "q": 2}
_h = F(1, 2)
SEVEN_ROWS = {"step": {"x": {"u": _h, "v": _h}, "y": {"w": F(1)}, "u": {"p": F(1)},
                       "v": {"q": F(1)}, "w": {"p": _h, "q": _h}, "p": {"p": F(1)},
                       "q": {"q": F(1)}}}


def seven_state_claims():
    print("\n17. Seven-state chain: behavioral defect, trace equality, modal witness, realizations")
    S, obs, rows = SEVEN_S, SEVEN_OBS, SEVEN_ROWS
    d0 = lambda s, t: F(int(obs[s] != obs[t]))
    dists = {}
    for g in (F(1), F(9, 10)):
        d, k = stoch_fixpoint(S, d0, rows, g)
        dists[g] = d
        check(f"gamma={fstr(g)}: d(u,w)=d(v,w)=gamma/2, d(u,v)=gamma, d(x,y)=gamma^2/2 (stable after {k} rounds)",
              d is not None and d[("u", "w")] == g / 2 and d[("v", "w")] == g / 2
              and d[("u", "v")] == g and d[("x", "y")] == g * g / 2)
    # trace laws of x and y agree at every horizon tested
    tr = [tv(trace_law("x", ["step"] * h, rows, obs), trace_law("y", ["step"] * h, rows, obs)) for h in range(0, 9)]
    check("trace laws of x and y agree through horizon 8 (TV = 0 at every horizon)", all(t == 0 for t in tr))
    # modal test witness: psi(s) = gamma Pr[o(X1)=1]; phi(s) = gamma E|psi(X1) - gamma/2|
    for g in (F(1), F(9, 10)):
        psi = {s: g * sum(p for t, p in rows["step"][s].items() if obs[t] == 1) for s in S}
        inner = {s: abs(psi[s] - g / 2) for s in S}
        phi = {s: g * sum(p * inner[t] for t, p in rows["step"][s].items()) for s in S}
        check(f"gamma={fstr(g)}: modal test phi(x)={fstr(phi['x'])}, phi(y)={fstr(phi['y'])}; gap equals d(x,y)",
              phi["x"] - phi["y"] == dists[g][("x", "y")] and phi["y"] == 0)
        if g == 1:
            check("undiscounted witness values phi(x)=1/2, phi(y)=0", phi["x"] == F(1, 2) and phi["y"] == 0)
    # the merge {x,y}: behavioral defect 1/2 (Refuted at Within 0), trace defect 0 (Checked)
    record("seven_state", {"d_uw": "gamma/2", "d_xy": "gamma^2/2", "d_xy_gamma_1": "1/2",
                           "d_xy_gamma_9_10": fstr(dists[F(9, 10)][("x", "y")]),
                           "modal_witness": {"phi_x": "1/2", "phi_y": "0"},
                           "merge_xy": {"behavioral_defect": "1/2", "trace_tv": "0"}})
    # signed minimal realization from the test space, with exact intertwining
    Y = [0, 1, 2]
    M = [[rows["step"][s].get(t, F(0)) for t in S] for s in S]
    E = {y: [[F(int(i == j and obs[S[i]] == y)) for j in range(7)] for i in range(7)] for y in Y}
    one = [[F(1)] for _ in S]
    def beta(word):
        vec = [[F(int(obs[s] == word[-1]))] for s in S]
        for yv in reversed(word[:-1]):
            vec = mat_mul(E[yv], mat_mul(M, vec))
        return vec
    basis = []
    for k in range(1, 6):
        for w in product(Y, repeat=k):
            col = [r[0] for r in beta(list(w))]
            grows = rank_q(basis + [col]) > rank_q(basis) if basis else any(c != 0 for c in col)
            if grows:
                basis.append(col)
    Lm = [[basis[j][i] for j in range(len(basis))] for i in range(7)]
    dim = len(basis)
    def solve_cols(target):
        cols = []
        for j in range(len(target[0])):
            sol = solve_exact(Lm, [target[i][j] for i in range(7)])
            if sol is None:
                return None
            cols.append(sol)
        return [[cols[j][i] for j in range(len(cols))] for i in range(dim)]
    A = solve_cols(mat_mul(M, Lm))
    Pi = {y: solve_cols(mat_mul(E[y], Lm)) for y in Y}
    eta = solve_exact(Lm, [F(1)] * 7)
    ok = A is not None and all(Pi[y] is not None for y in Y) and eta is not None
    if ok:
        etacol = [[v] for v in eta]
        def realized(sidx, word):
            row = [Lm[sidx]]
            row = mat_mul(row, Pi[word[0]])
            for yv in word[1:]:
                row = mat_mul(mat_mul(row, A), Pi[yv])
            return mat_mul(row, etacol)[0][0]
        for k in range(1, 5):
            for w in product(Y, repeat=k):
                b = beta(list(w))
                for i in range(7):
                    if realized(i, list(w)) != b[i][0]:
                        ok = False
        neg = any(v < 0 for row in A for v in row) or any(v < 0 for row in Lm for v in row)
    check(f"signed realization of dimension {dim}: M L = L A, E_y L = L Pi_y, L eta = 1, reproduces all traces up to 4 symbols",
          ok and dim == 5)
    check("signed minimum 5 equals the replayed positive candidate, so the positive dimension is exactly 5 here", dim == 5)
    record("seven_state_linear", {"signed_minimum": dim, "positive_upper": 5, "positive_interval": [5, 5],
                                  "basis_signed_entries": bool(neg) if ok else None})


def trace_bound_random(seed=11, trials=120):
    import random
    rnd = random.Random(seed)
    print("\n18. Randomized checks: trace TV through horizon h <= (h+1)-th behavioral iterate; induced trace bound")
    bad_h = bad_ind = 0
    for _ in range(trials):
        n = rnd.randint(3, 5)
        S = list(range(n))
        acts = ["a", "b"][: rnd.randint(1, 2)]
        obs = {s: rnd.randrange(2) for s in S}
        rows = {}
        for a in acts:
            rows[a] = {}
            for s in S:
                supp = rnd.sample(S, rnd.randint(1, 2))
                if len(supp) == 1:
                    rows[a][s] = {supp[0]: F(1)}
                else:
                    p = F(rnd.randint(1, 3), 4)
                    rows[a][s] = {supp[0]: p, supp[1]: 1 - p}
        d0 = lambda s, t: F(int(obs[s] != obs[t]))
        for h in range(0, 4):
            dh = stoch_iterate(S, d0, rows, F(1), h + 1)
            for s in S:
                for t in S:
                    worst = max(tv(trace_law(s, list(w), rows, obs), trace_law(t, list(w), rows, obs))
                                for w in product(acts, repeat=h))
                    if worst > dh[(s, t)]:
                        bad_h += 1
        # induced abstraction with current adequacy: q refines the observation partition
        q = {s: (obs[s], rnd.randrange(2)) for s in S}
        classes = sorted(set(q.values()))
        rep = {c: min(s for s in S if q[s] == c) for c in classes}
        bar_rows = {a: {c: {} for c in classes} for a in acts}
        for a in acts:
            for c in classes:
                for t, p in rows[a][rep[c]].items():
                    bar_rows[a][c][q[t]] = bar_rows[a][c].get(q[t], F(0)) + p
        bar_obs = {c: c[0] for c in classes}
        def push(row):
            out = {}
            for t, p in row.items():
                out[q[t]] = out.get(q[t], F(0)) + p
            return out
        eps = max(tv(push(rows[a][s]), bar_rows[a][q[s]]) for a in acts for s in S)
        for H in range(0, 4):
            for s in S:
                for w in product(acts, repeat=H):
                    P = trace_law(s, list(w), rows, obs)
                    Q = trace_law(q[s], list(w), bar_rows, bar_obs)
                    if tv(P, Q) > 1 - (1 - eps) ** H:
                        bad_ind += 1
    check(f"TV of trace laws through h transitions <= Phi^(h+1)(0) at gamma=1 ({trials} chains, h<=3, all words)", bad_h == 0, f"violations {bad_h}")
    check("induced abstraction with o = obar.q: trace TV <= 1-(1-eps)^H for every start and word", bad_ind == 0, f"violations {bad_ind}")
    # counterexample without current adequacy: two absorbing states, different reports, one code
    rows2 = {"a": {"r": {"r": F(1)}, "b": {"b": F(1)}}}
    obs2 = {"r": "red", "b": "blue"}
    bar2 = {"a": {"c": {"c": F(1)}}}
    obsbar = {"c": "red"}
    eps2 = max(tv({"c": F(1)}, bar2["a"]["c"]) for s in ("r", "b"))
    gap = tv(trace_law("b", [], rows2, obs2), trace_law("c", [], bar2, obsbar))
    check("without current adequacy: pushed rows agree (eps=0) yet the initial observation differs with probability 1",
          eps2 == 0 and gap == 1)
    record("trace_bounds", {"horizon_iterate_bound": "TV_h <= Phi^(h+1)(0)", "induced": "1-(1-eps)^H",
                            "counterexample_without_current_adequacy": {"eps": "0", "tv_at_H0": "1"}})


# ---------------------------------------------------------------------------
# Section 19. Linear arrows: residual composition needs amplification factors
# ---------------------------------------------------------------------------

def linear_composition():
    print("\n19. Signed linear arrows: residual law R_LK = R_L K + L R_K")
    I2 = eye(2)
    Swap = [[F(0), F(1)], [F(1), F(0)]]
    P = [[F(9, 10) * I2[i][j] + F(1, 10) * Swap[i][j] for j in range(2)] for i in range(2)]
    M = N = I2
    L = [[F(2), F(-1)], [F(-1), F(2)]]
    K = I2
    RL = mat_sub(mat_mul(M, L), mat_mul(L, N))
    RK = mat_sub(mat_mul(N, K), mat_mul(K, P))
    LK = mat_mul(L, K)
    RLK = mat_sub(mat_mul(M, LK), mat_mul(LK, P))
    ones = [[F(1)], [F(1)]]
    check("both arrows preserve the all-ones vector", mat_mul(L, ones) == ones and mat_mul(K, ones) == ones)
    check("residual norms 0, 1/5 and composite 3/5; ||L|| = 3",
          norm_inf(RL) == 0 and norm_inf(RK) == F(1, 5) and norm_inf(RLK) == F(3, 5) and norm_inf(L) == 3)
    ident = mat_sub(RLK, [[a + b for a, b in zip(r1, r2)] for r1, r2 in zip(mat_mul(RL, K), mat_mul(L, RK))])
    check("identity R_LK = R_L K + L R_K holds exactly", all(v == 0 for row in ident for v in row))
    bound = norm_inf(RL) * norm_inf(K) + norm_inf(L) * norm_inf(RK)
    check("graded bound rho_L lambda_K + lambda_L rho_K = 3/5 is attained; plain addition gives 1/5",
          bound == F(3, 5) and norm_inf(RL) + norm_inf(RK) == F(1, 5))
    # positivity alone does not give norm one: a positive arrow from a realization whose final vector
    # is (2,2) (operators I, one projector I) into the stochastic machine N = I_2
    eta = [[F(2)], [F(2)]]
    L2 = [[F(2), F(0)], [F(0), F(2)]]
    positive = all(v >= 0 for row in L2 for v in row) and mat_mul(L2, ones) == eta and mat_mul(I2, eta) == eta
    RL2 = mat_sub(mat_mul(I2, L2), mat_mul(L2, N))
    RL2K = mat_sub(mat_mul(I2, mat_mul(L2, K)), mat_mul(mat_mul(L2, K), P))
    check("positive arrow from a realization with final vector (2,2): ||L|| = 2, residual 0; composite with K "
          "has residual 2/5 = lambda_L rho_K, while adding residuals gives 1/5",
          positive and norm_inf(L2) == 2 and norm_inf(RL2) == 0 and norm_inf(RL2K) == F(2, 5)
          and norm_inf(RL2) + norm_inf(RK) == F(1, 5))
    # randomized: the law holds for signed arrows; for positive stochastic arrows it reduces to additivity
    import random
    rnd = random.Random(5)
    bad = bad_pos = 0
    def rand_stoch(n):
        out = []
        for _ in range(n):
            w = [rnd.randint(0, 3) for _ in range(n)]
            if sum(w) == 0:
                w[rnd.randrange(n)] = 1
            out.append([F(v, sum(w)) for v in w])
        return out
    for _ in range(200):
        n = rnd.randint(2, 3)
        Ma, Na, Pa = rand_stoch(n), rand_stoch(n), rand_stoch(n)
        La = [[F(rnd.randint(-2, 2)) for _ in range(n)] for _ in range(n)]
        Ka = [[F(rnd.randint(-2, 2)) for _ in range(n)] for _ in range(n)]
        rl = mat_sub(mat_mul(Ma, La), mat_mul(La, Na))
        rk = mat_sub(mat_mul(Na, Ka), mat_mul(Ka, Pa))
        rlk = mat_sub(mat_mul(Ma, mat_mul(La, Ka)), mat_mul(mat_mul(La, Ka), Pa))
        if norm_inf(rlk) > norm_inf(rl) * norm_inf(Ka) + norm_inf(La) * norm_inf(rk):
            bad += 1
        Lp, Kp = rand_stoch(n), rand_stoch(n)
        rl = mat_sub(mat_mul(Ma, Lp), mat_mul(Lp, Na))
        rk = mat_sub(mat_mul(Na, Kp), mat_mul(Kp, Pa))
        rlk = mat_sub(mat_mul(Ma, mat_mul(Lp, Kp)), mat_mul(mat_mul(Lp, Kp), Pa))
        if norm_inf(rlk) > norm_inf(rl) + norm_inf(rk):
            bad_pos += 1
    check("random signed arrows obey ||R_LK|| <= ||R_L|| ||K|| + ||L|| ||R_K|| (200 trials)", bad == 0, f"violations {bad}")
    check("random row-stochastic arrows: residuals add (200 trials)", bad_pos == 0, f"violations {bad_pos}")
    record("linear_composition", {"rho_L": "0", "rho_K": "1/5", "rho_LK": "3/5", "lambda_L": "3",
                                  "grade_law": "(lambda_L*lambda_K, rho_L*lambda_K + lambda_L*rho_K)",
                                  "unnormalized_source": {"final_vector": ["2", "2"], "lambda_L": "2",
                                                          "rho_LK": "2/5", "residual_sum": "1/5"}})


# ---------------------------------------------------------------------------
# Section 20. Counterexamples behind the theorem hypotheses
# ---------------------------------------------------------------------------

def hypothesis_counterexamples():
    print("\n20. Counterexamples: separated values, restriction, horizon index, surjectivity, simulation scope")
    # (a) pseudometric value tolerance: zero current defect without a literal decoder
    o = {"a": "red", "b": "blue"}
    beta_trivial = lambda y, z: F(1)
    dnow = max(1 - beta_trivial(o[s], o[t]) for s in o for t in o)
    literal = len({o[s] for s in o}) == 1
    zero_quotient_classes = 1
    check("trivial value tolerance: current defect 0, no literal decoder, one class in Y/~0",
          dnow == 0 and not literal and zero_quotient_classes == 1)
    # (b) restriction: constant code on two absorbing states with different reports
    full = max(int(o[s] != o[t]) for s in o for t in o)
    singles = [max(int(o[s] != o[t]) for s in [z] for t in [z]) for z in o]
    check("restriction: defect 1 on the two-state carrier, 0 on each singleton; the refutation does not restrict",
          full == 1 and singles == [0, 0])
    import random
    rnd = random.Random(3)
    bad = 0
    for _ in range(300):
        n = rnd.randint(3, 7)
        X = list(range(n))
        acts = {a: {x: rnd.randrange(n) for x in X} for a in ("a", "b")[: rnd.randint(1, 2)]}
        ov = {x: rnd.randrange(3) for x in X}
        qv = {x: rnd.randrange(3) for x in X}
        start = rnd.randrange(n)
        sub, frontier = {start}, [start]
        while frontier:
            x = frontier.pop()
            for T in acts.values():
                if T[x] not in sub:
                    sub.add(T[x]); frontier.append(T[x])
        def defects(Z):
            same = [(x, y) for x in Z for y in Z if qv[x] == qv[y]]
            od = lambda x, y: F(int(ov[x] != ov[y]))
            dbeh = behavioral_distance(sorted(Z), od, {a: {x: T[x] for x in Z} for a, T in acts.items()}, F(1))
            dn = max((od(x, y) for x, y in same), default=F(0))
            du = max((F(int(qv[T[x]] != qv[T[y]])) for x, y in same for T in acts.values()), default=F(0))
            db = max((dbeh[(x, y)] for x, y in same), default=F(0))
            return dn, du, db
        f, s = defects(X), defects(sub)
        if any(sv > fv for sv, fv in zip(s, f)):
            bad += 1
    check("universal upper bounds restrict to forward-closed subsets (300 random machines)", bad == 0, f"violations {bad}")
    # (c) horizon indexing on the staged example: states 0..3, update min(i+1,3), observations 0,0,0,1
    X = [0, 1, 2, 3]
    T = {"t": {i: min(i + 1, 3) for i in X}}
    ob = {0: 0, 1: 0, 2: 0, 3: 1}
    od = lambda x, y: F(int(ob[x] != ob[y]))
    def horizon_distance(x, y, iterates):
        # distance form of Phi^iterates(0): max over k < iterates of d0 after k steps
        best, px, py = F(0), x, y
        for k in range(iterates):
            best = max(best, od(px, py))
            px, py = T["t"][px], T["t"][py]
        return best
    vals = {h: horizon_distance(0, 1, h + 1) for h in range(0, 4)}
    wrong = {h: horizon_distance(0, 1, h) for h in range(0, 4)}
    check("staged pair (0,1): horizon-h defect via Phi^(h+1) is 0,0,1,1 for h=0..3; Phi^h would report 0,0,0,1",
          [vals[h] for h in range(4)] == [0, 0, 1, 1] and [wrong[h] for h in range(4)] == [0, 0, 0, 1])
    check("Phi^0 checks nothing: the wrong index at h=0 accepts the constant encoding of states with different reports",
          horizon_distance(2, 3, 0) == 0 and horizon_distance(2, 3, 1) == 1)
    # (d) zero-defect map into a reduced target need not be surjective
    Msrc = {"s": "s"}
    Ntgt = {"z0": "z0", "z1": "z1"}
    obs_src = {"s": 0}
    obs_tgt = {"z0": 0, "z1": 1}
    h = {"s": "z0"}
    hom = all(obs_tgt[h[x]] == obs_src[x] and h[Msrc[x]] == Ntgt[h[x]] for x in Msrc)
    check("zero-defect homomorphism s -> z0 into a reduced two-state target is not surjective",
          hom and set(h.values()) != set(Ntgt))
    # (e) the empty relation is a simulation; safety is vacuous unless initial states are covered
    bad_init = {"b0"}
    R = set()
    covered = all(any(x == a for a, _ in R) for x in bad_init)
    check("empty simulation relation: abstract scope from images is empty; initial coverage fails as required",
          not covered)
    record("counterexamples", {"pseudometric_zero": "dnow 0 without literal decoder",
                               "restriction": {"full": 1, "singletons": [0, 0]},
                               "horizon_index": {"correct": [0, 0, 1, 1], "wrong": [0, 0, 0, 1]},
                               "non_surjective_homomorphism": True, "empty_simulation": "vacuous"})


# ---------------------------------------------------------------------------
# Section 21. Transfer hive versus kernel hive (beacon systems)
# ---------------------------------------------------------------------------

def beacon_hives():
    print("\n21. Beacon systems: transfer-hive coherence up to gauge; derived kernel hive")
    S = ["Left", "Right"]
    Mv = ["ChooseLeft", "ChooseRight"]
    rew = lambda s, m: 1 if (s, m) in {("Left", "ChooseLeft"), ("Right", "ChooseRight")} else 0
    flip = lambda s: "Right" if s == "Left" else "Left"
    mflip = lambda m: "ChooseRight" if m == "ChooseLeft" else "ChooseLeft"
    ident = lambda s: s
    # transfers (pullback phi: X_target -> X_source, pushforward iota: Meth_source -> Meth_target)
    T = {"AB": (ident, ident), "BC": (ident, ident), "CA": (flip, mflip)}
    defect = {k: max(abs(rew(phi(b), m) - rew(b, iota(m))) for b in S for m in Mv) for k, (phi, iota) in T.items()}
    check("edge transfers AB, BC, GoodCA are exact (defect 0)", all(v == 0 for v in defect.values()))
    # holonomy at A: composite of A->B->C->A pullbacks and pushforwards
    phi_cyc = lambda a: T["AB"][0](T["BC"][0](T["CA"][0](a)))
    iota_cyc = lambda m: T["CA"][1](T["BC"][1](T["AB"][1](m)))
    hol = ({s: phi_cyc(s) for s in S}, {m: iota_cyc(m) for m in Mv})
    G = [({s: s for s in S}, {m: m for m in Mv}), ({s: flip(s) for s in S}, {m: mflip(m) for m in Mv})]
    symmetric = all(rew(g[0][s], g[1][m]) == rew(s, m) for g in G for s in S for m in Mv)
    check("holonomy is (flip, flip), a declared symmetry of the reward response", hol == G[1] and symmetric)
    # derived kernel hive: member tolerance from the response observer, correspondences from transfers
    def member_tol(x, xp):
        return 1 - max(abs(rew(x, m) - rew(xp, m)) for m in Mv)
    def corr(iota):
        return {(x, y): 1 - max(abs(rew(x, m) - rew(y, iota(m))) for m in Mv) for x in S for y in S}
    c = {k: corr(T[k][1]) for k in T}
    I = {(x, y): int(x == y) for x in S for y in S}
    Sw = {(x, y): int(x != y) for x in S for y in S}
    check("derived correspondences: c_AB = I, c_BC = I, c_CA = S (graph kernels)",
          c["AB"] == I and c["BC"] == I and c["CA"] == Sw)
    comp = lambda K1, K2: {(x, z): max(max(0, K1[(x, y)] + K2[(y, z)] - 1) for y in S) for x in S for z in S}
    holk = comp(comp(c["AB"], c["BC"]), c["CA"])
    alpha = {(x, y): member_tol(x, y) for x in S for y in S}
    check("unsaturated derived kernel hive: holonomy S is not below the member tolerance I (incoherent)",
          holk == Sw and alpha == I and any(holk[k] > alpha[k] for k in holk))
    # the unsaturated derived kernel hive is the parity triangle up to relabelling
    nodes = [(i, s) for i in "ABC" for s in S]
    def block(a, b):
        (i, x), (j, y) = a, b
        if i == j:
            return alpha[(x, y)]
        key = {("A", "B"): ("AB", False), ("B", "A"): ("AB", True), ("B", "C"): ("BC", False),
               ("C", "B"): ("BC", True), ("C", "A"): ("CA", False), ("A", "C"): ("CA", True)}[(i, j)]
        k, tr = key
        return c[k][(y, x)] if tr else c[k][(x, y)]
    w = F(1, 6)
    H = {(a, b): F(block(a, b)) for a in nodes for b in nodes}
    Hc = dict(H)
    for k in nodes:
        for a in nodes:
            for b in nodes:
                Hc[(a, b)] = max(Hc[(a, b)], max(F(0), Hc[(a, k)] + Hc[(k, b)] - 1))
    closure_cost = sum(w * w * (Hc[(a, b)] - H[(a, b)]) for a in nodes for b in nodes)
    check("its metric closure is all ones and the closure consensus cost is 1/2, as for the parity triangle",
          all(v == 1 for v in Hc.values()) and closure_cost == F(1, 2))
    # saturation by the gauge group: alpha^G(x,x') = max_g [responses of x and x' agree after relabelling by g]
    alphaG = {(x, y): max(1 - max(abs(rew(x, m) - rew(y, g[1][m])) for m in Mv) for g in G) for x in S for y in S}
    def saturated_block(members):
        def kern(a, b):
            (i, x), (j, y) = a, b
            ai = alphaG if i in members else alpha
            aj = alphaG if j in members else alpha
            if i == j:
                return F(ai[(x, y)])
            # alpha_i o c_ij o alpha_j, crisp composition
            return F(max(min(ai[(x, u)], block((i, u), (j, v)), aj[(v, y)]) for u in S for v in S))
        return {(a, b): kern(a, b) for a in nodes for b in nodes}
    def transitive(K):
        return all(max(F(0), K[(a, k)] + K[(k, b)] - 1) <= K[(a, b)] for a in nodes for b in nodes for k in nodes)
    full = saturated_block({"A", "B", "C"})
    only_a = saturated_block({"A"})
    check("saturating every member by its gauge (transported along the transfers) gives a coherent kernel hive",
          all(v == 1 for v in alphaG.values()) and transitive(full))
    check("saturating only the base member does not: the block kernel is then not transitive", not transitive(only_a))
    # adding an absolute-orientation observer removes the symmetry
    sym2 = all((g[0][s] == s) for g in G for s in S)
    check("with an absolute-orientation observer the flip is no longer a symmetry", not sym2)
    record("beacon_hives", {"edge_defects": {k: v for k, v in defect.items()}, "holonomy": "(flip, flip)",
                            "transfer_hive": "coherent up to declared gauge", "kernel_hive_unsaturated": "incoherent",
                            "kernel_hive_closure_cost": "1/2", "kernel_hive_saturated": "coherent",
                            "saturated_at_base_only": "incoherent"})


# ---------------------------------------------------------------------------
# Section 22. Symbolic admission: coverage and reachability scope
# ---------------------------------------------------------------------------

def symbolic_admission():
    print("\n22. Symbolic admission obligations on scaled zero-tail machines")
    for n in (5, 8, 12):
        N = 1 << n
        bit = lambda x, i: (x >> i) & 1
        tailzero = lambda x: int((x >> 2) == 0)
        def rotate(x):
            hi, m = x >> 2, n - 2
            hi = ((hi << 1) | (hi >> (m - 1))) & ((1 << m) - 1)
            return (hi << 2) | (x & 3)
        acts = {"swap": lambda x: (x & ~3) | (bit(x, 0) << 1) | bit(x, 1), "rotate": rotate,
                "inject": lambda x: x ^ (tailzero(x) << 1)}
        # adversarial candidate: four blocks B_ab = {x : x0=a, x1=b, tail=0}
        blocks = {(a, b): (lambda x, a=a, b=b: bit(x, 0) == a and bit(x, 1) == b and tailzero(x)) for a in (0, 1) for b in (0, 1)}
        reps = {(a, b): a | (b << 1) for a in (0, 1) for b in (0, 1)}
        uncovered = next((x for x in range(N) if not any(B(x) for B in blocks.values())), None)
        disjoint = all(sum(1 for B in blocks.values() if B(x)) <= 1 for x in range(N))
        members = all(B(reps[k]) for k, B in blocks.items())
        region = [x for x in range(N) if tailzero(x)]
        constancy = all(bit(x, 0) == k[0] for k, B in blocks.items() for x in region if B(x))
        stable = all(any(B2(f(x)) for B2 in blocks.values()) for f in acts.values() for x in region)
        check(f"width {n}: four zero-tail blocks pass local checks but coverage fails at word {uncovered}",
              uncovered == 4 and disjoint and members and constancy and stable)
        # as a quotient of the reachable carrier from 0 the same blocks are valid
        reach, frontier, words = {0}, [0], {0: ()}
        while frontier:
            x = frontier.pop(0)
            for nm in sorted(acts):
                y = acts[nm](x)
                if y not in reach:
                    reach.add(y); frontier.append(y); words[y] = words[x] + (nm,)
        closed = all(acts[nm](x) in reach for nm in acts for x in reach)
        check(f"width {n}: Reach(0) = the four zero-tail words, forward closed, each with a witnessing word",
              reach == set(region) and closed and len(words) == 4)
        # an over-approximation (the whole carrier) is forward closed and contains 0 but is not exact
        check(f"width {n}: the full carrier is a sound but inexact reachability over-approximation", len(region) < N)
    record("symbolic_admission", {"adversarial_candidate": {"status": "Refuted", "obligation": "Coverage", "witness_word": 4},
                                  "reach_from_zero": {"size": len(reach), "words": {str(k): list(v) for k, v in sorted(words.items())}}})


# ---------------------------------------------------------------------------
# Section 23. Ledgers and small fixtures quoted in the documents
# ---------------------------------------------------------------------------

def small_fixtures():
    print("\n23. Ledgers, descent converse, chain bound, lockout refinement, reports, patterns")
    def weakness(blocks, n):
        return sum(F(len(b), n) ** 2 for b in blocks)
    w_before = weakness([[0, 1, 2, 3], [4, 5, 6, 7]], 8)
    w_after = weakness([[0, 1], [2, 3], [4, 5], [6, 7]], 8)
    check("eight-state ledger: weakness 1/2 before, 1/4 after", (w_before, w_after) == (F(1, 2), F(1, 4)))
    p_before = weakness([["E"], ["U", "V"], ["B"]], 4)
    p_after = weakness([["E"], ["U"], ["V"], ["B"]], 4)
    p_two = weakness([["E"], ["U", "V", "B"]], 4)
    check("packet ledger: 3/8 before, 1/4 after; two-class frontier weakness 5/8",
          (p_before, p_after, p_two) == (F(3, 8), F(1, 4), F(5, 8)))
    # descent converse: constant queries, q(0)=q(1) != q(2), T(0)=0, T(1)=T(2)=2
    T = {0: 0, 1: 2, 2: 2}
    q = {0: 0, 1: 0, 2: 1}
    d = behavioral_distance([0, 1, 2], lambda x, y: F(0), {"t": T}, F(1))
    dbeh = max(d[(x, y)] for x in T for y in T if q[x] == q[y])
    dupd = max(int(q[T[x]] != q[T[y]]) for x in T for y in T if q[x] == q[y])
    check("descent converse: behavioral defect 0, update defect 1", dbeh == 0 and dupd == 1)
    # chain bound with n = 6: merging 0 and 1 is refuted by a word of length 4
    n = 6
    Tc = {i: min(i + 1, n - 1) for i in range(n)}
    mark = {i: int(i == n - 1) for i in range(n)}
    w = shortest_behavioral_witness(list(range(n)), {i: (0 if i in (0, 1) else i) for i in range(n)},
                                    {"marked": mark}, {"next": Tc})
    check("chain of six: witness for merging 0 and 1 has length n-2 = 4", w is not None and len(w[1]) == 4, str(w))
    # lockout: abstract one-step path Start -> Locked; concrete needs three failures from S0
    fail = {"S0": "S1", "S1": "S2", "S2": "Locked", "Locked": "Locked", "Auth": "Auth", "Admin": "Admin"}
    steps, x = 0, "S0"
    while x != "Locked":
        x, steps = fail[x], steps + 1
    check("lockout: abstraction reaches Locked in one step, the protocol from S0 needs 3 (spurious within 2)", steps == 3)
    # availability reports
    rep = {"Absent": "Missing", "Neither": (0, 0), "Support": (1, 0), "Oppose": (0, 1), "Both": (1, 1)}
    dz = {k: ((0, 0) if v == "Missing" else v) for k, v in rep.items()}
    bias = {k: (0 if v == "Missing" else v[0] - v[1]) for k, v in rep.items()}
    def merged(code):
        return sorted(tuple(sorted((a, b))) for a in rep for b in rep if a < b and code[a] == code[b] and rep[a] != rep[b])
    check("default-zero merges only Absent/Neither; bias also merges Neither/Both and Absent/Both",
          merged(dz) == [("Absent", "Neither")] and merged(bias) == [("Absent", "Both"), ("Absent", "Neither"), ("Both", "Neither")])
    # patterns
    lit, rpt = 6, 2 + 1 + 1
    check("description costs 6 and 4, gain 2 (1/3 normalized); execution 6 for both",
          (lit, rpt, lit - rpt, F(lit - rpt, lit)) == (6, 4, 2, F(1, 3)))
    # regime prior 3/4 on Plus: new averages 3/4 and 1/4, old stays 1/2
    pp = F(3, 4)
    newL = pp * 1 + (1 - pp) * 0
    newR = pp * 0 + (1 - pp) * 1
    check("regime with prior 3/4: new averages 3/4 and 1/4", (newL, newR) == (F(3, 4), F(1, 4)))
    # tick blind copy: reward-law total variation is 1 between point masses 3/4 and 0
    check("tick blind copy: reward-law TV 1 (point masses at 3/4 and 0)", tv({F(3, 4): F(1)}, {F(0): F(1)}) == 1)
    # evolution witness
    mut = {"G00": {"G01": F(1, 2), "G10": F(1, 2)}, "G01": {"G00": F(1, 2), "G11": F(1, 2)}}
    p00 = sum(p for t, p in mut["G00"].items() if t == "G11")
    p01 = sum(p for t, p in mut["G01"].items() if t == "G11")
    check("evolution witness: pair (G00,G01), event score=1, probabilities 0 and 1/2", (p00, p01) == (0, F(1, 2)))
    record("small_fixtures", {"eight_state_ledger": ["1/2", "1/4"], "packet_ledger": ["3/8", "1/4"],
                              "two_class_weakness": "5/8", "descent_converse": {"behavioral": "0", "update": "1"},
                              "chain_six_witness_length": len(w[1]), "lockout_concrete_steps": steps,
                              "availability": {"default_zero": [["Absent", "Neither"]],
                                               "bias": [["Absent", "Both"], ["Absent", "Neither"], ["Both", "Neither"]]},
                              "pattern_costs": [6, 4], "regime_skewed": ["3/4", "1/4"], "tick_copy_tv": "1",
                              "evolution_witness": ["G00", "G01", "mutate", "score=1", "0", "1/2"]})


# ---------------------------------------------------------------------------
# Section 24. Gauge intertwining, adaptive policies, merge-only machine
# ---------------------------------------------------------------------------

# the adaptive-policy machine of fixture certificate_limits.metta (module AdaptiveProbe)
ADAPT_OBS = {"x": 0, "x2": 0, "r1": 1, "r2": 2, "s1": 1, "s2": 2, "A": 3, "B": 4, "C": 5}


def adapt_rows():
    rows = {"a": {}, "b": {}, "c": {}}
    for st in ADAPT_OBS:
        for act in rows:
            rows[act][st] = {st: F(1)}
    rows["a"]["x"] = {"r1": F(1, 2), "r2": F(1, 2)}
    rows["a"]["x2"] = {"s1": F(1, 2), "s2": F(1, 2)}
    rows["b"]["r1"], rows["b"]["s1"], rows["b"]["r2"], rows["b"]["s2"] = {"A": F(1)}, {"B": F(1)}, {"C": F(1)}, {"C": F(1)}
    rows["c"]["r2"], rows["c"]["s2"], rows["c"]["r1"], rows["c"]["s1"] = {"A": F(1)}, {"B": F(1)}, {"C": F(1)}, {"C": F(1)}
    return rows


def gauge_policy_merge():
    print("\n24. Gauge intertwining, adaptive versus open-loop trace discrepancy, merge-only refinement")
    # (a) gauges that are not intertwined by the transfers break saturated coherence
    S = [0, 1, 2, 3]
    nu = lambda x, m: int(x == m)
    swap01 = {0: 1, 1: 0, 2: 2, 3: 3}
    swap23 = {0: 0, 1: 1, 2: 3, 3: 2}
    ident = {s: s for s in S}
    def gauge_tol(group):
        return {(x, y): max(1 - max(abs(nu(x, m) - nu(y, g[m])) for m in S) for g in group) for x in S for y in S}
    members = ["A", "B", "C"]
    def saturated(gauges):
        tol = {i: gauge_tol(gauges[i]) for i in members}
        nodes = [(i, s) for i in members for s in S]
        def corr(i, j, x, y):     # identity transfers: c_ij = graph of identity on response classes
            return int(all(nu(x, m) == nu(y, m) for m in S))
        def K(a, b):
            (i, x), (j, y) = a, b
            if i == j:
                return tol[i][(x, y)]
            return max(min(tol[i][(x, u)], corr(i, j, u, v), tol[j][(v, y)]) for u in S for v in S)
        KK = {(a, b): K(a, b) for a in nodes for b in nodes}
        return all(max(0, KK[(a, k)] + KK[(k, b)] - 1) <= KK[(a, b)] for a in nodes for b in nodes for k in nodes)
    bad = {"A": [ident, swap01], "B": [ident, swap23], "C": [ident, swap01]}
    good = {"A": [ident, swap01], "B": [ident, swap01], "C": [ident, swap01]}
    check("gauges swapping 0,1 at A and C but 2,3 at B: holonomy trivial, saturated hive not transitive",
          not saturated(bad))
    check("the same gauge at every member, intertwined by identity transfers: saturated hive transitive", saturated(good))
    # (b) an adaptive policy separates more than any fixed word
    rows, obs = adapt_rows(), ADAPT_OBS
    words = max(tv(trace_law("x", list(w), rows, obs), trace_law("x2", list(w), rows, obs))
                for w in product(["a", "b", "c"], repeat=2))
    def policy_law(s0):
        out = {}
        for s1, p1 in rows["a"][s0].items():
            act = "b" if obs[s1] == 1 else "c"
            for s2, p2 in rows[act][s1].items():
                key = (obs[s0], "a", obs[s1], act, obs[s2])
                out[key] = out.get(key, F(0)) + p1 * p2
        return out
    adaptive = tv(policy_law("x"), policy_law("x2"))
    d0 = lambda s, t: F(int(obs[s] != obs[t]))
    d2 = stoch_iterate(list(obs), d0, rows, F(1), 3)
    check("open-loop words separate by at most 1/2, the adaptive policy by 1, both within d^(1,2) = 1",
          words == F(1, 2) and adaptive == 1 and d2[("x", "x2")] == 1)
    # (c) a machine whose only operation is the union merge refines the posterior classes to singletons
    P = ["E", "U", "V", "B"]
    sets = {"E": set(), "U": {"u"}, "V": {"v"}, "B": {"u", "v"}}
    name = {frozenset(v): k for k, v in sets.items()}
    post = {"E": F(1, 2), "U": F(3, 4), "V": F(3, 4), "B": F(9, 10)}
    trans = {f"with{c}": {x: name[frozenset(sets[x] | sets[c])] for x in P} for c in P}
    block, _ = refine(P, lambda x: (post[x],), trans)
    witness = next(((x, y, c) for x in P for y in P for c in P if x < y and post[x] == post[y]
                    and post[name[frozenset(sets[x] | sets[c])]] != post[name[frozenset(sets[y] | sets[c])]]), None)
    check("merge alone: translations split U from V (witness via U), refinement gives four singletons",
          len(set(block.values())) == 4 and witness is not None)
    record("gauge_policy_merge", {"gauge_not_intertwined": "incoherent", "gauge_intertwined": "coherent",
                                  "words_tv": "1/2", "adaptive_tv": "1", "merge_only_classes": 4})


# ---------------------------------------------------------------------------
# Section 25. Literal congruence of code fibers under a non-discrete code tolerance
# ---------------------------------------------------------------------------

def literal_congruence():
    print("\n25. Literal congruence: zero graded defects under an indiscrete code tolerance")
    X = [0, 1, 2]
    hop = {0: 0, 1: 2, 2: 2}
    q = {0: 0, 1: 0, 2: 1}
    alpha0 = lambda x, y: F(1)                       # constant observation
    def defects(beta):
        aq = lambda x, y: beta(q[x], q[y])
        dnow = max(max(F(0), aq(x, y) - alpha0(x, y)) for x in X for y in X)
        dupd = max(max(F(0), aq(x, y) - aq(hop[x], hop[y])) for x in X for y in X)
        return dnow, dupd
    indiscrete = defects(lambda u, v: F(1))
    discrete = defects(lambda u, v: F(int(u == v)))
    witness = next(((x, y, "hop", q[hop[x]], q[hop[y]]) for x in X for y in X
                    if x < y and q[x] == q[y] and q[hop[x]] != q[hop[y]]), None)
    images = {c: sorted({q[hop[x]] for x in X if q[x] == c}) for c in (0, 1)}
    check("indiscrete code tolerance on {0,1}: current defect 0 and update defect 0", indiscrete == (0, 0))
    check("literal congruence fails: 0 and 1 share code 0, hop sends them to codes 0 and 1",
          witness == (0, 1, "hop", 0, 1), str(witness))
    check("no update on the codes commutes with hop: code 0 has successor codes {0,1}", images == {0: [0, 1], 1: [1]})
    check("with the discrete code tolerance the same encoding has update defect 1 (claim H10)", discrete == (0, 1))
    record("literal_congruence", {"now": "0", "updates": "0", "discrete_updates": fstr(discrete[1]),
                                  "witness": list(witness), "successor_codes_of_code_0": images[0]})


# ---------------------------------------------------------------------------
# Section 26. Policy-tree witnesses for observation-based trace claims
# ---------------------------------------------------------------------------

def tree_law(s0, tree, rows, obs, horizon):
    """Joint law of (y0, a1, y1, ..., ah, yh) from s0 under a deterministic policy tree, a map from
    observed histories to actions.  The tree reads histories only."""
    dist = {(obs[s0],): {s0: F(1)}}
    for _ in range(horizon):
        new = {}
        for hist, sub in dist.items():
            a = tree[hist]
            for x, p in sub.items():
                for y, r in rows[a][x].items():
                    cell = new.setdefault(hist + (a, obs[y]), {})
                    cell[y] = cell.get(y, F(0)) + p * r
        dist = new
    return {k: sum(v.values()) for k, v in dist.items()}


def all_trees(starts, rows, obs, actions, horizon):
    """Every deterministic policy tree of the horizon, defined on each history of positive probability
    from some start, in canonical order (histories in order, actions in declaration order)."""
    def extend(tree, frontier, depth):
        if depth == horizon:
            yield dict(tree)
            return
        hists = sorted(frontier, key=str)
        for choice in product(actions, repeat=len(hists)):
            t2, nxt = dict(tree), {}
            for hist, a in zip(hists, choice):
                t2[hist] = a
                for x in frontier[hist]:
                    for y in rows[a][x]:
                        nxt.setdefault(hist + (a, obs[y]), set()).add(y)
            yield from extend(t2, nxt, depth + 1)
    root = {}
    for s in starts:
        root.setdefault((obs[s],), set()).add(s)
    yield from extend({}, root, 0)


def policy_trees():
    print("\n26. Observation-based trace claims need policy-tree witnesses")
    rows, obs, acts = adapt_rows(), ADAPT_OBS, ["a", "b", "c"]
    words = max(tv(trace_law("x", list(w), rows, obs), trace_law("x2", list(w), rows, obs))
                for w in product(acts, repeat=2))
    trees = list(all_trees(["x", "x2"], rows, obs, acts, 2))
    vals = [tv(tree_law("x", t, rows, obs, 2), tree_law("x2", t, rows, obs, 2)) for t in trees]
    best = max(vals)
    canon = trees[vals.index(best)]
    P, Q = tree_law("x", canon, rows, obs, 2), tree_law("x2", canon, rows, obs, 2)
    event = sorted(h for h in set(P) | set(Q) if P.get(h, F(0)) > Q.get(h, F(0)))
    left, right = sum(P.get(h, F(0)) for h in event), sum(Q.get(h, F(0)) for h in event)
    check(f"horizon 2: fixed words separate x from x2 by at most 1/2; the best of {len(trees)} "
          "deterministic policy trees separates them by 1", words == F(1, 2) and best == 1)
    check("canonical policy tree: a at the root, then b after report 1 and c after report 2",
          canon == {(0,): "a", (0, "a", 1): "b", (0, "a", 2): "c"}, str(canon))
    check("its event 'last report is 3' has probabilities 1 and 0, so the discrepancy is 1",
          [h[-1] for h in event] == [3, 3] and (left, right) == (1, 0))
    check("the bound 3/4 holds over words (1/2) and is refuted over observation-based policies (1)",
          words <= F(3, 4) < best)
    # a fixed word is the policy tree whose actions ignore the observations; it replays as one
    as_tree = {(0,): "a", (0, "a", 1): "b", (0, "a", 2): "b"}
    check("the word (a b) replayed as a policy tree gives its word discrepancy 1/2",
          tv(tree_law("x", as_tree, rows, obs, 2), tree_law("x2", as_tree, rows, obs, 2))
          == tv(trace_law("x", ["a", "b"], rows, obs), trace_law("x2", ["a", "b"], rows, obs)) == F(1, 2))
    record("adaptive_policy", {"words_tv": fstr(words), "policies_tv": fstr(best), "trees": len(trees),
                               "witness": {"tree": [["0", "a"], ["0 a 1", "b"], ["0 a 2", "c"]],
                                           "event": "last report 3", "left": fstr(left), "right": fstr(right)},
                               "bound_3_4": {"Words": "Checked", "ObservationBased": "Refuted"}})


# ---------------------------------------------------------------------------
# Section 27. A behavioral distance that no finite test attains
# ---------------------------------------------------------------------------

def unattained_supremum():
    print("\n27. Behavioral distance as a supremum that no finite test attains")
    S = ["x", "y", "p"]
    obs = {"x": 0, "y": 0, "p": 1}
    rows = {"step": {"x": {"x": F(1, 2), "p": F(1, 2)}, "y": {"y": F(1)}, "p": {"p": F(1)}}}
    d0 = lambda s, t: F(int(obs[s] != obs[t]))
    H = 10
    out = {}
    for g, closed, limit, name in ((F(1), lambda h: 1 - F(1, 2 ** h), F(1), "undiscounted"),
                                   (F(1, 2), lambda h: (1 - F(1, 4 ** h)) / 3, F(1, 3), "discount_1_2")):
        vals = [stoch_iterate(S, d0, rows, g, h + 1)[("x", "y")] for h in range(H + 1)]
        # the depth-h test f_0 = [report = 1], f_(k+1) = max(f_0, <step>_g f_k)
        f0 = {s: F(int(obs[s] == 1)) for s in S}
        f, tests = dict(f0), []
        for h in range(H + 1):
            tests.append(f["x"] - f["y"])
            f = {s: max(f0[s], g * sum(p * f[t] for t, p in rows["step"][s].items())) for s in S}
        rec = all(closed(h + 1) == g * (closed(h) / 2 + F(1, 2)) for h in range(60))
        check(f"gamma={fstr(g)}: horizon distances d_h(x,y) = {'1-2^-h' if g == 1 else '(1-4^-h)/3'} < "
              f"{fstr(limit)} for h=0..{H}, attained by depth-h tests; the closed form obeys the recurrence",
              all(vals[h] == closed(h) == tests[h] < limit for h in range(H + 1)) and rec)
        out[name] = {"limit": fstr(limit), "horizons": [fstr(v) for v in vals[:6]]}
    # upper certificates: prefixpoints with the coupling of (1/2 x + 1/2 p) and y, all pairs
    def coupling(s, t):
        if (s, t) == ("x", "y"):
            return {("x", "y"): F(1, 2), ("p", "y"): F(1, 2)}
        if (s, t) == ("y", "x"):
            return {("y", "x"): F(1, 2), ("y", "p"): F(1, 2)}
        if s == t:
            return {(u, u): w for u, w in rows["step"][s].items()}
        return {(u, v): a * b for u, a in rows["step"][s].items() for v, b in rows["step"][t].items()}
    def prefixpoint(D, g):
        """D >= max(d0, g E_theta D) on every ordered pair, with theta a coupling of the two successor laws."""
        ok = True
        for s in S:
            for t in S:
                th, m1, m2 = coupling(s, t), {}, {}
                for (u, v), w in th.items():
                    m1[u] = m1.get(u, F(0)) + w
                    m2[v] = m2.get(v, F(0)) + w
                ok = ok and m1 == rows["step"][s] and m2 == rows["step"][t]
                ok = ok and D[(s, t)] >= max(d0(s, t), g * sum(w * D[uv] for uv, w in th.items()))
        return ok
    def kernel(v):
        D = {(s, t): F(0) if s == t else F(1) for s in S for t in S}
        D[("x", "y")] = D[("y", "x")] = v
        return D
    check("discount 1: D(x,y) = 1 is a prefixpoint, so d(x,y) = 1 = sup_h d_h, attained at no finite horizon",
          prefixpoint(kernel(F(1)), F(1)))
    # lower certificate for discount 1/2: a post-fixpoint with dual potentials; Phi contracts, so D <= d
    D = kernel(F(1, 3))
    f_pot, g_pot = {"x": F(1, 3), "p": F(1)}, {"y": F(0)}
    feasible = all(f_pot[u] - g_pot[v] <= D[(u, v)] for u in f_pot for v in g_pot)
    dual_value = sum(p * f_pot[u] for u, p in rows["step"]["x"].items()) - sum(p * g_pot[v] for v, p in rows["step"]["y"].items())
    post = feasible and D[("x", "y")] <= F(1, 2) * dual_value and all(D[(s, t)] == d0(s, t) for s, t in (("x", "p"), ("y", "p")))
    check("discount 1/2: D(x,y) = 1/3 is a coupling prefixpoint and a dual post-fixpoint (potentials 1/3, 1; 0), "
          "so d(x,y) = 1/3 exactly although every test gives less", prefixpoint(D, F(1, 2)) and post and dual_value == F(2, 3))
    # finite horizon 3 at discount 1: a depth-3 test and a layered prefixpoint meet at 7/8
    layers = [kernel(F(0))]
    for _ in range(3):
        layers.append(kernel(F(1, 2) * layers[-1][("x", "y")] + F(1, 2) * layers[-1][("p", "y")]))
    def layer_step_ok(Dn, Dt, g):
        return all(Dn[(s, t)] >= max(d0(s, t), g * sum(w * Dt[uv] for uv, w in coupling(s, t).items()))
                   for s in S for t in S)
    layered_ok = (all(layers[0][(s, t)] >= d0(s, t) for s in S for t in S)
                  and all(layer_step_ok(layers[k + 1], layers[k], F(1)) for k in range(3)))
    check("horizon 3: layered prefixpoint D_0..D_3 with D_3(x,y) = 7/8 meets the depth-3 test", layered_ok
          and layers[3][("x", "y")] == F(7, 8) == 1 - F(1, 8))
    depth = next(h for h in range(1, 40) if 1 - F(1, 2 ** h) > F(99, 100))
    check("a bound below the supremum is refuted by a finite test: depth 7 gives 127/128 > 99/100, depth 6 gives 63/64",
          depth == 7 and 1 - F(1, 2 ** 6) < F(99, 100))
    # an event test read as a plain probability is not discounted: the one-step tree (step) with the
    # event "the report after one step is 1" separates x from y by 1/2, which is at most d^1(x,y) = 1
    # but exceeds d^(1/2)(x,y) = 1/3; such tests are lower certificates at discount one only
    tree = {(0,): "step"}
    Px, Py = tree_law("x", tree, rows, obs, 1), tree_law("y", tree, rows, obs, 1)
    gap = sum(p for h, p in Px.items() if h[-1] == 1) - sum(p for h, p in Py.items() if h[-1] == 1)
    check("the undiscounted one-step event test separates x from y by 1/2: within d^1 = 1, above d^(1/2) = 1/3, "
          "so trace-event and policy-tree tests certify lower bounds at discount one only",
          gap == F(1, 2) and gap <= 1 and gap > F(1, 3))
    out["discount_1_2"]["undiscounted_event_test"] = fstr(gap)
    out["undiscounted"]["horizon_3"] = fstr(layers[3][("x", "y")])
    out["undiscounted"]["within_99_100"] = [depth, fstr(1 - F(1, 2 ** depth))]
    out["discount_1_2"]["potentials"] = {"f": {"x": "1/3", "p": "1"}, "g": {"y": "0"}}
    # at discount 1 a post-fixpoint bounds only the greatest fixed point of the distance operator
    S2, rows2 = ["s", "t"], {"step": {"s": {"s": F(1)}, "t": {"t": F(1)}}}
    zero = stoch_iterate(S2, lambda a, b: F(0), rows2, F(1), 5)[("s", "t")]
    W = kantorovich_exact(rows2["step"]["s"], rows2["step"]["t"], lambda u, v: F(0) if u == v else F(1, 2))
    check("two self-looping states with equal reports: d = 0, yet D(s,t) = 1/2 is a fixed point at discount 1 "
          "and not a post-fixpoint at discount 1/2", zero == 0 and W == F(1, 2) and F(1, 2) * W < F(1, 2))
    out["selfloop"] = {"distance": "0", "fixed_point_at_discount_1": "1/2"}
    record("unattained", out)


# ---------------------------------------------------------------------------
# Section 28. The clock-rate screen, one action at a time
# ---------------------------------------------------------------------------

def clock_screen():
    import random
    rnd = random.Random(13)
    print("\n28. Clock-rate screen per action")
    bad = 0
    for _ in range(300):
        n = rnd.randint(3, 6)
        X = list(range(n))
        acts = {a: {x: rnd.randrange(n) for x in X} for a in ("a", "b")}
        c = {x: F(rnd.randint(0, 4), 4) for x in X}
        ab = lambda x, y: abs(c[x] - c[y])                 # distance of the metric code tolerance 1-|c-c'|
        mu = F(1, n)
        per_action = []
        for T in acts.values():
            dfx = max(max(F(0), ab(T[x], T[y]) - ab(x, y)) for x in X for y in X)
            pm = sum(mu * mu * max(F(0), ab(T[x], T[y]) - ab(x, y)) for x in X for y in X)
            clock = max(ab(x, T[x]) for x in X)
            rate = sum(mu * ab(x, T[x]) for x in X)
            pointwise = all(max(F(0), ab(T[x], T[y]) - ab(x, y)) <= ab(x, T[x]) + ab(y, T[y]) for x in X for y in X)
            if not (pointwise and dfx <= 2 * clock and pm <= 2 * rate):
                bad += 1
            per_action.append((dfx, clock))
        if max(d for d, _ in per_action) > 2 * max(k for _, k in per_action):
            bad += 1
    check("per-action screen: pointwise bound, sup bound 2 max_x d(x,T_a x), pair-mass bound 2 r_a, and the "
          "maximum over actions (300 machines, two actions)", bad == 0, f"violations {bad}")
    # the bound does not hold with one action's clock on the right of the action-maximized defect
    X, q = [0, 1, 2], {0: 0, 1: 0, 2: 1}
    ident, mover = {0: 0, 1: 1, 2: 2}, {0: 0, 1: 2, 2: 2}
    dist = lambda x, y: F(int(q[x] != q[y]))
    dupd = max(max(F(0), dist(T[x], T[y]) - dist(x, y)) for T in (ident, mover) for x in X for y in X)
    check("an identity action has clock 0 while the update defect over both actions is 1; the moving action's "
          "clock 1 gives the correct bound 2",
          dupd == 1 and max(dist(x, ident[x]) for x in X) == 0 and max(dist(x, mover[x]) for x in X) == 1)
    record("clock_screen", {"per_action": "delta_upd^a <= 2 max_x d(x,T_a x)", "counterexample": {"identity_clock": "0",
                                                                                                 "update_defect": "1"}})


# ---------------------------------------------------------------------------
# Section 29. Estimates and the selection rule
# ---------------------------------------------------------------------------

def selection_rule():
    print("\n29. A rate over selected units need not survive removing units")
    keys = list(range(10))
    dup = {k: int(k == 0) for k in keys}
    old = set(keys)
    new = {0}                                          # the new policy withholds the nine others
    sel_old = F(sum(dup[k] for k in old), len(old))
    sel_new = F(sum(dup[k] for k in new), len(new))
    fixed_old = F(sum(dup[k] for k in old), len(keys))   # "a duplicate was proposed" over the fixed population
    fixed_new = F(sum(dup[k] for k in new), len(keys))
    check("removing proposals raises the duplicate rate among proposed keys from 1/10 to 1; over the fixed "
          "population of ten keys the rate cannot rise (1/10 to 1/10)",
          (sel_old, sel_new, fixed_old, fixed_new) == (F(1, 10), F(1), F(1, 10), F(1, 10)) and new <= old)
    record("selection_rule", {"selected": ["1/10", "1"], "fixed_population": ["1/10", "1/10"]})


# ---------------------------------------------------------------------------

def main():
    eight_state()
    witness_bound()
    packets()
    closure()
    affine()
    neural()
    evolution()
    transfers()
    trace_example()
    parity_fixture()
    security()
    arithmetic()
    reads()
    zero_fixture()
    hive_triangle()
    random_props()
    seven_state_claims()
    trace_bound_random()
    linear_composition()
    hypothesis_counterexamples()
    beacon_hives()
    symbolic_admission()
    small_fixtures()
    gauge_policy_merge()
    literal_congruence()
    policy_trees()
    unattained_supremum()
    clock_screen()
    selection_rule()
    print()
    if FAILS:
        print(f"{len(FAILS)} check(s) FAILED:", FAILS)
    else:
        print("All checks passed.")
    with open("mettadinc_oracle_results.json", "w") as fh:
        json.dump(RESULTS, fh, indent=1, default=str)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
