"""Derived facts of the simulated deployment: the counts and rates the guide quotes, the two
monitors' traces, and the ground truth against which the estimates are checked."""
import math
from fractions import Fraction as F

import cs
import wx_sim as W


def counts(sim):
    p = sim["params"]
    items, keys = sim["items"], sim["keys"]
    H = p["days"]
    out = {
        "items": len(items),
        "weekday_items": sum(1 for it in items if int(it["created"]) % 7 not in (5, 6)),
        "keys": len(keys),
        "duplicate_keys": sum(1 for k in keys if not k["primary"]),
        "replies": sum(1 for it in items if it["reply"] is not None and it["reply"] < H),
        "spurious": sum(1 for it in items if it["false_close"] is not None and it["false_close"] < H),
        "paraphrases": sum(1 for it in items if it["para"] is not None),
        "audited": sum(1 for it in items if it["audit"] and it["created"] + p["audit_age"] < H),
    }
    out["journal_notes"] = len(W.journal_notes(sim))
    # replies with no receipt: the item was older than seven days at the next cycle, or the reply
    # came after the last cycle
    last = H - 1 + p["cycle"]
    late = old = 0
    for k in keys:
        r = k["item"]["reply"]
        if not k["primary"] or r is None or r >= H:
            continue
        if r > last:
            late += 1
        else:
            nxt = math.ceil(r - p["cycle"]) + p["cycle"]
            if nxt - k["created"] > p["cap"]:
                old += 1
    out["reply_receipts"] = len(sim["reply_rows"])
    out["replies_too_old"] = old
    out["replies_after_last_cycle"] = late
    out["closure_receipts"] = len(sim["closure_rows"])
    props = [r for rows in sim["cycles"] for r in rows if r["event"]]
    wins = [r for rows in sim["cycles"] for r in rows if r["window"]]
    out["event_proposals"] = len(props)
    out["window_proposals"] = len(wins)
    out["proposals_per_day"] = round(len(props) / H, 1)
    return out


def regression(sim):
    """The parser update, the alarm, the rollback and the re-parse."""
    p = sim["params"]
    a = sim["alarms"][0]
    v2s, v2e = p["v2_start"], sim["v2_end"]
    in_v2 = [k for k in sim["keys"] if k["primary"] and k["item"]["reply"] is not None
             and v2s <= k["item"]["reply"] < v2e]
    missed = [k for k in in_v2 if not any(kind == "reply" for ts, kn, kind in k["closes"])]
    recovered = [k for k in missed if any(kind == "reply-reparsed" for ts, kn, kind in k["closes"])]
    rows = sim["reply_rows"]
    idx = a["observation"]
    since = [x for x in rows[:idx] if x["reply"] >= v2s]
    c = sim["confirmations"][0]
    rand, targeted = W.audits(sim)
    t_alarm = a["day"] + p["cycle"]
    before_alarm = [r for r in targeted if r["reply"] <= t_alarm]
    alarm_ids = {x["id"] for x in since}
    return {"alarm_day": a["day"], "alarm_observation": idx, "rollback": v2e,
            "receipts_since_update": len(since), "stale_since_update": sum(1 for x in since if x["stale"]),
            "replies_during_v2": len(in_v2), "missed_during_v2": len(missed), "recovered": len(recovered),
            "hours_update_to_alarm": round((a["day"] + p["cycle"] - v2s) * 24, 1),
            "targeted": len(targeted), "targeted_before_alarm": len(before_alarm),
            "targeted_alarm_receipts": sum(1 for r in targeted if r["id"] in alarm_ids),
            "confirmation_replies": c["replies"], "confirmation_missed": c["missed"],
            "confirmation_interval": (c["lower"], c["upper"]), "confirmed": c["confirmed"]}


def ville_trace(rows, p0, alts):
    """log of the average of the e-processes started at the first receipt."""
    lg, out = [0.0] * len(alts), []
    for x in rows:
        for i, q in enumerate(alts):
            lg[i] += math.log(q / p0) if x["stale"] else math.log((1 - q) / (1 - p0))
        m = max(lg)
        out.append(m + math.log(sum(math.exp(v - m) for v in lg) / len(lg)))
    return out


def sr_trace(rows, p0, alts):
    """log of the average Shiryaev-Roberts statistic (floating point, for the figure)."""
    R, out = [0.0] * len(alts), []
    for x in rows:
        for i, q in enumerate(alts):
            lr = float(q / p0) if x["stale"] else float((1 - q) / (1 - p0))
            R[i] = (1 + R[i]) * lr
        out.append(math.log(max(sum(R) / len(R), 1e-300)))
    return out


