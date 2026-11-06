#!/usr/bin/env python3
"""Oracle for the guide to Omega memory and goals in MeTTaDinC.

Part A recomputes every number the guide quotes from the Python models in models/ and checks it
against the expected value.  Part B reads memory_goals.metta with the reference evaluator
(mg_eval.py), rebuilds every machine, representation, abstraction map, block partition and
implementation from the module text, reruns the checks, and compares them with Part A result by
result.  It also answers the module's CheckInterpretation requests, including its two negative
fixtures, parses every Consumer declaration, and applies the gate's coverage rule to bundles built
from the module's results: bindings that name another machine, statuses and assumptions a consumer
does not accept, and a Refuted result each get their expected verdict.  Exact rational arithmetic
throughout, except for three floating-point summaries of the monitor (Kullback-Leibler rate, Wald's
approximation, the largest null e-value), which belong to no Checked claim.

Run: python3 mg_oracle.py        (about a minute on one core; writes mg_results.json)
"""
import json
import math
import os
import sys
import time
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "models"))

import dclib  # noqa: E402
from dclib import Machine, check_now, check_updates, check_behavioral, minimize_for_queries, \
    least_violation, check_abstraction_map, check_implementation, class_key, reach  # noqa: E402
import p1_open_items as P1  # noqa: E402
import p2_context as P2  # noqa: E402
import p3_consolidation as P3  # noqa: E402
import p4_checkpoint as P4  # noqa: E402
import p5_goals as P5  # noqa: E402
import p6_conflicts as P6  # noqa: E402
import p7_metamo as P7  # noqa: E402
import p8_monitor as P8  # noqa: E402
from mg_eval import World, InvalidInput, show, admits, parse_accepts  # noqa: E402

T0 = time.time()
CHECKS = [0]
FAILS = []
RESULTS = {}


def js(x):
    if isinstance(x, F):
        return str(x)
    if isinstance(x, (tuple, list)):
        return [js(y) for y in x]
    if isinstance(x, dict):
        return {str(k): js(v) for k, v in x.items()}
    if isinstance(x, set):
        return sorted(js(y) for y in x)
    return x


def check(name, got, want):
    CHECKS[0] += 1
    ok = got == want
    RESULTS[name] = {"got": js(got), "ok": ok}
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)
        print("     got ", got)
        print("     want", want)


def wit_pair(w):
    return None if w is None else w["pair"]


# ================================================================== Part A: the Python models

# ---- Pattern 1: open items
r1 = P1.results()
check("P1 reachable item states", r1["live_states"], 39)
check("P1 window view, CheckNow: witness pair and answers",
      (r1["window_now"]["pair"], r1["window_now"]["query"], r1["window_now"]["left"], r1["window_now"]["right"]),
      (((3, "none"), (3, "d3")), "suggest", True, False))
check("P1 window view, CheckUpdates: witness pair and action",
      (r1["window_updates"]["pair"], r1["window_updates"]["action"], r1["window_updates"]["left"],
       r1["window_updates"]["right"]),
      (((2, "d0"), (2, "d2")), "tick", (3, True), (3, False)))
check("P1 event view: now, updates and behavioral all Checked",
      (r1["event_now"], r1["event_updates"], r1["event_behavioral"]), (None, None, None))
check("P1 quotient sizes: engine, commitments, both",
      (len(r1["classes_suggest"]), len(r1["classes_commit"]), len(r1["classes_both"])), (9, 2, 10))
check("P1 engine quotient: closed items share a class with the open item older than seven days",
      [c for c in r1["classes_suggest"] if len(c) > 1][0][-5:], [(8, "none"), (8, "d0"), (8, "d1"), (8, "d2"), (8, "d3")])
check("P1 event view codes on reachable items", r1["event_view_codes"], 18)
check("P1 seven-day cap: adequate for the engine, refuted for commitments",
      (r1["capped_suggest_behavioral"], r1["capped_commit_now"]["pair"], r1["capped_commit_now"]["query"]),
      (None, ((8, "none"), (8, "d0")), "open"))
d1 = P1.dedupe_results()
check("P1 dedupe: reachable engine states (topic key, question key)", (d1["topic_live"], d1["question_live"]), (9, 7))
check("P1 dedupe by person+topic: least violating word and state",
      (d1["topic"]["word"], d1["topic"]["state"]), (["recv1", "recv2", "run"], (True, True, True, True, 2)))
check("P1 dedupe by question: at most one suggestion on every reachable state", d1["question"], None)

# ---- Pattern 2: the context block
t32 = P2.table(3, 2)
summary = {p: {c: ("Checked" if w is None else "Refuted") for c, w in row.items()} for p, row in t32.items()}
check("P2 three slots, block of two: verdicts", summary, {
    "Recency": {"latest-F": "Refuted", "latest-O": "Refuted", "latest-A": "Refuted"},
    "Relevance": {"latest-F": "Checked", "latest-O": "Refuted", "latest-A": "Refuted"},
    "ProtectedFirst": {"latest-F": "Refuted", "latest-O": "Refuted", "latest-A": "Checked"},
    "ConsumerAware": {"latest-F": "Checked", "latest-O": "Refuted", "latest-A": "Checked"}})
check("P2 witnesses (pair, left, right)", {p: {c: (None if w is None else (w["pair"], w["left"], w["right"]))
                                               for c, w in row.items()} for p, row in t32.items()}, {
    "Recency": {"latest-F": ((("O", "O", "F"), ("O", "O", "O")), 3, 0),
                "latest-O": ((("F", "F", "F"), ("F", "F", "O")), 0, 3),
                "latest-A": ((("F", "F", "F"), ("F", "F", "A")), 0, 3)},
    "Relevance": {"latest-F": None, "latest-O": ((("F", "F", "F"), ("F", "F", "O")), 0, 3),
                  "latest-A": ((("F", "F", "F"), ("F", "F", "A")), 0, 3)},
    "ProtectedFirst": {"latest-F": ((("F", "A", "A"), ("O", "A", "A")), 1, 0),
                       "latest-O": ((("F", "F", "F"), ("F", "F", "O")), 0, 3), "latest-A": None},
    "ConsumerAware": {"latest-F": None, "latest-O": ((("F", "F", "A"), ("F", "O", "A")), 0, 2),
                      "latest-A": None}})
for n, b in ((4, 2), (5, 3)):
    t = P2.table(n, b)
    check(f"P2 consumer-aware with {n} slots and a block of {b}",
          {c: w is None for c, w in t["ConsumerAware"].items()},
          {"latest-F": True, "latest-O": b >= 3, "latest-A": True})
check("P2 four slots, block of three: consumer-aware Checked for all three, others not",
      {p: all(w is None for w in row.values()) for p, row in P2.table(4, 3).items()},
      {"Recency": False, "Relevance": False, "ProtectedFirst": False, "ConsumerAware": True})
