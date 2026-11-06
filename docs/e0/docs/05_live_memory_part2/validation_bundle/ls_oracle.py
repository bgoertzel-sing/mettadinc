#!/usr/bin/env python3
"""Oracle for Part II of the guide to Omega memory and goals in MeTTaDinC (live memory through
summary statistics).

Part A recomputes every number the guide quotes from the Python models in models/: the symbolic
obligations with the Z3 solver on encodings written by hand (models/smt_live.py, p3_live.py),
the large simulations of the live stores, and the statistical procedures.  Part B reads
live_memory.metta with the reference evaluator ls_eval.py, rebuilds every statistic,
representation, simulation, block partition, contract, stream and monitor from the module text,
decides every request with the cvc5 solver, replays every witness by direct evaluation, and
compares each verdict with Part A.  Two solvers and two independent encodings therefore stand
behind every symbolic verdict; since neither solver's proof is checked, a verdict of
unsatisfiability is reported as Conditional on (TrustedBackend cvc5 ...), with Z3's agreement
recorded under agreed_by beside it in the section "verdicts" of ls_results.json.  Part B also runs
the negative fixtures: two requests of the module, a lift whose item statistic belongs to another
machine and a safety transfer along a simulation with another target, are InvalidInput, and a copy
of a stream whose content no longer matches its declared digest is refused before any estimate is
computed.

Run: python3 ls_oracle.py        (well under a minute on one core; writes ls_results.json)
"""
import hashlib
import json
import math
import os
import random
import sys
import time
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "models"))

import cs  # noqa: E402
import estimates as EST  # noqa: E402
import p1_live as P1  # noqa: E402
import p2_live as P2  # noqa: E402
import p3_live as P3  # noqa: E402
import p4_live as P4  # noqa: E402
import p6_live as P6  # noqa: E402
import p_attention as PA  # noqa: E402
import smt_live as SMT  # noqa: E402
from ls_eval import World, show  # noqa: E402

T0 = time.time()
CHECKS = [0]
FAILS = []
RESULTS = {}


def js(x):
    if isinstance(x, F):
        return str(x)
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, (tuple, list)):
        return [js(y) for y in x]
    if isinstance(x, (set, frozenset)):
        return sorted(js(y) for y in x)
    if isinstance(x, dict):
        return {str(k): js(v) for k, v in x.items()}
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


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def digest(path):
    return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()


ALPHA = 0.01

# ================================================================== Part A: the Python models
print("== Part A: models")

# ---- A1. confidence sequences and e-processes
cov = {p: cs.coverage(p, 2000, 2000, 0.05, seed) for p, seed in ((0.01, 1), (0.05, 2), (0.2, 3), (0.5, 4))}
check("A1 confidence sequence at level 0.05: the true rate leaves it in at most 5% of 2,000 runs "
      "of 2,000 events (p = 0.01, 0.05, 0.2, 0.5)", all(v <= 0.05 for v in cov.values()), True)
RESULTS["A1 coverage miss fractions"] = js(cov)
zf = {n: (cs.zero_failure_upper(n, ALPHA), cs.clopper_pearson_zero_upper(n, ALPHA)) for n in (100, 1000, 10000, 100000)}
check("A1 zero-failure upper bounds at level 0.01, anytime and fixed-n (n = 100, 1e3, 1e4, 1e5)",
      [tuple(round(v, 6) for v in zf[n]) for n in sorted(zf)],
      [(0.08808, 0.045007), (0.011448, 0.004595), (0.001381, 0.00046), (0.000161, 4.6e-05)])
check("A1 the zero-failure bound is the upper end of the mixture sequence at S = 0 (n = 1000)",
      close(cs.cs_interval(0, 1000, ALPHA)[1], zf[1000][0], 1e-9), True)
ss = EST.tables(ALPHA)["sample_size"]
def first_dip(p, target):
    n, U = cs.upper_ends(p, ALPHA, 40000)
    return int(n[int((U <= target).argmax())])


check("A1 events from which on the upper end stays below a target, and the first event at which it "
      "dips below, counts rounded half up (0.01->0.02, 0.05->0.10, 0.05->0.075, 0.2->0.25)",
      ([ss[k] for k in ("0.01->0.02", "0.05->0.1", "0.05->0.075", "0.2->0.25")],
       [first_dip(p, t) for p, t in ((0.01, 0.02), (0.05, 0.10), (0.05, 0.075), (0.2, 0.25))]),
      ([3275, 514, 1811, 1179], [3135, 486, 1729, 1147]))
dr = {q: cs.drift(p, 0.05, 0.2) for p, q in ((0.1, "0.1"), (0.2, "0.2"), (0.3, "0.3"))}
check("A1 drift of the log e-value per observation, fixed alternative 1/5 against 1/20, at rates "
      "1/10, 1/5, 3/10", [round(dr[k], 4) for k in ("0.1", "0.2", "0.3")], [-0.016, 0.1398, 0.2956])
