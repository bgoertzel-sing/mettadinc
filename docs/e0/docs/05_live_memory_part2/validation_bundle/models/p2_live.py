"""Pattern 2 on a live working memory: context blocks under a token budget.

A snapshot has n items in recency order (index 0 is the most recent).  Each item has a kind
(F fresh recall, O open item for the speaker, A anchor cue, X other), a token cost and a relevance
score.  A block is chosen greedily under the budget B: items are taken in the policy's order and an
item that does not fit is skipped (first fit).  Three consumers ask for the most recent item of
kinds F, O and A; a consumer is served when that item is in the block, or when the snapshot has no
item of its kind.

Policies: recency; relevance (score); protected-first (anchors by recency, then score);
consumer-aware (the required items in the order A, F, O, then the rest by score).
"""
import random

KINDS = ("F", "O", "A")


def required(snap):
    out = {}
    for i, (k, cost, score) in enumerate(snap):
        if k in KINDS and k not in out:
            out[k] = i
    return out


def order(snap, policy):
    idx = list(range(len(snap)))
    if policy == "recency":
        return idx
    if policy == "relevance":
        return sorted(idx, key=lambda i: (-snap[i][2], i))
    if policy == "protected":
        anchors = [i for i in idx if snap[i][0] == "A"]
        rest = sorted((i for i in idx if snap[i][0] != "A"), key=lambda i: (-snap[i][2], i))
        return anchors + rest
    if policy == "consumer":
        req = required(snap)
        first = [req[k] for k in ("A", "F", "O") if k in req]
        rest = sorted((i for i in idx if i not in first), key=lambda i: (-snap[i][2], i))
        return first + rest
    raise ValueError(policy)


def block(snap, policy, budget):
    used, chosen = 0, set()
    for i in order(snap, policy):
        c = snap[i][1]
        if used + c <= budget:
            chosen.add(i)
            used += c
    return chosen


def served(snap, policy, budget):
    b = block(snap, policy, budget)
    req = required(snap)
    return {k: (k not in req) or (req[k] in b) for k in KINDS}


def random_snapshot(rng, n=60):
    snap = []
    for _ in range(n):
        u = rng.random()
        if u < 0.15:
            k, s = "F", rng.betavariate(5, 2)
        elif u < 0.25:
            k, s = "O", rng.betavariate(3, 3)
        elif u < 0.33:
            k, s = "A", rng.betavariate(1.5, 6)
        else:
            k, s = "X", rng.betavariate(2, 4)
        snap.append((k, rng.randint(15, 120), s))
    return snap


def required_cost(snap):
    req = required(snap)
    return sum(snap[i][1] for i in req.values())


def theorem_check(trials, seed, budgets=(150, 300, 600, 1500)):
    """Consumer-aware serves every consumer whenever the required items fit the budget, for any
    number of items; and when they do not fit, no policy serves all three."""
    rng = random.Random(seed)
    holds, fit_cases, nofit_cases, others_fail = True, 0, 0, 0
    for _ in range(trials):
        n = rng.randint(1, 80)
        snap = random_snapshot(rng, n)
        B = rng.choice(budgets)
        s = served(snap, "consumer", B)
        if required_cost(snap) <= B:
            fit_cases += 1
            if not all(s.values()):
                holds = False
            if any(not all(served(snap, p, B).values()) for p in ("recency", "relevance", "protected")):
                others_fail += 1
        else:
            nofit_cases += 1
            # no block within budget can contain all required items
    return {"holds": holds, "fit_cases": fit_cases, "nofit_cases": nofit_cases,
            "fit_cases_where_another_policy_misses": others_fail}


def receipt_log(snapshots, seed, budget=1500, n=60):
    """A simulated receipt log: per snapshot, which consumers each policy serves."""
    rng = random.Random(seed)
    rows = []
    for _ in range(snapshots):
        snap = random_snapshot(rng, n)
        row = {"required_cost": required_cost(snap)}
        for p in ("recency", "relevance", "protected", "consumer"):
            row[p] = served(snap, p, budget)
        rows.append(row)
    return rows


if __name__ == "__main__":
    print(theorem_check(20000, 1))
    log = receipt_log(2000, 2)
    for p in ("recency", "relevance", "protected", "consumer"):
        print(p, {k: sum(1 for r in log if not r[p][k]) for k in KINDS})
    print(max(r["required_cost"] for r in log))
