"""Pattern 3: consolidation of evidence and anchor cues (GOLEM-Iter Use Case I).

Evidence about one claim comes from three sources a, b, c and is either supporting (+) or
contradicting (-).  Contradicting incidents are also the integrity incidents from which the
verification commitment is re-derived.  The memory keeps, for each source and polarity, a count
capped at two.  Consumers:
  contra  is there contradicting evidence?              (the contradiction probe)
  eff     distinct supporting sources, capped at two     (dependence-aware evidence weight)
  regen   do at least two distinct sources contradict?   (the anchor's regeneration cue set)
"""
from itertools import product

from dclib import Machine, check_now, check_updates, check_behavioral, minimize_for_queries, \
    check_abstraction_map

SOURCES = ["a", "b", "c"]
CAP = 2
# state: (pa, pb, pc, ma, mb, mc), counts of + and - per source
CARRIER = list(product(range(CAP + 1), repeat=6))


def add(idx):
    def f(s):
        t = list(s)
        t[idx] = min(t[idx] + 1, CAP)
        return tuple(t)
    return f


ACTIONS = [("plus-a", add(0)), ("plus-b", add(1)), ("plus-c", add(2)),
           ("minus-a", add(3)), ("minus-b", add(4)), ("minus-c", add(5))]


def contra(s):
    return sum(s[3:]) > 0


def eff(s):
    return min(sum(1 for x in s[:3] if x > 0), 2)


def regen(s):
    return sum(1 for x in s[3:] if x > 0) >= 2


CONSUMERS = [("contra", contra), ("eff", eff), ("regen", regen)]


def machine(names):
    return Machine(CARRIER, ACTIONS, [(n, f) for n, f in CONSUMERS if n in names])


ALL = machine(["contra", "eff", "regen"])


# ------------------------------------------------------------------ consolidation policies

def majority(s):
    """Lossy summary: which polarity has more raw incidents."""
    p, m = sum(s[:3]), sum(s[3:])
    return "+" if p > m else ("-" if m > p else "=")


def counts(s):
    """Raw totals per polarity, capped at two like the per-source counts."""
    return (min(sum(s[:3]), CAP), min(sum(s[3:]), CAP))


def distinct(s):
    """Numbers of distinct sources per polarity."""
    return (sum(1 for x in s[:3] if x > 0), sum(1 for x in s[3:] if x > 0))


def provenance(s):
    """Which sources have supported and which have contradicted."""
    return tuple(x > 0 for x in s)


def protected(s):
    """Use Case I repair: raw totals plus the provenance of the contradicting incidents."""
    return counts(s) + tuple(x > 0 for x in s[3:])


POLICIES = [("Majority", majority), ("Counts", counts), ("Distinct", distinct),
            ("Protected", protected), ("Provenance", provenance)]


def minimal_matches_quotient():
    cls, _ = minimize_for_queries(ALL)
    key = {}
    for i, c in enumerate(cls):
        for x in c:
            key[x] = i
    by_code = {}
    for x in CARRIER:
        by_code.setdefault(minimal_code(x), set()).add(key[x])
    return all(len(v) == 1 for v in by_code.values()) and len(by_code) == len(cls)


def policy_table():
    """For each policy and consumer: CheckNow, CheckBehavioral (index use) and CheckUpdates (whether
    the codes can be maintained on their own, i.e. whether a memory that keeps only the codes can
    run)."""
    out = {}
    for pname, code in POLICIES:
        row = {}
        for cname, _ in CONSUMERS:
            m = machine([cname])
            row[cname] = {"now": check_now(m, code), "behavioral": check_behavioral(m, code),
                          "updates": check_updates(m, code)}
        out[pname] = row
    return out


def minimal_code(s):
    """The coarsest adequate memory for all three consumers: per polarity, no source, the one
    source seen so far, or two or more sources."""
    def part(xs):
        seen = [SOURCES[i] for i, x in enumerate(xs) if x > 0]
        return "none" if not seen else (seen[0] if len(seen) == 1 else "2+")
    return (part(s[:3]), part(s[3:]))


def quotient_sizes():
    out = {}
    for names in (["contra"], ["eff"], ["regen"], ["contra", "regen"], ["contra", "eff", "regen"]):
        cls, hist = minimize_for_queries(machine(names))
        out["+".join(names)] = (len(cls), hist)
    out["codes"] = {pname: len({code(s) for s in CARRIER}) for pname, code in POLICIES}
    return out


# ------------------------------------------------------------------ the migration cell

# The anchor's goal atom and its control link.  Old schema: the consolidation gate policy is named
# consolidation-requires-independent-check (link value "old").  The migration renames it to
# evidence-gate/verification-floor (link value "new").  A lesion deletes the atom and its link;
# repair regrows the atom from cues whose text still names the old policy.
OLD_STATES = [("present", "old"), ("absent", "none")]
NEW_STATES = [("present", "new"), ("present", "old"), ("absent", "none")]


def lesion(s):
    return ("absent", "none")


def repair_old(s):
    return ("present", "old") if s[0] == "absent" else s


def repair_new_naive(s):
    return ("present", "old") if s[0] == "absent" else s      # cue text names the old policy


def repair_new_cell(s):
    return ("present", "new") if s[0] == "absent" else s      # boundary map carried by the cell


OLD = Machine(OLD_STATES, [("lesion", lesion), ("repair", repair_old)],
              [("live", lambda s: s[1] == "old")])
NEW_NAIVE = Machine(NEW_STATES, [("lesion", lesion), ("repair", repair_new_naive)],
                    [("live", lambda s: s[1] == "new")])
NEW_CELL = Machine(NEW_STATES, [("lesion", lesion), ("repair", repair_new_cell)],
                   [("live", lambda s: s[1] == "new")])


def migrate(s):
    return ("present", "new") if s == ("present", "old") else s


def migration_results():
    return {"naive": check_abstraction_map(OLD, NEW_NAIVE, migrate),
            "cell": check_abstraction_map(OLD, NEW_CELL, migrate)}


if __name__ == "__main__":
    t = policy_table()
    for p, row in t.items():
        print(p)
        for c, r in row.items():
            print("   ", c, {k: ("Checked" if v is None else v) for k, v in r.items()})
    print("minimal code = quotient:", minimal_matches_quotient())
    print(quotient_sizes())
    print(migration_results())