mon = EST.monitor_comparison(alpha=ALPHA, p0=0.05, runs=1000, steps=2000, seed=11)
det = mon["detect"]
check("A1 detection within 2,000 observations at rate 1/10: fixed, finite mixture, uniform mixture",
      [det["0.1"][k]["detected"] for k in ("fixed", "finite", "uniform")], [0.496, 1.0, 1.0])
check("A1 median detection time at rate 1/10 (finite and uniform mixture) and at rate 1/5 "
      "(fixed, finite, uniform)",
      [det["0.1"]["finite"]["median"], det["0.1"]["uniform"]["median"],
       det["0.2"]["fixed"]["median"], det["0.2"]["finite"]["median"], det["0.2"]["uniform"]["median"]],
      [224.0, 310.0, 32.0, 37.0, 40.0])
check("A1 false alarms at the null rate 1/20 in 2,000 runs, all three at most 0.01",
      all(v <= ALPHA for v in mon["false_alarm"].values()), True)
RESULTS["A1 false alarm fractions"] = js(mon["false_alarm"])
# Proposition 5.1: one-sided claims hold for the running average of the conditional rates
osb = cs.one_sided_bound(0.05, ALPHA)
check("A1 Proposition 5.1's bound for the claim 'rate below 1/20' at level 0.01: 0.05/(99 + 0.05)",
      round(osb, 6), 0.000505)
ose = {sc: cs.one_sided_errors(0.05, 0.05, 2000, 2000, seed, sc)
       for sc, seed in (("common", 21), ("spread", 22), ("runs", 23))}
check("A1 Proposition 5.1 at level 0.05, 2,000 runs of 2,000 rows whose conditional rates are all at least 1/20 "
      "(common rate, rates spread over [1/20, 3/20], labels in runs): the upper end falls below 1/20 in no more "
      "runs than the bound 0.0026 allows", all(v <= cs.one_sided_bound(0.05, 0.05) for v in ose.values()), True)
check("A1 Proposition 5.1 simulation: the largest of the three error fractions (0.15 percent)", max(ose.values()),
      0.0015)
RESULTS["A1 one-sided error fractions"] = js(ose)

# ---- A2. the stored streams
streams = {name: digest(os.path.join(HERE, "streams", name + ".json"))
           for name in ("context_receipts_seed2", "stale_ten_seed1", "stale_alt_seed1", "stale_null_seed1")}
check("A2 stream digests", streams, {
    "context_receipts_seed2": "sha256:71b78af0105a000962267564e4ecf181ff696b2d227523e37b7dfd3011491019",
    "stale_ten_seed1": "sha256:d1c692b4962de6113c041d046f012d93348fb1779dcbfa99d94f713356608dcc",
    "stale_alt_seed1": "sha256:f0d4be8461a2904e728f7b0a8ad895385ccd56f340ec854d729936aaf6a48763",
    "stale_null_seed1": "sha256:8e76cbdeee37a8ab4156c6068ee59fab740c2f9d1b02146e3ee7e38c594b59b0"})
ten = EST.load_stream("stale_ten_seed1")
check("A2 stale_ten_seed1: stale suggestions among 2,000", sum(ten), 200)
lo, hi = cs.cs_interval(sum(ten), len(ten), ALPHA)
check("A2 stale_ten_seed1: confidence-sequence interval at level 0.01", (round(lo, 4), round(hi, 4)),
      (0.0744, 0.1303))
fx = cs.first_crossing(ten, lambda S, t: cs.log_e_fixed(S, t, 0.05, 0.2), ALPHA)
fm = cs.first_crossing(ten, lambda S, t: cs.log_e_finite_mixture(S, t, 0.05, [0.1, 0.2, 0.4]), ALPHA)
um = cs.first_crossing(ten, lambda S, t: cs.log_e_uniform_mixture(S, t, 0.05), ALPHA)
check("A2 stale_ten_seed1: first crossing of 100 (fixed 1/5, finite mixture, uniform mixture)", (fx, fm, um),
      (27, 132, 152))
S = 0
peak, final = 0.0, 0.0
for t, x in enumerate(ten, 1):
    S += x
    v = cs.log_e_fixed(S, t, 0.05, 0.2)
    peak = max(peak, v)
    final = v
check("A2 stale_ten_seed1: fixed alternative, largest e-value and e-value after 2,000 observations",
      (round(math.exp(peak), 1), f"{math.exp(final):.2e}"), (154.7, "1.18e-14"))
p1s = EST.part1_streams(ALPHA, 0.05)
check("A2 Part I streams: stale counts and intervals at level 0.01 (alternative stream, null stream)",
      [(p1s[k]["stale"], round(p1s[k]["lo"], 4), round(p1s[k]["hi"], 4)) for k in ("stale_alt_seed1", "stale_null_seed1")],
      [(79, 0.128, 0.2822), (28, 0.03, 0.1327)])

# ---- A3. Pattern 1: open items in real time
r0 = P1.simulate()
check("A3 open items, 120 days: items, replies, query times", (r0["items"], r0["replies"], r0["queries"]),
      (917, 650, 960))
