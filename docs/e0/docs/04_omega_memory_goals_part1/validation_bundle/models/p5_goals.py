"""Pattern 5: goals as observers on medium-term memory.

One item record: status (open, closed), age in days (4 stands for "four or more"), addressee (ben,
andy) and priority (normal, urgent).  Actions: tick, close, escalate.  Three goals read it:
  reply   answer open questions addressed to Ben        open and addressee = ben
  nag     follow up on open items for two days          open and age <= 2
  triage  handle urgent open items first                open and priority = urgent
Goal-sufficient memory for a set of goals is the coarsest partition that preserves their answers
now and after every sequence of updates (goal-preservation paper, Theorem 4.2), computed by
MinimizeForQueries.  A proposed change to the nag goal is classified by two informational checks
(is each goal's answer a function of the other's?) and by the interpretation obligation, which
compares the decisions the two goals call for through their declared decoders.
"""
from itertools import product

from dclib import Machine, minimize_for_queries, refine, class_key, check_now, check_behavioral, \
    check_abstraction_map

STATUS = ["open", "closed"]
AGES = [0, 1, 2, 3, 4]
WHO = ["ben", "andy"]
PRIO = ["normal", "urgent"]
CARRIER = list(product(STATUS, AGES, WHO, PRIO))


def tick(s):
    st, a, w, p = s
    return (st, min(a + 1, 4), w, p)


def close(s):
    st, a, w, p = s
    return ("closed", a, w, p)


def escalate(s):
    st, a, w, p = s
    return (st, a, w, "urgent")


ACTIONS = [("tick", tick), ("close", close), ("escalate", escalate)]

GOALS = {
    "reply": lambda s: s[0] == "open" and s[2] == "ben",
    "nag": lambda s: s[0] == "open" and s[1] <= 2,
    "triage": lambda s: s[0] == "open" and s[3] == "urgent",
}


def machine(names):
    return Machine(CARRIER, ACTIONS, [(n, GOALS[n]) for n in names])


def closure(names):
    cls, hist = minimize_for_queries(machine(names))
    return cls, hist


def closure_table():
    out = {}
    for names in (["reply"], ["nag"], ["triage"], ["reply", "nag"], ["reply", "nag", "triage"],
                  ["reply", "triage"]):
        cls, hist = closure(names)
        out["+".join(names)] = {"classes": len(cls), "rounds": len(hist), "history": hist}
    return out


def add_goal_incrementally():
    """Adding triage to {reply, nag}: resume from the current partition met with the new query."""
    base, _ = closure(["reply", "nag"])
    key = class_key(base)
    m = machine(["reply", "nag", "triage"])
    resumed, hist_resumed = refine(m, lambda s: (key[s], GOALS["triage"](s)))
    scratch, hist_scratch = minimize_for_queries(m)
    same = sorted(map(tuple, resumed)) == sorted(map(tuple, scratch))
    return {"resumed_history": hist_resumed, "scratch_history": hist_scratch, "same": same,
            "classes": len(scratch)}


def retire_goal():
    """Retiring nag from {reply, nag, triage}: the 17-class memory stays adequate (sufficient) for
    {reply, triage}, whose coarsest memory has 5 classes."""
    full, _ = closure(["reply", "nag", "triage"])
    smaller, _ = closure(["reply", "triage"])
    m = machine(["reply", "triage"])
    key = class_key(full)
    still_adequate = check_behavioral(m, lambda s: key[s]) is None
    # which distinctions may now be merged: classes of the old memory that fall into one new class
    newkey = class_key(smaller)
    merged = {}
    for c in full:
        merged.setdefault(newkey[c[0]], set()).add(id(c))
    return {"old": len(full), "new": len(smaller), "still_adequate": still_adequate,
            "largest_merge": max(len(v) for v in merged.values())}


def distinctions_only(a, b):
    """Least pair of states that goal set a separates (behaviorally) and goal set b does not."""
    ka = class_key(closure(a)[0])
    kb = class_key(closure(b)[0])
    for i, x in enumerate(CARRIER):
        for y in CARRIER[i + 1:]:
            if ka[x] != ka[y] and kb[x] == kb[y]:
                return (x, y)
    return None


# ------------------------------------------------------------------ classifying a goal change

NAG = machine(["nag"])


def days_left(s):
    """Refinement: the nag answer together with the number of days left to follow up."""
    st, a, w, p = s
    return (st == "open" and a <= 2, max(0, 3 - a) if st == "open" else 0)


def nag_cap3(s):
    """Content change: follow up for three days instead of two."""
    return s[0] == "open" and s[1] <= 3


# Migration: the memory schema stores the days remaining in the follow-up window instead of the age.
NEW_CARRIER = list(product(STATUS, [3, 2, 1, 0], WHO, PRIO))


def to_new(s):
    st, a, w, p = s
    return (st, max(0, 3 - a), w, p)


def new_tick(s):
    st, d, w, p = s
    return (st, max(0, d - 1), w, p)


NEW_NAG = Machine(NEW_CARRIER, [("tick", new_tick), ("close", lambda s: ("closed",) + s[1:]),
                                ("escalate", lambda s: s[:3] + ("urgent",))],
                  [("nag", lambda s: s[0] == "open" and s[1] > 0)])


# A failed migration: the same schema and map, but the new tick forgets to count the days left down.
NEW_NAG_STUCK = Machine(NEW_CARRIER, [("tick", lambda s: s), ("close", lambda s: ("closed",) + s[1:]),
                                      ("escalate", lambda s: s[:3] + ("urgent",))],
                        [("nag", lambda s: s[0] == "open" and s[1] > 0)])


