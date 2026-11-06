#!/usr/bin/env python3
"""Oracle for the worked example of Part II of the guide to Omega memory and goals in MeTTaDinC:
WMTM's open-item store, simulated through eight weeks of the goal engine's log-only phase.

Part A regenerates the simulated deployment from its seed and recomputes every number the guide
quotes: the frozen streams and their digests, the counts of the run, the parser regression, its
confirmation and the monitors, the estimates with the confidence sequences of models/cs.py, the
ground truth against which the estimates are checked, the planning sizes, and the obligations of
every symbolic request in the Z3 solver on encodings written by hand (models/wx_smt.py).  Part B
reads wmtm_example.metta with the reference evaluator ls_eval.py (with Part II's and Part I's
module files, which the example imports from), answers every request from the module text with
the cvc5 solver or from the frozen streams, replays every witness, compares each verdict and
number with Part A, and runs four differential tests: the conformance replay of the frozen
journal, through an abstraction function, against the module's maps at every daily cycle of every
key; a randomized test of the release's snooze semantics; the rebuild of the release's indexes from
the durable records; and the replay of the frozen journal through the release's engine index with
snoozes given on proposals, which leaves every key's first proposal, and so the key receipts of E2,
unchanged.  A verdict that rests on cvc5's answer of unsatisfiability is Conditional on
(TrustedBackend cvc5 ...); the file wx_results.json records every verdict under "verdicts", with
Z3's agreement under agreed_by beside each Conditional one.

Run: python3 wx_oracle.py        (a few seconds on one core; writes wx_results.json)
"""
import hashlib
import json
import math
import os
import random
import re
import sys
import tempfile
import time
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "models"))

import cs  # noqa: E402
import wx_facts as X  # noqa: E402
import wx_sim as W  # noqa: E402
import wx_smt as SMT  # noqa: E402
from ls_eval import World, show  # noqa: E402

T0 = time.time()
CHECKS = [0]
FAILS = []
RESULTS = {}
FACTS = {}


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


def r4(x):
    return round(x, 4)


ALPHA = 0.01
P = W.P
MODULE = os.path.join(HERE, "wmtm_example.metta")

# ============================================================ Part A
print("== Part A: the simulated deployment, the estimates and the Z3 obligations")
sim = W.run()
FACTS["counts"] = X.counts(sim)
FACTS["regression"] = X.regression(sim)
mon = X.monitors(sim)
traces = mon.pop("traces")
FACTS["monitors"] = mon
FACTS["gate_descriptive"] = X.gate_descriptive(sim)
FACTS["truth"] = X.truth(sim)

# A1 the frozen streams are reproduced from the seed, byte for byte
with tempfile.TemporaryDirectory() as tmp:
    saved = W.DATA
    W.DATA = tmp
    regenerated = W.freeze(sim)
    W.DATA = saved
on_disk = {n: "sha256:" + hashlib.sha256(open(os.path.join(HERE, "streams", n + ".json"), "rb").read()).hexdigest()
           for n in regenerated}
check("A1 every frozen stream is reproduced byte for byte from the seed", regenerated == on_disk, True)
declared = dict(re.findall(r'\(Source "streams/([a-z_0-9]+)\.json"\)\s*\(Digest "(sha256:[0-9a-f]+)"\)',
                           open(MODULE).read()))
check("A1 the module pins the ten streams it reads by their digests",
      (len(declared), all(on_disk[n] == d for n, d in declared.items())), (10, True))
FACTS["digests"] = on_disk

# A counterfactual run of the same simulation without the rollback (v2 stays deployed)
pcf = dict(P)
pcf["arl"] = 10 ** 300
cf = W.run(pcf)
vcf = X.ville_trace(cf["reply_rows"], P["p0"], P["alternatives"])
first_v = next(i for i, v in enumerate(vcf) if v >= math.log(1 / ALPHA))
scf = X.sr_trace(cf["reply_rows"], P["p0"], P["alternatives"])
first_s = next(i for i, v in enumerate(scf) if v >= math.log(P["arl"]))
d_s, d_v = cf["reply_rows"][first_s]["day"], cf["reply_rows"][first_v]["day"]
cf_stale = sum(1 for rows in cf["cycles"] for r in rows if r["event"] and r["stale"] and d_s < r["day"] <= d_v)
run_stale = sum(1 for rows in sim["cycles"] for r in rows if r["event"] and r["stale"] and d_s < r["day"] <= d_v)
FACTS["counterfactual"] = {"ville_receipt": first_v + 1, "ville_day": d_v, "sr_receipt": first_s + 1, "sr_day": d_s,
                           "stale_without_rollback": cf_stale, "stale_in_the_run": run_stale,
                           "difference": cf_stale - run_stale}
check("A4 without the rollback: Part II's monitor would fire at receipt 524 on day 30 and the changepoint monitor at "
      "receipt 399 on day 23; stale proposals on days 24-30 without the rollback, in the run, and the difference",
      (first_v + 1, d_v, first_s + 1, d_s, cf_stale, run_stale, cf_stale - run_stale),
      (524, 30, 399, 23, 169, 21, 148))

c = FACTS["counts"]
check("A2 the run: items (weekdays), keys, duplicate keys, replies, spurious closings, paraphrases, audited items",
      (c["items"], c["weekday_items"], c["keys"], c["duplicate_keys"], c["replies"], c["spurious"], c["paraphrases"],
       c["audited"]), (1357, 1218, 1362, 5, 955, 9, 5, 438))
check("A2 the journal and the logs: notes of the eight weeks, event-design proposals (per day), window-design "
      "proposals", (c["journal_notes"], c["event_proposals"], c["proposals_per_day"], c["window_proposals"]),
      (2326, 3767, 67.3, 7176))
check("A2 replies and reply receipts: replies before day 56, receipts, replies to items older than seven days at the "
      "next cycle, replies after the last cycle; closure receipts",
      (c["replies"], c["reply_receipts"], c["replies_too_old"], c["replies_after_last_cycle"], c["closure_receipts"]),
      (955, 916, 31, 8, 937))

g = FACTS["regression"]
check("A3 the regression: alarm day and receipt, hours from the update, receipts and stale ones since the update",
      (g["alarm_day"], g["alarm_observation"], g["hours_update_to_alarm"], g["receipts_since_update"],
       g["stale_since_update"]), (23, 399, 47.0, 37, 10))
check("A3 the confirmation fixed in advance: replies received after the alarm's receipts and audited the next "
      "morning, missed, interval at level 0.01, confirmed (lower end above 1/20)",
      (g["confirmation_replies"], g["confirmation_missed"], r4(g["confirmation_interval"][0]),
       r4(g["confirmation_interval"][1]), g["confirmed"]), (15, 5, 0.0512, 0.7525, True))