check("A3 the keyed event statistic answers every suggestion query and every count exactly",
      (r0["event_exact"], r0["counts_exact"]), (True, True))
check("A3 the window view: stale suggestions among its suggestions", (r0["window_stale"], r0["window_suggestions"]),
      (15800, 40208))
check("A3 creation-day histogram: two-sided bounds hold; total width against total count",
      (r0["hist_bounds_hold"], r0["hist_width_total"], r0["hist_count_total"]), (True, 2150, 24408))
r1 = P1.simulate(miss=0.1, seed=2)
check("A3 with 10% of replies missed (seed 2): items, replies, missed replies, stale suggestions, "
      "all stale ones are missed replies",
      (r1["items"], r1["replies"], r1["missed"], r1["event_stale"], r1["stale_subset_of_missed"]),
      (974, 677, 71, 2907, True))
s1 = SMT.p1()
check("A3 Z3: event, joint and engine statistics, every obligation unsat",
      all(v == "unsat" for k, v in s1.items() if k.split("_")[0] in ("event", "joint", "engine")), True)
check("A3 Z3: the window view, now and updates (sat) and the designed witnesses",
      (s1["window_now"], s1["window_now_witness_ok"], s1["window_updates"], s1["window_updates_witness_ok"]),
      ("sat", True, "sat", True))

# ---- A4. Pattern 2: context blocks
th = P2.theorem_check(20000, 1)
check("A4 consumer-aware blocks serve every consumer whenever the required items fit (20,000 random "
      "snapshots of 1 to 80 items, four budgets)", (th["holds"], th["fit_cases"], th["nofit_cases"]),
      (True, 16399, 3601))
check("A4 snapshots in which the required items fit but another policy misses a consumer",
      th["fit_cases_where_another_policy_misses"], 13057)
re_ = EST.receipt_estimates(2000, 2, ALPHA)
misses = {p: [re_["rates"][p][k]["misses"] for k in P2.KINDS] for p in re_["rates"]}
check("A4 receipt log, 2,000 snapshots: misses of the fresh, open and anchor consumers per policy", misses,
      {"recency": [53, 182, 298], "relevance": [139, 817, 1856], "protected": [262, 1063, 0],
       "consumer": [0, 0, 0]})
check("A4 receipt log: the largest token cost of the required items (budget 1,500)", re_["max_required_cost"], 349)
ra = re_["rates"]["relevance"]["A"]
check("A4 relevance policy, anchor consumer: interval at level 0.01", (round(ra["lo"], 4), round(ra["hi"], 4)),
      (0.9012, 0.9498))
check("A4 consumer-aware policy, anchor consumer: upper end after 2,000 snapshots without a miss",
      round(re_["rates"]["consumer"]["A"]["hi"], 5), 0.00608)
pr = re_["paired"]
check("A4 paired comparison, relevance against consumer-aware on the anchor: discordant snapshots and "
      "the lower end of the share", (pr["relevance_misses_consumer_serves"], pr["relevance_serves_consumer_misses"],
                                     round(pr["share_lo"], 4)), (1856, 0, 0.9935))

# ---- A5. Pattern 3: evidence from many sources
ex = P3.exhaustive()
check("A5 D_2 against brute force, every incident sequence of length at most 6 over 4 sources",
      (ex["prefixes"], ex["ok"]), (299593, True))
check("A5 D_2 is minimal: distinct reachable values separated (3 sources K = 2; 4 sources K = 3)",
      (P3.minimality(), P3.minimality(sources=("a", "b", "c", "d"), K=3)),
      ({"values": 5, "separated": True}, {"values": 12, "separated": True}))
check("A5 D_K on 100,000 incidents over 10,000 sources (K = 1, 2, 3, 5)", P3.large_random()["ok"], True)
mg = P3.merges()
check("A5 merges of forks with a shared history: D_2 exact; summed totals wrong in trials",
      (mg["dk_merge_exact"], mg["summed_totals_wrong"]), (True, 15017))
wd = P3.withdrawal_counterexample()
check("A5 D_2 is not maintainable under withdrawals: {a, b} and {a, b, c} share the value Many and differ "
      "after withdrawing a and b", (wd["same_value_before"], wd["contra_after"]), (True, (False, True)))
check("A5 Z3: D_2 on an unbounded sort of sources (initial, step, reads, merge)", P3.smt_proof(),
      {"initial": "unsat", "step": "unsat", "reads": "unsat", "merge": "unsat"})

# ---- A6. Pattern 4: read sets at scale
bl = P4.simulate(n_results=2000, withdrawals=500)
check("A6 inverted index exact; Bloom filters miss no stale result", (bl["index_exact"], bl["bloom_missed"]),
      (True, 0))
