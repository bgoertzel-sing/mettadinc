#!/usr/bin/env python3
"""Oracle for Example 3 (sharing skills between robots with different camera frames).

Recomputes every number quoted for the example from d4.py, robots.py and hive.py: symmetry
groups, transfer defects and canonical witnesses, holonomies, transfer-hive coherence under four
gauge declarations, the derived kernel hives (coherence, holonomy kernel, consensus cost), the
round trip of a skill, the docking task and the pallet bay.  Exact arithmetic throughout.  The
reference evaluator (metta_eval.py) evaluates the maps of skill_share.metta, and the last section
checks that the module's responses, free cells, transfers, symmetries and skills are those of the
Python model at every cell and command.

Run: python3 ex3_oracle.py        (a few seconds; writes ex3_results.json)
"""
import json
import sys
import time

import d4
from hive import *  # noqa: F401,F403
from metta_eval import World

RESULTS, FAILS, N_CHECKS = {}, [], [0]


def check(name, got, want):
    N_CHECKS[0] += 1
    ok = got == want
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": got {got!r}, want {want!r}"))
    if not ok:
        FAILS.append(name)
    RESULTS[name] = got


def s(x):
    return str(x) if isinstance(x, F) else x


T0 = time.time()
A, B, C = Robot("A", "id", progress), Robot("B", "r90", progress), Robot("C", "md", progress)
check("free cells per robot", (len(A.states), len(B.states), len(C.states)), (21, 21, 21))
check("symmetries of the progress responses (A, B, C)",
      [[g for g in ORDER if is_symmetry(r, g)] for r in (A, B, C)], [["id", "r180", "mv", "mh"]] * 3)
rows = {}
for x in A.states:
    rows.setdefault(tuple(A.resp(x, m) for m in DIRS), []).append(x)
check("cells with identical response rows", sorted(v for v in rows.values() if len(v) > 1),
      [[(0, 0), (2, 0), (4, 0)], [(0, 4), (2, 4), (4, 4)]])

# ------------------------------------------------------------------ transfers
check("calibrated pullbacks AB, BC, CA", (calibrated(A, B), calibrated(B, C), calibrated(C, A)), ("r270", "mv", "md"))
check("learned CA (first exact candidate in element order)", learned(C, A), "r90")
check("FindTransfers C A: the exact candidates among the eight frame changes",
      [f for f in ORDER if is_exact(C, A, f)], ["r90", "r270", "md", "ma"])
check("learned CA = calibrated CA after A's up-down mirror", compose("md", "mh"), "r90")
AB, BC, CA = Transfer("AB", A, B, "r270"), Transfer("BC", B, C, "mv"), Transfer("CA", C, A, "r90")
CAcal = Transfer("CAcal", C, A, "md")
check("AB, BC, CA, CAcal are exact", [t.defect()[0] for t in (AB, BC, CA, CAcal)], [0, 0, 0, 0])
Naive = Transfer("NaiveAB", A, B, "r270", iota={m: m for m in DIRS})
check("NaiveAB: defect (reward-law TV, expected reward)", (Naive.defect()[0], Naive.defect("ER")[0]), (1, 1))
check("NaiveAB: canonical witness (B cell, A command, B command, A response, B response)",
      tuple(map(s, Naive.least_witness())), ((0, 0), "right", "right", "1", "1/2"))
value = lambda r, x: max(r.resp(x, m) for m in DIRS)
check("NaiveAB: optimal values still agree", all(value(A, Naive.phi(y)) == value(B, y) for y in B.states), True)
phim, iota, gs, gm = holonomy_pair((AB, BC, CA))
check("round-trip holonomy at A (state part, method part)", (gs, gm), ("mh", "mh"))
check("round trip with the calibrated CA", holonomy_pair((AB, BC, CAcal))[2:], ("id", "id"))

