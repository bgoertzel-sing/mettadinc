"""Pattern 6 on live values: real confidence and deadline pressure, mapped onto Part I's finite model.

Random real runs are mapped through the class abstraction h(c, checked, consolidated, p) =
(c >= 4/5, checked, consolidated, p >= 1/2).  Every real step must map to a stutter or to the
corresponding step of the finite model, and the abstract states visited must lie among the states
that Part I found reachable.  The symbolic proof of the same facts is in smt_live.p6.
"""
import os
import random
import sys
from fractions import Fraction as Q

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "part1_models"))

import dclib  # noqa: E402
import p6_conflicts as F6  # noqa: E402

THC, THP = Q(4, 5), Q(1, 2)


def h(s):
    c, k, d, p = s
    return ("high" if c >= THC else "low", k, d, "deadline" if p >= THP else "calm")


def real_rule(kind):
    abstract = F6.weighted if kind == "weighted" else F6.norm_first

    def rule(s):
        return abstract(h(s))
    return rule


def real_act(s, kind):
    m = real_rule(kind)(s)
    c, k, d, p = s
    if m == "verify":
        return (c, True, d, p)
    if m == "consolidate":
        return (c, k, True, p)
    return s


def run(rng, kind, length):
    s = (Q(0), False, False, Q(0))
    steps = []
    for _ in range(length):
        u = rng.random()
        if u < 0.4:
            lam = Q(rng.randint(0, 10), 10)
            t = (s[0] + lam * (1 - s[0]), s[1], s[2], s[3])
            steps.append(("evidence", s, t))
        elif u < 0.6:
            dl = Q(rng.randint(0, 6), 10)
            t = (s[0], s[1], s[2], min(Q(1), s[3] + dl))
            steps.append(("deadline", s, t))
        else:
            t = real_act(s, kind)
            steps.append(("act", s, t))
        s = t
    return steps


def check(runs=20000, length=8, seed=5):
    rng = random.Random(seed)
    out = {}
    for kind in ("weighted", "norm_first"):
        policy = F6.weighted if kind == "weighted" else F6.norm_first
        m = F6.machine(policy)
        reach = set(dclib.reach(m, [F6.START]))
        abstract_step = {"evidence": F6.evidence, "deadline": F6.deadline, "act": lambda x: F6.apply(x, policy(x))}
        simulation_ok, inside, unlawful_runs, visited = True, True, 0, set()
        for _ in range(runs):
            bad = False
            for a, s, t in run(rng, kind, length):
                hs, ht = h(s), h(t)
                visited.add(hs)
                visited.add(ht)
                if ht != hs and ht != abstract_step[a](hs):
                    simulation_ok = False
                if a == "act" and real_rule(kind)(s) == "consolidate" and not s[1]:
                    bad = True
            if bad:
                unlawful_runs += 1
        inside = visited <= reach
        out[kind] = {"runs": runs, "simulation_ok": simulation_ok, "visited_inside_part1_reach": inside,
                     "abstract_states_visited": len(visited), "part1_reachable": len(reach),
                     "runs_consolidating_unchecked": unlawful_runs}
    return out


if __name__ == "__main__":
    print(check())
