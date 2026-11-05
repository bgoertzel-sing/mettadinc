"""The synthetic WMTM deployment of the worked example.

Eight weeks of the goal engine's log-only phase.  Open items are created by explicit markers
("open question for Ben: ...", "pending: ..."); closing replies arrive after a lognormal delay;
a reply detector in the parser misses some replies, many more of them while parser version 2 is
deployed; spurious closing notes and paraphrased re-mentions corrupt the input events.  Two
record designs (the recall window and the event record) run side by side in a daily proposal
cycle; a live review labels every logged proposal; a third of the items are audited at age four
days.  A Shiryaev-Roberts mixture monitor reads one receipt per reply.  When it fires, the team follows
a rule fixed in advance: on the next morning it audits the replies received since the alarm's
receipts, and only if the confidence sequence for their miss rate lies above the accepted rate
does it roll the parser back at noon and re-parse the journal written since the update.  The
monitor restarts after the rollback, or at once if the alarm is not confirmed.

The receipts are reduced, before any estimate, to units whose average is what a claim of the gate
is about: one row per reply (was the item proposed at the first cycle after its reply?), one row
per key (was its first proposal a duplicate?), one row per key at the end of its seven days (did
each design decide wrongly on it at least once?), one row per key at its first closing (was the
closing note a real reply?), and one row per audited item.  Labels of individual proposals come
in runs, because the log-only engine proposes an open item every day, so their average counts a
missed reply once for every day its item stays young.

Everything is seeded, and every item's random draws are made when the item is created.  The
ground truth (which replies really arrived, which keys are duplicates) is kept beside the parsed
journal and is used only to write the review's labels and the audit's findings, and to check the
estimates afterwards; no record design sees it.

Times are in days from the start (day 0 is a Monday, 00:00).
"""
import hashlib
import json
import math
import os
from fractions import Fraction as F

import numpy as np

import cs

P = dict(
    days=56,
    weekday_rate=30.0, weekend_rate=8.0,       # items opened per day
    work_start=8 / 24, work_end=20 / 24,       # markers are written during working hours
    p_reply=0.72, delay_median=0.8, delay_sigma=1.1,
    miss_v1=0.015, miss_v2=0.25,               # reply-detector miss probabilities
    v2_start=21 + 10 / 24,                     # parser v2 deployed on day 21 at 10:00
    p_false=0.012, false_mean=1.5,             # spurious closing notes
    p_para=0.006, para_lo=0.05, para_hi=1.0,   # paraphrased re-mentions with a new topic label
    audit_frac=1 / 3, audit_age=4.0,
    cycle=9 / 24, cap=7.0, window=2.0,
    rollback_hour=12 / 24,                     # the day after an alarm: audit, rollback at noon
    gate=(28, 56),                             # the gate reads receipts released on these days
    p0=F(1, 20), alternatives=(F(1, 10), F(1, 5), F(2, 5)), arl=100000,
    alpha=0.01,                                # level of the estimates and of the confirmation
    seed=20261104,
)
PEOPLE = ["ben", "andy", "kofi", "mira", "tomas", "yuki"]
WEIGHTS = [0.32, 0.20, 0.14, 0.14, 0.10, 0.10]
STEMS = ["gpu-lease", "hive-sync", "q4-budget", "paper-review", "demo-script", "eval-suite", "node-upgrade",
         "grant-report", "parser-fix", "talk-slides", "dataset-access", "release-notes", "hiring-panel",
         "travel-plan", "benchmark-run", "license-check", "board-memo", "api-quota", "backup-policy",
         "workshop-cfp", "chain-audit", "token-bridge", "onboarding-doc", "cluster-move", "vendor-call"]
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "streams")