check("A3 the targeted audit of all replies since the update: replies, received before the alarm's cycle, among them "
      "the replies of the receipts that raised the alarm",
      (g["targeted"], g["targeted_before_alarm"], g["targeted_alarm_receipts"]), (59, 44, 37))
check("A3 the rollback at day 24 noon: replies during v2, missed by v2, recovered by the re-parse",
      (g["rollback"], g["replies_during_v2"], g["missed_during_v2"], g["recovered"]), (24.5, 64, 18, 18))
check("A3 only one alarm in eight weeks", len(sim["alarms"]), 1)

m = FACTS["monitors"]
check("A4 Part II's mixture monitor (Ville scheme) never fires: largest value and where, log value at the update, "
      "at the alarm and at the end",
      (r4(m["ville_largest"]), m["ville_largest_at"], m["ville_log_at_update"], m["ville_log_at_alarm"],
       m["ville_log_end"]), (0.807, 1, -16.93, -11.46, -31.2))
check("A4 the Shiryaev-Roberts mixture: log value at the update and at the alarm (threshold log 100,000 = 11.51)",
      (m["sr_log_at_update"], m["sr_log_at_alarm"], round(math.log(P["arl"]), 2)), (2.12, 11.67, 11.51))
check("A4 the last receipt for a reply received before the update, and the first after it",
      (m["update_receipt"], sim["reply_rows"][m["update_receipt"]]["reply"] >= P["v2_start"]), (362, True))
check("A4 the restarted monitor: first receipt it read, receipts no monitor read, receipts read, largest value and "
      "its logarithm",
      (m["restart_first"], tuple(m["unread"]), m["restart_receipts"], round(m["restart_largest"], 2),
       m["restart_log_largest"]), (420, (400, 419), 497, 47.63, 3.86))
check("A4 the days of receipts 399, 400, 404, 405, 419 and 420: the alarm's batch, the batch of day 24, the "
      "first batch after the rollback", tuple(sim["reply_rows"][i - 1]["day"] for i in (399, 400, 404, 405, 419, 420)),
      (23, 23, 23, 24, 24, 25))


# A5 the estimates, from the frozen streams with models/cs.py
def stream(name):
    return json.load(open(os.path.join(HERE, "streams", name + ".json")))


def est(name, col):
    d = stream(name)
    i = d["schema"].index(col)
    S, n = sum(1 for r in d["rows"] if r[i] == 1), len(d["rows"])
    lo, hi = cs.cs_interval(S, n, ALPHA)
    return S, n, lo, hi


EST = {}
for nm, (sname, col) in {"replies_before": ("replies_before", "stale"), "audit_v2": ("audit_replies_v2", "missed"),
                         "audit_after_alarm": ("audit_after_alarm", "missed"),
                         "replies_gate": ("replies_gate", "stale"), "keys_gate": ("keys_gate", "duplicate"),
                         "closures_gate": ("closures_gate", "spurious"),
                         "audit_replies_gate": ("audit_replies_gate", "missed"),
                         "audit_open_gate": ("audit_open_gate", "false_close")}.items():
    EST[nm] = est(sname, col)
lv = stream("lives_gate")
b = sum(1 for r in lv["rows"] if r[2] == 1 and r[3] == 0)
cc = sum(1 for r in lv["rows"] if r[2] == 0 and r[3] == 1)
both = sum(1 for r in lv["rows"] if r[2] == 1 and r[3] == 1)
lo, hi = cs.cs_interval(b, b + cc, ALPHA)
EST["lives_gate"] = (b, cc, both, len(lv["rows"]), lo, hi)
FACTS["estimates"] = {k: list(v) for k, v in EST.items()}
fmt = lambda t: (t[0], t[1], r4(t[2]), r4(t[3]))
check("A5 reply receipts before the update: stale, receipts, interval at level 0.01",
      fmt(EST["replies_before"]), (5, 362, 0.0009, 0.0565))
check("A5 targeted audit of the replies since the update: missed, audited, interval",
      fmt(EST["audit_v2"]), (17, 59, 0.1144, 0.5202))
check("A5 the confirmation stream (replies after the alarm's receipts): missed, audited, interval, as the rule in "
      "the loop", fmt(EST["audit_after_alarm"]) + (EST["audit_after_alarm"][2] > float(P["p0"]),),
      (5, 15, 0.0512, 0.7525, True))
check("A5 the interval before the update and the audit's interval do not overlap",
      EST["replies_before"][3] < EST["audit_v2"][2], True)
check("A5 gate E1: reply receipts days 28-55: stale, receipts, interval (upper end below 1/20)",
      fmt(EST["replies_gate"]) + (EST["replies_gate"][3] < 0.05,), (4, 436, 0.0004, 0.0436, True))
check("A5 gate E2: keys first proposed days 28-55: duplicates, keys, interval (upper end below 1/20)",
      fmt(EST["keys_gate"]) + (EST["keys_gate"][3] < 0.05,), (5, 453, 0.0007, 0.046, True))
check("A5 gate E3: lifetime receipts of keys whose decisions all fall in the window: window worse only, event worse "
      "only, both, keys, interval for the window's share of the discordant keys",
      (b, cc, both, len(lv["rows"]), r4(lo), r4(hi)), (314, 0, 4, 482, 0.9676, 1.0))
check("A5 gate E6: closure receipts days 28-55: spurious, closures, interval (upper end below 1/20)",
      fmt(EST["closures_gate"]) + (EST["closures_gate"][3] < 0.05,), (2, 451, 0.0, 0.0339, True))
check("A5 gate E4: random audit, items with a reply by age four: missed, audited, interval",
      fmt(EST["audit_replies_gate"]), (2, 140, 0.0001, 0.0969))
check("A5 gate E5: random audit, items without a reply by age four: false closings, audited, interval",
      fmt(EST["audit_open_gate"]), (0, 76, 0.0, 0.1111))
check("A5 the gate's confidence budget: six Estimated claims at level 0.01", round(6 * ALPHA, 2), 0.06)
check("A5 a union bound over all nine estimates of the example (six gate claims, three of the incident)",
      (len(EST), round(len(EST) * ALPHA, 2)), (9, 0.09))