def nag_ben_first(s):
    """Refinement with a memory cost: the nag answer, and whether the follow-up is for Ben."""
    n = GOALS["nag"](s)
    return (n, n and s[2] == "ben")


def closure_of_observer(f):
    cls, _ = minimize_for_queries(Machine(CARRIER, ACTIONS, [("g", f)]))
    return len(cls)


def anti_nag(s):
    """The negated goal: the same information as nag, the opposite answer on every record."""
    return not GOALS["nag"](s)


# ------------------------------------------------------------------ what the answers mean

def follow_up_if_true(b):
    """The protected decoder of the nag goal: a true answer calls for a follow-up."""
    return "follow-up" if b else "wait"


def wait_if_true(b):
    return "wait" if b else "follow-up"


def on_first(decoder):
    """A decoder for a refined answer that reads only whether a follow-up is due."""
    return lambda answer: decoder(answer[0])


def interpretation(old, d_old, new, d_new, h=lambda s: s, records=CARRIER):
    """The interpretation obligation d_new(new(h x)) = d_old(old x) on every valid record x; the
    least record (in carrier order) where it fails, with both answers and decisions, or None."""
    for x in records:
        a_old, a_new = old(x), new(h(x))
        if d_new(a_new) != d_old(a_old):
            return {"record": x, "old_answer": a_old, "new_answer": a_new,
                    "old_decision": d_old(a_old), "new_decision": d_new(a_new)}
    return None


def kind(recoverable, converse, same_decisions, migration=None):
    """The classification of a goal change from its verdicts (True for Checked)."""
    if not same_decisions:
        return "change of content"
    if migration is not None:
        return "migration" if migration else "failed migration"
    if recoverable and converse:
        return "renaming"
    if recoverable:
        return "refinement"
    return "coarsening"


# the proposed changes: the new observer and the decoder its consumer declares
CHANGES = [("days-left", days_left, on_first(follow_up_if_true)),
           ("nag-ben-first", nag_ben_first, on_first(follow_up_if_true)),
           ("cap3", nag_cap3, follow_up_if_true),
           ("anti-nag", anti_nag, follow_up_if_true),
           ("anti-nag-waits", anti_nag, wait_if_true)]


def classify():
    """Answers recoverable: the new observer determines the old one (CheckNow on the old goal with
    the new observer as code): informational refinement, and with the converse informational
    equivalence.  Interpretation: the decoded decisions agree on every valid record.  Migration: an
    abstraction map between memory schemas that commutes with every action and preserves the goal,
    with the interpretation obligation along the map.  A change is a renaming only when the goals
    are informationally equivalent and the interpretation obligation holds."""
    out = {}
    nag = GOALS["nag"]
    for name, f, dec in CHANGES:
        new_m = Machine(CARRIER, ACTIONS, [(name, f)])
        r = {"determines_old": check_now(NAG, f),
             "old_determines_new": check_now(new_m, nag),
             "closure_classes": closure_of_observer(f),
             "interpretation": interpretation(nag, follow_up_if_true, f, dec)}
        r["kind"] = kind(r["determines_old"] is None, r["old_determines_new"] is None,
                         r["interpretation"] is None)
        out[name] = r
    out["nag_closure_classes"] = closure_of_observer(GOALS["nag"])
    out["migration"] = check_abstraction_map(NAG, NEW_NAG, to_new)
    new_nag = NEW_NAG.observers[0][1]
    out["migration_interpretation"] = interpretation(nag, follow_up_if_true, new_nag, follow_up_if_true,
                                                     h=to_new)
    out["migration_kind"] = kind(None, None, out["migration_interpretation"] is None,
                                 migration=out["migration"] is None)
    # a coarsening: the reverse of the first change, which drops the days left from the answer again
    days_m = Machine(CARRIER, ACTIONS, [("days-left", days_left)])
    r = {"determines_old": check_now(days_m, nag), "old_determines_new": check_now(NAG, days_left),
         "interpretation": interpretation(days_left, on_first(follow_up_if_true), nag, follow_up_if_true)}
    r["kind"] = kind(r["determines_old"] is None, r["old_determines_new"] is None, r["interpretation"] is None)
    out["drop-days-left"] = r
    # a failed migration: every record is translated correctly, and the map does not commute
    out["stuck_migration"] = check_abstraction_map(NAG, NEW_NAG_STUCK, to_new)
    out["stuck_interpretation"] = interpretation(nag, follow_up_if_true, NEW_NAG_STUCK.observers[0][1],
                                                 follow_up_if_true, h=to_new)
    out["stuck_kind"] = kind(None, None, out["stuck_interpretation"] is None,
                             migration=out["stuck_migration"] is None)
    out["anti_disagreements"] = sum(1 for x in CARRIER if follow_up_if_true(anti_nag(x)) != follow_up_if_true(nag(x)))
    anti_cls, _ = minimize_for_queries(Machine(CARRIER, ACTIONS, [("anti", anti_nag)]))
    nag_cls, _ = closure(["nag"])
    out["anti_same_memory"] = sorted(map(tuple, anti_cls)) == sorted(map(tuple, nag_cls))
    return out


if __name__ == "__main__":
    for k, v in closure_table().items():
        print(k, v)
    print(add_goal_incrementally())
    print(retire_goal())
    print("reply-only distinctions vs nag:", distinctions_only(["reply"], ["nag"]))
    print("nag-only distinctions vs reply:", distinctions_only(["nag"], ["reply"]))
    for k, v in classify().items():
        print(k, v)