# ------------------------------------------------------------------ transfer hives
def transport(t, g):
    inv = {v: k for k, v in t.iota.items()}
    gm_ = dir_map(g)
    p = {m: t.iota[gm_[inv[m]]] for m in DIRS}
    return next(h for h in ORDER if dir_map(h) == p)


gB = transport(AB, "mh"); gC = transport(BC, gB)
check("gauge {id, mh} at A transported: to B, to C, back to A", (gB, gC, transport(CA, gC)), ("mv", "mv", "mh"))
cases = {"Strict": {}, "FullGauge": {"A": ["mh", "mv"], "B": ["mh", "mv"], "C": ["mh", "mv"]},
         "Copied": {"A": ["mh"], "B": ["mh"], "C": ["mh"]}, "Transported": {"A": ["mh"], "B": ["mv"], "C": ["mv"]}}
got = {k: check_transfer_hive((AB, BC, CA), g) for k, g in cases.items()}
check("Strict: refuted by the holonomy (element, least moved cell and its image)",
      got["Strict"], ("Refuted", ("holonomy", "mh", "mh", (0, 0), (4, 0))))
check("FullGauge: coherent", got["FullGauge"][0], "Checked")
check("Copied: refuted on intertwining at AB (B's mh corresponds to A's mv)",
      (got["Copied"][0], got["Copied"][1][:3], conj_methods(AB, "mh") == dir_map("mv")), ("Refuted", ("intertwining", "AB", "mh"), True))
check("Transported (and GaugeFrom A): coherent", got["Transported"][0], "Checked")

# ------------------------------------------------------------------ derived kernel hives
nodes, H = kernel_hive((AB, BC, CA))
ok, wit = transitive(nodes, H)
check("unsaturated derived hive: coherent?, least transitivity witness",
      (ok, wit), (False, (("A", (0, 1)), ("B", (1, 4)), ("C", (1, 0)))))
cost, _ = consensus_cost(nodes, H)
check("unsaturated derived hive: consensus cost of closure", s(cost), "4/147")


def comp(K1, K2, S1, S2, S3):
    return {(x, z): max(max(F(0), K1[(x, y)] + K2[(y, z)] - 1) for y in S2) for x in S1 for z in S3}


cAB = {(x, y): H[(("A", x), ("B", y))] for x in A.states for y in B.states}
cBC = {(y, z): H[(("B", y), ("C", z))] for y in B.states for z in C.states}
cCA = {(z, x): H[(("C", z), ("A", x))] for z in C.states for x in A.states}
hol = comp(comp(cAB, cBC, A.states, B.states, C.states), cCA, A.states, C.states, A.states)
over = sorted((x, z) for (x, z), v in hol.items() if v > H[(("A", x), ("A", z))])
check("holonomy kernel above A's tolerance: pairs, least pair", (len(over), over[0]), (12, ((0, 1), (4, 1))))
for name, want in (("FullGauge", (True, None)), ("Copied", (False, (("A", (0, 0)), ("B", (0, 0)), ("A", (0, 4))))),
                   ("Transported", (True, None))):
    nodes_s, Hs = kernel_hive((AB, BC, CA), cases[name], saturate=True)
    check(f"saturated derived hive, gauges {name}: coherent?, witness", transitive(nodes_s, Hs), want)

# ------------------------------------------------------------------ skills
pi_A = {x: max(DIRS, key=lambda m: (A.resp(x, m), -DIRS.index(m))) for x in A.states}
pi_B = {y: AB.iota[pi_A[AB.phi(y)]] for y in B.states}
pi_C = {z: BC.iota[pi_B[BC.phi(z)]] for z in C.states}
pi_A2 = {x: CA.iota[pi_C[CA.phi(x)]] for x in A.states}
changed = sorted(x for x in A.states if pi_A2[x] != pi_A[x])
check("round-trip skill: cells where it changed", changed, [(0, 1), (1, 1), (2, 2), (3, 1), (4, 1)])
check("round-trip skill: same response at every cell", all(A.resp(x, pi_A2[x]) == A.resp(x, pi_A[x]) for x in A.states), True)
check("transported skills earn the source responses at B and C",
      (all(B.resp(y, pi_B[y]) == A.resp(AB.phi(y), pi_A[AB.phi(y)]) for y in B.states),
       all(C.resp(z, pi_C[z]) == B.resp(BC.phi(z), pi_B[BC.phi(z)]) for z in C.states)), (True, True))


