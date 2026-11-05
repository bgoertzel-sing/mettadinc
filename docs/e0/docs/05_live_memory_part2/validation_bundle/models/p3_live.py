"""Pattern 3 on a live store: evidence from an unbounded set of sources.

The identity-bounded statistic D_K keeps the set of distinct identifiers while it has fewer than K
elements and the marker TOP afterwards.  It answers min(K, number of distinct identifiers) exactly,
is maintained under insertions, merges by union and truncation, and is the coarsest statistic with
these properties.  The evidence consumers of Pattern 3 need D_2 for each polarity:
  contra  any contradicting incident        (minus statistic is not empty)
  eff     min(2, distinct supporting sources)
  regen   at least two distinct contradicting sources
"""
import random
from itertools import product

TOP = "TOP"


def dk_step(stat, x, K):
    if stat == TOP:
        return TOP
    s = stat | {x}
    return TOP if len(s) >= K else frozenset(s)


def dk_read(stat, K):
    return K if stat == TOP else len(stat)


def dk_merge(a, b, K):
    if a == TOP or b == TOP:
        return TOP
    s = a | b
    return TOP if len(s) >= K else frozenset(s)


EMPTY = frozenset()


def answers_from_stats(plus, minus):
    return {"contra": dk_read(minus, 2) >= 1, "eff": dk_read(plus, 2), "regen": dk_read(minus, 2) >= 2}


def answers_brute(incidents):
    sup = {s for s, pol in incidents if pol == "+"}
    con = {s for s, pol in incidents if pol == "-"}
    return {"contra": len(con) >= 1, "eff": min(2, len(sup)), "regen": len(con) >= 2}


def exhaustive(sources=("a", "b", "c", "d"), max_len=6):
    """Every sequence of incidents up to max_len over the given sources and both polarities: the
    statistic's answers equal the brute-force answers at every prefix."""
    alphabet = [(s, p) for s in sources for p in "+-"]
    checked = [0]
    ok = [True]

    def rec(prefix_inc, plus, minus, depth):
        checked[0] += 1
        if answers_from_stats(plus, minus) != answers_brute(prefix_inc):
            ok[0] = False
        if depth == max_len:
            return
        for (s, p) in alphabet:
            if p == "+":
                rec(prefix_inc + [(s, p)], dk_step(plus, s, 2), minus, depth + 1)
            else:
                rec(prefix_inc + [(s, p)], plus, dk_step(minus, s, 2), depth + 1)
    rec([], EMPTY, EMPTY, 0)
    return {"prefixes": checked[0], "ok": ok[0]}


def minimality(sources=("a", "b", "c"), K=2):
    """Distinct reachable statistic values are separated by a future insertion sequence: the
    statistic is the coarsest exact one.  Checked by search for a separating word of length <= K."""
    vals = {EMPTY}
    frontier = [EMPTY]
    while frontier:
        nxt = []
        for v in frontier:
            for s in sources:
                w = dk_step(v, s, K)
                if w not in vals:
                    vals.add(w)
                    nxt.append(w)
        frontier = nxt
    vals = sorted(vals, key=lambda v: (v == TOP, sorted(v) if v != TOP else []))
    words = [()]
    for L in range(1, K + 1):
        words += list(product(sources, repeat=L))

    def run(v, w):
        for s in w:
            v = dk_step(v, s, K)
        return dk_read(v, K)
    separated = all(any(run(u, w) != run(v, w) for w in words)
                    for i, u in enumerate(vals) for v in vals[i + 1:])
    return {"values": len(vals), "separated": separated}


def large_random(seed=1, n=100000, nsources=10000, Ks=(1, 2, 3, 5)):
    rng = random.Random(seed)
    stats = {K: EMPTY for K in Ks}
    seen = set()
    ok = True
    for t in range(n):
        x = rng.randrange(nsources) if rng.random() < 0.5 else rng.randrange(20)
        seen.add(x)
        for K in Ks:
            stats[K] = dk_step(stats[K], x, K)
        if t % 97 == 0 or t < 50:
            for K in Ks:
                if dk_read(stats[K], K) != min(K, len(seen)):
                    ok = False
    return {"incidents": n, "ok": ok}