t = FACTS["truth"]
check("A6 the ground truth lies inside every interval: miss rate before the update, under v2 (all audited replies and "
      "those after the alarm), at the gate (reply receipts and audit), duplicates among proposed keys, spurious first "
      "closings, false closings by age four",
      (EST["replies_before"][2] <= t["miss_v1"] <= EST["replies_before"][3],
       EST["audit_v2"][2] <= t["miss_v2"] <= EST["audit_v2"][3],
       EST["audit_after_alarm"][2] <= t["miss_v2"] <= EST["audit_after_alarm"][3],
       EST["replies_gate"][2] <= t["miss_v1"] <= EST["replies_gate"][3],
       EST["audit_replies_gate"][2] <= t["audit_missed"] <= EST["audit_replies_gate"][3],
       EST["keys_gate"][2] <= t["duplicate_among_proposed"] <= EST["keys_gate"][3],
       EST["closures_gate"][2] <= t["spurious_first_closing"] <= EST["closures_gate"][3],
       EST["audit_open_gate"][2] <= t["false_close_by_age4"] <= EST["audit_open_gate"][3]),
      (True,) * 8)
check("A6 the truths: audited miss rate, share of primary keys proposed, duplicates among proposed keys, spurious first "
      "closings, false closings by age four",
      (r4(t["audit_missed"]), r4(t["primary_proposed"]), r4(t["duplicate_among_proposed"]),
       r4(t["spurious_first_closing"]), r4(t["false_close_by_age4"])), (0.0148, 0.6841, 0.0087, 0.0103, 0.0112))

late = math.exp(-P["audit_age"] / P["false_mean"])
FACTS["truth"]["spurious_after_audit"] = round(late, 4)
check("A6 the share of spurious closing notes that arrive after the age of the audit (about one in fourteen)",
      (round(late, 4), round(1 / late, 1)), (0.0695, 14.4))
gd = FACTS["gate_descriptive"]
check("A7 per-proposal labels in the gate window (descriptions only): event proposals, stale, duplicate; window "
      "proposals, stale; distinct stale keys",
      (gd["event_proposals"], gd["event_stale"], gd["event_duplicate"], gd["window_proposals"], gd["window_stale"],
       gd["stale_keys"]), (1952, 39, 30, 3752, 1839, 7))
check("A7 with feedback each stale key would be proposed stale once: proposals, stale",
      (gd["with_feedback_proposals"], gd["with_feedback_stale"]), (1920, 7))

dc = X.decomposition(sim)
FACTS["decomposition"] = dc
check("A7 the window design's stale proposals in the gate window: all, shared with the event design, its own; "
      "proposals the event design made and the window did not",
      (dc["window_stale"], dc["shared"], dc["window_only"], dc["event_not_window"]), (1839, 39, 1800, 0))
check("A7 the event design's stale proposals in the gate window: from missed replies (keys), from duplicate keys "
      "of answered items (keys)",
      (dc["stale_missed"], dc["stale_missed_keys"], dc["stale_duplicate"], dc["stale_duplicate_keys"]),
      (30, 5, 9, 2))
check("A7 the event design's stale proposals in the gate window come in runs: stale proposals per key",
      dc["stale_runs"], [7, 7, 6, 6, 5, 4, 4])
check("A7 the keys of the lifetime receipts: keys, keys the window design erred on, keys the event design erred on "
      "(replies lost to v2, replies missed by v1)",
      (dc["lives"], dc["window_bad_keys"], dc["event_bad_keys"], dc["event_bad_reparsed"], dc["event_bad_missed"]),
      (482, 318, 4, 0, 4))
ex = X.examples(sim)
FACTS["examples"] = ex
check("A2 the journal items followed in the text: cycles at which the event design and the window design proposed "
      "i0288 (falsely closed on day 11), and its audit at age four",
      (ex["i0288"]["event"], ex["i0288"]["window"], ex["i0288"]["audit"]["false_close"],
       round(ex["i0288"]["audit"]["time"], 2)), ([11], [11, 14, 15, 16, 17], True, 14.75))
check("A2 i0500 (reply missed by v2 on day 22): proposed on days 19-24, stale on days 23 and 24; i1235 and its "
      "paraphrased key i1235b, whose key receipt on day 52 carries the duplicate label",
      (ex["i0500"]["event"], ex["i0500"]["stale"], ex["i1235"]["event"], ex["i1235"]["window"],
       ex["i1235b"]["event"], tuple(ex["i1235b_key_receipt"])),
      ([19, 20, 21, 22, 23, 24], [23, 24], [], [53, 54, 55], [52, 53, 54, 55], (52, True)))
rp = stream("replies")
ir = {c: i for i, c in enumerate(rp["schema"])}
kofi = [(r[ir["day"]], r[ir["stale"]]) for r in rp["rows"] if r[ir["key"]] == "i0500"]
FACTS["examples"]["i0500_reply_receipt"] = kofi
check("A2 i0500: the one reply receipt of its reply, released at the cycle of day 23 and labeled stale",
      kofi, [(23, 1)])
pr, kg = stream("proposals"), stream("keys_gate")
ip, ik = {c: i for i, c in enumerate(pr["schema"])}, {c: i for i, c in enumerate(kg["schema"])}
dup_labels = {}
for r in pr["rows"]:
    if P["gate"][0] <= r[ip["day"]] < P["gate"][1] and r[ip["duplicate"]]:
        dup_labels[r[ip["key"]]] = dup_labels.get(r[ip["key"]], 0) + 1
kg_dup = sum(1 for r in kg["rows"] if r[ik["duplicate"]])
check("A7 E2 does not transport to a policy that withholds first proposals: one that withheld every key that is not a "
      "duplicate would propose a subset of the log-only keys, with duplicate share 5 of 5 instead of 5 of 453",
      (kg_dup, len(kg["rows"]), kg_dup, kg_dup), (5, 453, 5, 5))
check("A7 the duplicate labels of the gate window come from the duplicate keys of KeysGate: labels, keys",
      (sum(dup_labels.values()), sorted(dup_labels)), (30, sorted(r[ik["key"]] for r in kg["rows"] if r[ik["duplicate"]])))
it0829 = next(it for it in sim["items"] if it["id"] == "i0829")
check("A2 i0829: spurious closing note and real reply (times), cycles at which each design proposed it, stale ones; "
      "the three spurious first closings and the days of their receipts",
      (round(it0829["false_close"], 2), round(it0829["reply"], 2), ex["i0829"]["event"], ex["i0829"]["window"],
       ex["i0829"]["stale"], [tuple(x) for x in ex["spurious_closures"]]),
      (34.98, 35.57, [33, 34], [33, 34, 37, 38, 39], [37, 38, 39], [("i0288", 12), ("i0829", 35), ("i1107", 46)]))