def round_trip(pi):
    pb = {y: AB.iota[pi[AB.phi(y)]] for y in B.states}
    pc = {z: BC.iota[pb[BC.phi(z)]] for z in C.states}
    return {x: CA.iota[pc[CA.phi(x)]] for x in A.states}


hol = lambda x: phim[x]  # noqa: E731 -- the holonomy's state part at A, the up-down mirror
up_A = {x: "up" for x in A.states}
up_A2 = round_trip(up_A)
check("TransportSkill contract: a round-trip skill earns at each cell what the original earns at the mirrored "
      "cell (greedy, always-up)",
      (all(A.resp(x, pi_A2[x]) == A.resp(hol(x), pi_A[hol(x)]) for x in A.states),
       all(A.resp(x, up_A2[x]) == A.resp(hol(x), up_A[hol(x)]) for x in A.states)), (True, True))
check("always-up sent around the loop comes back as always-down", sorted(set(up_A2.values())), ["down"])
check("always-up: rewards at the same cell before and after the round trip, cells (3,2) and (1,2)",
      tuple(s(A.resp(x, p[x])) for x in ((3, 2), (1, 2)) for p in (up_A, up_A2)), ("1", "0", "0", "1"))
diff_cells = sorted(x for x in A.states if A.resp(x, up_A2[x]) != A.resp(x, up_A[x]))
check("always-up: cells where the same-cell reward changes (count, least)", (len(diff_cells), diff_cells[0]), (12, (0, 1)))
profile_inv = lambda pi: all(A.resp(hol(x), pi[hol(x)]) == A.resp(x, pi[x]) for x in A.states)  # noqa: E731
check("reward profile invariant under the holonomy (greedy, always-up)", (profile_inv(pi_A), profile_inv(up_A)),
      (True, False))
mean = lambda pi, cells: sum(A.resp(x, pi[x]) for x in cells) / len(cells)  # noqa: E731
check("always-up: mean reward under the uniform law on A's cells (invariant under the mirror), before and after; "
      "and from the cell (3,2) alone",
      (s(mean(up_A, A.states)), s(mean(up_A2, A.states)), s(mean(up_A, [(3, 2)])), s(mean(up_A2, [(3, 2)]))),
      ("1/2", "1/2", "1", "0"))

# ------------------------------------------------------------------ docking
Ad, Bd, Cd = Robot("A", "id", docking), Robot("B", "r90", docking), Robot("C", "md", docking)
check("symmetries of the docking responses (A, B, C)", [[g for g in ORDER if is_symmetry(r, g)] for r in (Ad, Bd, Cd)],
      [["id", "mv"], ["id", "mh"], ["id", "mh"]])
ABd, BCd, CAold = Transfer("AB", Ad, Bd, "r270"), Transfer("BC", Bd, Cd, "mv"), Transfer("CA", Cd, Ad, "r90")
check("docking: AB and BC still exact", (ABd.defect()[0], BCd.defect()[0]), (0, 0))
check("docking: old CA defect (TV, expected reward)", (CAold.defect()[0], s(CAold.defect("ER")[0])), (1, "1/2"))
check("docking: old CA canonical witness", tuple(map(s, CAold.least_witness())), ((1, 2), "left", "down", "1/2", "1"))
check("docking: re-learned CA", learned(Cd, Ad), "r270")
check("docking: the exact C-to-A candidates", [f for f in ORDER if is_exact(Cd, Ad, f)], ["r270", "md"])
check("re-learned CA = calibrated CA after A's left-right mirror", compose("md", "mv"), "r270")
CAnew = Transfer("CA", Cd, Ad, "r270")
check("docking: holonomy with the re-learned CA", holonomy_pair((ABd, BCd, CAnew))[2:], ("mv", "mv"))
check("docking gauge {id, mv} at A transported to B and C", (transport(ABd, "mv"), transport(BCd, transport(ABd, "mv"))),
      ("mh", "mh"))