check("P2 share of the 64 patterns in which the block holds the answer (F, O, A)",
      {p: [P2.served_fraction(3, 2, p, c)[0] for c, _ in P2.CONSUMERS] for p, _ in P2.POLICIES},
      {"Recency": [55, 55, 55], "Relevance": [64, 61, 37], "ProtectedFirst": [61, 52, 64],
       "ConsumerAware": [64, 58, 64]})

# ---- Pattern 3: consolidation and anchor cues
t3 = P3.policy_table()
verdict = lambda w: "C" if w is None else "R"
check("P3 policy table (now, behavioral, updates) per consumer",
      {p: {c: "".join(verdict(r[k]) for k in ("now", "behavioral", "updates")) for c, r in row.items()}
       for p, row in t3.items()},
      {"Majority": {"contra": "RRR", "eff": "RRR", "regen": "RRR"},
       "Counts": {"contra": "CCC", "eff": "RRC", "regen": "RRC"},
       "Distinct": {"contra": "CCR", "eff": "CRR", "regen": "CRR"},
       "Protected": {"contra": "CCC", "eff": "RRC", "regen": "CCC"},
       "Provenance": {"contra": "CCC", "eff": "CCC", "regen": "CCC"}})
check("P3 majority hides a contradiction: witness pair",
      wit_pair(t3["Majority"]["contra"]["now"]), ((0, 0, 0, 0, 0, 0), (0, 0, 1, 0, 0, 1)))
check("P3 counts confuse two reports from one source with two sources: eff witness",
      (wit_pair(t3["Counts"]["eff"]["now"]), t3["Counts"]["eff"]["now"]["left"], t3["Counts"]["eff"]["now"]["right"]),
      (((0, 0, 2, 0, 0, 0), (0, 1, 1, 0, 0, 0)), 1, 2))
check("P3 counts and the anchor: regen witness",
      wit_pair(t3["Counts"]["regen"]["now"]), ((0, 0, 0, 0, 0, 2), (0, 0, 0, 0, 1, 1)))
check("P3 distinct sources: right today, wrong tomorrow (regen word witness)",
      (wit_pair(t3["Distinct"]["regen"]["behavioral"]), t3["Distinct"]["regen"]["behavioral"]["word"]),
      (((0, 0, 0, 0, 0, 1), (0, 0, 0, 0, 1, 0)), ["minus-b"]))
check("P3 distinct sources cannot be maintained on their own: update witness",
      (wit_pair(t3["Distinct"]["contra"]["updates"]), t3["Distinct"]["contra"]["updates"]["action"]),
      (((0, 0, 0, 0, 0, 1), (0, 0, 0, 0, 1, 0)), "minus-b"))
q3 = P3.quotient_sizes()
check("P3 coarsest memories (classes): contra, eff, regen, contra+regen, all three",
      [q3[k][0] for k in ("contra", "eff", "regen", "contra+regen", "contra+eff+regen")], [2, 5, 5, 5, 25])
check("P3 codes per policy on the 729 states",
      q3["codes"], {"Majority": 3, "Counts": 9, "Distinct": 16, "Protected": 33, "Provenance": 64})
check("P3 the minimal code (first source or two-plus, per polarity) is the 25-class quotient",
      P3.minimal_matches_quotient(), True)
m3 = P3.migration_results()
check("P3 naive migration: transform and repair do not commute",
      m3["naive"], {"state": ("absent", "none"), "action": "repair", "map-then-act": ("present", "old"),
                    "act-then-map": ("present", "new")})
check("P3 migration cell: Checked", m3["cell"], None)

# ---- Pattern 4: task checkpoints
r4 = P4.results()
check("P4 reachable task states", r4["live"], 12)
check("P4 checkpoint without read sets: Checked now", r4["noreads_now"], None)
check("P4 checkpoint without read sets: update witness",
      (r4["noreads_updates"]["pair"], r4["noreads_updates"]["action"]),
      ((("valid", "valid", "r1", "current"), ("valid", "valid", "r2", "current")), "withdraw1"))
check("P4 checkpoint without read sets: behavioral witness",
      (r4["noreads_behavioral"]["word"], r4["noreads_behavioral"]["query"], r4["noreads_behavioral"]["left"],
       r4["noreads_behavioral"]["right"]), (["withdraw1"], "needs-revalidation", True, False))
check("P4 checkpoint with read sets: Checked", r4["reads_behavioral"], None)
check("P4 restart memory: 11 classes; the only merge", (len(r4["classes"]), [c for c in r4["classes"] if len(c) > 1]),
      (11, [[("withdrawn", "withdrawn", "r1", "stale"), ("withdrawn", "withdrawn", "r2", "stale")]]))
check("P4 codes of the checkpoint without read sets", r4["noreads_codes"], 10)

# ---- Pattern 5: goals as observers
c5 = P5.closure_table()
check("P5 goal-sufficient memories (classes)", {k: v["classes"] for k, v in c5.items()},
      {"reply": 2, "nag": 4, "triage": 3, "reply+nag": 8, "reply+nag+triage": 17, "reply+triage": 5})
a5 = P5.add_goal_incrementally()
check("P5 adding triage: resumed refinement versus scratch (class counts per round)",
      (a5["resumed_history"], a5["scratch_history"], a5["same"]), ([16, 17], [8, 13, 17], True))
r5 = P5.retire_goal()
check("P5 retiring nag: old memory still adequate, coarsest 5 classes, largest merge 4",
      (r5["old"], r5["new"], r5["still_adequate"], r5["largest_merge"]), (17, 5, True, 4))
check("P5 a distinction reply needs and nag does not", P5.distinctions_only(["reply"], ["nag"]),
      (("open", 0, "ben", "normal"), ("open", 0, "andy", "normal")))
check("P5 a distinction nag needs and reply does not", P5.distinctions_only(["nag"], ["reply"]),
      (("open", 0, "ben", "normal"), ("open", 1, "ben", "normal")))
k5 = P5.classify()
check("P5 days-left: determines the old answers, is strictly finer, costs no memory",
      (k5["days-left"]["determines_old"], wit_pair(k5["days-left"]["old_determines_new"]),
       k5["days-left"]["closure_classes"], k5["nag_closure_classes"]),
      (None, (("open", 0, "ben", "normal"), ("open", 1, "ben", "normal")), 4, 4))
check("P5 nag-ben-first: determines the old answers; memory grows from 4 to 7 classes",
      (k5["nag-ben-first"]["determines_old"], wit_pair(k5["nag-ben-first"]["old_determines_new"]),
       k5["nag-ben-first"]["closure_classes"]),
      (None, (("open", 0, "ben", "normal"), ("open", 0, "andy", "normal")), 7))
check("P5 cap3: changes goal content in both directions",
      (wit_pair(k5["cap3"]["determines_old"]), wit_pair(k5["cap3"]["old_determines_new"]),
       k5["cap3"]["closure_classes"]),
      ((("open", 0, "ben", "normal"), ("open", 3, "ben", "normal")),
       (("open", 3, "ben", "normal"), ("open", 4, "ben", "normal")), 5))