def monitors(sim):
    p = sim["params"]
    rows = sim["reply_rows"]
    v = ville_trace(rows, p["p0"], p["alternatives"])
    s = sr_trace(rows, p["p0"], p["alternatives"])
    a = sim["alarms"][0]["observation"]
    before = max(i for i, x in enumerate(rows) if x["reply"] < p["v2_start"])
    # the restarted monitor after the rollback: exact, for its largest value
    first = next(i for i, x in enumerate(rows) if x["day"] + p["cycle"] >= sim["v2_end"])
    restart = rows[first:]
    sr = W.SR(p["p0"], p["alternatives"])
    best = F(0)
    for x in restart:
        best = max(best, sr.update(int(x["stale"])))
    # the monitor as it ran in the loop: up to the alarm, then from the restart on
    loop = s[:a] + [None] * (first - a) + sr_trace(restart, p["p0"], p["alternatives"])
    return {"ville_largest": max(math.exp(t) for t in v), "ville_largest_at": 1 + v.index(max(v)),
            "ville_log_at_update": round(v[before], 2), "ville_log_at_alarm": round(v[a - 1], 2),
            "ville_log_end": round(v[-1], 2), "sr_log_at_update": round(s[before], 2),
            "sr_log_at_alarm": round(s[a - 1], 2), "restart_receipts": len(restart),
            "restart_largest": float(best), "restart_log_largest": round(math.log(float(best)), 2),
            "restart_first": first + 1, "unread": (a + 1, first), "update_receipt": before + 1,
            "traces": (v, s, loop)}


def gate_descriptive(sim):
    """Per-proposal shares in the gate window, which the guide quotes only as descriptions: the
    log-only engine proposes an open item every day, so these labels are not independent."""
    p = sim["params"]
    a, b = p["gate"]
    ev = [r for rows in sim["cycles"][a:b] for r in rows if r["event"]]
    win = [r for rows in sim["cycles"][a:b] for r in rows if r["window"]]
    stale_keys = {r["id"] for r in ev if r["stale"]}
    # with feedback ("already handled" closes the item) each stale key is proposed stale once
    first_stale = {}
    for r in ev:
        if r["stale"] and r["id"] not in first_stale:
            first_stale[r["id"]] = r["day"]
    shown = [r for r in ev if not r["stale"] or first_stale.get(r["id"]) == r["day"]]
    return {"event_proposals": len(ev), "event_stale": sum(r["stale"] for r in ev),
            "event_duplicate": sum(r["duplicate"] for r in ev),
            "window_proposals": len(win), "window_stale": sum(r["stale"] for r in win),
            "stale_keys": len(stale_keys), "with_feedback_proposals": len(shown),
            "with_feedback_stale": sum(r["stale"] for r in shown)}


def decomposition(sim):
    """The question Part II leaves to the example, in the gate window: which stale proposals of the
    recall window come from the record design and which from the input events, and what the input
    errors behind the event design's wrong decisions were."""
    p = sim["params"]
    a, b = p["gate"]
    rows = [r for rr in sim["cycles"][a:b] for r in rr]
    wst = [r for r in rows if r["window"] and r["stale"]]
    est = [r for r in rows if r["event"] and r["stale"]]
    keys = {k["id"]: k for k in sim["keys"]}
    lives = W.lives_in_gate(sim)
    both = [keys[x["id"]] for x in lives if x["window_bad"] and x["event_bad"]]
    reparsed = sum(1 for k in both if any(kind == "reply-reparsed" for ts, kn, kind in k["closes"]))
    missed = sum(1 for k in both if k["item"]["reply"] is not None
                 and not any(kind in ("reply", "reply-reparsed") for ts, kn, kind in k["closes"]))
    return {"window_stale": len(wst), "shared": sum(1 for r in wst if r["event"]),
            "window_only": sum(1 for r in wst if not r["event"]),
            "event_not_window": sum(1 for r in rows if r["event"] and not r["window"]),
            "stale_missed": sum(1 for r in est if r["primary"]),
            "stale_missed_keys": len({r["id"] for r in est if r["primary"]}),
            "stale_duplicate": sum(1 for r in est if not r["primary"]),
            "stale_duplicate_keys": len({r["id"] for r in est if not r["primary"]}),
            "lives": len(lives), "window_bad_keys": sum(1 for x in lives if x["window_bad"]),
            "event_bad_keys": len(both), "event_bad_reparsed": reparsed, "event_bad_missed": missed,
            "stale_runs": sorted((sum(1 for r in est if r["id"] == k) for k in {r["id"] for r in est}),
                                 reverse=True)}