lv_ = stream("lives_gate")
il_ = {c: i for i, c in enumerate(lv_["schema"])}
row0829 = [(r[il_["day"]], r[il_["window_bad"]], r[il_["event_bad"]]) for r in lv_["rows"] if r[il_["key"]] == "i0829"]
check("A2 i0829's lifetime receipt (day, window_bad, event_bad): the window design's stale proposals are counted, the "
      "omission both designs made at the cycle of day 35 is not", row0829, [(40, 1, 0)])
check("A2 the random audit over the eight weeks: audited, with a reply by age four, missed, false closings; stale "
      "proposals caused by the replies v2 missed, and their first and last day",
      (ex["audits"]["audited"], ex["audits"]["replied"], ex["audits"]["missed"], ex["audits"]["false_close"],
       ex["v2_stale_proposals"], tuple(ex["v2_stale_days"])), (438, 279, 6, 1, 28, (22, 24)))

# A8 planning: the plug-in sizes of models/cs.py and the sizes that establish a claim nine times in ten
rates = {"audit_miss_1in20": (t["audit_missed"], 0.05), "audit_false_1in20": (t["false_close_by_age4"], 0.05),
         "replies_3in100": (P["miss_v1"], 0.03)}
plan = {}
for nm, (rate, target) in rates.items():
    plug = cs.sample_size(rate, target, ALPHA, nmax=200000)
    n90, probs = X.plan_size(rate, target, ALPHA, 0.9, nmax=6000)
    plan[nm] = {"plug_in": plug, "prob_at_plug_in": round(probs[plug - 1], 2), "n90": n90}
FACTS["planning"] = plan
check("A8 planning, plug-in sizes at the simulation's rates (audited replies and audited open items for 1/20, reply "
      "receipts for 3/100), and the probability that the claim is established at those sizes",
      tuple((plan[k]["plug_in"], plan[k]["prob_at_plug_in"]) for k in rates),
      ((521, 0.63), (414, 0.68), (2104, 0.58)))
check("A8 planning: sizes from which on the claim is established with probability at least 0.9",
      tuple(plan[k]["n90"] for k in rates), (776, 587, 3304))
per_week = {"audit_miss_1in20": EST["audit_replies_gate"][1] / 4, "audit_false_1in20": EST["audit_open_gate"][1] / 4,
            "replies_3in100": EST["replies_gate"][1] / 4}
per_day = len(sim["reply_rows"]) / P["days"]
cad = {"receipts_per_day": round(per_day, 1),
       "per_week": {k: v for k, v in per_week.items()},
       "weeks_n90": {k: round(plan[k]["n90"] / per_week[k], 1) for k in rates},
       "years_to_false_alarm": round(P["arl"] / per_day / 365.25, 1),
       "false_alarm_bound_run": round(len(sim["reply_rows"]) / P["arl"], 4),
       "false_alarm_bound_year": round(per_day * 365.25 / P["arl"], 2)}
cad["proposals_per_reply_receipt"] = round(gd["with_feedback_proposals"] / EST["replies_gate"][1], 1)
ar_, rp_ = stream("audit_replies_gate"), stream("replies")
ia_, ir_ = {c: i for i, c in enumerate(ar_["schema"])}, {c: i for i, c in enumerate(rp_["schema"])}
aud_missed = [r[ia_["key"]] for r in ar_["rows"] if r[ia_["missed"]]]
stale_keys = {r[ir_["key"]] for r in rp_["rows"] if r[ir_["stale"]]}
cad["audit_misses_found_by_review"] = [sum(1 for k in aud_missed if k in stale_keys), len(aud_missed)]
check("A8 with feedback, proposals per reply receipt in the gate window (about four)",
      cad["proposals_per_reply_receipt"], 4.4)
check("A5 the audit's misses in the gate window all have stale reply receipts (the review found them too)",
      tuple(cad["audit_misses_found_by_review"]), (2, 2))
FACTS["cadence"] = cad
check("A8 cadence: reply receipts per day; audited replies, audited open items and reply receipts per week in the gate "
      "window; weeks to the nine-in-ten sizes at those rates",
      (cad["receipts_per_day"], tuple(per_week.values()), tuple(cad["weeks_n90"].values())),
      (16.4, (35.0, 19.0, 109.0), (22.2, 30.9, 30.3)))
check("A8 the changepoint monitor's false alarms: years of receipts before the expected one; bound N/A on the "
      "probability of one within the 916 receipts and within a year of receipts",
      (cad["years_to_false_alarm"], cad["false_alarm_bound_run"], cad["false_alarm_bound_year"]), (16.7, 0.0092, 0.06))

z0 = SMT.store_statistics()
FACTS["z3_store"] = z0
z0_unsat = [k for k in z0 if "witness" not in k]
check("A9 Z3: the deployed store: closure of the item machine, the event and joint statistics (all unsat); the window "
      "view refuted now and on updates (witnesses exist)",
      (all(z0[k] == "unsat" for k in z0_unsat), len(z0_unsat), z0["window now (witness exists)"],
       z0["window updates (witness exists)"]), (True, 10, "sat", "sat"))
z1 = SMT.nag_index_v1()
check("A9 Z3: the deployed two-day nag index (step wait, step reply, read nag)", sorted(z1.values()), ["unsat"] * 3)
z2 = SMT.release_indexes()
FACTS["z3_release"] = z2
witness_names = ("two-day index for the three-day goal", "designed witness (5/2, 7/2)",
                 "carried index now (witness exists)")
unsat_names = [k for k in z2 if k not in witness_names]
check("A9 Z3: the release's closure, record, engine index and nag indexes, minimality of the engine index, the "
      f"rebuild ({len(unsat_names)} obligations unsat)", all(z2[k] == "unsat" for k in unsat_names), True)
check("A9 Z3: witnesses exist against the carried-over index and against the two-day index for the three-day goal; "
      "the designed witness (5/2, 7/2) works", tuple(z2[k] for k in witness_names), ("sat", "sat", "sat"))

# ============================================================ Part B
print("== Part B: the module text, decided by cvc5 and replayed")
Wd = World([os.path.join(HERE, "memory_goals.metta"), os.path.join(HERE, "live_memory.metta"), MODULE])
B = {}
for path, form in Wd.runs:
    if path.endswith("wmtm_example.metta"):
        _, mod, rq = form
        B[(mod, show(rq))] = Wd.run(mod, rq)
check("B number of run requests in wmtm_example.metta", len(B), 33)
check("B lines of wmtm_example.metta (the size quoted in the text)",
      sum(1 for _ in open(MODULE)), 357)


def res(mod, rq):
    return B[(mod, rq)]