check("P5 migration to a deadline schema: Checked", k5["migration"], None)
w5 = lambda r: None if r is None else (r["record"], r["old_answer"], r["new_answer"], r["old_decision"], r["new_decision"])
CHANGES5 = ("days-left", "nag-ben-first", "cap3", "anti-nag", "anti-nag-waits")
check("P5 a negated nag goal: both informational checks Checked, the same 4-class memory",
      (k5["anti-nag"]["determines_old"], k5["anti-nag"]["old_determines_new"], k5["anti-nag"]["closure_classes"],
       k5["anti_same_memory"]), (None, None, 4, True))
check("P5 interpretation obligation with the declared decoders: least witness record or None",
      dict({n: None if k5[n]["interpretation"] is None else k5[n]["interpretation"]["record"] for n in CHANGES5},
           migration=k5["migration_interpretation"]),
      {"days-left": None, "nag-ben-first": None, "cap3": ("open", 3, "ben", "normal"),
       "anti-nag": ("open", 0, "ben", "normal"), "anti-nag-waits": None, "migration": None})
check("P5 interpretation witnesses (record, answers, decisions); the negated goal disagrees on all 40 records",
      (w5(k5["cap3"]["interpretation"]), w5(k5["anti-nag"]["interpretation"]), k5["anti_disagreements"]),
      ((("open", 3, "ben", "normal"), False, True, "wait", "follow-up"),
       (("open", 0, "ben", "normal"), True, False, "follow-up", "wait"), 40))
KINDS5 = dict({n: k5[n]["kind"] for n in CHANGES5}, migration=k5["migration_kind"])
check("P5 classification of the six proposed changes", KINDS5,
      {"days-left": "refinement", "nag-ben-first": "refinement", "cap3": "change of content",
       "anti-nag": "change of content", "anti-nag-waits": "renaming", "migration": "migration"})
dd = k5["drop-days-left"]
check("P5 a coarsening: dropping the days left from the refined goal again; the old answers are not recoverable "
      "(ages 0 and 1), the converse holds, the decisions agree",
      (dd["determines_old"] and dd["determines_old"]["pair"], dd["old_determines_new"], dd["interpretation"], dd["kind"]),
      ((("open", 0, "ben", "normal"), ("open", 1, "ben", "normal")), None, None, "coarsening"))
sm = k5["stuck_migration"]
check("P5 a failed migration: a new schema whose tick forgets to count the days left down; every record is "
      "translated correctly, and the map fails to commute at the first tick from age 0 (3 days left against 2)",
      (k5["stuck_interpretation"], sm and (sm["state"], sm["action"], sm["map-then-act"][1], sm["act-then-map"][1]),
       k5["stuck_kind"]), (None, (("open", 0, "ben", "normal"), "tick", 3, 2), "failed migration"))

# ---- Pattern 6: conflicts
r6 = P6.results()
check("P6 reachable claim states (weighted, norm-first)", (r6["live_weighted"], r6["live_normfirst"]), (14, 11))
check("P6 weighted arbitration: least unlawful word and state",
      (r6["weighted_lawful"]["word"], r6["weighted_lawful"]["state"]), (["evidence"], ("high", False, False, "calm")))
check("P6 weighted arbitration: consolidation without a check after two steps",
      r6["weighted_outcome"]["word"], ["evidence", "act"])
check("P6 norm-first arbitration: lawful and never consolidates unchecked",
      (r6["normfirst_lawful"], r6["normfirst_outcome"]), (None, None))
mn = P6.machine(P6.norm_first)
cw = least_violation(mn, [P6.START], P6.no_conflict)
check("P6 conflict under norm-first: least word", (cw["word"], cw["state"]), (["evidence"], ("high", False, False, "calm")))
check("P6 conflict states reachable under norm-first", r6["conflict_states"],
      [("low", False, False, "deadline"), ("low", True, False, "deadline"), ("high", False, False, "calm"),
       ("high", False, False, "deadline")])
check("P6 the arbitrated move in each conflict state (norm-first)",
      [P6.norm_first(s) for s in r6["conflict_states"]], ["verify", "consolidate", "verify", "verify"])

# ---- Pattern 7: MetaMo on a grid
check("P7 states and settled states", (len(P7.CARRIER), sum(1 for x in P7.CARRIER if P7.psi(x) == x)), (720, 80))
mp, mf = P7.machine(P7.D_PLAIN), P7.machine(P7.D_FLOOR)
start7 = (3, 2, 1, 1, 0, 0)
vp = least_violation(mp, [start7], P7.safe)
check("P7 plain design leaves the safe region: least word and state",
      (vp["word"], vp["state"]), (["novel", "cycle", "cycle", "cycle", "cycle"], (1, 4, 2, 0, 1, 0)))
check("P7 floor design stays in the safe region from the start state", least_violation(mf, [start7], P7.safe), None)
check("P7 reachable states from the start (plain, floor)", (len(reach(mp, [start7])), len(reach(mf, [start7]))), (96, 80))
check("P7 states in the safe region", sum(1 for x in P7.CARRIER if P7.safe(x)), 540)
check("P7 whole safe region closed under the floor design, not under the plain one",
      (P7.closure_violation(P7.D_FLOOR), P7.closure_violation(P7.D_PLAIN)["state"]), (None, (2, 4, 0, 0, 1, 0)))
os_floor = P7.order_swap(P7.D_FLOOR)
os_damped = P7.order_swap(P7.decide_damped)
check("P7 order swap, least eta at L = 1 (floor, damped)",
      (os_floor["least_eta_L1"], os_damped["least_eta_L1"]), (F(1), F(1, 2)))
check("P7 order swap, floor design: witness at eta = 1/2",
      (os_floor["witness"]["1/2"]["pair"], os_floor["witness"]["1/2"]["out"]),
      (((1, 1, 2, 0, 0, 1), (1, 1, 2, 0, 0, 1)), F(3, 4)))
settled = [x for x in P7.CARRIER if P7.psi(x) == x]
ideal_f = lambda s: P7.D_FLOOR(P7.psi(s))
actual_f = lambda s: P7.psi(P7.D_FLOOR(s))
least_s, _ = check_implementation(settled, ideal_f, actual_f, P7.dist, P7.dist, 1, F(1), P7.same_stimulus)
_, wit_s = check_implementation(settled, ideal_f, actual_f, P7.dist, P7.dist, 1, F(1, 4), P7.same_stimulus)
goal_part = max(max(abs(F(actual_f(x)[0] - ideal_f(x)[0], 4)), abs(F(actual_f(x)[1] - ideal_f(x)[1], 4)))
                for x in settled)
