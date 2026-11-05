"""Pattern 1 on a live store: open items in real time.

Time is in minutes.  An item has a creation time, an addressee and, once a closing reply is
detected, the time of that reply.  The engine asks at time t whether an item is open and at most
seven days old (suggest); the commitment record asks whether it is open.  Aggregate consumers ask
how many items are suggestable for each addressee.

Statistics compared with the brute-force answers on the full store:
  event      id -> (created, closed?)                     exact (keyed statistic)
  window     id -> (created, reply visible in a 2-day window)   not adequate
  histogram  addressee -> creation day -> number of open items   two-sided bounds for the counts
"""
import random

DAY = 24 * 60
CAP = 7 * DAY          # the engine ignores items older than seven days
WINDOW = 2 * DAY       # replies visible to the engine's recall window


class Store:
    def __init__(self):
        self.items = {}            # id -> [created, who, reply_time_true or None]
        self.detected = {}         # id -> detected closing time or None

    def suggest_true(self, t):
        return {i for i, (c, w, r) in self.items.items() if r is None and t - c <= CAP}

    def counts_true(self, t):
        out = {"ben": 0, "andy": 0}
        for i, (c, w, r) in self.items.items():
            if r is None and t - c <= CAP:
                out[w] += 1
        return out


def simulate(seed=1, days=120, rate_per_day=8, reply_prob=0.7, mean_delay_days=2.0, miss=0.0,
             query_every=180):
    """Event-driven simulation.  Returns a dict of checks over all query times."""
    rng = random.Random(seed)
    st = Store()
    events = []                     # (time, kind, id)
    nid = 0
    t = 0
    horizon = days * DAY
    while True:
        t += int(rng.expovariate(rate_per_day / DAY)) + 1
        if t > horizon:
            break
        nid += 1
        who = "ben" if rng.random() < 0.6 else "andy"
        events.append((t, "create", nid, who))
        if rng.random() < reply_prob:
            rt = t + int(rng.expovariate(1 / (mean_delay_days * DAY))) + 1
            if rt <= horizon:
                events.append((rt, "reply", nid, None))
    for q in range(query_every, horizon + 1, query_every):
        events.append((q, "query", None, None))
    order = {"create": 0, "reply": 1, "query": 2}
    events.sort(key=lambda e: (e[0], order[e[1]], e[2] or 0))

    # statistics maintained only from detected events
    event_stat = {}                 # id -> (created, closed)
    window_stat = {}                # id -> (created, detected reply time or None)
    hist = {"ben": {}, "andy": {}}  # who -> creation day -> open count (detected)
    who_of = {}
    res = {"items": 0, "replies": 0, "missed": 0, "queries": 0, "event_exact": True,
           "event_stale": 0, "stale_subset_of_missed": True, "window_stale": 0,
           "window_suggestions": 0, "event_suggestions": 0, "hist_bounds_hold": True,
           "hist_width_total": 0, "hist_count_total": 0, "counts_exact": True}
    for (t, kind, i, who) in events:
        if kind == "create":
            st.items[i] = [t, who, None]
            event_stat[i] = (t, False)
            window_stat[i] = (t, None)
            who_of[i] = who
            hist[who][t // DAY] = hist[who].get(t // DAY, 0) + 1
            res["items"] += 1
        elif kind == "reply":
            if st.items[i][2] is not None:
                continue
            st.items[i][2] = t
            res["replies"] += 1
            if rng.random() < miss:
                res["missed"] += 1
                st.detected[i] = None
                continue
            st.detected[i] = t
            c, closed = event_stat[i]
            if not closed:
                event_stat[i] = (c, True)
                hist[who_of[i]][c // DAY] -= 1
            window_stat[i] = (c, t)
        else:
            res["queries"] += 1
            truth = st.suggest_true(t)
            ev = {i for i, (c, closed) in event_stat.items() if not closed and t - c <= CAP}
            win = {i for i, (c, r) in window_stat.items()
                   if not (r is not None and t - r <= WINDOW) and t - c <= CAP}
            res["event_suggestions"] += len(ev)
            res["window_suggestions"] += len(win)
            if miss == 0 and ev != truth:
                res["event_exact"] = False
            stale_ev = ev - truth
            res["event_stale"] += len(stale_ev)
            missed_ids = {j for j, d in st.detected.items() if d is None}
            if not stale_ev <= missed_ids:
                res["stale_subset_of_missed"] = False
            res["window_stale"] += len(win - truth)
            # aggregate counts per addressee
            if miss == 0:
                ct = st.counts_true(t)
                ce = {"ben": 0, "andy": 0}
                for j in ev:
                    ce[who_of[j]] += 1
                if ce != ct:
                    res["counts_exact"] = False
                # creation-day histogram: days fully inside the window count surely; the boundary
                # day may or may not; days before it never do
                for w in ("ben", "andy"):
                    lo = hi = 0
                    first_full = (t - CAP) // DAY + 1        # creation days d with d*DAY >= t-CAP
                    boundary = (t - CAP) // DAY
                    for d, n in hist[w].items():
                        if d >= first_full:
                            lo += n
                            hi += n
                        elif d == boundary:
                            hi += n
                    if not (lo <= ct[w] <= hi):
                        res["hist_bounds_hold"] = False
                    res["hist_width_total"] += hi - lo
                    res["hist_count_total"] += ct[w]
    return res


if __name__ == "__main__":
    print(simulate())
    print(simulate(miss=0.1, seed=2))