def on_cvc5(r):
    """(status, solver of the TrustedBackend assumption): a verdict that rests on cvc5's answer of
    unsatisfiability, with no checked proof, is Conditional on that backend."""
    a = r.get("assumptions") or [{}]
    return r["status"], a[0].get("TrustedBackend", {}).get("solver")


COND = ("Conditional", "cvc5")
Z3_AGREES = {}   # subject name -> True when Z3 reached the same verdict on its own encodings


z3_store = {"EventStat": ["closed wait", "closed reply"] + [k for k in z0 if k.startswith("event ")],
            "JointStat": ["closed wait", "closed reply"] + [k for k in z0 if k.startswith("joint ")]}
for st in ("EventStat", "JointStat"):
    r = res("WMTMStore", f"(CheckStatistic {st} (Method Symbolic))")
    Z3_AGREES[st] = all(z0[k] == "unsat" for k in z3_store[st])
    check(f"B WMTMStore: {st}: {len(r['obligations'])} obligations unsat, Conditional on cvc5; Z3 agrees",
          (on_cvc5(r), set(r["obligations"].values()), Z3_AGREES[st]), (COND, {"unsat"}, True))
r = res("WMTMStore", "(CheckStatistic NagIndex (Method Symbolic))")
Z3_AGREES["NagIndex"] = all(v == "unsat" for v in z1.values()) and z0["closed wait"] == z0["closed reply"] == "unsat"
check(f"B WMTMStore: NagIndex: {len(r['obligations'])} obligations unsat, Conditional on cvc5; Z3 agrees",
      (on_cvc5(r), set(r["obligations"].values()), Z3_AGREES["NagIndex"]), (COND, {"unsat"}, True))
for st, bound, qs in (("Records", "ItemTime", ["open", "suggest"]), ("EngineIndex", "ItemTime", ["open", "suggest"]),
                      ("NagIndexByKey", "NagTime", ["nag"])):
    r = res("WMTMStore", f"(CheckStatistic {st} (Method Lift))")
    check(f"B WMTMStore: {st} by lifting, bound to {bound}'s queries, Conditional as its premise",
          (on_cvc5(r), r["method"], r["binding"]["bound_to"][1], r["binding"]["queries"]), (COND, "Lift", bound, qs))
r = res("WMTMStore", "(CheckNow WindowView)")
wx, wy = r["witness"]["values"]["x"], r["witness"]["values"]["y"]
sug = Wd.fn("LiveOpenItems", "suggest")
view = Wd.fn("LiveOpenItems", "window-view")
check("B WMTMStore: WindowView refuted now; the witness replays (same view, different suggest), as Z3",
      (r["status"], view(wx) == view(wy), sug(wx) != sug(wy), z0["window now (witness exists)"]),
      ("Refuted", True, True, "sat"))
FACTS["window_now_witness"] = [js(wx), js(wy)]
r = res("WMTMStore", "(CheckUpdates WindowView)")
w = r["witness"]["values"]
wait = lambda d: Wd.fn("LiveOpenItems", ["wait", "$d"], {"$d": d})
check("B WMTMStore: WindowView refuted on updates; the witness replays (same view, views differ after the wait), "
      "as Z3", (r["status"], r["witness"]["obligation"], view(w["x"]) == view(w["y"]),
                view(wait(w["$d"])(w["x"])) != view(wait(w["$d"])(w["y"])), z0["window updates (witness exists)"]),
      ("Refuted", "updates wait", True, True, "sat"))
FACTS["window_updates_witness"] = js(w)

r = res("WMTMRelease", "(CheckStatistic JointCarried (Method Symbolic))")
check("B WMTMRelease: the carried-over engine index is invalid input, missing the snooze step",
      (r["status"], r["missing"]), ("InvalidInput", ["Step snooze"]))
r = res("WMTMRelease", "(CheckNow CarriedIndex)")
cx, cy = r["witness"]["values"]["x"], r["witness"]["values"]["y"]
carried = Wd.fn("WMTMRelease", "joint-carried")
sug_s = Wd.fn("WMTMRelease", "suggest")
check("B WMTMRelease: the carried-over index refuted now on the new machine; the witness replays (same code, different "
      "suggest), as Z3", (r["status"], carried(cx) == carried(cy), sug_s(cx) != sug_s(cy),
                          z2["carried index now (witness exists)"]), ("Refuted", True, True, "sat"))
FACTS["carried_witness"] = [js(cx), js(cy)]
release_closure = all(z2[k] == "unsat" for k in ("closed wait", "closed reply", "closed snooze"))
z3_of = {"RecordS": "record", "JointS": "engine", "NagTwoIndex": "nag two", "NagThreeIndex": "nag three"}
for st, pre in z3_of.items():
    r = res("WMTMRelease", f"(CheckStatistic {st} (Method Symbolic))")
    agree = release_closure and all(v == "unsat" for k, v in z2.items() if k.startswith(pre + " "))
    Z3_AGREES[st] = agree
    check(f"B WMTMRelease: {st}: {len(r['obligations'])} obligations unsat, Conditional on cvc5; Z3 agrees",
          (on_cvc5(r), set(r["obligations"].values()), agree), (COND, {"unsat"}, True))
record_steps = release_closure and all(z2[k] == "unsat" for k in z2 if k.startswith("record step"))
r = res("WMTMRelease", "(CheckStatistic RebuildFromRecords (Method Symbolic))")
Z3_AGREES["RebuildFromRecords"] = record_steps and z2["rebuild from the record"] == "unsat"
Z3_AGREES["RebuildEngineIndex"] = record_steps and z2["engine index rebuilt from the record"] == "unsat"
check("B WMTMRelease: the three-day index is rebuilt from the durable record by its read map (Conditional on cvc5), "
      "as Z3", (on_cvc5(r), set(r["obligations"].values()), record_steps and z2["rebuild from the record"] == "unsat"),
      (COND, {"unsat"}, True))
r = res("WMTMRelease", "(CheckStatistic RebuildEngineIndex (Method Symbolic))")
check("B WMTMRelease: the engine index is rebuilt from the durable record by its read map (Conditional on cvc5), "
      "as Z3", (on_cvc5(r), set(r["obligations"].values()),
                record_steps and z2["engine index rebuilt from the record"] == "unsat"), (COND, {"unsat"}, True))