def digest_bytes(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ the journal
def generate(p=P):
    """Items with their ground truth and the random numbers that decide how they are parsed."""
    rng = np.random.default_rng(p["seed"])
    items = []
    for k in range(p["days"]):
        rate = p["weekend_rate"] if k % 7 in (5, 6) else p["weekday_rate"]
        n = rng.poisson(rate)
        for t in np.sort(k + rng.uniform(p["work_start"], p["work_end"], n)):
            i = len(items)
            it = {"created": float(t), "id": f"i{i:04d}"}
            it["person"] = PEOPLE[int(rng.choice(len(PEOPLE), p=WEIGHTS))]
            it["topic"] = f"{STEMS[int(rng.integers(len(STEMS)))]}-{i:04d}"
            it["marker"] = "open question for Ben" if rng.random() < 0.6 else "pending"
            u_reply = rng.random()
            delay = float(rng.lognormal(math.log(p["delay_median"]), p["delay_sigma"]))
            it["reply"] = it["created"] + delay if u_reply < p["p_reply"] else None
            it["u_detect"] = float(rng.random())        # compared with the miss probability in force
            it["u_reparse"] = float(rng.random())       # used if the reply is re-parsed after a rollback
            u_false, fdelay = rng.random(), float(rng.exponential(p["false_mean"]))
            it["false_close"] = it["created"] + fdelay if u_false < p["p_false"] else None
            u_para, pdelay = rng.random(), float(rng.uniform(p["para_lo"], p["para_hi"]))
            alt = STEMS[int(rng.integers(len(STEMS)))]
            it["para"] = (it["created"] + pdelay, f"{alt}-{i:04d}b") if u_para < p["p_para"] else None
            it["audit"] = bool(rng.random() < p["audit_frac"])
            items.append(it)
    return items


def miss_prob(t, p, v2_end):
    return p["miss_v2"] if p["v2_start"] <= t < v2_end else p["miss_v1"]


def keys_of(items, p, v2_end):
    """The keys the abstraction function produces from the parsed journal: for each key, its
    creation time and the closing notes it receives, each as (timestamp, time known to memory,
    kind).  A reply missed while v2 was deployed is recovered by the re-parse at the rollback
    (time v2_end) with probability 1 - miss_v1."""
    keys = []
    for it in items:
        closes = []
        r = it["reply"]
        if r is not None:
            if it["u_detect"] >= miss_prob(r, p, v2_end):
                closes.append((r, r, "reply"))
            elif p["v2_start"] <= r < v2_end and it["u_reparse"] >= p["miss_v1"]:
                closes.append((r, v2_end, "reply-reparsed"))
        if it["false_close"] is not None:
            closes.append((it["false_close"], it["false_close"], "spurious"))
        keys.append({"key": (it["person"], it["topic"]), "id": it["id"], "created": it["created"],
                     "closes": sorted(closes, key=lambda c: c[1]), "item": it, "primary": True})
        if it["para"] is not None:
            keys.append({"key": (it["person"], it["para"][1]), "id": it["id"] + "b", "created": it["para"][0],
                         "closes": [], "item": it, "primary": False})
    return keys


# ------------------------------------------------------------------ the two record designs
def event_closed(k, t):
    """The event record: closed once any closing note for the key is known."""
    return any(known <= t for ts, known, kind in k["closes"])


def window_closed(k, t, w):
    """The recall window, as Part I models it: the first closing the engine learned of is visible
    for w days from the time it was learned, and the item looks open again afterwards."""
    known = [kn for ts, kn, kind in k["closes"] if kn <= t]
    return bool(known) and t - min(known) <= w


def settled(k, t):
    r = k["item"]["reply"]
    return r is not None and r <= t


# ------------------------------------------------------------------ the monitor in the loop
class SR:
    """Shiryaev-Roberts statistics for fixed alternatives, averaged, in exact arithmetic."""

    def __init__(self, p0, alts):
        self.p0, self.alts = p0, alts
        self.R = [F(0)] * len(alts)

    def update(self, x):
        for i, q in enumerate(self.alts):
            lr = (q / self.p0) if x else ((1 - q) / (1 - self.p0))
            self.R[i] = (1 + self.R[i]) * lr
        return sum(self.R) / len(self.R)


def run(p=P):
    """The daily cycle.  At each cycle both designs decide on every key at most seven days old;
    the review labels every proposal and every closing; the receipts of the cycle are released
    after the review, in the order of the events they record; the monitor reads the reply
    receipts."""
    items = generate(p)
    v2_end = p["days"] + 1.0                   # until an alarm, v2 stays deployed
    keys = keys_of(items, p, v2_end)
    sr, n_obs, alarms, restart = SR(p["p0"], p["alternatives"]), 0, [], None
    cycles, reply_rows, key_rows, life_rows, closure_rows, confirmations = [], [], [], [], [], []
    seen, union, closed_seen = set(), {}, set()
    prev = -1.0
    for k in range(p["days"]):
        t = k + p["cycle"]
        if restart is not None and t >= restart:
            sr, n_obs, restart = SR(p["p0"], p["alternatives"]), 0, None
        rows, proposed_ev = [], set()
        for kk in keys:
            if kk["created"] > t:
                continue
            if t - kk["created"] > p["cap"]:
                if kk["id"] in union and kk["primary"]:
                    w_bad, e_bad = union.pop(kk["id"])
                    life_rows.append({"day": k, "id": kk["id"], "created": kk["created"], "window_bad": w_bad,
                                      "event_bad": e_bad})
                continue
            ev = not event_closed(kk, t)
            win = not window_closed(kk, t, p["window"])
            if ev:
                proposed_ev.add(kk["id"])
            if not (ev or win):
                continue
            st = settled(kk, t)
            rows.append({"day": k, "id": kk["id"], "key": kk["key"], "age": t - kk["created"], "event": ev,
                         "window": win, "stale": st, "duplicate": not kk["primary"], "primary": kk["primary"]})
            if kk["primary"]:
                w, e = union.get(kk["id"], (False, False))
                union[kk["id"]] = (w or (win == st), e or (ev == st))
            if ev and kk["id"] not in seen:
                seen.add(kk["id"])
                key_rows.append({"day": k, "id": kk["id"], "duplicate": not kk["primary"]})
        cycles.append(rows)
        # one receipt per key at its first closing, at the first cycle after memory learned of it;
        # the review labels the closing spurious when no reply had arrived by the note's time
        for kk in keys:
            if kk["primary"] and kk["closes"] and kk["id"] not in closed_seen:
                ts, kn, kind = min(kk["closes"], key=lambda c: c[1])
                if kn <= t:
                    closed_seen.add(kk["id"])
                    r = kk["item"]["reply"]
                    closure_rows.append({"day": k, "id": kk["id"], "known": kn, "kind": kind,
                                         "spurious": r is None or r > ts})
        # one receipt per reply received since the last cycle, for items young enough to be proposed
        new = []
        for kk in keys:
            r = kk["item"]["reply"]
            if kk["primary"] and r is not None and prev < r <= t and t - kk["created"] <= p["cap"]:
                new.append({"day": k, "id": kk["id"], "reply": r, "stale": kk["id"] in proposed_ev})
        new.sort(key=lambda x: x["reply"])
        reply_rows += new
        fired = False
        if restart is None:
            for x in new:
                n_obs += 1
                if sr.update(int(x["stale"])) >= p["arl"]:
                    alarms.append({"day": k, "observation": n_obs, "reply": x["id"]})
                    fired = True
                    break
        if fired:
            # the confirmation fixed in advance: audit, on the next morning, the replies received
            # after the alarm's receipts; roll back only if the confidence sequence for their miss
            # rate lies above the accepted rate
            t_audit = k + 1 + p["cycle"]
            fresh = [kk for kk in keys if kk["primary"] and kk["item"]["reply"] is not None
                     and t < kk["item"]["reply"] < t_audit]
            missed = sum(1 for kk in fresh if not any(kind == "reply" for ts, kn, kind in kk["closes"]))
            lo, hi = cs.cs_interval(missed, len(fresh), p["alpha"])
            confirmed = lo > float(p["p0"])
            confirmations.append({"day": k, "audit": t_audit, "replies": len(fresh), "missed": missed,
                                  "lower": lo, "upper": hi, "confirmed": confirmed})
            if confirmed and v2_end > t:
                v2_end = k + 1 + p["rollback_hour"]
                keys = keys_of(items, p, v2_end)      # the re-parse at the rollback, from then on
                restart = v2_end                      # the monitor restarts after the rollback
            else:
                restart = k + 1.0
        prev = t
    return {"items": items, "keys": keys, "cycles": cycles, "alarms": alarms, "v2_end": v2_end, "params": p,
            "reply_rows": reply_rows, "key_rows": key_rows, "life_rows": life_rows,
            "closure_rows": closure_rows, "confirmations": confirmations}


# ------------------------------------------------------------------ audits
def audits(sim):
    """The random audit at age four days, and the targeted audit, on the morning after the first
    alarm, of every reply received since the parser update."""
    p, keys = sim["params"], sim["keys"]
    rand, targeted = [], []
    for kk in keys:
        if not kk["primary"]:
            continue
        it = kk["item"]
        ta = kk["created"] + p["audit_age"]
        if it["audit"] and ta < p["days"]:
            replied = it["reply"] is not None and it["reply"] <= ta
            closed = event_closed(kk, ta)
            rand.append({"id": kk["id"], "created": kk["created"], "time": ta, "replied": replied,
                         "missed": replied and not closed, "false_close": (not replied) and closed})
    if sim["alarms"]:
        t_audit = sim["alarms"][0]["day"] + 1 + p["cycle"]
        for kk in keys:
            it = kk["item"]
            if kk["primary"] and it["reply"] is not None and p["v2_start"] <= it["reply"] < t_audit:
                caught = any(kind == "reply" for ts, kn, kind in kk["closes"])   # the first parse only
                targeted.append({"id": kk["id"], "reply": it["reply"], "missed": not caught})
    return rand, targeted


# ------------------------------------------------------------------ frozen streams
def write_stream(name, schema, rows, prov):
    os.makedirs(DATA, exist_ok=True)
    data = {"schema": schema, "provenance": prov, "rows": rows}
    b = json.dumps(data, separators=(",", ":")).encode()
    with open(os.path.join(DATA, name + ".json"), "wb") as f:
        f.write(b)
    return digest_bytes(b)


def journal_notes(sim):
    """The journal of the eight weeks as the parser saw it, with the ground truth beside each note.
    parsed is the first parse; reparsed is 1 for a reply note recovered by the re-parse at the
    rollback.  Notes timestamped after the end of day 55 are not part of the deployment."""
    p, notes = sim["params"], []
    for it in sim["items"]:
        notes.append([round(it["created"], 6), it["person"], it["topic"], "open", 0, it["marker"], it["id"], "open"])
        if it["reply"] is not None:
            caught = it["u_detect"] >= miss_prob(it["reply"], p, sim["v2_end"])
            rec = (not caught) and p["v2_start"] <= it["reply"] < sim["v2_end"] and it["u_reparse"] >= p["miss_v1"]
            notes.append([round(it["reply"], 6), it["person"], it["topic"], "close" if caught else "other",
                          int(rec), "decided", it["id"], "reply"])
        if it["false_close"] is not None:
            notes.append([round(it["false_close"], 6), it["person"], it["topic"], "close", 0, "decided", None,
                          "spurious"])
        if it["para"] is not None:
            notes.append([round(it["para"][0], 6), it["person"], it["para"][1], "open", 0, it["marker"], it["id"],
                          "paraphrase"])
    notes = [n for n in notes if n[0] < p["days"]]
    notes.sort(key=lambda n: n[0])
    return notes


def lives_in_gate(sim):
    """Lifetime receipts of the keys whose daily decisions all fall in the gate window: keys
    created after the cycle of the day before the window opens."""
    p = sim["params"]
    a, b = p["gate"]
    return [x for x in sim["life_rows"] if x["created"] > a - 1 + p["cycle"] and a <= x["day"] < b]


def after_alarm(sim, targeted):
    """The targeted audit's rows for replies received after the receipts that raised the alarm."""
    t_alarm = sim["alarms"][0]["day"] + sim["params"]["cycle"]
    return [r for r in targeted if r["reply"] > t_alarm]


def freeze(sim):
    p = sim["params"]
    rand, targeted = audits(sim)
    a, b = p["gate"]
    prov = lambda **kw: {"generator": "wx_sim.run", "seed": p["seed"], "note": "simulated deployment", **kw}
    proposals = [r for rows in sim["cycles"] for r in rows if r["event"]]
    out = {}
    out["journal"] = write_stream(
        "journal", ["time", "person", "topic", "parsed", "reparsed", "marker", "item", "truth"], journal_notes(sim),
        prov(what="the parsed journal with the ground truth of each note"))
    out["proposals"] = write_stream(
        "proposals", ["day", "key", "stale", "duplicate"],
        [[r["day"], r["id"], int(r["stale"]), int(r["duplicate"])] for r in proposals],
        prov(what="every logged proposal of the event design with the review's labels (not independent: an open "
                  "item is proposed every day)"))
    out["replies"] = write_stream(
        "replies", ["day", "key", "stale"], [[x["day"], x["id"], int(x["stale"])] for x in sim["reply_rows"]],
        prov(what=f"one receipt per reply to an item at most seven days old, released at the next cycle: stale is 1 "
                  f"when the event design proposed the item at that cycle; days 0-{p['days'] - 1}"))
    out["replies_gate"] = write_stream(
        "replies_gate", ["day", "key", "stale"],
        [[x["day"], x["id"], int(x["stale"])] for x in sim["reply_rows"] if a <= x["day"] < b],
        prov(what=f"the reply receipts released on days {a}-{b - 1}"))
    out["keys_gate"] = write_stream(
        "keys_gate", ["day", "key", "duplicate"],
        [[x["day"], x["id"], int(x["duplicate"])] for x in sim["key_rows"] if a <= x["day"] < b],
        prov(what=f"one receipt per key at its first proposal, days {a}-{b - 1}: duplicate is the review's label"))
    out["lives_gate"] = write_stream(
        "lives_gate", ["day", "key", "window_bad", "event_bad"],
        [[x["day"], x["id"], int(x["window_bad"]), int(x["event_bad"])] for x in lives_in_gate(sim)],
        prov(what=f"one receipt per primary key whose daily decisions all fall on days {a}-{b - 1}, written when "
                  "its seven days end: bad is 1 when the design proposed the item while it was settled, or did not "
                  "propose it while it was open and the other design did, on at least one day"))
    out["closures_gate"] = write_stream(
        "closures_gate", ["day", "key", "spurious"],
        [[x["day"], x["id"], int(x["spurious"])] for x in sim["closure_rows"] if a <= x["day"] < b],
        prov(what=f"one receipt per primary key at its first closing, released at the first cycle after memory "
                  f"learned of it, days {a}-{b - 1}: spurious is the review's label, 1 when no reply had arrived by "
                  "the time of the closing note"))
    out["audit_replies_gate"] = write_stream(
        "audit_replies_gate", ["key", "missed"],
        [[r["id"], int(r["missed"])] for r in rand if r["replied"] and a <= r["time"] < b],
        prov(what=f"random audit at age four days of items with a reply by then, audits on days {a}-{b - 1}"))
    out["audit_open_gate"] = write_stream(
        "audit_open_gate", ["key", "false_close"],
        [[r["id"], int(r["false_close"])] for r in rand if not r["replied"] and a <= r["time"] < b],
        prov(what=f"random audit at age four days of items without a reply by then, audits on days {a}-{b - 1}"))
    out["replies_before"] = write_stream(
        "replies_before", ["day", "key", "stale"],
        [[x["day"], x["id"], int(x["stale"])] for x in sim["reply_rows"] if x["day"] <= 21],
        prov(what="the reply receipts released on days 0-21, all for replies received before the parser update"))
    out["audit_replies_v2"] = write_stream(
        "audit_replies_v2", ["key", "missed"], [[r["id"], int(r["missed"])] for r in targeted],
        prov(what="targeted audit, on the morning after the alarm, of every reply received since the parser "
                  "update, as memory held them before the re-parse"))
    out["audit_after_alarm"] = write_stream(
        "audit_after_alarm", ["key", "missed"], [[r["id"], int(r["missed"])] for r in after_alarm(sim, targeted)],
        prov(what="the confirmation: the targeted audit's replies received after the receipts that raised the "
                  "alarm, up to the audit"))
    return out


if __name__ == "__main__":
    # writes the streams into the directory given as the first argument (default:
    # streams_regenerated/ beside streams/), so the shipped streams are never overwritten
    import sys
    DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(DATA), "streams_regenerated")
    sim = run()
    print("alarms", sim["alarms"], "confirmation", sim["confirmations"], "v2_end", sim["v2_end"])
    for k, v in freeze(sim).items():
        print(f"{k:24s} {v}")
    print("written to", os.path.abspath(DATA))
