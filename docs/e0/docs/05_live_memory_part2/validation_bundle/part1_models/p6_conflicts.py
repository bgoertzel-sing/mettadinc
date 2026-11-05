"""Pattern 6: goal conflicts and prohibitions.

A research agent's handling of one claim: confidence (low, high), whether an independent check has
been done, whether the claim has been consolidated into durable belief, and deadline pressure.
Environment actions: evidence (confidence becomes high), deadline (pressure appears).  The agent's
move, chosen by an arbitration rule over two goals, is the action act.
  throughput   consolidate as soon as confidence is high or a deadline presses
  verify       check independently first; consolidate only checked, high-confidence claims
  norm         consolidating an unchecked claim is forbidden (deontic kernel)
"""
from itertools import product

from dclib import Machine, reach, least_violation

CONF = ["low", "high"]
BOOL = [False, True]
PRESS = ["calm", "deadline"]
CARRIER = list(product(CONF, BOOL, BOOL, PRESS))        # (conf, checked, consolidated, pressure)
START = ("low", False, False, "calm")
MOVES = ["verify", "consolidate", "hold"]


def throughput(s):
    """Preferred move, or None when the goal has no preference."""
    conf, chk, cons, pr = s
    if cons:
        return None
    return "consolidate" if (conf == "high" or pr == "deadline") else None


def verify(s):
    """Preferred move; hold means: do not consolidate yet."""
    conf, chk, cons, pr = s
    if cons:
        return None
    if not chk:
        return "verify"
    return "consolidate" if conf == "high" else "hold"


def forbidden(s, move):
    conf, chk, cons, pr = s
    return move == "consolidate" and not chk


def apply(s, move):
    conf, chk, cons, pr = s
    if move == "verify":
        return (conf, True, cons, pr)
    if move == "consolidate":
        return (conf, chk, True, pr)
    return s


def weighted(s):
    """Consensus by weight: throughput 3/5, verify 2/5.  The heavier goal with a preference
    decides; with no preference at all the agent holds."""
    for m in (throughput(s), verify(s)):
        if m is not None:
            return m
    return "hold"


def norm_first(s):
    """Deontic filter first: a preference for a forbidden move is discarded; then the heavier goal
    with a remaining preference decides."""
    for m in (throughput(s), verify(s)):
        if m is not None and not forbidden(s, m):
            return m
    return "hold"


def evidence(s):
    return ("high",) + s[1:]


def deadline(s):
    return s[:3] + ("deadline",)


def machine(policy):
    return Machine(CARRIER, [("evidence", evidence), ("deadline", deadline),
                             ("act", lambda s: apply(s, policy(s)))], [])


def no_conflict(s):
    """A conflict: both goals have a preference and the preferences differ."""
    a, b = throughput(s), verify(s)
    return a is None or b is None or a == b


def lawful(policy):
    return lambda s: not forbidden(s, policy(s))


def never_unchecked_consolidation(s):
    return not (s[2] and not s[1])


def results():
    out = {}
    m = machine(weighted)
    out["live_weighted"] = len(reach(m, [START]))
    out["conflict"] = least_violation(m, [START], no_conflict)
    out["weighted_lawful"] = least_violation(m, [START], lawful(weighted))
    out["weighted_outcome"] = least_violation(m, [START], never_unchecked_consolidation)
    mn = machine(norm_first)
    out["live_normfirst"] = len(reach(mn, [START]))
    out["normfirst_lawful"] = least_violation(mn, [START], lawful(norm_first))
    out["normfirst_outcome"] = least_violation(mn, [START], never_unchecked_consolidation)
    out["normfirst_conflicts"] = sum(1 for s in reach(mn, [START]) if not no_conflict(s))
    out["conflict_states"] = [s for s in reach(mn, [START]) if not no_conflict(s)]
    return out


if __name__ == "__main__":
    for k, v in results().items():
        print(k, v)