dock_g = {"A": ["mv"], "B": ["mh"], "C": ["mh"]}
stale = {"A": ["mh", "mv"], "B": ["mh", "mv"], "C": ["mh", "mv"]}
check("StaleGauge: refuted on a gauge symmetry at A", check_transfer_hive((ABd, BCd, CAnew), stale)[0:2][0], "Refuted")
wit = next((x, m, s(Ad.resp(x, m)), s(Ad.resp(CELL_MAP["mh"](*x), dir_map("mh")[m])))
           for x in Ad.states for m in DIRS if Ad.resp(CELL_MAP["mh"](*x), dir_map("mh")[m]) != Ad.resp(x, m))
check("StaleGauge: FlipUD-A is not a docking symmetry (least cell, command, response, mirrored response)",
      wit, ((1, 2), "down", "1", "1/2"))
check("OldLibrary: refuted on the CA edge", check_transfer_hive((ABd, BCd, CAold), dock_g)[1][:2], ("edge", "CA"))
check("Docking: coherent", check_transfer_hive((ABd, BCd, CAnew), dock_g)[0], "Checked")
nd, Hd = kernel_hive((ABd, BCd, CAnew), dock_g, saturate=True)
check("docking: saturated derived hive coherent", transitive(nd, Hd)[0], True)
nu_, Hu = kernel_hive((ABd, BCd, CAnew))
check("docking: unsaturated derived hive incoherent, closure cost", (transitive(nu_, Hu)[0], s(consensus_cost(nu_, Hu)[0])),
      (False, "4/63"))


# ------------------------------------------------------------------ the pallet bay
def progress_pallet(x, d):
    y = (x[0] + d4.STEP[d][0], x[1] + d4.STEP[d][1])
    if not (0 <= y[0] < 5 and 0 <= y[1] < 5) or y in d4.PILLARS or y == (0, 2):
        y = x
    dx, dy = d4.dist(x), d4.dist(y)
    return F(1) if dy < dx else F(1, 2) if dy == dx else F(0)


class PalletRobot(Robot):
    def __init__(self):
        super().__init__("Cp", "md", progress_pallet)
        self.states = sorted(CELL_MAP["md"](*x) for x in FREE if x != (0, 2))


Cp = PalletRobot()
ACp, BCp = Transfer("ACp", A, Cp, "md"), Transfer("BCp", B, Cp, "mv")
check("pallet: states of Cp", len(Cp.states), 20)
check("pallet: A to Cp defect (TV, expected reward)", (ACp.defect()[0], s(ACp.defect("ER")[0])), (1, "1/2"))
check("pallet: canonical witness above 1/4 (Cp cell, A command, Cp command, responses)",
      tuple(map(s, ACp.least_witness(F(1, 4), "ER"))), ((1, 0), "right", "down", "1", "1/2"))
comp_phi = lambda z: AB.phi(BCp.phi(z))
comp_iota = {m: BCp.iota[AB.iota[m]] for m in DIRS}
d = max(abs(A.resp(comp_phi(z), m) - Cp.resp(z, comp_iota[m])) for z in Cp.states for m in DIRS)
check("pallet: composite A->B->Cp defect equals the bound 0 + 1/2, and equals A->Cp",
      (s(d), all(comp_phi(z) == ACp.phi(z) for z in Cp.states)), ("1/2", True))
check("pallet: the reverse pullback Cp->A leaves Cp's carrier at A's cell",
      [(x, CELL_MAP["md"](*x)) for x in A.states if CELL_MAP["md"](*x) not in Cp.states], [((0, 2), (2, 0))])