check("A6 Bloom filters, 10 bits per item, 7 hashes: unaffected results flagged at least once (of all "
      "unaffected), stale results, results flagged in total, false positives per result-withdrawal pair, "
      "observed and predicted false-positive rates",
      (bl["bloom_unnecessary"], bl["results"] - bl["stale_true"], bl["stale_true"], bl["flagged_total"],
       bl["fp_hits"], bl["fp_trials"], round(bl["fp_rate"], 5), round(bl["fp_expected"], 5)),
      (1720, 1761, 239, 1959, 8483, 999744, 0.00849, 0.00819))

# ---- A7. Pattern 5: goals on real ages
s5 = SMT.p5()
check("A7 Z3: classification of the three changes (days-left, ben-first, three days): new determines old, "
      "old determines new",
      [(s5[f"{c}_preserves_old"], s5[f"{c}_converse"]) for c in ("days_left", "ben_first", "cap3")],
      [("unsat", "sat"), ("unsat", "sat"), ("sat", "sat")])
check("A7 Z3: certificates for saturation at two and at three days and for the deadline migration",
      all(v == "unsat" for k, v in s5.items()
          if k.startswith(("saturate_at_2_", "saturate_at_3_", "deadline_")) and not k.endswith("separated")), True)
check("A7 Z3: the two-day statistic also answers the days-left goal (a refinement at no cost in memory)",
      s5["saturate_at_2_serves_days_left"], "unsat")
check("A7 Z3: among statistics that keep the open flag, saturating at the threshold is the coarsest "
      "(two and three days): open ages up to the threshold are separated by a wait",
      (s5["saturate_at_2_ages_separated"], s5["saturate_at_3_ages_separated"]), ("unsat", "unsat"))
check("A7 Z3: the two-day statistic cannot serve the three-day goal; ages 5/2 and 7/2 witness it",
      (s5["two_for_both_now"], s5["two_for_both_witness_ok"]), ("sat", True))

# ---- A8. Pattern 6: arbitration on real values
s6 = SMT.p6()
check("A8 Z3: stuttering simulation of both rules onto Part I's model (every obligation unsat)",
      all(s6[k] == "unsat" for k in ("evidence_stutter_or_step", "pressure_stutter_or_step", "domain_closed",
                                     "act_commutes_weighted", "act_commutes_norm_first", "goals_factor_weighted",
                                     "goals_factor_norm_first", "unlawful_preserved_weighted",
                                     "unlawful_preserved_norm_first")), True)
check("A8 Z3: the two evidence obligations become linear when lambda (1 - c) is replaced by t with "
      "0 <= t <= 1 - c: matching and closure unsat, the forms linear, the original nonlinear, the range "
      "lemma unsat",
      (s6["evidence_linear_match"], s6["evidence_linear_closed"], s6["evidence_linear_forms"],
       s6["evidence_original_nonlinear"], s6["evidence_range_lemma"]),
      ("unsat", "unsat", True, True, "unsat"))
check("A8 Z3: the norm-first rule never picks a forbidden move; the weighted rule can",
      (s6["norm_first_never_forbidden"], s6["weighted_can_be_forbidden"]), ("unsat", "sat"))
check("A8 live runs of the weighted rule from the start: (evidence 4/5) and (deadline 1/2) each reach an "
      "unlawful state", (s6["weighted_live_run_evidence"], s6["weighted_live_run_deadline"], s6["start_lawful"]),
      (True, True, True))
p6r = P6.check()
check("A8 20,000 random real runs of 8 steps per rule: every step a stutter or the matching step; "
      "abstract states visited, Part I reachable states",
      [(p6r[k]["simulation_ok"], p6r[k]["visited_inside_part1_reach"], p6r[k]["abstract_states_visited"],
        p6r[k]["part1_reachable"]) for k in ("weighted", "norm_first")],
      [(True, True, 14, 14), (True, True, 11, 11)])
check("A8 random runs in which the rule consolidates an unchecked claim (weighted, norm-first)",
      (p6r["weighted"]["runs_consolidating_unchecked"] > 0, p6r["norm_first"]["runs_consolidating_unchecked"]),
      (True, 0))
RESULTS["A8 weighted runs consolidating unchecked"] = p6r["weighted"]["runs_consolidating_unchecked"]

# ---- A9. Pattern 7: MetaMo on real values
s7 = SMT.p7()
check("A9 Z3: the floor keeps the safe region (unsat); the plain rule leaves it (sat), to 1/4 from the "
      "designed witness", (s7["floor_keeps_safe_region"], s7["plain_leaves_safe_region"], s7["plain_witness_gi_after"]),
      ("unsat", "sat", "1/4"))
check("A9 Z3: on settled states the two orders give equal goal weights", s7["settled_goal_weights_agree"], "unsat")
check("A9 Z3 optimization: the largest goal-weight difference between the two orders, and a maximizer",
      (s7["order_swap_goal_sup"], s7["order_swap_goal_argmax"]), ("9/10", ["1", "2/5", "1", "0", "0", "1"]))
run7 = SMT.p7_run()
check("A9 exact run from the start after (stimulus 1 0): individuation after four cycles, plain and floor",
      (run7["plain"], run7["floor"]), (["3/4", "3/4", "1/2", "1/4"], ["3/4", "3/4", "1/2", "1/2"]))