check("P7 order swap on settled states: least eta 1/2, goal weights agree, witness at 1/4",
      (least_s, goal_part, wit_s["pair"]), (F(1, 2), F(0), ((1, 3, 1, 0, 1, 0), (1, 3, 1, 0, 1, 0))))
gdist = lambda x, y: max(abs(F(x[0] - y[0], 4)), abs(F(x[1] - y[1], 4)))
check("P7 order swap on all states, goal weights only (floor, damped)",
      (max(gdist(actual_f(x), ideal_f(x)) for x in P7.CARRIER),
       max(gdist(P7.psi(P7.decide_damped(x)), P7.decide_damped(P7.psi(x))) for x in P7.CARRIER)),
      (F(1), F(1, 2)))
cf, cd = P7.contraction(P7.D_FLOOR), P7.contraction(P7.decide_damped)
check("P7 contraction near the boundary at c = 1/2: least eta (floor, damped)",
      (cf["least_eta"], cd["least_eta"]), (F(3, 4), F(5, 8)))
check("P7 contraction witness at eta = 1/4 (floor)",
      (cf["witness_quarter"]["pair"], cf["witness_quarter"]["out"], cf["witness_quarter"]["in"]),
      (((1, 0, 0, 0, 0, 0), (2, 3, 0, 0, 0, 0)), F(3, 4), F(3, 4)))
_, wit_half = check_implementation(P7.CARRIER, P7.cycle(P7.D_FLOOR), P7.cycle(P7.D_FLOOR), P7.dist, P7.dist,
                                   F(1, 2), F(1, 2),
                                   lambda x, y: P7.same_stimulus(x, y) and (P7.in_band(x) or P7.in_band(y)))
check("P7 contraction at (1/2, 1/2), floor: witness", (wit_half["pair"], wit_half["out"], wit_half["in"]),
      (((1, 1, 0, 0, 0, 1), (2, 4, 0, 0, 0, 1)), F(1), F(3, 4)))

# ---- Pattern 8: the monitor
r8 = P8.results()
check("P8 null expectation of the factor", r8["validity"], F(1))
check("P8 factors", (P8.FACTOR[1], P8.FACTOR[0]), (F(4), F(16, 19)))
check("P8 alternative stream: fires at suggestion 21 after 6 stale, e-value 2^72/19^15",
      (r8["stale_alt_seed1"]["detect"]["step"], r8["stale_alt_seed1"]["detect"]["stale"],
       r8["stale_alt_seed1"]["detect"]["evalue"]), (21, 6, F(2 ** 72, 19 ** 15)))
check("P8 null stream: no detection in 400 suggestions", r8["stale_null_seed1"]["detect"]["fired"], False)
check("P8 stale counts in the two streams", (r8["stale_alt_seed1"]["stale"], r8["stale_null_seed1"]["stale"]), (79, 28))
check("P8 digests", (r8["stale_alt_seed1"]["digest"], r8["stale_null_seed1"]["digest"]),
      ("sha256:f0d4be8461a2904e728f7b0a8ad895385ccd56f340ec854d729936aaf6a48763",
       "sha256:8e76cbdeee37a8ab4156c6068ee59fab740c2f9d1b02146e3ee7e38c594b59b0"))
check("P8 e-value at detection, decimal", round(float(F(2 ** 72, 19 ** 15)), 1), 311.1)
check("P8 floating summaries: KL rate (nats), Wald steps, largest null e-value",
      (round(r8["kl"], 4), round(r8["wald"], 1), round(float(r8["stale_null_seed1"]["max"]), 1)),
      (0.1398, 32.9, 23.6))

# ---- further results quoted in the text and in the appendix
big1 = [c for c in r1["classes_suggest"] if len(c) > 1][0]
check("P1 the large class of the engine's memory holds ten event-view codes",
      len({P1.event_view(x) for x in big1}), 10)

summarize = lambda t: {p: {c: ("Checked" if w is None else "Refuted") for c, w in row.items()} for p, row in t.items()}
check("P2 four slots, block of two: every policy's verdicts equal those with three slots",
      summarize(P2.table(4, 2)), summary)


def held_when_present(pname, cname, n=3, b=2):
    order, cf = dict(P2.POLICIES)[pname], dict(P2.CONSUMERS)[cname]
    code = P2.select(order, b)
    present = [x for x in P2.carrier(n) if cf(x) != 0]
    return sum(1 for x in present if any(i == cf(x) for i, _ in code(x))), len(present)


check("P2 patterns that contain an item of each kind (F, O, A)",
      [held_when_present("Recency", c)[1] for c, _ in P2.CONSUMERS], [37, 37, 37])
check("P2 of those, patterns in which the block holds the most recent item of the kind (F, O, A)",
      {p: [held_when_present(p, c)[0] for c, _ in P2.CONSUMERS] for p, _ in P2.POLICIES},
      {"Recency": [28, 28, 28], "Relevance": [37, 34, 10], "ProtectedFirst": [34, 25, 37],
       "ConsumerAware": [37, 31, 37]})
foa = ("F", "O", "A")
code_foa = P2.select(dict(P2.POLICIES)["ConsumerAware"], 2)(foa)
check("P2 the receipt example FOA under the consumer-aware policy: block and consumers served",
      (code_foa, [any(i == cf(foa) for i, _ in code_foa) for _, cf in P2.CONSUMERS]),
      (((1, "F"), (3, "A")), [True, False, True]))

full5, _ = P5.closure(["reply", "nag", "triage"])
small5, _ = P5.closure(["reply", "triage"])
newkey5 = class_key(small5)
merged5 = [c for c in full5 if newkey5[c[0]] == newkey5[("open", 0, "ben", "normal")]]
check("P5 retiring nag: the old classes merged with (open, 0, ben, normal) are its four age classes",
      (sorted(sorted(x[1] for x in c) for c in merged5),
       all(x[0] == "open" and x[2] == "ben" and x[3] == "normal" for c in merged5 for x in c)),
      ([[0], [1], [2], [3, 4]], True))

check("P6 the two goals' preferences in each conflict state (throughput, verification)",
      [(P6.throughput(x), P6.verify(x)) for x in r6["conflict_states"]],
      [("consolidate", "verify"), ("consolidate", "hold"), ("consolidate", "verify"),
       ("consolidate", "verify")])
least6 = ("high", False, False, "calm")
check("P6 the conflict record of the appendix: forbidden moves and the move taken",
      ([m for m in P6.MOVES if P6.forbidden(least6, m)], P6.norm_first(least6)), (["consolidate"], "verify"))

x7, traj7 = dict(P7.setters())["novel"](start7), []
for _ in range(4):
    x7 = P7.cycle(P7.D_PLAIN)(x7)
    traj7.append((F(x7[1], 4), F(x7[0], 4)))
check("P7 plain design along the least word: exploration and individuation after each cycle",
      traj7, [(F(3, 4), F(3, 4)), (F(1), F(3, 4)), (F(1), F(1, 2)), (F(1), F(1, 4))])