def examples(sim):
    """The journal items the guide follows: the cycles at which each design proposed them."""
    out = {}
    rand, _ = W.audits(sim)
    audited = {r["id"]: r for r in rand}
    for kid in ("i0288", "i0500", "i1235", "i1235b"):
        rows = [r for rr in sim["cycles"] for r in rr if r["id"] == kid]
        out[kid] = {"event": [r["day"] for r in rows if r["event"]],
                    "window": [r["day"] for r in rows if r["window"]],
                    "stale": [r["day"] for r in rows if r["stale"] and (r["event"] or r["window"])],
                    "audit": audited.get(kid)}
    out["audits"] = {"audited": len(rand), "replied": sum(r["replied"] for r in rand),
                     "missed": sum(r["missed"] for r in rand), "false_close": sum(r["false_close"] for r in rand)}
    v2s, v2e = sim["params"]["v2_start"], sim["v2_end"]
    lost = {k["id"] for k in sim["keys"] if k["primary"] and k["item"]["reply"] is not None
            and v2s <= k["item"]["reply"] < v2e and not any(kind == "reply" for ts, kn, kind in k["closes"])}
    days = sorted({r["day"] for rr in sim["cycles"] for r in rr if r["id"] in lost and r["event"] and r["stale"]})
    out["v2_stale_proposals"] = sum(1 for rr in sim["cycles"] for r in rr
                                    if r["id"] in lost and r["event"] and r["stale"])
    out["v2_stale_days"] = (days[0], days[-1])
    # the false closings among the closure receipts, and what the two designs did with i0829
    out["spurious_closures"] = [(x["id"], x["day"]) for x in sim["closure_rows"] if x["spurious"]]
    rows = [r for rr in sim["cycles"] for r in rr if r["id"] == "i0829"]
    out["i0829"] = {"event": [r["day"] for r in rows if r["event"]], "window": [r["day"] for r in rows if r["window"]],
                    "stale": [r["day"] for r in rows if r["stale"]]}
    first = next(x for x in sim["key_rows"] if x["id"] == "i1235b")
    out["i1235b_key_receipt"] = (first["day"], first["duplicate"])
    return out


def plan_size(p, target, alpha=0.01, prob=0.9, nmax=20000):
    """The smallest n from which on the upper end of the confidence sequence at n lies below the
    target with probability at least prob, when the count of failures is binomial(n, p); and that
    probability at the plug-in size of models/cs.py, where the expected count just suffices."""
    from scipy.stats import binom
    smax, probs = -1, []
    for n in range(1, nmax + 1):
        while cs.cs_interval(smax + 1, n, alpha)[1] < target:
            smax += 1
        probs.append(float(binom.cdf(smax, n, p)) if smax >= 0 else 0.0)
    last_bad = max((i for i, q in enumerate(probs) if q < prob), default=-1)
    assert last_bad + 2 < nmax - 200, "scan range too short"
    return last_bad + 2, probs


def truth(sim):
    """The quantities the estimates are about, as the simulation defines them.  The share of
    duplicates is among keys that reach a proposal: a primary key whose reply is detected before
    its first cycle is never proposed, a duplicate key always is."""
    import numpy as np
    from scipy.stats import expon, lognorm
    p = sim["params"]
    q_false = p["p_false"] * (1 - math.exp(-p["audit_age"] / p["false_mean"]))
    h = np.linspace(p["work_start"], p["work_end"], 200001)
    gap = np.where(h < p["cycle"], p["cycle"] - h, 1 + p["cycle"] - h)
    fd = lognorm.cdf(gap, s=p["delay_sigma"], scale=p["delay_median"])
    fe = expon.cdf(gap, scale=p["false_mean"])
    proposed = float(np.mean((1 - p["p_reply"] * (1 - p["miss_v1"]) * fd) * (1 - p["p_false"] * fe)))
    # a key's first closing is spurious when a spurious note exists and comes before any detected
    # reply, and no reply had arrived by its time: P(F < D) for the two delays
    x = np.linspace(0, 60, 600001)
    f_before_d = float(np.trapezoid(lognorm.pdf(x, s=p["delay_sigma"], scale=p["delay_median"])
                                * expon.cdf(x, scale=p["false_mean"]), x))
    p_det = p["p_reply"] * (1 - p["miss_v1"])
    spurious_first = p["p_false"] * ((1 - p["p_reply"]) + p["p_reply"] * f_before_d)
    has_closing = 1 - (1 - p_det) * (1 - p["p_false"])
    return {"miss_v1": p["miss_v1"], "miss_v2": p["miss_v2"],
            "audit_missed": p["miss_v1"] * (1 - q_false),
            "primary_proposed": proposed,
            "duplicate_among_proposed": p["p_para"] / (p["p_para"] + proposed),
            "false_close_by_age4": q_false,
            "spurious_first_closing": spurious_first / has_closing}