# ---- A10. approximate statistics
at = PA.attention()
check("A10 attention decaying by 1/2 with rounding after every update: largest error over 5,000 updates "
      "within the contraction bound 1", (at["within_bound"], at["bound"]), (True, "1"))
RESULTS["A10 attention largest error"] = at["max_error"]
tt = PA.totals()
check("A10 running totals of 100,000 weights rounded half up: largest and final error without "
      "recomputation, largest error with exact recomputation from the records every 100 updates (bound 50.5)",
      (tt["max_error_plain"], tt["final_error_plain"], tt["max_error_anchored"],
       tt["max_error_anchored"] <= tt["anchored_bound"]), (534.8, 512.09, 12.44, True))
RESULTS["A10 totals"] = js(tt)

# ================================================================== Part B: the module text
print("== Part B: module text, cvc5")
W = World([os.path.join(HERE, "memory_goals.metta"), os.path.join(HERE, "live_memory.metta")])
B = {}
for path, form in W.runs:
    if not path.endswith("live_memory.metta"):
        continue
    _, mod, rq = form
    B[(mod, show(rq))] = W.run(mod, rq)
check("B number of run requests in live_memory.metta", len(B), 37)


def res(mod, rq):
    return B[(mod, rq)]


def on_cvc5(r):
    """(status, solver named in the TrustedBackend assumption) of a solver-backed result."""
    a = r.get("assumptions") or [{}]
    return r["status"], a[0].get("TrustedBackend", {}).get("solver")


COND = ("Conditional", "cvc5")


# ---- B1. LiveOpenItems
for st in ("EventStat", "JointStat", "EngineStat"):
    r = res("LiveOpenItems", f"(CheckStatistic {st} (Method Symbolic))")
    check(f"B LiveOpenItems: CheckStatistic {st}: every obligation unsat, Conditional on cvc5, as Z3 (A3)",
          (on_cvc5(r), set(r["obligations"].values())), (COND, {"unsat"}))
for st in ("EventIndex", "JointIndex"):
    r = res("LiveOpenItems", f"(CheckStatistic {st} (Method Lift))")
    check(f"B LiveOpenItems: CheckStatistic {st} by lifting, bound to ItemTime's queries, Conditional as its premise",
          (on_cvc5(r), r["method"], r["binding"]["bound_to"][1], r["binding"]["queries"]),
          (COND, "Lift", "ItemTime", ["open", "suggest"]))
rv = res("LiveOpenItems", "(CheckStatistic EngineIndex (Method Lift))")
check("B LiveOpenItems: the engine statistic lifted to a declared view is bound to that view's one query",
      (on_cvc5(rv), rv["binding"]["bound_to"][1], rv["binding"]["queries"]), (COND, "EngineTime", ["suggest"]))
rx = res("LiveOpenItems", "(CheckStatistic EngineAsItems (Method Lift))")
check("B LiveOpenItems: negative fixture: a statistic of EngineTime lifted as an index of the store's item "
      "machine is InvalidInput", (rx["status"], "EngineTime" in rx["mismatch"] and "ItemTime" in rx["mismatch"]),
      ("InvalidInput", True))
# the review's separating pair: equal engine codes, different open answers, so the wrong lift would
# have certified an index that cannot answer the commitment query
es = W.fn("LiveOpenItems", "engine-stat")
op = W.fn("LiveOpenItems", "open")
xa, xb = (F(8), False, F(0)), (F(8), True, F(0))
check("B LiveOpenItems: why the wrong lift is refused: (8, false, 0) and (8, true, 0) have the same engine code and "
      "different open answers", (es(xa) == es(xb), op(xa), op(xb)), (True, True, False))
rn = res("LiveOpenItems", "(CheckNow WindowView)")
ru = res("LiveOpenItems", "(CheckUpdates WindowView)")
check("B LiveOpenItems: WindowView refuted now and under updates, as Z3 (A3)", (rn["status"], ru["status"]),
      ("Refuted", "Refuted"))
# replay the solver's witnesses by direct evaluation
enc = W.fn("LiveOpenItems", "window-view")
sug = W.fn("LiveOpenItems", "suggest")
x, y = rn["witness"]["values"]["x"], rn["witness"]["values"]["y"]
check("B LiveOpenItems: the CheckNow witness replays (equal codes, different suggest answers)",
      (enc(x) == enc(y), sug(x) != sug(y), W.member("LiveOpenItems", "Item", x), W.member("LiveOpenItems", "Item", y)),
      (True, True, True, True))
wv = ru["witness"]["values"]
wt = W.fn("LiveOpenItems", ["wait", "$d"], {"$d": wv["$d"]})
check("B LiveOpenItems: the CheckUpdates witness replays (equal codes, different codes after the wait)",
      (enc(wv["x"]) == enc(wv["y"]), enc(wt(wv["x"])) != enc(wt(wv["y"]))), (True, True))