check("P7 order swap on settled states: the modulators differ by at most one step of the grid",
      max(max(abs(F(actual_f(x)[2] - ideal_f(x)[2], 2)), abs(F(actual_f(x)[3] - ideal_f(x)[3], 2)))
          for x in settled), F(1, 2))

check("P8 suggestions in each stream", (len(P8.load("stale_alt_seed1")), len(P8.load("stale_null_seed1"))),
      (400, 400))

check("P3 the bundle example: totals with contradiction provenance against the evaluator",
      (wit_pair(t3["Protected"]["eff"]["now"]), t3["Protected"]["eff"]["now"]["left"],
       t3["Protected"]["eff"]["now"]["right"]),
      (((0, 0, 2, 0, 0, 0), (0, 1, 1, 0, 0, 0)), 1, 2))

# ================================================================== Part B: the module itself

W = World(os.path.join(HERE, "memory_goals.metta"))


def mach(mod, name, observers=None):
    st, acts, obs = W.machine(mod, name)
    return Machine(st, acts, obs if observers is None else observers)


def rep(mod, name):
    of, enc = W.representation(mod, name)
    return mach(mod, of), enc


def same_partition(ca, cb):
    return sorted(sorted(map(tuple, c)) for c in ca) == sorted(sorted(map(tuple, c)) for c in cb)


# ---- OpenItems
m, enc = rep("OpenItems", "WindowView")
check("B OpenItems: Live has 39 states", len(m.states), 39)
check("B OpenItems: WindowView CheckNow witness as in Part A", wit_pair(check_now(m, enc)), ((3, "none"), (3, "d3")))
w = check_updates(m, enc)
check("B OpenItems: WindowView CheckUpdates witness and codes", (w["pair"], w["action"], w["left"], w["right"]),
      (((2, "d0"), (2, "d2")), "tick", (3, "closed"), (3, "open")))
m, enc = rep("OpenItems", "EventView")
check("B OpenItems: EventView Checked (behavioral, updates)", (check_behavioral(m, enc), check_updates(m, enc)), (None, None))
for name, py in (("GoalEngine", r1["classes_suggest"]), ("Commitments", r1["classes_commit"]), ("Both", r1["classes_both"])):
    cls, _ = minimize_for_queries(mach("OpenItems", name))
    check(f"B OpenItems: MinimizeForQueries {name} equals Part A", same_partition(cls, py), True)
m, enc = rep("OpenItems", "CapForEngine")
check("B OpenItems: CapForEngine Checked", check_behavioral(m, enc), None)
m, enc = rep("OpenItems", "CapForCommitments")
check("B OpenItems: CapForCommitments witness", wit_pair(check_now(m, enc)), ((8, "none"), (8, "d0")))

# ---- SuggestionDedupe
for wname, bname, want in (("TopicWatch", "OnceByTopic", (["recv1", "recv2", "run"], (True, True, True, True, 2))),
                           ("QuestionWatch", "OnceByQuestion", None)):
    mm = mach("SuggestionDedupe", wname)
    start = W.ev("SuggestionDedupe", "start", {}, {})
    pred = W.block_predicate("SuggestionDedupe", bname)
    lv = least_violation(mm, [start], pred)
    check(f"B SuggestionDedupe: {bname}", None if lv is None else (lv["word"], lv["state"]), want)

# ---- ContextBlock
for pol, pname in (("Recency", "Recency"), ("Relevance", "Relevance"), ("Protected", "ProtectedFirst"),
                   ("Consumer", "ConsumerAware")):
    for suf, cname in (("F", "latest-F"), ("O", "latest-O"), ("A", "latest-A")):
        m, enc = rep("ContextBlock", pol + suf)
        got = check_now(m, enc)
        want = t32[pname][cname]
        check(f"B ContextBlock: {pol}{suf} as in Part A",
              None if got is None else (got["pair"], got["left"], got["right"]),
              None if want is None else (want["pair"], want["left"], want["right"]))

# ---- EvidenceMemory
act_label = {"(plus a)": "plus-a", "(plus b)": "plus-b", "(plus c)": "plus-c",
             "(minus a)": "minus-a", "(minus b)": "minus-b", "(minus c)": "minus-c"}
pol_map = {"Majority": "Majority", "Counts": "Counts", "Distinct": "Distinct", "Protected": "Protected"}
con_map = {"C": "contra", "E": "eff", "R": "regen"}
for pol in pol_map:
    for suf, cname in con_map.items():
        m, enc = rep("EvidenceMemory", pol + suf)
        got = {"now": check_now(m, enc), "behavioral": check_behavioral(m, enc), "updates": check_updates(m, enc)}
        want = t3[pol_map[pol]][cname]
        ok = all((got[k] is None) == (want[k] is None) and
                 (got[k] is None or got[k]["pair"] == want[k]["pair"]) for k in got)
        ok = ok and all(got[k] is None or k != "behavioral" or
                        [act_label[a] for a in got[k]["word"]] == want[k]["word"] for k in got)
        check(f"B EvidenceMemory: {pol}{suf} verdicts and witness pairs as in Part A", ok, True)
for name in ("ProvenanceAll", "MinimalAll"):
    m, enc = rep("EvidenceMemory", name)
    check(f"B EvidenceMemory: {name} Checked (updates, behavioral)", (check_updates(m, enc), check_behavioral(m, enc)), (None, None))
for name, key in (("Contra", "contra"), ("Eff", "eff"), ("Regen", "regen"), ("ContraRegen", "contra+regen"),
                  ("AllThree", "contra+eff+regen")):
    cls, _ = minimize_for_queries(mach("EvidenceMemory", name))
    check(f"B EvidenceMemory: MinimizeForQueries {name}", len(cls), q3[key][0])

# ---- AnchorMigration
for amap, want in (("NaiveMigration", m3["naive"]), ("CellMigration", None)):
    src, tgt, h = W.abstraction_map("AnchorMigration", amap)
    got = check_abstraction_map(mach("AnchorMigration", src), mach("AnchorMigration", tgt), h)
    check(f"B AnchorMigration: {amap}", got, want)

# ---- TaskResume
m, enc = rep("TaskResume", "NoReadSets")
check("B TaskResume: NoReadSets now / updates pair / behavioral word",
      (check_now(m, enc), check_updates(m, enc)["pair"], check_behavioral(m, enc)["word"]),
      (None, r4["noreads_updates"]["pair"], ["withdraw1"]))
m, enc = rep("TaskResume", "ReadSets")
check("B TaskResume: ReadSets Checked", check_behavioral(m, enc), None)
cls, _ = minimize_for_queries(mach("TaskResume", "Resume"))
check("B TaskResume: ResumeMemory equals Part A", same_partition(cls, r4["classes"]), True)

