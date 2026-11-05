#!/usr/bin/env python3
"""Oracle for Example 1 (belief-memory compaction).

Recomputes every number quoted for the example, checks it against the expected value, and writes
ex1_results.json.  Exact arithmetic throughout.  The machines are those of belief_memory.metta: the
reference evaluator (metta_eval.py) evaluates the module's maps, and the oracle checks, state by
state, that they define the observations, actions and encodings of the Python model in ex1lib.py;
the distance tables and every obligation below are computed from the module-derived successor
arrays.  Max-clique (networkx) and SAT (CaDiCaL 1.5.3 through python-sat) are used only for frontier
optimality.  Every satisfiable answer is replayed (a coloring's defect is recomputed from the
distance table, a set of centers is checked to cover every state), every clique is checked pair by
pair, and every unsatisfiable answer comes with a DRAT proof written to obligations/ together with
its CNF.  With MDINC_TOOLS naming a directory that holds drat-trim/drat-trim and cake_lpr/cake_lpr,
each proof is converted to LRAT and checked by cake_lpr, and the optimality claims that rest on a
refutation are Checked; without the tools those claims are reported as Conditional, with the
assumption (TrustedBackend cadical 1.5.3 SAT <digest of the obligations>).

Run: python3 ex1_oracle.py        (about four minutes; writes ex1_results.json and obligations/)
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from collections import deque

import networkx as nx
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

from ex1lib import *  # noqa: F401,F403
from metta_eval import World

RESULTS, FAILS, CLAIMS, CHECKS = {}, [], [], [0]
TOOLS = os.environ.get("MDINC_TOOLS", "")
PROOFS = bool(TOOLS) and os.path.exists(os.path.join(TOOLS, "drat-trim", "drat-trim")) and \
    os.path.exists(os.path.join(TOOLS, "cake_lpr", "cake_lpr"))
OUT = "obligations"
os.makedirs(OUT, exist_ok=True)
INDEX = []


def check(name, got, want):
    CHECKS[0] += 1
    ok = got == want
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": got {got!r}, want {want!r}"))
    if not ok:
        FAILS.append(name)
    RESULTS[name] = got if not isinstance(got, F) else str(got)


def sha(text):
    return "sha256:" + hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


def solve_logged(clauses, name, claim):
    """Solve with CaDiCaL 1.5.3; an unsatisfiable answer is written with its CNF and DRAT proof and,
    when the tools are present, converted to LRAT by drat-trim and checked by cake_lpr."""
    nv = max((abs(l) for c in clauses for l in c), default=0)
    sv = Solver(name="cadical153", with_proof=True, bootstrap_with=clauses)
    ok = sv.solve()
    model = sv.get_model() if ok else None
    rec = {"name": name, "claim": claim, "vars": nv, "clauses": len(clauses), "sat": ok}
    if not ok:
        dimacs = f"p cnf {nv} {len(clauses)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in clauses)
        rec["cnf"] = sha(dimacs)
        base = os.path.join(OUT, name)
        with open(base + ".cnf", "w") as f:
            f.write(dimacs)
        proof = sv.get_proof()
        with open(base + ".drat", "w") as f:
            f.write("\n".join(proof) + "\n")
        rec["drat_lines"] = len(proof)
        if PROOFS:
            p = subprocess.run([os.path.join(TOOLS, "drat-trim", "drat-trim"), base + ".cnf", base + ".drat",
                                "-L", base + ".lrat"], capture_output=True, text=True)
            rec["drat_trim"] = any(line.strip() == "s VERIFIED" for line in p.stdout.splitlines())
            q = subprocess.run([os.path.join(TOOLS, "cake_lpr", "cake_lpr"), "--CML_HEAP_SIZE=1024",
                                "--CML_STACK_SIZE=512", base + ".cnf", base + ".lrat"], capture_output=True, text=True)
            out = q.stdout.strip().splitlines()
            rec["cake_lpr"] = out[-1] if out else q.stderr.strip()[-80:]
            os.remove(base + ".lrat")
    rec["replayed"] = bool(rec.get("drat_trim")) and rec.get("cake_lpr") == "s VERIFIED UNSAT"
    sv.delete()
    INDEX.append(rec)
    return ok, model, rec


def assurance(refutations):
    """D2 status of an optimality claim: Checked by a clique, or by refutations whose proofs were
    replayed; Conditional on the solver otherwise."""
    if all(r["replayed"] for r in refutations):
        return "Checked", []
    digest = sha("\n".join(sorted(r["cnf"] for r in refutations)))
    return "Conditional", [f"(TrustedBackend cadical 1.5.3 SAT {digest})"]


def s(x):
    return str(x)


# ------------------------------------------------------------------ the module defines the model
T0 = time.time()
SOURCE = open("belief_memory.metta").read()
DIGEST = sha(SOURCE)
WLD = World("belief_memory.metta")


def machine_maps(mod, name):
    m, d = WLD.lookup(mod, name)
    obs = [(o[1], WLD.instance(m, o[2])) for o in d[2:] if isinstance(o, list) and o[0] == "Observe"]
    acts = [(a[1], WLD.instance(m, a[2])) for a in d[2:] if isinstance(a, list) and a[0] == "Action"]
    return obs, acts


SUCC_SRC, agree = {}, []
for mod, decay in (("BeliefMemory", "floor-halve"), ("GentleMemory", "gentle")):
    obs, acts = machine_maps(mod, "Report")
    dobs, dacts = machine_maps(mod, "Decide")
    SUCC_SRC[decay] = [np.array([IDX[f(x)] for x in STATES], dtype=np.int64) for _, f in acts]
    agree.append(([l for l, _ in obs], [l for l, _ in acts], [l for l, _ in dobs], [l for l, _ in dacts]) ==
                 (["strength", "confidence"], ACTIONS, ["status"], ACTIONS)
                 and all(obs[0][1](x) == strength(*x) and obs[1][1](x) == confidence(*x) and dobs[0][1](x) == status(*x)
                         for x in STATES)
                 and all(np.array_equal(a, b) for a, b in zip(SUCC_SRC[decay], successors(decay)))
                 and all(np.array_equal(a, b) for a, b in zip(SUCC_SRC[decay], [np.array([IDX[f(x)] for x in STATES])
                                                                                for _, f in dacts])))
ENC_SRC = {"RoundedTV20": "tv-grid-20", "RoundedTV10": "tv-grid-10", "Grid10x7": "tv-grid-10-7", "Buckets7": "buckets7",
           "Capped7": "cap7"}
ENC_MODEL = {"RoundedTV20": rounded_tv(20), "RoundedTV10": rounded_tv(10), "Grid10x7": rounded_tv(10, 7),
             "Buckets7": ENCODINGS["Buckets7"], "Capped7": ENCODINGS["Capped7"]}
enc_ok = all([WLD.instance("BeliefMemory", m)(x) for x in STATES] == code_of(ENC_MODEL[k]) for k, m in ENC_SRC.items())
check("module: the observations, actions and encodings of belief_memory.metta equal the model on all 256 states "
      "(both decay rules, both interfaces)", (agree, enc_ok), ([True, True], True))
RESULTS["source"] = {"file": "belief_memory.metta", "digest": DIGEST}

# ------------------------------------------------------------------ machines and tables
SUCC = {d: SUCC_SRC[d] for d in ("floor-halve", "gentle")}
TAB = {}
for d in SUCC:
    D1, r1 = fixpoint_table(SUCC[d])
    H = {h: horizon_table(SUCC[d], h) for h in range(0, 9)}
    Dg, rg = discounted_table(SUCC[d], F(9, 10))
    TAB[d] = {"D1": D1, "H": H, "Dg": Dg, "rounds": (r1, rg)}
check("floor-halve: rounds to the undiscounted / discounted fixpoint", TAB["floor-halve"]["rounds"], (15, 12))
check("gentle: rounds to the undiscounted / discounted fixpoint", TAB["gentle"]["rounds"], (23, 12))
ST = [status(*x) for x in STATES]

# ------------------------------------------------------------------ 1. decision interface
for d, want_hist, want_w in (("floor-halve", [3, 17, 68, 144, 206, 220, 225], "81/16384"),
                             ("gentle", [3, 15, 56, 126, 198, 240, 256], "1/256")):
    hist, blk = refine_counts(ST, SUCC[d])
    check(f"{d}: decision refinement classes by round", hist, want_hist)
    check(f"{d}: weakness of the decision quotient", s(weakness(classes_of(blk))), want_w)
hist, blk = refine_counts(ST, SUCC["floor-halve"])
merged = sorted(sorted(STATES[i] for i in b) for b in classes_of(blk) if len(b) > 1)
sat_pairs = sorted([[(k, 14), (k, 15)] for k in range(14)] + [[(14, k), (15, k)] for k in range(14)]
                   + [[(14, 14), (14, 15), (15, 14), (15, 15)]])
check("floor-halve: the only exact merges are the saturation pairs", merged, sorted(sat_pairs))
ledger = []
for r in range(0, 7):
    _, b = refine_counts(ST, SUCC["floor-halve"], max_rounds=r)
    ledger.append(s(weakness(classes_of(b))))
check("floor-halve: refinement ledger (weakness by round)", ledger,
      ["11931/32768", "7525/32768", "3953/32768", "59/2048", "143/16384", "11/2048", "81/16384"])
check("StatusOnly: update witness", update_witness(ST, SUCC["floor-halve"]),
      ((0, 0), (0, 3), "pos", "Uncertain", "Disbelieved"))
viol = violating_pairs(None, crisp_obs=ST)
w = canonical_witness(ST, SUCC["floor-halve"], viol, horizon=1)
check("StatusOnly: behavioral witness at horizon 1", (w["pair"], w["word"]), (((0, 0), (0, 3)), ["pos"]))
for h, want in ((1, ((0, 0), (0, 2), "pos")), (2, ((0, 0), (0, 1), "pos")), (3, ((0, 0), (6, 6), "pos"))):
    _, b = refine_counts(ST, SUCC["floor-halve"], max_rounds=h)
    check(f"staged partition P_{h}: update witness (InduceExact refuted)", update_witness(b, SUCC["floor-halve"])[:3], want)

# ------------------------------------------------------------------ 2. graded interface, candidate encodings
CANDS = dict(ENCODINGS)
CANDS["Grid10x7"] = rounded_tv(10, 7)
del CANDS["StatusOnly"]
EXPECT = {
    "floor-halve": {
        "RoundedTV20": (113, "5/104", ["5/104", "1/10", "1/4", "1/2", "1/2", "1/2", "1", "1", "1"], "1", "531441/1000000"),
        "RoundedTV10": (53, "33/340", ["33/340", "1/5", "1/2", "1", "1", "1", "1", "1", "1"], "1", "729/1000"),
        "Buckets7": (49, "1/5", ["1/5", "1/5", "1/3", "1", "1", "1", "1", "1", "1"], "1", "729/1000"),
        "Capped7": (64, "4/11", ["4/11", "2/5", "1/2", "1", "1", "1", "1", "1", "1"], "1", "729/1000"),
    },
    "gentle": {
        "RoundedTV20": (113, "5/104", ["5/104", "3/22", "1/7", "3/20", "3/20", "1/5", "1/5", "1/5", "1/5"], "1/5", "27/220"),
        "RoundedTV10": (53, "33/340", ["33/340", "3/20", "1/5", "1/5", "1/5", "1/5", "1/5", "7/30", "7/30"], "7/30", "81/500"),
        "Buckets7": (49, "1/5", ["1/5", "1/4", "1/4", "1/4", "1/4", "1/4", "1/4", "1/4", "1/4"], "1/4", "9/40"),
        "Capped7": (64, "4/11", ["4/11"] * 9, "4/11", "4/11"),
        "Grid10x7": (43, None, None, "1/5", None),
    },
}
for d, table in EXPECT.items():
    for name, (codes, now, hs, beh, disc) in table.items():
        code = code_of(CANDS[name]); bl = classes_of(code)
        got = [len(bl), s(defect_val(bl, R0)), [s(defect_val(bl, TAB[d]["H"][h])) for h in range(9)],
               s(defect_val(bl, TAB[d]["D1"])), s(defect_val(bl, TAB[d]["Dg"]))]
        want = [codes, now, hs, beh, disc]
        got = [g if wnt is not None else None for g, wnt in zip(got, want)]
        check(f"{d}: {name} codes, now, horizons 0-8, undiscounted, discounted 9/10", got, want)
        check(f"{d}: {name} update defect with crisp codes", 0 if update_witness(code, SUCC[d]) is None else 1, 1)
check("RoundedTV20: update witness", update_witness(code_of(CANDS["RoundedTV20"]), SUCC["floor-halve"]),
      ((0, 7), (0, 8), "pos", (3, 13), (2, 14)))


def witness(d, name, bound):
    code = code_of(CANDS[name])
    w = canonical_witness(code, SUCC[d], violating_pairs(bound))
    if w is None:
        return None
    x, y = w["pair"]
    ex, ey = run(x, w["word"], d)[-1], run(y, w["word"], d)[-1]
    return (w["pair"], w["word"], ex, ey)


check("floor-halve: RoundedTV20 within 1/5 refuted, canonical witness", witness("floor-halve", "RoundedTV20", F(1, 5)),
      (((3, 11), (4, 14)), ["decay", "decay"], (0, 2), (1, 3)))
check("floor-halve: RoundedTV20 within 1/2 refuted, canonical witness", witness("floor-halve", "RoundedTV20", F(1, 2)),
      (((11, 12), (12, 11)), ["decay", "decay", "pos", "neg", "decay", "decay"], (0, 1), (1, 0)))
check("gentle: RoundedTV20 within 1/5 checked", witness("gentle", "RoundedTV20", F(1, 5)), None)
check("gentle: RoundedTV20 within 3/20 refuted, canonical witness", witness("gentle", "RoundedTV20", F(3, 20)),
      (((4, 10), (5, 11)), ["decay", "decay", "pos", "pos", "decay"], (2, 3), (4, 3)))

# distance distribution: the gap under floor-halving and the floor under the gentle rule
for d, want in (("floor-halve", (34, 34, 10788, 14161, "1/58")), ("gentle", (0, 7561, 25983, 225, "6/35"))):
    D1 = TAB[d]["D1"]
    vs = [VALS[D1[i, j]] for i in range(N) for j in range(i + 1, N)]
    got = (sum(v <= F(1, 29) for v in vs), sum(v <= F(2, 5) if d == "floor-halve" else v <= F(1, 5) for v in vs),
           sum(v <= F(1, 2) for v in vs), sum(v == 1 for v in vs), s(min(vs)))
    check(f"{d}: pairs <= 1/29, <= 2/5 (resp. 1/5), <= 1/2, = 1; least distance", got, want)
check("gentle: (14,14) and (15,15) are 6/35 apart", s(VALS[TAB["gentle"]["D1"][IDX[(14, 14)], IDX[(15, 15)]]]), "6/35")

# ------------------------------------------------------------------ 3. decay rules
code20 = code_of(CANDS["RoundedTV20"]); bl20 = classes_of(code20)
DECAY_EXPECT = {"floor-halve": ("1", 225, "1/58"), "ceil-halve": ("1/3", 256, "1/6"),
                "floor-halve-if-t>=8": ("4/15", 225, "1/58"), "gentle": ("1/5", 256, "6/35"),
                "minus-one": ("1", 256, "1/2")}
for d, want in DECAY_EXPECT.items():
    sc = successors(d)
    D1, _ = fixpoint_table(sc)
    hist, _ = refine_counts(ST, sc)
    off = D1 + np.eye(N, dtype=np.int64) * 10 ** 6
    check(f"decay rule {d}: RoundedTV20 defect, decision classes, least distance",
          (s(defect_val(bl20, D1)), hist[-1], s(VALS[int(off.min())])), want)


# ------------------------------------------------------------------ 4. frontiers
FRONTIER = {}


def lim_of(vals, bound):
    return max((k for k, v in enumerate(vals) if v <= bound), default=-1)


def conflict_graph(D, bound, vals=VALS):
    lim = lim_of(vals, bound)
    G = nx.Graph(); G.add_nodes_from(range(N))
    G.add_edges_from((i, j) for i in range(N) for j in range(i + 1, N) if D[i, j] > lim)
    return G


def is_clique(G, cl):
    return all(G.has_edge(a, b) for x, a in enumerate(cl) for b in cl[x + 1:])


def colorable(G, k, clique, tag, claim):
    """k-coloring of the conflict graph; the states of the clique are fixed to the first colors,
    which excludes no coloring up to a renaming of colors."""
    var = lambda v, c: v * k + c + 1  # noqa: E731
    cls = [[var(v, c) for c in range(k)] for v in range(N)]
    for (i, j) in sorted(G.edges()):
        for c in range(k):
            cls.append([-var(i, c), -var(j, c)])
    for c, v in enumerate(clique[:k]):
        cls.append([var(v, c)])
    ok, model, rec = solve_logged(cls, f"{tag}_colors{k}", claim)
    if not ok:
        return None, rec
    pos = {x for x in model if x > 0}
    return [next(c for c in range(k) if var(v, c) in pos) for v in range(N)], rec


def by_components(G, D, lim):
    """Exact frontier when the compatible pairs (the complement of G) form small components: a
    state of one component conflicts with every state of another, so the fewest codes is the sum,
    over components, of the least number of compatible blocks covering the component, and the
    largest clique is the sum of the largest sets of pairwise conflicting states in each."""
    H = nx.complement(G)
    comps = [sorted(c) for c in nx.connected_components(H)]
    if max(len(c) for c in comps) > 6:
        return None
    from itertools import combinations
    coloring, clique, nxt = [0] * N, [], 0
    for comp in sorted(comps):
        best = None
        for r in range(1, len(comp) + 1):
            for labels in __import__("itertools").product(range(r), repeat=len(comp)):
                if len(set(labels)) != r or labels[0] != 0:
                    continue
                if all(D[a, b] <= lim for (a, la), (b, lb) in combinations(zip(comp, labels), 2) if la == lb):
                    best = labels
                    break
            if best is not None:
                break
        for v, l in zip(comp, best):
            coloring[v] = nxt + l
        nxt += max(best) + 1
        indep = max((c for r in range(len(comp), 0, -1) for c in combinations(comp, r)
                     if all(D[a, b] > lim for a, b in combinations(c, 2))), key=len)
        clique += list(indep)
    return sorted(clique), coloring


def min_codes(D, bound, tag, vals=VALS):
    """(largest clique, fewest codes) with both certificates replayed; refutation of one code fewer
    by the solver when the two differ."""
    G = conflict_graph(D, bound, vals)
    lim = lim_of(vals, bound)
    comp = by_components(G, D, lim)
    if comp is not None:
        clique, col = comp
        refutation = None
        omega, k = len(clique), len(set(col))
    else:
        clique, omega = nx.max_weight_clique(G, weight=None)
        clique = sorted(clique)
        k, refutation = omega, None
        while True:
            col, rec = colorable(G, k, clique, tag, f"{tag}: no summary within {bound} has {k} codes")
            if col is not None:
                break
            refutation = rec
            k += 1
    assert is_clique(G, clique) and len(clique) == omega
    assert max((D[a, b] for bl in classes_of(col) for a in bl for b in bl), default=0) <= lim and len(set(col)) == k
    with open(os.path.join(OUT, f"{tag}_certificate.json"), "w") as f:
        json.dump({"bound": str(bound), "codes": k, "clique": [STATES[v] for v in clique],
                   "coloring": col, "refutation": refutation and refutation["name"]}, f)
    status, assumptions = ("Checked", []) if k == omega else assurance([refutation])
    FRONTIER[tag] = {"bound": str(bound), "clique": omega, "codes": k, "status": status, "assumptions": assumptions,
                     "certificate": "clique" if k == omega else "refutation of " + str(k - 1)}
    return omega, k


for d, bound, want in (("floor-halve", F(1, 5), (225, 225)), ("floor-halve", F(2, 5), (225, 225)),
                       ("floor-halve", F(1, 2), (17, 17)),
                       ("gentle", F(6, 35), (32, 33)), ("gentle", F(1, 5), (20, 21)), ("gentle", F(1, 4), (18, 19)),
                       ("gentle", F(3, 10), (12, 12)), ("gentle", F(1, 3), (8, 8)), ("gentle", F(2, 5), (6, 6)),
                       ("gentle", F(1, 2), (4, 5))):
    tag = f"{d}_codes_{bound.numerator}_{bound.denominator}"
    check(f"{d}: frontier at {bound}, codes objective (clique bound, minimum)", min_codes(TAB[d]["D1"], bound, tag), want)
fl = TAB["floor-halve"]["D1"]
small = sorted((STATES[i], STATES[j], s(VALS[fl[i, j]])) for i in range(N) for j in range(i + 1, N) if VALS[fl[i, j]] <= F(1, 29))
check("floor-halve: the 34 pairs within 1/29: 33 at distance 1/58, and ((14,15),(15,14)) at 1/29",
      (len(small), sum(v == "1/58" for _, _, v in small), [(a, b) for a, b, v in small if v != "1/58"]),
      (34, 33, [((14, 15), (15, 14))]))
check("floor-halve: frontier below 1/58, at 1/58, between 1/58 and 1/29, and at 1/29 (clique bound, minimum)",
      [min_codes(fl, b, f"floor-halve_codes_{b.numerator}_{b.denominator}") for b in (F(1, 100), F(1, 58), F(1, 40), F(1, 29))],
      [(256, 256), (226, 226), (226, 226), (225, 225)])


def min_centers(D, eps, k_expect, tag):
    """[k-1 centers satisfiable?, k centers satisfiable?]; the k centers found are checked to cover
    every state, and the refutation of k-1 is proof-logged."""
    lim = lim_of(VALS, eps)
    out = []
    for k in (k_expect - 1, k_expect):
        cls = [[c + 1 for c in range(N) if D[x, c] <= lim] for x in range(N)]
        enc = CardEnc.atmost(lits=list(range(1, N + 1)), bound=k, top_id=N, encoding=EncType.seqcounter)
        cls += [list(c) for c in enc.clauses]
        ok, model, rec = solve_logged(cls, f"{tag}_centers{k}", f"{tag}: no {k} centers cover every state within {eps}")
        if ok:
            centers = [c for c in range(N) if model[c] > 0]
            assert len(centers) <= k and all(any(D[x, c] <= lim for c in centers) for x in range(N))
            with open(os.path.join(OUT, f"{tag}_centers{k}.solution.json"), "w") as f:
                json.dump({"radius": str(eps), "centers": [STATES[c] for c in centers]}, f)
        else:
            FRONTIER[tag] = {"radius": str(eps), "centers": k_expect, "certificate": f"refutation of {k}",
                             "status": assurance([rec])[0], "assumptions": assurance([rec])[1]}
        out.append(ok)
    return out


check("gentle: radius 1/5 needs 10 centers (9 refuted, 10 found)",
      min_centers(TAB["gentle"]["D1"], F(1, 5), 10, "gentle_radius_1_5"), [False, True])
check("gentle: radius 6/35 needs 12 centers (11 refuted, 12 found)",
      min_centers(TAB["gentle"]["D1"], F(6, 35), 12, "gentle_radius_6_35"), [False, True])

# declared families (exhaustive) at 1/5 under the gentle rule
INTERVALS = [(a, b) for a in range(C + 1) for b in range(a, C + 1)]
IID = {iv: k for k, iv in enumerate(INTERVALS)}
D1 = TAB["gentle"]["D1"]
M = np.zeros((len(INTERVALS), len(INTERVALS)), dtype=np.int64)
for (a, b) in INTERVALS:
    for (c2, d2) in INTERVALS:
        ids = [IDX[(p, n)] for p in range(a, b + 1) for n in range(c2, d2 + 1)]
        M[IID[(a, b)], IID[(c2, d2)]] = D1[np.ix_(ids, ids)].max()
lim = max(k for k, v in enumerate(VALS) if v <= F(1, 5))
best = None
for mask in range(1 << C):
    ivs, start = [], 0
    for k in range(C):
        if mask >> k & 1:
            ivs.append((start, k)); start = k + 1
    ivs.append((start, C))
    ids = [IID[iv] for iv in ivs]
    if M[np.ix_(ids, ids)].max() <= lim:
        cand = (len(ivs) ** 2, ivs)
        if best is None or cand[0] < best[0]:
            best = cand
check("gentle: best tied bucketing at 1/5 (32768 candidates)", best,
      (49, [(0, 0), (1, 1), (2, 2), (3, 4), (5, 7), (8, 10), (11, 15)]))
bestg = None
for gs in range(1, 41):
    for gc in range(1, 41):
        bl = classes_of(code_of(rounded_tv(gs, gc)))
        if defect_val(bl, D1) <= F(1, 5):
            if bestg is None or len(bl) < bestg[0]:
                bestg = (len(bl), (gs, gc))
check("gentle: best rounding grid at 1/5 (1600 candidates)", bestg, (43, (10, 7)))


# ------------------------------------------------------------------ 5. induced machines
def induce(code, d, horizon=None):
    succ, D = SUCC[d], TAB[d]["D1"]
    codes, seen = [], {}
    for c in code:
        if c not in seen:
            seen[c] = len(codes); codes.append(c)
    members = [[] for _ in codes]
    for i, c in enumerate(code):
        members[seen[c]].append(i)
    rep = [min((max(D[x, r] for x in m), r) for r in m)[1] for m in members]
    radius = max(D[x, rep[seen[code[x]]]] for x in range(N))
    qcode = np.array([seen[c] for c in code])
    qsucc = [qcode[sa[np.array(rep)]] for sa in succ]
    R = R0[:, rep]; Dm = R.copy(); it = 0
    while True:
        D2 = R.copy()
        for a, sa in enumerate(succ):
            np.maximum(D2, Dm[np.ix_(sa, qsucc[a])], out=D2)
        it += 1
        if horizon is not None and it >= horizon:
            Dm = D2; break
        if horizon is None and np.array_equal(D2, Dm):
            break
        Dm = D2
    return s(VALS[int(radius)]), s(VALS[int(Dm[np.arange(N), qcode].max())])


check("gentle: InduceApprox RoundedTV20 radius and arrow defect", induce(code20, "gentle"), ("6/35", "20/63"))
check("gentle: InduceApprox RoundedTV20 arrow defect at horizons 1-4",
      [induce(code20, "gentle", h)[1] for h in (1, 2, 3, 4)], ["3/22", "3/22", "3/20", "6/35"])
check("gentle: InduceApprox Grid10x7 radius and arrow defect", induce(code_of(CANDS["Grid10x7"]), "gentle"), ("6/35", "29/55"))
check("floor-halve: InduceApprox RoundedTV20 radius and arrow defect", induce(code20, "floor-halve"), ("1/2", "2/3"))

# ------------------------------------------------------------------ 6. product rule (small instance)
ok_all = True
for decay in (lambda p, n: (p // 2, n // 2), lambda p, n: ((p + 1) // 2, (n + 1) // 2) if p + n >= 4 else (p, n)):
    Cs = 3
    S1 = [(p, n) for p in range(Cs + 1) for n in range(Cs + 1)]; i1 = {x: k for k, x in enumerate(S1)}
    ps = lambda p, n: (min(p + 1, Cs), n); ng = lambda p, n: (p, min(n + 1, Cs))
    tvf = lambda p, n: (F(p, p + n) if p + n else F(1, 2), F(p + n, p + n + 4))
    d0 = lambda a, b: max(abs(tvf(*a)[0] - tvf(*b)[0]), abs(tvf(*a)[1] - tvf(*b)[1]))
    P = [(a, b) for a in S1 for b in S1]; ip = {x: k for k, x in enumerate(P)}
    s1 = [np.array([i1[f(*x)] for x in S1]) for f in (ps, ng, decay)]
    s2 = [np.array([ip[f(x)] for x in P]) for f in (lambda x: (ps(*x[0]), x[1]), lambda x: (ng(*x[0]), x[1]),
                                                     lambda x: (x[0], ps(*x[1])), lambda x: (x[0], ng(*x[1])),
                                                     lambda x: (decay(*x[0]), decay(*x[1])))]
    for gamma in (F(1), F(9, 10)):
        A, _ = discounted_table(s1, gamma, np.array([[d0(a, b) for b in S1] for a in S1], dtype=object))
        B, _ = discounted_table(s2, gamma, np.array([[max(d0(x[0], y[0]), d0(x[1], y[1])) for y in P] for x in P], dtype=object))
        ok_all &= all(B[ip[x], ip[y]] == max(A[i1[x[0]], i1[y[0]]], A[i1[x[1]], i1[y[1]]]) for x in P for y in P)
check("product rule: distance of two copies with shared decay = max of component distances", ok_all, True)

# ------------------------------------------------------------------ 7. receipt ledger and merges
NAMES = ["u1", "u2", "u3", "u4", "v1", "v2"]
RS = list(range(64))
cnt = lambda x: (bin(x & 0b001111).count("1"), bin(x & 0b110000).count("1"))
tvc = lambda c: (F(c[0], c[0] + c[1]) if c[0] + c[1] else F(1, 2), F(c[0] + c[1], c[0] + c[1] + 4))
dc = lambda a, b: max(abs(tvc(a)[0] - tvc(b)[0]), abs(tvc(a)[1] - tvc(b)[1]))
nm = lambda x: "{" + ",".join(NAMES[i] for i in range(6) if x >> i & 1) + "}"
code = [cnt(x) for x in RS]
hear = [np.array([x | (1 << i) for x in RS]) for i in range(6)]
trans = [np.array([x | c for x in RS]) for c in RS]
D0r = np.array([[dc(code[x], code[y]) for y in RS] for x in RS], dtype=object)
wit = None
for x in RS:
    for y in RS:
        if y > x and code[x] == code[y] and wit is None:
            for i in range(6):
                if code[x | (1 << i)] != code[y | (1 << i)]:
                    wit = (nm(x), nm(y), "hear-" + NAMES[i], code[x | (1 << i)], code[y | (1 << i)]); break
check("Counts: update witness", wit, ("{u1}", "{u2}", "hear-u1", (1, 0), (2, 0)))
for label, sc in (("hear actions", hear), ("hear actions and merge translations", hear + trans)):
    Dr, _ = discounted_table(sc, F(1), D0r)
    dmax = max(Dr[x, y] for x in RS for y in RS if code[x] == code[y])
    check(f"Counts: behavioral defect with {label}", s(dmax), "1/3")
pairs = [(x, y) for x in RS for y in RS]
add = lambda x, y: (code[x][0] + code[y][0], code[x][1] + code[y][1])
mx = lambda x, y: (max(code[x][0], code[y][0]), max(code[x][1], code[y][1]))
for label, f, want in (("AddMerge", add, ("6/35", ("{u1,u2,u3}", "{u1,u2,u3}"))),
                       ("MaxMerge", mx, ("6/35", ("{u1,u2,v1}", "{u3,u4,v2}")))):
    e = max(dc(f(x, y), code[x | y]) for x, y in pairs)
    a = min((x, y) for x, y in pairs if dc(f(x, y), code[x | y]) == e)
    check(f"{label}: worst error and least witness", (s(e), (nm(a[0]), nm(a[1]))), want)
outs = [(p, q) for p in range(9) for q in range(5)]
groups = {}
for x, y in pairs:
    groups.setdefault((code[x], code[y]), set()).add(code[x | y])
floor_ = max(min(max(dc(o, i) for i in ideals) for o in outs) for ideals in groups.values())
check("no merge on counts has worst error below", s(floor_), "6/35")
tri = [(b, x, y) for b in RS for x in RS for y in RS if (b & x) == b and (b & y) == b]
three = lambda b, x, y: (code[x][0] + code[y][0] - code[b][0], code[x][1] + code[y][1] - code[b][1])
e_all = max(dc(three(*t), code[t[1] | t[2]]) for t in tri)
e_clean = max(dc(three(*t), code[t[1] | t[2]]) for t in tri if ((t[1] ^ t[0]) & (t[2] ^ t[0])) == 0)
check("ThreeWay: worst error over all forks / forks with disjoint news", (s(e_all), s(e_clean)), ("6/35", "0"))

# compaction below a fork horizon, with and without a delivery protocol (the module's own maps)
compact = WLD.instance("ReceiptLedger", "compact")
lstr, lconf = WLD.instance("ReceiptLedger", "ledger-strength"), WLD.instance("ReceiptLedger", "ledger-confidence")
check("module: counts, ledger-strength and ledger-confidence of ReceiptLedger equal the model on all 64 receipt sets",
      all(WLD.instance("ReceiptLedger", "counts")(x) == cnt(x) and (lstr(x), lconf(x)) == tvc(cnt(x)) for x in RS), True)
CC = [compact(x) for x in RS]
led_obs, led_acts = machine_maps("ReceiptLedger", "Ledger")
set_obs, set_acts = machine_maps("ReceiptLedger", "SettledLedger")


def updates_witness(code, acts):
    for x in RS:
        for y in RS:
            if y > x and code[x] == code[y]:
                for lab, f in acts:
                    if code[f(x)] != code[f(y)]:
                        return (nm(x), nm(y), lab, code[f(x)], code[f(y)])
    return None


def ledger_distance(acts):
    sc = [np.array([f(x) for x in RS]) for _, f in acts]
    D, _ = discounted_table(sc, F(1), D0r)
    return D


def behavioral_witness(code, acts, bound):
    """Shortest word, then least same-code pair, then least word, to an observation gap above bound."""
    best = None
    for x in RS:
        for y in RS:
            if y > x and code[x] == code[y]:
                prev, frontier = {(x, y): None}, [(x, y)]
                hit = (x, y) if D0r[x, y] > bound else None
                while hit is None and frontier:
                    nxt = []
                    for p in frontier:
                        for a, (lab, f) in enumerate(acts):
                            q = (f(p[0]), f(p[1]))
                            if q not in prev:
                                prev[q] = (p, lab)
                                nxt.append(q)
                                if hit is None and D0r[q] > bound:
                                    hit = q
                    frontier = nxt
                if hit is not None:
                    w, z = [], hit
                    while prev[z] is not None:
                        z, lab = prev[z]
                        w.append(lab)
                    cand = (len(w), x, y, list(reversed(w)), hit)
                    if best is None or cand[:3] < best[:3]:
                        best = cand
    return best


check("Compacted on Ledger (every hear action allowed): CheckUpdates refuted (pair, action, codes after)",
      updates_witness(CC, led_acts), ("{u1}", "{u2}", "hear-u1", (1, 0), (2, 0)))
bw = behavioral_witness(CC, led_acts, F(1, 10))
check("Compacted: CheckBehavioral within 1/10 refuted (word, pair, confidence after the word, gap)",
      (bw[3], nm(bw[1]), nm(bw[2]), s(lconf(bw[4][0])), s(lconf(bw[4][1])), s(D0r[bw[4]])),
      (["hear-u1"], "{u1}", "{u2}", "1/5", "1/3", "2/15"))
Dl = ledger_distance(led_acts)
check("Compacted: MeasureBehavioral (the largest distance between two receipt sets with the same code)",
      s(max(Dl[x, y] for x in RS for y in RS if CC[x] == CC[y])), "1/6")
check("CompactedSettled on SettledLedger (the protocol: u1 and u2 never delivered again): CheckUpdates checked, "
      "MeasureBehavioral 0", (updates_witness(CC, set_acts), s(max(ledger_distance(set_acts)[x, y] for x in RS for y in RS
                                                                   if CC[x] == CC[y]))), (None, "0"))
cmerge = WLD.instance("ReceiptLedger", "compact-merge")
merged = WLD.instance("ReceiptLedger", "merged-tally")
same_old = WLD.instance("ReceiptLedger", "same-old")
errs = {(x, y): dc(cmerge((x, y)), merged((x, y))) for x, y in pairs}
worst = max(errs.values())
least_pos = min(p for p in pairs if errs[p] > 0)
check("CompactMerge over all fork pairs refuted (worst error, least witness, its error); over forks that share the "
      "compacted part checked with error 0",
      (s(worst), (nm(least_pos[0]), nm(least_pos[1])), s(errs[least_pos]),
       s(max(errs[p] for p in pairs if same_old(p)))), ("2/3", ("{}", "{u1}"), "1/2", "0"))

# ------------------------------------------------------------------ 8. further figures of the write-up
# (the floor, the slow pair, the discounted frontier, more radius frontiers, the greedy weakness
#  search, the horizon at which the induced machine reaches its full drift, and running on codes
#  across the rounding-grid family)
D1g = TAB["gentle"]["D1"]
floor_rank = VALS.index(F(6, 35))
check("gentle: pairs of states at the floor 6/35",
      sum(1 for i in range(N) for j in range(i + 1, N) if D1g[i, j] == floor_rank), 5106)
i14, i15 = IDX[(14, 14)], IDX[(15, 15)]
seen, dq, reach = {(i14, i15): 0}, deque([(i14, i15)]), None
while dq:
    a, b = dq.popleft()
    if R0[a, b] >= floor_rank:
        reach = seen[(a, b)]
        break
    for sa in SUCC["gentle"]:
        nxt = (int(sa[a]), int(sa[b]))
        if nxt not in seen:
            seen[nxt] = seen[(a, b)] + 1
            dq.append(nxt)
check("gentle: (14,14) and (15,15): current distance, shortest word reaching the floor",
      (s(VALS[R0[i14, i15]]), reach), ("1/136", 11))


def to_rank(Dg):
    vals = sorted({Dg[i, j] for i in range(N) for j in range(N)})
    rk = {v: k for k, v in enumerate(vals)}
    return np.array([[rk[Dg[i, j]] for j in range(N)] for i in range(N)], dtype=np.int64), vals


for d, want in (("gentle", [(256, 256), (54, 54), (26, 26), (15, 15)]),
                ("floor-halve", [(225, 225)] * 4)):
    Dr, vals = to_rank(TAB[d]["Dg"])
    check(f"{d}: discounted 9/10 frontier at 1/20, 1/10, 3/20, 1/5 (clique bound, minimum)",
          [min_codes(Dr, b, f"{d}_discounted_codes_{b.numerator}_{b.denominator}", vals)
           for b in (F(1, 20), F(1, 10), F(3, 20), F(1, 5))], want)
check("gentle: radius frontier at 1/4, 1/3, 1/2 (k-1 refuted, k found)",
      [min_centers(D1g, e, k, f"gentle_radius_{e.numerator}_{e.denominator}") for e, k in ((F(1, 4), 10), (F(1, 3), 4), (F(1, 2), 2))],
      [[False, True]] * 3)
CENTERS = [(0, 0), (0, 2), (0, 8), (1, 2), (2, 0), (3, 11), (4, 2), (7, 8), (8, 0), (11, 3)]
lim5 = max(k for k, v in enumerate(VALS) if v <= F(1, 5))
check("gentle: the quoted ten centers cover every state within 1/5",
      all(any(D1g[x, IDX[c]] <= lim5 for c in CENTERS) for x in range(N)), True)


def greedy(D, lim):
    """Complete-linkage agglomeration: merge the admissible pair of classes with the largest
    weakness gain |A||B|; ties by the least (min member of A, min member of B)."""
    cl = [[i] for i in range(N)]; alive = list(range(N)); size = {i: 1 for i in range(N)}
    diam = {i: 0 for i in range(N)}; CD = D.copy()
    while True:
        bestp = None
        for x in range(len(alive)):
            A = alive[x]
            for y in range(x + 1, len(alive)):
                B = alive[y]
                m = max(CD[A, B], diam[A], diam[B])
                if m <= lim:
                    key = (-size[A] * size[B], min(cl[A]), min(cl[B]))
                    if bestp is None or key < bestp[0]:
                        bestp = (key, A, B, m)
        if bestp is None:
            break
        _, A, B, m = bestp
        cl[A] += cl[B]; size[A] += size[B]; diam[A] = m; alive.remove(B)
        for Z in alive:
            if Z != A:
                v = max(CD[A, Z], CD[B, Z]); CD[A, Z] = v; CD[Z, A] = v
    return [cl[A] for A in alive]


gb = greedy(D1g, lim5)
check("gentle: greedy weakness search at 1/5 (classes, weakness, defect within bound)",
      (len(gb), s(weakness(gb)), defect_val(gb, D1g) <= F(1, 5)), (24, "1187/16384", True))
full = induce(code20, "gentle")[1]
h = 1
while induce(code20, "gentle", h)[1] != full:
    h += 1
check("gentle: InduceApprox RoundedTV20 first reaches its full drift at horizon", h, 33)
best_run = min((F(induce(code_of(rounded_tv(gs, gc)), "gentle")[1]), (gs, gc))
               for gs in range(1, 41) for gc in range(1, 41))
check("gentle: least arrow defect running on codes over the 1600 rounding grids (center representatives)",
      (s(best_run[0]), best_run[0] > F(1, 4)), ("4/15", True))
check("bits for six beliefs (raw, decision quotient, RoundedTV20, Grid10x7, 21 codes, 10 centers)",
      [round(6 * math.log2(k), 1) for k in (256, 225, 113, 43, 21, 10)], [48.0, 46.9, 40.9, 32.6, 26.4, 19.9])

# ------------------------------------------------------------------ 9. assurance of the optimality claims
refs = [r for r in INDEX if not r["sat"]]
want = "Checked" if PROOFS else "Conditional"
if PROOFS:
    check("frontier: every refutation (codes at 6/35, 1/5, 1/4, 1/2; centers at 6/35, 1/5, 1/4, 1/3, 1/2) has a DRAT "
          "proof that drat-trim converted to LRAT and cake_lpr checked",
          (len(refs), all(r["replayed"] for r in refs)), (9, True))
check("frontier: the nine refuted obligations (variables, clauses), codes at 6/35, 1/5, 1/4, 1/2, centers at 6/35, "
      "1/5, 1/4, 1/3, 1/2", {r["name"]: (r["vars"], r["clauses"]) for r in refs},
      {"gentle_codes_6_35_colors32": (8192, 881376), "gentle_codes_1_5_colors20": (5120, 501856),
       "gentle_codes_1_4_colors18": (4608, 432022), "gentle_codes_1_2_colors4": (1024, 26888),
       "gentle_radius_6_35_centers11": (2951, 5880), "gentle_radius_1_5_centers9": (2479, 4940),
       "gentle_radius_1_4_centers9": (2479, 4940), "gentle_radius_1_3_centers3": (1015, 2024),
       "gentle_radius_1_2_centers1": (511, 1020)})
check("claims: Fewest at 1/5 (21 codes) and FewestCenters at 1/5 (10 centers); the cliques alone at 3/10, 1/3, 2/5",
      (FRONTIER["gentle_codes_1_5"]["status"], FRONTIER["gentle_radius_1_5"]["status"],
       [FRONTIER[f"gentle_codes_{b}"]["status"] for b in ("3_10", "1_3", "2_5")]),
      (want, want, ["Checked", "Checked", "Checked"]))
for tag, f in sorted(FRONTIER.items()):
    CLAIMS.append({"request": tag, "status": f["status"],
                   "assurance": "Replayed" if f["status"] == "Checked" else "TrustedBackend",
                   "values": {k: v for k, v in f.items() if k not in ("status", "assumptions")},
                   "assumptions": f["assumptions"],
                   "binding": {"module_digest": DIGEST, "file": "belief_memory.metta",
                               "module": "BeliefMemory" if tag.startswith("floor") else "GentleMemory",
                               "declarations": ["Report", "WeakestWithin"]}})
with open(os.path.join(OUT, "index.json"), "w") as f:
    json.dump({"solver": ["cadical", "1.5.3"], "module_digest": DIGEST,
               "replayed_with": "drat-trim -L, cake_lpr --CML_HEAP_SIZE=1024 --CML_STACK_SIZE=512" if PROOFS else None,
               "obligations": INDEX}, f, indent=1)
RESULTS["claims"] = CLAIMS
RESULTS["proofs"] = {"refutations": len(refs), "replayed": sum(r["replayed"] for r in refs), "tools": PROOFS}
RESULTS["_assurance"] = {
    "policy": "Checked: exact computation on the machines of belief_memory.metta, a replayed clique or coloring, or a "
              "refutation whose DRAT proof drat-trim converted to LRAT and cake_lpr checked; Conditional: a refutation "
              "whose proof was not replayed, with a TrustedBackend assumption",
    "conditional": [c["request"] for c in CLAIMS if c["status"] == "Conditional"]}
RESULTS["seconds"] = round(time.time() - T0, 1)
json.dump(RESULTS, open("ex1_results.json", "w"), indent=1, default=str)
print(f"{CHECKS[0] - len(FAILS)} checks passed, {len(FAILS)} failed, {RESULTS['seconds']} s, proofs checked: {PROOFS}")
sys.exit(1 if FAILS else 0)