# ---- B2. LiveEvidence
r = res("LiveEvidence", "(CheckStatistic FirstOrMore (Method Symbolic))")
check("B LiveEvidence: CheckStatistic FirstOrMore Conditional on cvc5, merge included, as Z3 (A5)",
      (on_cvc5(r), r["obligations"].get("merge join")), (COND, "unsat"))
rng = random.Random(7)
agree = True
for _ in range(3000):
    st = (frozenset(), frozenset())
    inc = []
    for _ in range(rng.randint(0, 8)):
        s, pol = rng.choice("abcdef"), rng.choice("+-")
        inc.append((s, pol))
        st = W.fn("LiveEvidence", ["plus" if pol == "+" else "minus", "$s"], {"$s": s})(st)
    code = W.fn("LiveEvidence", "d2-stat")(st)
    got = {"contra": W.fn("LiveEvidence", "d2-contra")(code), "eff": int(W.fn("LiveEvidence", "d2-eff")(code)),
           "regen": W.fn("LiveEvidence", "d2-regen")(code)}
    if got != P3.answers_brute(inc):
        agree = False
check("B LiveEvidence: the module's maps against the brute-force answers on 3,000 random incident logs", agree, True)

# ---- B3. LiveGoals
want5 = {"DaysLeft": "Conditional", "NagForDays": "Refuted", "BenFirst": "Conditional", "NagForBenFirst": "Refuted",
         "Cap3": "Refuted", "NagForCap3": "Refuted", "TwoForBoth": "Refuted"}
check("B LiveGoals: CheckNow verdicts, as Z3 (A7)",
      {k: res("LiveGoals", f"(CheckNow {k})")["status"] for k in want5}, want5)
for st in ("SaturateAtTwo", "SaturateAtThree", "Deadline"):
    check(f"B LiveGoals: CheckStatistic {st} Conditional on cvc5, as Z3 (A7)",
          on_cvc5(res("LiveGoals", f"(CheckStatistic {st} (Method Symbolic))")), COND)
ok_replay = True
for k, v in want5.items():
    if v != "Refuted":
        continue
    d = W.find("LiveGoals", k)[1]
    enc = W.fn("LiveGoals", W.field(d, "Encode")[1])
    mach = W.field(d, "Of")[1]
    qs = [W.fn(e[0], e[4]) for e in W.entries("LiveGoals", mach, "Observe")]
    wv = res("LiveGoals", f"(CheckNow {k})")["witness"]["values"]
    if not (enc(wv["x"]) == enc(wv["y"]) and any(q(wv["x"]) != q(wv["y"]) for q in qs)):
        ok_replay = False
check("B LiveGoals: every CheckNow witness replays", ok_replay, True)

# ---- B4. LiveArbitration
for sim in ("StutterWeighted", "StutterNormFirst"):
    r = res("LiveArbitration", f"(CheckSimulation {sim})")
    check(f"B LiveArbitration: CheckSimulation {sim} Conditional on cvc5, with stuttering, as Z3 (A8)",
          (on_cvc5(r), r["matching"]), (COND, "Stutter"))
rs = res("LiveArbitration", "(CheckSafety NormFirst (Never (Shows unlawful True)) (Via StutterNormFirst) "
                            "(Init live-start))")
check("B LiveArbitration: CheckSafety NormFirst, Conditional as its simulation; Part I's reachable states; the result "
      "is about RealNormFirst", (on_cvc5(rs), rs["reachable_target_states"], rs["binding"]["about"][1]),
      (COND, 11, "RealNormFirst"))
rm_ = res("LiveArbitration", "(CheckSafety NormFirst (Never (Shows unlawful True)) (Via StutterWeighted) "
                             "(Init live-start))")
check("B LiveArbitration: negative fixture: safety of NormFirst along StutterWeighted, whose target is Weighted, is "
      "InvalidInput", (rm_["status"], "Weighted" in rm_["mismatch"]), ("InvalidInput", True))
rw = res("LiveArbitration", "(CheckSafety Weighted (Never (Shows unlawful True)) (Via StutterWeighted) "
                            "(Init live-start))")
check("B LiveArbitration: CheckSafety Weighted refuted by a concrete live run, as A8",
      (rw["status"], rw["run"], rw["state"]), ("Refuted", ["(evidence 4/5)"], (F(4, 5), False, False, F(0))))
rng = random.Random(9)
agree = True
for _ in range(5000):
    st = (F(rng.randint(0, 20), 20), rng.random() < 0.5, rng.random() < 0.5, F(rng.randint(0, 20), 20))
    for kind, mp in (("weighted", "weighted"), ("norm_first", "norm-first")):
        if W.fn("LiveArbitration", mp)(st) != P6.real_rule(kind)(st):
            agree = False
check("B LiveArbitration: the module's rules against Part I's rules through the class map, 5,000 random "
      "real states", agree, True)

