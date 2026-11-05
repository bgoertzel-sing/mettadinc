"""Pattern 4: task checkpoints and resumption (OCO/2 TaskCheckpoint).

A task has two evidence items e1, e2 (valid or withdrawn) and at most one derived result, which
records the evidence it was derived from (r1 or r2).  A withdrawal of evidence that a result used
makes the result stale until it is revalidated.  The restart consumer asks whether a result needs
revalidation and whether a current result is available.
"""
from itertools import product

from dclib import Machine, reach, check_now, check_updates, check_behavioral, minimize_for_queries

EV = ["valid", "withdrawn"]
RES = ["none", "r1", "r2"]
FLAG = ["current", "stale"]
CARRIER = list(product(EV, EV, RES, FLAG))          # (v1, v2, result, flag)
START = ("valid", "valid", "none", "current")


def derive(i):
    def f(s):
        v1, v2, r, fl = s
        if (v1, v2)[i - 1] == "valid" and r == "none":
            return (v1, v2, f"r{i}", "current")
        return s
    return f


def withdraw(i):
    def f(s):
        v1, v2, r, fl = s
        v = [v1, v2]
        v[i - 1] = "withdrawn"
        if r == f"r{i}":
            fl = "stale"
        return (v[0], v[1], r, fl)
    return f


def revalidate(s):
    v1, v2, r, fl = s
    return (v1, v2, "none", "current") if fl == "stale" else s


def needs_revalidation(s):
    return s[3] == "stale"


def available(s):
    return s[2] != "none" and s[3] == "current"


ACTIONS = [("derive1", derive(1)), ("derive2", derive(2)), ("withdraw1", withdraw(1)),
           ("withdraw2", withdraw(2)), ("revalidate", revalidate)]
FULL = Machine(CARRIER, ACTIONS, [("needs-revalidation", needs_revalidation),
                                  ("available", available)])
LIVE = reach(FULL, [START])
RESTART = FULL.restrict(LIVE)


def checkpoint_without_reads(s):
    """Records that a result exists, its status and the evidence statuses; not what it read."""
    v1, v2, r, fl = s
    return (v1, v2, r != "none", fl)


def checkpoint_with_reads(s):
    return s


def results():
    out = {"live": len(LIVE)}
    out["noreads_now"] = check_now(RESTART, checkpoint_without_reads)
    out["noreads_updates"] = check_updates(RESTART, checkpoint_without_reads)
    out["noreads_behavioral"] = check_behavioral(RESTART, checkpoint_without_reads)
    out["reads_behavioral"] = check_behavioral(RESTART, checkpoint_with_reads)
    cls, hist = minimize_for_queries(RESTART)
    out["classes"] = cls
    out["history"] = hist
    out["noreads_codes"] = len({checkpoint_without_reads(s) for s in LIVE})
    return out


if __name__ == "__main__":
    for k, v in results().items():
        print(k, len(v) if k == "classes" else v)
    print(results()["classes"])