check("pallet: state-command pairs where A's response differs from Cp's under ACp",
      [(z, m) for z in Cp.states for m in DIRS if A.resp(ACp.phi(z), m) != Cp.resp(z, ACp.iota[m])],
      [((1, 0), "right"), ((2, 1), "up"), ((3, 0), "left")])

# ------------------------------------------------------------------ the module defines the model
WLD = World("skill_share.metta")


def decl(mod, name):
    return WLD.lookup(mod, name)


def field(mod, name, key):
    m, d = decl(mod, name)
    return m, next(x for x in d[2:] if isinstance(x, list) and x[0] == key)[1]


def mod_map(mod, name):
    m, d = decl(mod, name)
    return WLD.instance(m, name)


def same_system(mod, ms, robot):
    m, states = field(mod, ms, "States")
    _, resp = field(mod, ms, "Response")
    cm, cd = decl(m, states)
    sub = next(x for x in cd[2:] if isinstance(x, list) and x[0] == "Subset")
    member = mod_map(cm, sub[2])
    f = mod_map(m, resp)
    return sorted(x for x in d4.CELLS if member(x)) == sorted(robot.states) and \
        all(f((y, c)) == robot.resp(y, c) for y in robot.states for c in DIRS)


def same_transfer(mod, name, t):
    _, pb = field(mod, name, "StatePullback")
    _, pf = field(mod, name, "MethodPushforward")
    fp, fq = mod_map(mod, pb), mod_map(mod, pf)
    return all(fp(y) == t.phi(y) for y in t.tgt.states) and all(fq(c) == t.iota[c] for c in DIRS)


def same_symmetry(mod, name, g):
    _, st = field(mod, name, "States")
    _, me = field(mod, name, "Methods")
    return all(mod_map(mod, st)(x) == CELL_MAP[g](*x) for x in d4.CELLS) and \
        all(mod_map(mod, me)(c) == dir_map(g)[c] for c in DIRS)


check("module: the method systems of skill_share.metta (free cells and responses) are the model's robots "
      "(progress, docking, pallet bay)",
      [same_system("SkillShare", n, r) for n, r in (("A", A), ("B", B), ("C", C))] +
      [same_system("SkillShareDock", n, r) for n, r in (("A", Ad), ("B", Bd), ("C", Cd))] +
      [same_system("PalletBay", "Cp", Cp)], [True] * 7)
check("module: the transfers of the three modules are the model's (pullback on target cells, pushforward on commands)",
      [same_transfer("SkillShare", n, t) for n, t in (("AB", AB), ("BC", BC), ("CA", CA), ("CAcal", CAcal),
                                                      ("NaiveAB", Naive))] +
      [same_transfer("SkillShareDock", n, t) for n, t in (("AB", ABd), ("BC", BCd), ("CAold", CAold), ("CAnew", CAnew))] +
      [same_transfer("PalletBay", n, t) for n, t in (("ACp", ACp), ("BCp", BCp))], [True] * 11)
check("module: the declared symmetries and the two skills are the model's",
      ([same_symmetry("SkillShare", f"Flip{k}-{r}", g) for r in "ABC" for k, g in (("UD", "mh"), ("LR", "mv"))],
       all(mod_map("SkillShare", "greedy-A")(x) == pi_A[x] for x in A.states),
       all(mod_map("SkillShare", "always-up")(x) == "up" for x in A.states)), ([True] * 6, True, True))

RESULTS["_assurance"] = {
    "policy": "every Checked or Refuted result of this example is an exact computation on the machines of "
              "skill_share.metta (enumeration and exact rational arithmetic), with each witness replayed by "
              "evaluation; no result rests on a solver, so none is Conditional",
    "conditional": []}
RESULTS["seconds"] = round(time.time() - T0, 1)
json.dump(RESULTS, open("ex3_results.json", "w"), indent=1, default=str)
print(f"{N_CHECKS[0] - len(FAILS)} checks passed, {len(FAILS)} failed, {RESULTS['seconds']} s")
sys.exit(1 if FAILS else 0)