r = res("WMTMRelease", "(CheckNow TwoForThree)")
tx, ty = r["witness"]["values"]["x"], r["witness"]["values"]["y"]
s2 = Wd.fn("WMTMRelease", "sat-two")
n3 = Wd.fn("WMTMRelease", "nag-three")
check("B WMTMRelease: the two-day index refuted for the three-day goal; the witness replays, as Z3",
      (r["status"], s2(tx) == s2(ty), n3(tx) != n3(ty), z2["two-day index for the three-day goal"]),
      ("Refuted", True, True, "sat"))
FACTS["two_for_three_witness"] = [js(tx), js(ty)]
for st, bound, qs in (("EngineIndexS", "ItemSnooze", ["open", "suggest"]), ("NagIndexS", "NagThree", ["nag"])):
    r = res("WMTMRelease", f"(CheckStatistic {st} (Method Lift))")
    check(f"B WMTMRelease: {st} by lifting, bound to {bound}'s queries, Conditional as its premise",
          (on_cvc5(r), r["method"], r["binding"]["bound_to"][1], r["binding"]["queries"]), (COND, "Lift", bound, qs))

for mname in ("MissTenth", "MissFifth", "MissTwoFifths"):
    r = res("WMTMReceipts", f"(CheckMonitor {mname})")
    check(f"B WMTMReceipts: {mname} is a valid monitor, Checked by exact arithmetic",
          (r["status"], r["assurance"], r["valid"], r["blind"]), ("Checked", "Exact", True, False))
rv = res("WMTMReceipts", "(Detect MissTenth MissFifth MissTwoFifths (On Replies) (Level (Rat 1 100)) "
                         "(Combine Mixture))")
check("B WMTMReceipts: Detect, Ville scheme: no alarm in 916 receipts; largest value and where, as A4",
      (rv["fired"], rv["observations"], r4(rv["largest"]), rv["largest_at"], rv["binding"]["stream"][1]),
      (None, 916, r4(m["ville_largest"]), m["ville_largest_at"], "Replies"))
rs = res("WMTMReceipts", "(Detect MissTenth MissFifth MissTwoFifths (On Replies) (Combine Mixture) "
                         "(Scheme ShiryaevRoberts) (MeanTimeToFalseAlarm 100000))")
check("B WMTMReceipts: Detect, Shiryaev-Roberts scheme: alarm at the same receipt as the monitor in the loop",
      (rs["fired"], rs["step"], rs["binding"]["stream"][1], round(math.log(rs["statistic"]), 2)),
      ("Mixture", g["alarm_observation"], "Replies", m["sr_log_at_alarm"]))
FACTS["sr_alarm_statistic"] = rs["statistic"]
rq_of = {"replies_before": '(EstimateRate (On RepliesBefore) (Column "stale") (Equals 1) (Level (Rat 1 100)))',
         "audit_after_alarm": '(EstimateRate (On AuditAfterAlarm) (Column "missed") (Equals 1) (Level (Rat 1 100)))',
         "audit_v2": '(EstimateRate (On AuditV2) (Column "missed") (Equals 1) (Level (Rat 1 100)))',
         "replies_gate": '(EstimateRate (On RepliesGate) (Column "stale") (Equals 1) (Level (Rat 1 100)))',
         "keys_gate": '(EstimateRate (On KeysGate) (Column "duplicate") (Equals 1) (Level (Rat 1 100)))',
         "closures_gate": '(EstimateRate (On ClosuresGate) (Column "spurious") (Equals 1) (Level (Rat 1 100)))',
         "audit_replies_gate": '(EstimateRate (On AuditRepliesGate) (Column "missed") (Equals 1) (Level (Rat 1 100)))',
         "audit_open_gate": '(EstimateRate (On AuditOpenGate) (Column "false_close") (Equals 1) (Level (Rat 1 100)))'}
for nm, rq in rq_of.items():
    r = res("WMTMReceipts", rq)
    S, n, lo, hi = EST[nm]
    bnd = r["binding"]
    check(f"B WMTMReceipts: EstimateRate {nm}: counts and interval as A5; bound to its stream, digest, population, "
          f"selection rule and policy", (r["status"], r["count"], r["observations"], abs(r["lower"] - lo) < 1e-9,
                                         abs(r["upper"] - hi) < 1e-9,
                                         bnd["digest"] == FACTS["digests"][{"audit_v2": "audit_replies_v2"}.get(nm, nm)],
                                         all(k in bnd for k in ("population", "selection", "policy"))),
          ("Estimated", S, n, True, True, True, True))
r = res("WMTMReceipts", '(CompareRates (On LivesGate) (First "window_bad") (Second "event_bad") (Equals 1) '
                        '(Level (Rat 1 100)))')
check("B WMTMReceipts: CompareRates on the lifetime receipts: discordant counts and interval as A5",
      (r["first_only"], r["second_only"], abs(r["lower"] - EST["lives_gate"][4]) < 1e-9,
       r["binding"]["digest"] == FACTS["digests"]["lives_gate"]), (b, cc, True, True))

# B: negative fixture.  A copy of the bundle in which every stale label of RepliesGate is set to 0, the
# declared digest unchanged: the evaluator must refuse the request before computing anything.
import shutil  # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    for f_ in ("memory_goals.metta", "live_memory.metta", "wmtm_example.metta"):
        shutil.copy(os.path.join(HERE, f_), tmp)
    shutil.copytree(os.path.join(HERE, "streams"), os.path.join(tmp, "streams"))
    sp = os.path.join(tmp, "streams", "replies_gate.json")
    data_ = json.load(open(sp))
    ci = data_["schema"].index("stale")
    for row in data_["rows"]:
        row[ci] = 0
    open(sp, "w").write(json.dumps(data_, separators=(",", ":")))
    Wt = World([os.path.join(tmp, f_) for f_ in ("memory_goals.metta", "live_memory.metta", "wmtm_example.metta")])
    rq_t = [form[2] for path, form in Wt.runs if path.endswith("wmtm_example.metta") and form[2][0] == "EstimateRate"
            and "RepliesGate" in show(form[2])][0]
    rt = Wt.run("WMTMReceipts", rq_t)
check("B WMTMReceipts: negative fixture: RepliesGate with every stale label set to 0 under its declared digest is "
      "refused (InvalidInput, no count, no interval)",
      (rt["status"], "count" in rt or "upper" in rt, "RepliesGate" in rt.get("mismatch", "")), ("InvalidInput", False, True))


# B: conformance replay.  The abstraction function reads the frozen journal: an opening note creates
# the key of its person and topic; a note parsed as closing an item, or recovered by the re-parse,
# closes the key from the time memory learned of it.  The module's maps are then stepped through
# every key's history and compared, at every daily cycle, with the record designs of the simulation.
def abstract(rows, reparse_time):
    keys = {}
    for t, person, topic, parsed, reparsed, marker, item, truth in sorted(rows, key=lambda n: n[0]):
        key = (person, topic)
        if parsed == "open":
            keys.setdefault(key, {"created": t, "known": []})
        elif parsed == "close" and key in keys:
            keys[key]["known"].append(t)
        elif parsed == "other" and reparsed == 1 and key in keys:
            keys[key]["known"].append(reparse_time)
    return keys