# ---- ItemGoals
for name, key in (("Reply", "reply"), ("Nag", "nag"), ("Triage", "triage"), ("ReplyNag", "reply+nag"),
                  ("AllGoals", "reply+nag+triage"), ("ReplyTriage", "reply+triage")):
    cls, _ = minimize_for_queries(mach("ItemGoals", name))
    py, _ = P5.closure(key.split("+"))
    check(f"B ItemGoals: MinimizeForQueries {name} equals Part A", same_partition(cls, py), True)
for rname, want in (("DaysLeft", None), ("BenFirst", None), ("Cap3", k5["cap3"]["determines_old"]),
                    ("NagForDays", k5["days-left"]["old_determines_new"]),
                    ("NagForBenFirst", k5["nag-ben-first"]["old_determines_new"]),
                    ("NagForCap3", k5["cap3"]["old_determines_new"])):
    m, enc = rep("ItemGoals", rname)
    check(f"B ItemGoals: CheckNow {rname} as in Part A", wit_pair(check_now(m, enc)), wit_pair(want))
for gname, n in (("DaysGoal", 4), ("BenFirstGoal", 7), ("Cap3Goal", 5)):
    cls, _ = minimize_for_queries(mach("ItemGoals", gname))
    check(f"B ItemGoals: MinimizeForQueries {gname}", len(cls), n)
src, tgt, h = W.abstraction_map("ItemGoals", "ToDeadline")
check("B ItemGoals: ToDeadline Checked", check_abstraction_map(mach("ItemGoals", src), mach("ItemGoals", tgt), h), None)
cls, _ = minimize_for_queries(mach("ItemGoals", "NagByDeadline"))
check("B ItemGoals: MinimizeForQueries NagByDeadline (the migrated goal keeps 4 classes)", len(cls), 4)

# the negated goal: informational equivalence without goal preservation
check("B ItemGoals: CheckNow AntiAsNag and CheckNow NagForAntiNag both Checked (informational equivalence)",
      (check_now(*rep("ItemGoals", "AntiAsNag")), check_now(*rep("ItemGoals", "NagForAntiNag"))), (None, None))
cls_anti, _ = minimize_for_queries(mach("ItemGoals", "AntiNagGoal"))
cls_nag, _ = minimize_for_queries(mach("ItemGoals", "Nag"))
check("B ItemGoals: AntiNagMemory is the 4-class partition of NagMemory",
      (len(cls_anti), same_partition(cls_anti, cls_nag)), (4, True))

# the interpretation obligation, from the declared consumers and decoders
INTERP_A = {"DaysFollowUps": k5["days-left"]["interpretation"],
            "BenFirstFollowUps": k5["nag-ben-first"]["interpretation"],
            "Cap3FollowUps": k5["cap3"]["interpretation"],
            "DeadlineFollowUps": k5["migration_interpretation"],
            "AntiNagFollowUps": k5["anti-nag"]["interpretation"],
            "AntiNagWaits": k5["anti-nag-waits"]["interpretation"]}
INTERP_B = {}
for new, want in INTERP_A.items():
    via = "ToDeadline" if new == "DeadlineFollowUps" else None
    got = W.check_interpretation("ItemGoals", "NagFollowUps", new, via)
    INTERP_B[new] = got
    check(f"B ItemGoals: CheckInterpretation NagFollowUps {new}{' (Via ToDeadline)' if via else ''} as in Part A",
          (got["status"], w5(got.get("witness"))), ("Checked" if want is None else "Refuted", w5(want)))
got = W.check_interpretation("ItemGoals", "NagFollowUps", "DeadlineFollowUps")
check("B ItemGoals: CheckInterpretation across schemas without Via is InvalidInput naming both carriers",
      (got["status"], got["reason"]),
      ("InvalidInput", "Nag has states Record and NagByDeadline has states DeadlineRecord; "
                       "a change of record schema needs (Via map)"))
got = W.check_interpretation("ItemGoals", "DaysFollowUps", "DeadlineFollowUps", "ToDeadline")
check("B ItemGoals: CheckInterpretation along a map from another machine is InvalidInput naming the mismatch",
      (got["status"], got["reason"]),
      ("InvalidInput", "ToDeadline starts from Nag, not from DaysGoal, the machine of DaysFollowUps"))
b5 = INTERP_B["AntiNagFollowUps"]["binding"]
check("B ItemGoals: an interpretation result is bound to both consumers, machines, queries and decoders with "
      "their custody, and to the 40 records",
      (b5["subject"], b5["old"], b5["new"], b5["via"], b5["scope"], b5["module_digest"] == W.module_digest("ItemGoals")),
      (["NagFollowUps", "AntiNagFollowUps"],
       {"consumer": "NagFollowUps", "machine": "Nag", "queries": {"nag": "nag"}, "decoder": "follow-up-if-true",
        "custody": "Frame"},
       {"consumer": "AntiNagFollowUps", "machine": "AntiNagGoal", "queries": {"anti": "anti-nag"},
        "decoder": "follow-up-if-true", "custody": "Frame"},
       None, {"records": "Record", "count": 40}, True))
check("B ItemGoals: interpretation results carry no assumptions; Checked by enumeration, Refuted by a replayed witness",
      {n: (r["binding"]["assumptions"], r["binding"]["assurance"]) for n, r in INTERP_B.items()},
      {n: ([], "Exact" if INTERP_A[n] is None else "Witness") for n in INTERP_A})
ci_runs = [r[2] for r in W.runs if r[1] == "ItemGoals" and isinstance(r[2], list) and r[2][0] == "CheckInterpretation"]
check("B ItemGoals: the module's CheckInterpretation requests and their statuses",
      [(show(rq), W.run_request("ItemGoals", rq)["status"]) for rq in ci_runs],
      [("(CheckInterpretation NagFollowUps DaysFollowUps)", "Checked"),
       ("(CheckInterpretation NagFollowUps BenFirstFollowUps)", "Checked"),
       ("(CheckInterpretation NagFollowUps Cap3FollowUps)", "Refuted"),
       ("(CheckInterpretation NagFollowUps DeadlineFollowUps (Via ToDeadline))", "Checked"),
       ("(CheckInterpretation NagFollowUps AntiNagFollowUps)", "Refuted"),
       ("(CheckInterpretation NagFollowUps AntiNagWaits)", "Checked"),
       ("(CheckInterpretation NagFollowUps DeadlineFollowUps)", "InvalidInput"),
       ("(CheckInterpretation DaysFollowUps DeadlineFollowUps (Via ToDeadline))", "InvalidInput")])
kinds_b = {}
for name, old_from_new, new_from_old, cons in (("days-left", "DaysLeft", "NagForDays", "DaysFollowUps"),
                                               ("nag-ben-first", "BenFirst", "NagForBenFirst", "BenFirstFollowUps"),
                                               ("cap3", "Cap3", "NagForCap3", "Cap3FollowUps"),
                                               ("anti-nag", "AntiAsNag", "NagForAntiNag", "AntiNagFollowUps"),
                                               ("anti-nag-waits", "AntiAsNag", "NagForAntiNag", "AntiNagWaits")):
    kinds_b[name] = P5.kind(check_now(*rep("ItemGoals", old_from_new)) is None,
                            check_now(*rep("ItemGoals", new_from_old)) is None,
                            INTERP_B[cons]["status"] == "Checked")