def merges(seed=2, trials=20000, K=2, nsources=6):
    """Forks share a history, extend it separately and merge.  D_K merges exactly; totals counted
    by summing the forks' totals double count the shared history."""
    rng = random.Random(seed)
    exact, totals_wrong = True, 0
    for _ in range(trials):
        shared = [rng.randrange(nsources) for _ in range(rng.randint(0, 3))]
        f1 = shared + [rng.randrange(nsources) for _ in range(rng.randint(0, 3))]
        f2 = shared + [rng.randrange(nsources) for _ in range(rng.randint(0, 3))]
        s1 = s2 = EMPTY
        for x in f1:
            s1 = dk_step(s1, x, K)
        for x in f2:
            s2 = dk_step(s2, x, K)
        union_distinct = len(set(f1) | set(f2))
        if dk_read(dk_merge(s1, s2, K), K) != min(K, union_distinct):
            exact = False
        # totals: the merged history has len(shared) + extensions incidents, the summed totals more
        true_total = len(f1) + len(f2) - len(shared)
        if len(f1) + len(f2) != true_total:
            totals_wrong += 1
    return {"trials": trials, "dk_merge_exact": exact, "summed_totals_wrong": totals_wrong}


def withdrawal_counterexample():
    """D_2 cannot be maintained when sources can be withdrawn: two contradicting-source sets with the
    same D_2 value differ in the contradiction answer after the same withdrawals."""
    s1, s2 = {"a", "b"}, {"a", "b", "c"}
    d1, d2 = frozenset(s1) if len(s1) < 2 else TOP, frozenset(s2) if len(s2) < 2 else TOP
    after1, after2 = s1 - {"a", "b"}, s2 - {"a", "b"}
    return {"same_value_before": d1 == d2, "contra_after": (len(after1) >= 1, len(after2) >= 1)}


def smt_proof():
    """D_2 on an unbounded source sort, against the set S of distinct sources seen."""
    import z3
    Src = z3.DeclareSort("Src")
    S = z3.Array("S", Src, z3.BoolSort())
    tag, idv, s, x, y = z3.Int("tag"), z3.Const("id", Src), z3.Const("s", Src), z3.Const("x", Src), z3.Const("y", Src)

    def rel(Sv, tg, i):
        u, v, w = z3.Consts("u v w", Src)
        none_ = z3.And(tg == 0, z3.ForAll([u], z3.Not(z3.Select(Sv, u))))
        one = z3.And(tg == 1, z3.Select(Sv, i), z3.ForAll([u], z3.Implies(z3.Select(Sv, u), u == i)))
        many = z3.And(tg == 2, z3.Exists([v, w], z3.And(v != w, z3.Select(Sv, v), z3.Select(Sv, w))))
        return z3.Or(none_, one, many)

    def step(tg, i, sv):
        ntag = z3.If(tg == 0, 1, z3.If(tg == 1, z3.If(sv == i, 1, 2), 2))
        nid = z3.If(tg == 0, sv, i)
        return ntag, nid

    out = {}
    sol = z3.Solver()
    # initial state: the empty set is related to (0, any)
    E = z3.K(Src, False)
    sol.push()
    sol.add(z3.Not(rel(E, z3.IntVal(0), idv)))
    out["initial"] = str(sol.check())
    sol.pop()
    # maintenance: Rel(S, stat) implies Rel(S + s, step(stat, s))
    sol.push()
    nt, ni = step(tag, idv, s)
    sol.add(rel(S, tag, idv), z3.Not(rel(z3.Store(S, s, True), nt, ni)))
    out["step"] = str(sol.check())
    sol.pop()
    # reads: nonempty iff tag != 0; at least two iff tag == 2
    sol.push()
    nonempty = z3.Exists([x], z3.Select(S, x))
    two = z3.Exists([x, y], z3.And(x != y, z3.Select(S, x), z3.Select(S, y)))
    sol.add(rel(S, tag, idv), z3.Or(nonempty != (tag != 0), two != (tag == 2)))
    out["reads"] = str(sol.check())
    sol.pop()
    # merges: Rel(S1, stat1) and Rel(S2, stat2) imply Rel(S1 union S2, merge(stat1, stat2))
    S2 = z3.Array("S2", Src, z3.BoolSort())
    tag2, id2 = z3.Int("tag2"), z3.Const("id2", Src)
    mtag = z3.If(z3.Or(tag == 2, tag2 == 2), 2,
                 z3.If(tag == 0, tag2, z3.If(tag2 == 0, tag, z3.If(idv == id2, 1, 2))))
    mid = z3.If(tag == 0, id2, idv)
    sol.push()
    sol.add(rel(S, tag, idv), rel(S2, tag2, id2), z3.Not(rel(z3.SetUnion(S, S2), mtag, mid)))
    out["merge"] = str(sol.check())
    sol.pop()
    return out


if __name__ == "__main__":
    print(exhaustive())
    print(minimality())
    print(minimality(sources=("a", "b", "c", "d"), K=3))
    print(large_random())
    print(merges())
    print(smt_proof())