journal = stream("journal")
abstracted = abstract(journal["rows"], sim["v2_end"])
by_key = {kk["key"]: kk for kk in sim["keys"]}
same = sum(1 for key, a_ in abstracted.items() if key in by_key
           and abs(a_["created"] - by_key[key]["created"]) < 1e-6
           and abs(min(a_["known"], default=99) - min([kn for ts, kn, kd in by_key[key]["closes"] if kn < P["days"]],
                                                       default=99)) < 1e-6)
check("B the abstraction function applied to the frozen journal gives the simulation's keys, creation times and "
      "first closings known to memory", (len(abstracted), len(by_key), same), (1362, 1362, 1362))
print("   replaying the deployment through the module's maps ...")
L = "LiveOpenItems"
f_wait = lambda d: Wd.fn(L, ["wait", "$d"], {"$d": d})
f_reply = Wd.fn(L, "on-reply")
enc_ev, enc_j = Wd.fn(L, "event-stat"), Wd.fn(L, "joint-stat")
ev_wait = lambda d: Wd.fn(L, ["event-wait", "$d"], {"$d": d})
ev_reply, ev_sug = Wd.fn(L, "event-reply"), Wd.fn(L, "event-suggest")
j_wait = lambda d: Wd.fn(L, ["joint-wait", "$d"], {"$d": d})
j_reply, j_sug = Wd.fn(L, "joint-reply"), Wd.fn(L, "joint-suggest")
win_view = Wd.fn(L, "window-view")
S = "WMTMStore"
enc_n = Wd.fn(S, "sat-two")
n_wait = lambda d: Wd.fn(S, ["sat-two-wait", "$d"], {"$d": d})
n_close, n_read = Wd.fn(S, "sat-two-close"), Wd.fn(S, "sat-two-nag")
cap = F(7)
decisions = agree_ev = agree_win = agree_joint = agree_nag = identity = 0
for key, a_ in abstracted.items():
    kk = by_key[key]
    created = F(a_["created"])
    first = F(min(a_["known"])) if a_["known"] else None
    cycles = [F(k) + F(P["cycle"]) for k in range(P["days"])
              if F(k) + F(P["cycle"]) >= created and F(k) + F(P["cycle"]) - created <= cap]
    x = (F(0), False, F(0))
    ce, cj, cn = enc_ev(x), enc_j(x), enc_n(x)
    now = created
    events = sorted([(tc, "cycle") for tc in cycles] + ([(first, "reply")] if first is not None else []))
    for tm, kind in events:
        d = tm - now
        if d < 0:
            continue
        if d > 0:
            x, ce, cj, cn = f_wait(d)(x), ev_wait(d)(ce), j_wait(d)(cj), n_wait(d)(cn)
            now = tm
        if kind == "reply":
            x, ce, cj, cn = f_reply(x), ev_reply(ce), j_reply(cj), n_close(cn)
            continue
        t_ = float(tm)
        decisions += 1
        py_ev = not W.event_closed(kk, t_) and t_ - kk["created"] <= P["cap"]
        py_win = not W.window_closed(kk, t_, P["window"]) and t_ - kk["created"] <= P["cap"]
        # the window design decides from the module's window view: propose when no closing note
        # is visible and the item is at most seven days old
        a2, visible = win_view(x)
        mod_win = (not visible) and a2 <= 7
        agree_ev += ev_sug(ce) == py_ev
        agree_joint += j_sug(cj) == py_ev
        agree_win += mod_win == py_win
        agree_nag += n_read(cn) == (py_ev and t_ - kk["created"] <= 2)
        identity += (ce == enc_ev(x)) and (cj == enc_j(x)) and (cn == enc_n(x))
FACTS["replay"] = {"decisions": decisions}
check("B conformance replay from the frozen journal: at every daily cycle of every key, the module's statistics and "
      "window view decide as the simulated designs, and the codes equal the encodings of the replayed items",
      (decisions, agree_ev, agree_joint, agree_win, agree_nag, identity), (decisions,) * 6)
check("B conformance replay: number of decisions replayed", decisions, 8966)

# B: randomized differential test of the release's snooze semantics against a direct implementation
R_ = "WMTMRelease"
rw = lambda d: Wd.fn(R_, ["wait", "$d"], {"$d": d})
rr, rs_ = Wd.fn(R_, "on-reply"), (lambda s: Wd.fn(R_, ["snooze", "$s"], {"$s": s}))
rec, jt = Wd.fn(R_, "rec"), Wd.fn(R_, "joint")
rec_w = lambda d: Wd.fn(R_, ["rec-wait", "$d"], {"$d": d})
rec_r, rec_s = Wd.fn(R_, "rec-reply"), (lambda s: Wd.fn(R_, ["rec-snooze", "$s"], {"$s": s}))
rec_sug = Wd.fn(R_, "rec-suggest")
js_w = lambda d: Wd.fn(R_, ["joint-s-wait", "$d"], {"$d": d})
js_r, js_s = Wd.fn(R_, "joint-s-reply"), (lambda s: Wd.fn(R_, ["joint-s-snooze", "$s"], {"$s": s}))
js_sug = Wd.fn(R_, "joint-s-suggest")
rng = random.Random(7)
steps = agree = 0
dead_open = 0
for _ in range(400):
    created, now, closed, until = F(0), F(0), False, F(0)
    x = (F(0), False, F(0), F(0))
    cr, cj = rec(x), jt(x)
    for _ in range(12):
        u = rng.random()
        if u < 0.5:
            d = F(rng.randint(0, 36), 12)
            x, cr, cj, now = rw(d)(x), rec_w(d)(cr), js_w(d)(cj), now + d
        elif u < 0.6:
            x, cr, cj, closed = rr(x), rec_r(cr), js_r(cj), True
        else:
            s = F(rng.randint(0, 60), 12)
            x, cr, cj = rs_(s)(x), rec_s(s)(cr), js_s(s)(cj)
            until = max(until, now + s)
        direct = (not closed) and now - created <= 7 and until <= now
        steps += 1
        agree += (rec_sug(cr) == direct) and (js_sug(cj) == direct) and (cr == rec(x)) and (cj == jt(x))
        dead_open += (not closed) and now - created <= 7 and now + max(F(0), until - now) - created > 7