# ---- B5. LiveMotivation
rp = res("LiveMotivation", "(CheckBlockPartition SafePlain (Of PlainWatch) (Budget (Unrollings 8)))")
check("B LiveMotivation: SafePlain refuted: the invariant is not inductive, and a reachable run leaves "
      "the safe region, as A9", (rp["status"], rp["inductive"], rp["violation"], rp["word"], rp["state"][0]),
      ("Refuted", False, "cover", ["(stimulus 1 0)", "cycle", "cycle", "cycle", "cycle"], F(1, 4)))
wx = rp["witness"]["values"]["x"]
cyc = W.fn("LiveMotivation", "cycle-plain")
check("B LiveMotivation: the non-inductiveness witness replays", (wx[0] >= F(1, 2), cyc(wx)[0] < F(1, 2)),
      (True, True))
rf = res("LiveMotivation", "(CheckBlockPartition SafeFloor (Of FloorWatch))")
check("B LiveMotivation: SafeFloor established by the inductive invariant, Conditional on cvc5, as A9",
      (on_cvc5(rf), rf["inductive"]), (COND, True))
r9 = res("LiveMotivation", "(CheckImplementation OrderSwapGoals (Grade 1 (Rat 9 10)))")
r8 = res("LiveMotivation", "(CheckImplementation OrderSwapGoals (Grade 1 (Rat 4 5)))")
rS = res("LiveMotivation", "(CheckImplementation OrderSwapSettled (Grade 1 0))")
check("B LiveMotivation: order swap within 9/10 (Conditional on cvc5), refuted at 4/5, exact on settled states "
      "(Conditional on cvc5), as A9", (on_cvc5(r9), r8["status"], on_cvc5(rS)), (COND, "Refuted", COND))
check("B LiveMotivation: the 4/5 witness replays (difference above 4/5, at most 9/10)",
      (r8["witness"]["out"] > F(4, 5), r8["witness"]["out"] <= F(9, 10)), (True, True))
rng = random.Random(11)
agree = True
for _ in range(3000):
    s = (F(rng.randint(1, 4), 4), F(rng.randint(0, 8), 8), F(rng.randint(0, 8), 8), F(rng.randint(0, 8), 8),
         F(rng.randint(0, 1)), F(rng.randint(0, 1)))
    gi, g1, a, c, nu, rho = s
    psi = (gi, g1, (nu + g1) / 2, (rho + gi) / 2, nu, rho)
    if psi != W.fn("LiveMotivation", "appraise")(s):
        agree = False
check("B LiveMotivation: the module's appraisal against the model's on 3,000 grid states", agree, True)

# ---- B6. LiveReceipts
e1 = res("LiveReceipts", '(EstimateRate (On ContextReceipts) (Column "relevance_A") (Equals 0) (Level (Rat 1 100)))')
e2 = res("LiveReceipts", '(EstimateRate (On ContextReceipts) (Column "consumer_A") (Equals 0) (Level (Rat 1 100)))')
c12 = res("LiveReceipts", '(CompareRates (On ContextReceipts) (First "relevance_A") (Second "consumer_A") '
                          '(Equals 0) (Level (Rat 1 100)))')
e3 = res("LiveReceipts", '(EstimateRate (On LiveSuggestions) (Column "stale") (Equals 1) (Level (Rat 1 100)))')
check("B LiveReceipts: each estimate is bound to its stream, digest, population, selection rule and policy",
      (e1["binding"]["stream"][1], e1["binding"]["digest"] == digest(os.path.join(HERE, "streams",
                                                                                 "context_receipts_seed2.json")),
       sorted(k for k in e1["binding"] if k in ("population", "selection", "policy")), e3["binding"]["stream"][1]),
      ("ContextReceipts", True, ["policy", "population", "selection"], "LiveSuggestions"))
check("B LiveReceipts: EstimateRate and CompareRates from the frozen stream equal A4 recomputed from the "
      "generator", ((e1["count"], round(e1["lower"], 4), round(e1["upper"], 4)), (e2["count"], round(e2["upper"], 5)),
                    (c12["first_only"], c12["second_only"], round(c12["lower"], 4))),
      ((1856, 0.9012, 0.9498), (0, 0.00608), (1856, 0, 0.9935)))
check("B LiveReceipts: EstimateRate on Part I's alternative stream equals A2", (e3["count"], round(e3["lower"], 4),
                                                                                  round(e3["upper"], 4)),
      (79, 0.128, 0.2822))
cm = res("LiveReceipts", "(CheckMonitor StaleFifth)")
check("B LiveReceipts: CheckMonitor StaleFifth: null expectation of the factor exactly one, Checked by exact "
      "arithmetic", (cm["status"], cm["assurance"], cm["valid"], cm["exactly_one"], cm["blind"]),
      ("Checked", "Exact", True, True, False))
d1 = res("LiveReceipts", "(Detect StaleFifth (On TenPercent) (Level (Rat 1 100)))")
d3 = res("LiveReceipts", "(Detect StaleTenth StaleFifth StaleTwoFifths (On TenPercent) (Level (Rat 1 100)) "
                         "(Combine Mixture))")
