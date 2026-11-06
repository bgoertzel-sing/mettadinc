"""Pattern 1: open items and the goal engine (medium-term memory).

One open item: its age in days (8 stands for "more than seven") and the time since its closing
reply (none, or 0, 1, 2, 3 = three or more days ago).  The goal engine suggests follow-ups for open
items up to seven days old.  The commitment record (a self-model consumer) asks only whether the
item is still open.
"""
from dclib import Machine, reach, check_now, check_updates, check_behavioral, minimize_for_queries, \
    least_violation

AGES = list(range(9))
REPLIES = ["none", "d0", "d1", "d2", "d3"]
NEXT_REPLY = {"none": "none", "d0": "d1", "d1": "d2", "d2": "d3", "d3": "d3"}
CARRIER = [(a, r) for a in AGES for r in REPLIES]          # Product Age Reply, declaration order
START = (0, "none")
WINDOW = ("d0", "d1", "d2")                                  # replies the engine's recall window shows


def tick(s):
    a, r = s
    return (min(a + 1, 8), NEXT_REPLY[r])


def on_reply(s):
    a, r = s
    return (a, "d0" if r == "none" else r)


def is_open(s):
    return s[1] == "none"


def suggest(s):
    return s[1] == "none" and s[0] <= 7


ACTIONS = [("tick", tick), ("reply", on_reply)]
FULL = Machine(CARRIER, ACTIONS, [("suggest", suggest)])
LIVE = reach(FULL, [START])                                 # (Reach ItemLife (From start))
SUGGEST = FULL.restrict(LIVE)
COMMIT = SUGGEST.with_observers([("open", is_open)])
BOTH = SUGGEST.with_observers([("suggest", suggest), ("open", is_open)])


def window_view(s):
    """What the engine sees: the age and whether a closing reply is inside its recall window."""
    return (s[0], s[1] in WINDOW)


def event_view(s):
    """Closing recorded as an event on the item: the age and whether it has been closed."""
    return (s[0], s[1] != "none")


def capped_view(s):
    """The seven-day cap applied to the record itself: older items are dropped entirely."""
    return ("dropped",) if s[0] == 8 else event_view(s)


def results():
    out = {}
    out["live_states"] = len(LIVE)
    out["window_now"] = check_now(SUGGEST, window_view)
    out["window_updates"] = check_updates(SUGGEST, window_view)
    out["window_behavioral"] = check_behavioral(SUGGEST, window_view)
    out["event_now"] = check_now(SUGGEST, event_view)
    out["event_updates"] = check_updates(SUGGEST, event_view)
    out["event_behavioral"] = check_behavioral(SUGGEST, event_view)
    cls_s, hist_s = minimize_for_queries(SUGGEST)
    cls_c, hist_c = minimize_for_queries(COMMIT)
    cls_b, hist_b = minimize_for_queries(BOTH)
    out["classes_suggest"] = cls_s
    out["classes_commit"] = cls_c
    out["classes_both"] = cls_b
    out["capped_suggest_behavioral"] = check_behavioral(SUGGEST, capped_view)
    out["capped_commit_now"] = check_now(COMMIT, capped_view)
    out["event_view_codes"] = len({event_view(s) for s in LIVE})
    return out


# ------------------------------------------------------------------ deduplication of paraphrases

# One question asked twice in paraphrase.  Notes n1 and n2 carry different topic labels, so the
# person+topic key gives them different keys; the question key gives them the same key.
# State: (n1 received, n2 received, keys already suggested (bits k1, k2), suggestions about the
# question, capped at 2).
BOOLS = [False, True]
COUNTS = [0, 1, 2]
DCARRIER = [(r1, r2, s1, s2, c) for r1 in BOOLS for r2 in BOOLS for s1 in BOOLS for s2 in BOOLS
            for c in COUNTS]
DSTART = (False, False, False, False, 0)


def recv1(s):
    return (True,) + s[1:]


def recv2(s):
    return (s[0], True) + s[2:]


def run_topic(s):
    """Suggest every received note whose person+topic key has not been suggested."""
    r1, r2, s1, s2, c = s
    if r1 and not s1:
        s1, c = True, min(c + 1, 2)
    if r2 and not s2:
        s2, c = True, min(c + 1, 2)
    return (r1, r2, s1, s2, c)


def run_question(s):
    """Suggest a received note only if its question has not been suggested (both notes: key k1)."""
    r1, r2, s1, s2, c = s
    if (r1 or r2) and not s1:
        s1, c = True, min(c + 1, 2)
    return (r1, r2, s1, s2, c)


def at_most_once(s):
    return s[4] <= 1


TOPIC = Machine(DCARRIER, [("recv1", recv1), ("recv2", recv2), ("run", run_topic)], [])
QUESTION = Machine(DCARRIER, [("recv1", recv1), ("recv2", recv2), ("run", run_question)], [])


def dedupe_results():
    out = {}
    out["topic_live"] = len(reach(TOPIC, [DSTART]))
    out["question_live"] = len(reach(QUESTION, [DSTART]))
    out["topic"] = least_violation(TOPIC, [DSTART], at_most_once)
    out["question"] = least_violation(QUESTION, [DSTART], at_most_once)
    return out


if __name__ == "__main__":
    r = results()
    for k, v in r.items():
        if k.startswith("classes"):
            print(k, len(v), v)
        else:
            print(k, v)
    print(dedupe_results())
