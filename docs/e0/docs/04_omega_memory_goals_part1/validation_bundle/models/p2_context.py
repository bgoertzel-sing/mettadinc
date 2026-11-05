"""Pattern 2: selecting the context block from working memory.

Working memory is modeled as n recency-ordered slots (slot 1 is the most recent), each holding an
item of one kind: F (fresh recall for the current message), O (open item for the current speaker),
A (anchor cue or active commitment, protected), X (anything else).  The context block holds b items.
Each consumer asks for the most recent item of one kind (its slot number, or 0 if there is none).
A selection policy is a representation: the code of a memory state is the set of selected
(slot, kind) pairs.  CheckNow asks whether the code determines a consumer's answer.
"""
from itertools import product

from dclib import Machine, check_now

KINDS = ["F", "O", "A", "X"]                 # declaration order of the Kind carrier


def carrier(n):
    return list(product(KINDS, repeat=n))


def latest(kind):
    def f(s):
        for i, k in enumerate(s):
            if k == kind:
                return i + 1
        return 0
    return f


CONSUMERS = [("latest-F", latest("F")), ("latest-O", latest("O")), ("latest-A", latest("A"))]


def select(order, b):
    """Rank slots by (rank of kind, recency) and keep the best b."""
    def code(s):
        ranked = sorted(range(len(s)), key=lambda i: (order(s, i), i))
        chosen = sorted(ranked[:b])
        return tuple((i + 1, s[i]) for i in chosen)
    return code


def recency(s, i):
    return 0


RELEVANCE_RANK = {"F": 0, "O": 1, "X": 2, "A": 3}     # anchors rarely match the message text
PROTECTED_RANK = {"A": 0, "F": 1, "O": 2, "X": 3}


def relevance(s, i):
    return RELEVANCE_RANK[s[i]]


def protected_first(s, i):
    return PROTECTED_RANK[s[i]]


def consumer_aware(priority):
    """Fill the budget with the latest item of each declared consumer kind, in priority order,
    then with the remaining items by recency."""
    def order(s, i):
        firsts = []
        for k in priority:
            for j, kk in enumerate(s):
                if kk == k:
                    firsts.append(j)
                    break
        if i in firsts:
            return firsts.index(i)
        return len(priority) + 1
    return order


POLICIES = [("Recency", recency), ("Relevance", relevance), ("ProtectedFirst", protected_first),
            ("ConsumerAware", consumer_aware(["A", "F", "O"]))]


def table(n, b):
    out = {}
    states = carrier(n)
    for pname, order in POLICIES:
        code = select(order, b)
        row = {}
        for cname, cf in CONSUMERS:
            m = Machine(states, [], [(cname, cf)])
            row[cname] = check_now(m, code)
        out[pname] = row
    return out


def served_fraction(n, b, pname, cname):
    """Fraction of memory states in which the selected block contains the consumer's answer."""
    order = dict(POLICIES)[pname]
    cf = dict(CONSUMERS)[cname]
    code = select(order, b)
    states = carrier(n)
    good = 0
    for s in states:
        ans = cf(s)
        good += (ans == 0 or any(i == ans for i, _ in code(s)))
    return good, len(states)


if __name__ == "__main__":
    for n, b in ((3, 2), (4, 2), (4, 3), (5, 3)):
        print("slots", n, "budget", b)
        t = table(n, b)
        for p, row in t.items():
            print("  ", p, {c: ("Checked" if w is None else (w["pair"], w["left"], w["right"])) for c, w in row.items()})
    for p, _ in POLICIES:
        print(p, [served_fraction(3, 2, p, c) for c, _ in CONSUMERS])