check("B LiveReceipts: Detect in exact arithmetic: first crossings equal A2 (fixed 27, mixture 132)",
      ((d1["fired"], d1["step"]), (d3["fired"], d3["step"])), (("StaleFifth", 27), ("Mixture", 132)))

# ---- B7. negative fixture: a stream changed under its declared digest is refused
import shutil  # noqa: E402
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    for f in ("live_memory.metta",):
        shutil.copy(os.path.join(HERE, f), tmp)
    part1_src = os.path.join(HERE, "memory_goals.metta")
    shutil.copy(part1_src if os.path.exists(part1_src) else os.path.join(HERE, "..", "memgoals", "memory_goals.metta"),
                tmp)
    shutil.copytree(os.path.join(HERE, "streams"), os.path.join(tmp, "streams"))
    sp = os.path.join(tmp, "streams", "stale_alt_seed1.json")
    data = json.load(open(sp))
    col = data["schema"].index("stale")
    for row in data["rows"]:
        row[col] = 0
    open(sp, "w").write(json.dumps(data, separators=(",", ":")))
    Wt = World([os.path.join(tmp, "memory_goals.metta"), os.path.join(tmp, "live_memory.metta")])
    rq = [x for p_, (_, m_, x) in [(p_, f_) for p_, f_ in Wt.runs] if m_ == "LiveReceipts" and x[0] == "EstimateRate"
          and "LiveSuggestions" in show(x)][0]
    rt = Wt.run("LiveReceipts", rq)
check("B LiveReceipts: negative fixture: every stale label of LiveSuggestions set to 0 under the declared digest; "
      "EstimateRate is InvalidInput and computes no count", (rt["status"], "count" in rt, "LiveSuggestions" in
                                                              rt["mismatch"]), ("InvalidInput", False, True))

# ---- the verdicts, with the agreement of Z3 recorded under agreed_by beside every Conditional one.  Each
# subject names the Part A checks in which Z3 decided the same obligations on encodings written by hand; a
# lifted statistic agrees when its premise does, and a safety transfer when its simulation does as well.
import re  # noqa: E402
import z3  # noqa: E402
Z3V = "z3 " + z3.get_version_string()
Z3_OF = {"EventStat": ["A3 Z3: event, joint and engine statistics"],
         "JointStat": ["A3 Z3: event, joint and engine statistics"],
         "EngineStat": ["A3 Z3: event, joint and engine statistics"],
         "FirstOrMore": ["A5 Z3: D_2 on an unbounded sort"],
         "DaysLeft": ["A7 Z3: classification of the three changes"],
         "BenFirst": ["A7 Z3: classification of the three changes"],
         "SaturateAtTwo": ["A7 Z3: certificates for saturation"],
         "SaturateAtThree": ["A7 Z3: certificates for saturation"],
         "Deadline": ["A7 Z3: certificates for saturation"],
         "StutterWeighted": ["A8 Z3: stuttering simulation"],
         "StutterNormFirst": ["A8 Z3: stuttering simulation"],
         "NormFirst": ["A8 Z3: the norm-first rule never picks a forbidden move"],
         "SafeFloor": ["A9 Z3: the floor keeps the safe region"],
         "OrderSwapGoals": ["A9 Z3 optimization"],
         "OrderSwapSettled": ["A9 Z3: on settled states"]}


def z3_agrees(subject):
    names = [k for pre in Z3_OF.get(subject, []) for k in RESULTS if k.startswith(pre)]
    return bool(names) and all(RESULTS[k]["ok"] for k in names)


VERDICTS = {}
n_cond = n_agreed = 0
for (mod, rq), r in B.items():
    e = {"module": mod, "request": rq, "status": r["status"], "assurance": r.get("assurance")}
    for k in ("method", "assumptions", "binding", "witness", "mismatch"):
        if k in r:
            e[k] = js(r[k])
    if r["status"] == "Conditional":
        n_cond += 1
        subjects = [r["binding"]["premise"][1]] if r.get("method") == "Lift" else [rq.split()[1].rstrip(")")]
        via = re.search(r"\(Via (\S+?)\)", rq)
        if rq.startswith("(CheckSafety") and via:
            subjects.append(via.group(1))
        if all(z3_agrees(x) for x in subjects):
            e["agreed_by"] = [Z3V]
            n_agreed += 1
    VERDICTS[f"{mod} {rq}"] = e
check("B every Conditional verdict records the agreement of Z3 under agreed_by (lifts through their premises, the "
      "safety transfer through its simulation)", (n_cond, n_agreed), (18, 18))
RESULTS["verdicts"] = VERDICTS

RESULTS["seconds"] = round(time.time() - T0, 1)
with open(os.path.join(HERE, "ls_results.json"), "w") as f:
    json.dump(RESULTS, f, indent=1)
print(f"{CHECKS[0] - len(FAILS)} checks passed, {len(FAILS)} failed, {RESULTS['seconds']} s")
sys.exit(1 if FAILS else 0)