check("B release: random runs of waits, replies and snoozes; the record and the engine index decide as a direct "
      "implementation with absolute times, and the codes equal the encodings", (steps, agree), (4800, 4800))
check("B release: states met in those runs that are open, younger than seven days, and snoozed past the seventh "
      "day (the merged class)", dead_open > 0, True)

# B: the rebuild of the release's indexes from the durable records at the end of day 55, for every key
# of the frozen journal
n3_enc = Wd.fn(R_, "sat-three")
n3_wait = lambda d: Wd.fn(R_, ["sat-three-wait", "$d"], {"$d": d})
n3_close = Wd.fn(R_, "sat-close")
rebuild = Wd.fn(R_, "rebuild-three")
rebuild_j = Wd.fn(R_, "rebuild-joint")
t_end = F(P["days"])
rebuilt = agree_rb = 0
for key, a_ in abstracted.items():
    created = F(a_["created"])
    first = F(min(a_["known"])) if a_["known"] else None
    x = (F(0), False, F(0), F(0))
    code, cj = n3_enc(x), jt(x)
    now = created
    for tm, kind in sorted(([(first, "reply")] if first is not None else []) + [(t_end, "end")]):
        d = tm - now
        if d > 0:
            x, code, cj, now = rw(d)(x), n3_wait(d)(code), js_w(d)(cj), tm
        if kind == "reply":
            x, code, cj = rr(x), n3_close(code), js_r(cj)
    rebuilt += 1
    agree_rb += (rebuild(rec(x)) == code == n3_enc(x)) and (rebuild_j(rec(x)) == cj == jt(x))
check("B rebuild at the end of day 55: for every key, the three-day nag index and the engine index rebuilt from the "
      "durable record equal the indexes stepped through the key's history", (rebuilt, agree_rb), (1362, 1362))

# B: E2 under the snooze release.  Every key of the frozen journal is stepped through the deployed engine
# index and through the release's, at every daily cycle, and the release's index receives a snooze of one
# to four days on a random 30 percent of the proposals it makes.  A snooze is given only on a proposal,
# so the two indexes agree up to and including each key's first proposal.
rng = random.Random(13)
first_same = snoozes = gate_old = gate_new = 0
kg_release = []
for key, a_ in abstracted.items():
    kk = by_key[key]
    created = F(a_["created"])
    first = F(min(a_["known"])) if a_["known"] else None
    cycles = [F(k) + F(P["cycle"]) for k in range(P["days"])
              if F(k) + F(P["cycle"]) >= created and F(k) + F(P["cycle"]) - created <= cap]
    c_old, c_new = enc_j((F(0), False, F(0))), jt((F(0), False, F(0), F(0)))
    now, f_old, f_new = created, None, None
    for tm, kind in sorted([(tc, "cycle") for tc in cycles] + ([(first, "reply")] if first is not None else [])):
        d = tm - now
        if d < 0:
            continue
        if d > 0:
            c_old, c_new, now = j_wait(d)(c_old), js_w(d)(c_new), tm
        if kind == "reply":
            c_old, c_new = j_reply(c_old), js_r(c_new)
            continue
        day = int(tm - F(P["cycle"]))
        p_old, p_new = j_sug(c_old), js_sug(c_new)
        in_gate = P["gate"][0] <= day < P["gate"][1]
        gate_old += in_gate and p_old
        gate_new += in_gate and p_new
        f_old = day if (p_old and f_old is None) else f_old
        f_new = day if (p_new and f_new is None) else f_new
        if p_new and rng.random() < 0.3:
            c_new = js_s(F(rng.randint(1, 4)))(c_new)
            snoozes += 1
    first_same += f_old == f_new
    if f_new is not None and P["gate"][0] <= f_new < P["gate"][1]:
        kg_release.append((f_new, kk["id"], int(not kk["primary"])))
kg_rows = sorted((r[ik["day"]], r[ik["key"]], r[ik["duplicate"]]) for r in kg["rows"])
FACTS["release_e2"] = {"keys": len(abstracted), "snoozes": snoozes, "gate_proposals_deployed": gate_old,
                       "gate_proposals_release": gate_new, "removed": gate_old - gate_new}
check("B E2 under the snooze release: the frozen journal through the deployed engine index and the release's, with a "
      "snooze of one to four days on 30 percent of the release's proposals: every key is first proposed at the same "
      "cycle, the release's key receipts are KeysGate's rows and labels, and the snoozes remove proposals of the gate "
      "window: keys first proposed alike, KeysGate unchanged, gate-window proposals deployed and under the release, "
      "snoozes given", (first_same, sorted(kg_release) == kg_rows, gate_old, gate_new, snoozes),
      (1362, True, 1952, 1541, 900))

# B: the verdicts, with the agreement of Z3 recorded under agreed_by beside every Conditional one.  A
# lifted statistic agrees when its premise does.
import z3  # noqa: E402
Z3V = "z3 " + z3.get_version_string()
VERDICTS = {}
n_cond = n_agreed = 0
for (mod, rq), r in B.items():
    e = {"module": mod, "request": rq, "status": r["status"], "assurance": r.get("assurance")}
    for k in ("method", "assumptions", "binding", "witness", "missing", "mismatch"):
        if k in r:
            e[k] = js(r[k])
    if r["status"] == "Conditional":
        n_cond += 1
        subject = r["binding"]["premise"][1] if r.get("method") == "Lift" else rq.split()[1].rstrip(")")
        if Z3_AGREES.get(subject):
            e["agreed_by"] = [Z3V]
            n_agreed += 1
    VERDICTS[f"{mod} {rq}"] = e
check("B every Conditional verdict records the agreement of Z3 under agreed_by (lifts through their premises)",
      (n_cond, n_agreed), (14, 14))

# ============================================================ summary
FACTS["checks"] = CHECKS[0]
FACTS["seconds"] = round(time.time() - T0, 1)
FACTS["traces"] = {"ville": [round(v, 4) for v in traces[0]], "sr": [round(v, 4) for v in traces[1]],
                   "loop": [None if v is None else round(v, 4) for v in traces[2]],
                   "days": [x["day"] for x in sim["reply_rows"]]}
json.dump({"results": RESULTS, "facts": js(FACTS), "verdicts": VERDICTS}, open(os.path.join(HERE, "wx_results.json"), "w"),
          indent=1)
print(f"{CHECKS[0]} checks passed, {len(FAILS)} failed, {FACTS['seconds']} s" if not FAILS else
      f"{CHECKS[0] - len(FAILS)} checks passed, {len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