kinds_b["migration"] = P5.kind(None, None, INTERP_B["DeadlineFollowUps"]["status"] == "Checked",
                               migration=check_abstraction_map(mach("ItemGoals", src), mach("ItemGoals", tgt), h) is None)
check("B ItemGoals: the classification from the module's results equals Part A", kinds_b, KINDS5)

# ---- ClaimArbitration
start6 = W.ev("ClaimArbitration", "start", {}, {})
for wname, bname, want in (("WeightedLaw", "LawfulWeighted", (["evidence"], ("high", False, False, "calm"))),
                           ("NormFirstLaw", "LawfulNormFirst", None),
                           ("ConflictWatch", "Agreement", (["evidence"], ("high", False, False, "calm")))):
    mm = mach("ClaimArbitration", wname)
    lv = least_violation(mm, [start6], W.block_predicate("ClaimArbitration", bname))
    check(f"B ClaimArbitration: {bname}", None if lv is None else (lv["word"], lv["state"]), want)
check("B ClaimArbitration: reachable states (weighted, norm-first)",
      (len(mach("ClaimArbitration", "WeightedLaw").states), len(mach("ClaimArbitration", "NormFirstLaw").states)),
      (14, 11))

# ---- MotivationGrid
start7m = W.ev("MotivationGrid", "start", {}, {})
for wname, bname, want in (("PlainWatch", "SafePlain", (vp["word"], vp["state"])), ("FloorWatch", "SafeFloor", None)):
    mm = mach("MotivationGrid", wname)
    lv = least_violation(mm, [start7m], W.block_predicate("MotivationGrid", bname))
    check(f"B MotivationGrid: {bname}", None if lv is None else (lv["word"], lv["state"]), want)
check("B MotivationGrid: Settled has 80 states", len(W.carrier("MotivationGrid", "Settled")), 80)
for iname, L, eta, want_ok in (("OrderSwapFloor", F(1), F(1, 2), False), ("OrderSwapDamped", F(1), F(1, 2), True),
                               ("OrderSwapSettled", F(1), F(1, 2), True), ("OrderSwapSettled", F(1), F(1, 4), False),
                               ("NearBoundaryFloor", F(1, 2), F(3, 4), True), ("NearBoundaryFloor", F(1, 2), F(1, 2), False),
                               ("NearBoundaryDamped", F(1, 2), F(5, 8), True)):
    ideal, actual, audit, din, dout, ok = W.implementation("MotivationGrid", iname)
    least, wit = check_implementation(audit, ideal, actual, din, dout, L, eta, ok)
    check(f"B MotivationGrid: CheckImplementation {iname} (Grade {L} {eta})", wit is None, want_ok)

# ---- StaleMonitor
null = W.ev("StaleMonitor", ["stale", "accepted", "one"], {}, {})
alt = W.ev("StaleMonitor", ["stale", "failing", "one"], {}, {})
check("B StaleMonitor: null and alternative laws", (null, alt), ({1: F(1, 20), 0: F(19, 20)}, {1: F(1, 5), 0: F(4, 5)}))
check("B StaleMonitor: CheckMonitor validity", sum(null[k] * alt[k] / null[k] for k in null), F(1))
for sname, fname in (("LiveSuggestions", "stale_alt_seed1"), ("QuietSuggestions", "stale_null_seed1")):
    d = W.decl("StaleMonitor", sname)
    path = os.path.join(HERE, W.field(d, "Source")[1].strip('"'))
    digest = W.field(d, "Digest")[1].strip('"')
    check(f"B StaleMonitor: {sname} digest matches the stored file", P8.digest(path), digest)

# ---- consumers and the gate
CONSUMERS = [(mn, n) for mn, md in W.modules.items() for n, d in md.decls.items() if d[0] == "Consumer"]
parsed = {}
for mn, n in CONSUMERS:
    try:
        parsed[(mn, n)] = W.consumer(mn, n)
    except InvalidInput as e:
        parsed[(mn, n)] = str(e)
check("B Consumers: every Accepts declaration parses; frame consumers accept only Checked results",
      (len(CONSUMERS), sum(isinstance(c, dict) for c in parsed.values()),
       sorted(n for (mn, n), c in parsed.items() if isinstance(c, dict) and c["custody"] == "Frame"
              and (c["accepts"]["statuses"] != ["Checked"] or c["accepts"]["backends"]))),
      (15, 15, []))
OBLIGATION = "sha256:" + "0" * 64


def trusted(solver, version, logic):
    return {"TrustedBackend": {"solver": solver, "version": version, "logic": logic, "obligation": OBLIGATION}}


offers = [{"status": "Checked", "binding": {"assumptions": []}},
          {"status": "Conditional", "binding": {"assumptions": [trusted("cvc5", "1.4.2", "QF_LRA")]}},
          {"status": "Conditional", "binding": {"assumptions": [trusted("z3", "5.3.3", "QF_LRA")]}},
          {"status": "Conditional", "binding": {"assumptions": [trusted("cvc5", "1.4.2", "QF_LRA"),
                                                                trusted("z3", "5.3.3", "QF_LRA")]}},
          {"status": "Estimated", "binding": {"assumptions": []}},
          {"status": "Unknown", "binding": {"assumptions": []}}]
check("B Consumers: what EngineQueries and CommitmentQueries accept "
      "(Checked; Conditional on cvc5, on z3, on both; Estimated; Unknown)",
      {c: [W.accepts("OpenItems", c, r)[0] for r in offers] for c in ("EngineQueries", "CommitmentQueries")},
      {"EngineQueries": [True, True, False, False, False, False],
       "CommitmentQueries": [True, False, False, False, False, False]})


def assumed(name):
    return {"Assumption": {"name": name, "digest": OBLIGATION}}


def from_estimate(delta):
    return {"EstimatedPremise": {"result": OBLIGATION, "delta": delta}}


def conditional(*asm):
    return {"status": "Conditional", "binding": {"assumptions": list(asm)}}


combined = parse_accepts(["Checked", "Estimated", ["Conditional", ["TrustedBackend", "cvc5"], ["Assumption", "StepModel"]]])
cvc5_only = parse_accepts(["Checked", ["Conditional", ["TrustedBackend", "cvc5"]]])
offers2 = [conditional(trusted("cvc5", "1.4.2", "QF_LRA")), conditional(assumed("StepModel")),
           conditional(assumed("OtherModel")), conditional(from_estimate("1/100")),
           conditional(trusted("cvc5", "1.4.2", "QF_LRA"), assumed("StepModel")),
           conditional(assumed("StepModel"), trusted("z3", "5.3.3", "QF_LRA"))]
check("B Consumers: the specification's combined form (Accepts Checked Estimated (Conditional (TrustedBackend cvc5) "
      "(Assumption StepModel))) against (Accepts Checked (Conditional (TrustedBackend cvc5))), on results "
      "Conditional on cvc5, on StepModel, on another assumption, on an estimate, on cvc5 and StepModel, on StepModel "
      "and z3", ([admits(combined, r)[0] for r in offers2], [admits(cvc5_only, r)[0] for r in offers2]),
      ([True, True, False, True, True, False], [True, False, False, False, False, False]))


def bound_result(mod, request, subject, scope, status, assumptions=()):
    assurance = {"Checked": "Exact", "Refuted": "Witness", "Conditional": "TrustedBackend"}[status]
    return {"request": request, "status": status,
            "binding": W.binding(mod, subject, scope, assumptions, assurance)}


ONE_STEP = {"horizon": 1}
ALL_WORDS = {"horizon": "AllFiniteWords", "discount": 1, "policies": "Words"}
m, enc = rep("EvidenceMemory", "MinimalAll")
r_upd = bound_result("EvidenceMemory", "(CheckUpdates MinimalAll)", "MinimalAll", ONE_STEP,
                     "Checked" if check_updates(m, enc) is None else "Refuted")
r_beh = bound_result("EvidenceMemory", "(CheckBehavioral MinimalAll)", "MinimalAll", ALL_WORDS,
                     "Checked" if check_behavioral(m, enc) is None else "Refuted")
check("B Gate: the binding of (CheckUpdates MinimalAll) as printed in Appendix C.6",
      {k: v for k, v in r_upd["binding"].items() if k != "module_digest"},
      {"module": "EvidenceMemory", "subject": ["MinimalAll", "minimal"], "machine": "AllThree",
       "states": "Evidence", "queries": {"contra": "contra", "eff": "eff", "regen": "regen"},
       "actions": {"(plus a)": "(plus a)", "(plus b)": "(plus b)", "(plus c)": "(plus c)",
                   "(minus a)": "(minus a)", "(minus b)": "(minus b)", "(minus c)": "(minus c)"},
       "merges": {}, "tolerance": "exact", "scope": {"horizon": 1}, "assumptions": [], "assurance": "Exact"})
r_win = bound_result("OpenItems", "(CheckUpdates WindowView)", "WindowView", ONE_STEP,
                     "Checked" if check_updates(*rep("OpenItems", "WindowView")) is None else "Refuted")
check("B Gate: the binding of (CheckUpdates WindowView) as printed in Appendix C.2",
      (r_win["status"], {k: v for k, v in r_win["binding"].items() if k not in ("module", "module_digest")}),
      ("Refuted", {"subject": ["WindowView", "window-view"], "machine": "GoalEngine", "states": "Live",
                   "queries": {"suggest": "suggest"}, "actions": {"tick": "tick", "reply": "on-reply"},
                   "merges": {}, "tolerance": "exact", "scope": {"horizon": 1}, "assumptions": [],
                   "assurance": "Witness"}))
TOUCHED3 = [{"module": "EvidenceMemory", "consumer": "ContraProbe", "custody": "Frame"},
            {"module": "EvidenceMemory", "consumer": "EffectiveSupport", "custody": "Agent"},
            {"module": "EvidenceMemory", "consumer": "AnchorCues", "custody": "Frame"}]
g = W.gate({"touched": TOUCHED3, "results": [r_upd, r_beh]})
check("B Gate: the bundle of Appendix C.6 covers its three consumers through the joint machine AllThree",
      ({c: v["verdict"] for c, v in g.items()},
       [W.covers("EvidenceMemory", t["consumer"], r_upd["binding"])[1] for t in TOUCHED3]),
      ({"ContraProbe": "covered", "EffectiveSupport": "covered", "AnchorCues": "covered"},
       ["removed queries"] * 3))
m, enc = rep("EvidenceMemory", "CountsC")
r_counts = bound_result("EvidenceMemory", "(CheckBehavioral CountsC)", "CountsC", ALL_WORDS,
                        "Checked" if check_behavioral(m, enc) is None else "Refuted")
g = W.gate({"touched": TOUCHED3[:2], "results": [r_counts]})
check("B Gate: a result bound to Contra covers ContraProbe and is InvalidInput for EffectiveSupport",
      (g["ContraProbe"]["verdict"], g["EffectiveSupport"]["verdict"], g["EffectiveSupport"]["notes"]),
      ("covered", "inadequate",
       [{"request": "(CheckBehavioral CountsC)", "status": "InvalidInput",
         "mismatch": "bound to Contra, checked without the query eff that EffectiveSupport reads through Eff"}]))
m, enc = rep("EvidenceMemory", "ProtectedE")
r_prot = bound_result("EvidenceMemory", "(CheckNow ProtectedE)", "ProtectedE", {"horizon": 0},
                      "Checked" if check_now(m, enc) is None else "Refuted")
g = W.gate({"touched": TOUCHED3, "results": [r_upd, r_beh, r_prot]})
check("B Gate: the Refuted (CheckNow ProtectedE) blocks EffectiveSupport and does not count for the other two",
      {c: v["verdict"] for c, v in g.items()},
      {"ContraProbe": "covered", "EffectiveSupport": "blocked", "AnchorCues": "covered"})
CVC5 = [trusted("cvc5", "1.4.2", "QF_LRA")]
r_eng = bound_result("OpenItems", "(CheckBehavioral EventView)", "EventView", ALL_WORDS, "Conditional", CVC5)
r_com = bound_result("OpenItems", "CommitmentMemory", "Commitments", ALL_WORDS, "Conditional", CVC5)
g = W.gate({"touched": [{"module": "OpenItems", "consumer": "EngineQueries", "custody": "Agent"},
                        {"module": "OpenItems", "consumer": "CommitmentQueries", "custody": "Frame"}],
            "results": [r_eng, r_com]})
check("B Gate: results Conditional on cvc5 cover EngineQueries and are inadequate coverage for CommitmentQueries",
      ({c: v["verdict"] for c, v in g.items()}, [n for n in g["CommitmentQueries"]["notes"] if "not_accepted" in n]),
      ({"EngineQueries": "covered", "CommitmentQueries": "inadequate"},
       [{"request": "CommitmentMemory", "status": "Conditional",
         "not_accepted": "CommitmentQueries accepts no Conditional result"}]))

RESULTS["seconds"] = round(time.time() - T0, 1)
with open(os.path.join(HERE, "mg_results.json"), "w") as f:
    json.dump(RESULTS, f, indent=1)
print(f"{CHECKS[0] - len(FAILS)} checks passed, {len(FAILS)} failed, {RESULTS['seconds']} s")
sys.exit(1 if FAILS else 0)
