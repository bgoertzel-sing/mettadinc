"""Exact routines for finite deterministic machines, used by the memory-and-goals guide.

A machine has a carrier (a list in declaration order), actions and observers (lists of
(label, function) in declaration order).  Every routine returns the canonical witness of the
specification: shortest word first, then pairs in lexicographic order of the carrier declaration,
then actions and queries in declaration order, then words in numeric order.
"""
from collections import deque
from fractions import Fraction as F
from itertools import product


class Machine:
    def __init__(self, states, actions, observers):
        self.states = list(states)
        self.pos = {s: i for i, s in enumerate(self.states)}
        self.actions = list(actions)
        self.observers = list(observers)
        self.T = {a: {s: f(s) for s in self.states} for a, f in self.actions}
        self.O = {o: {s: f(s) for s in self.states} for o, f in self.observers}
        for a, f in self.actions:
            for s in self.states:
                assert self.T[a][s] in self.pos, (a, s, self.T[a][s])

    @property
    def alabels(self):
        return [a for a, _ in self.actions]

    @property
    def olabels(self):
        return [o for o, _ in self.observers]

    def run(self, s, word):
        for a in word:
            s = self.T[a][s]
        return s

    def restrict(self, keep):
        """The machine on a forward-closed subset, in the order of the original carrier."""
        keep = set(keep)
        states = [s for s in self.states if s in keep]
        for a in self.alabels:
            for s in states:
                assert self.T[a][s] in keep, "subset is not forward closed"
        return Machine(states, [(a, (lambda a: lambda s: self.T[a][s])(a)) for a in self.alabels],
                       [(o, (lambda o: lambda s: self.O[o][s])(o)) for o in self.olabels])

    def with_observers(self, observers):
        return Machine(self.states, [(a, (lambda a: lambda s: self.T[a][s])(a)) for a in self.alabels],
                       observers)


def reach(m, starts):
    """Reachable states from the start states (breadth first, actions in declaration order)."""
    seen = set(starts)
    dq = deque(starts)
    while dq:
        s = dq.popleft()
        for a in m.alabels:
            t = m.T[a][s]
            if t not in seen:
                seen.add(t)
                dq.append(t)
    return [s for s in m.states if s in seen]


def pairs(states):
    for i in range(len(states)):
        for j in range(i + 1, len(states)):
            yield states[i], states[j]


# ------------------------------------------------------------------ the three obligations

def check_now(m, code):
    """Least pair with equal codes and a differing query; None if the code determines every query."""
    for x, y in pairs(m.states):
        if code(x) == code(y):
            for o in m.olabels:
                if m.O[o][x] != m.O[o][y]:
                    return {"pair": (x, y), "query": o, "left": m.O[o][x], "right": m.O[o][y]}
    return None


def check_updates(m, code):
    """Least pair with equal codes whose successors under some action have different codes."""
    for x, y in pairs(m.states):
        if code(x) == code(y):
            for a in m.alabels:
                cx, cy = code(m.T[a][x]), code(m.T[a][y])
                if cx != cy:
                    return {"pair": (x, y), "action": a, "left": cx, "right": cy}
    return None


def check_behavioral(m, code, horizon=None):
    """Least word witness: shortest word, then least pair, then word in numeric order, then query.

    Returns None when every pair with equal codes agrees on every query after every word (within
    the horizon if one is given)."""
    same = [(x, y) for x, y in pairs(m.states) if code(x) == code(y)]
    # breadth-first search on the pair graph gives the length of the shortest separating word
    dist = {}
    dq = deque()
    for p in same:
        dist[p] = 0
        dq.append(p)
    best = None
    while dq:
        p = dq.popleft()
        x, y = p
        if any(m.O[o][x] != m.O[o][y] for o in m.olabels):
            best = dist[p]
            break
        if horizon is not None and dist[p] >= horizon:
            continue
        for a in m.alabels:
            q = (m.T[a][x], m.T[a][y])
            if q[0] == q[1]:
                continue
            if q not in dist:
                dist[q] = dist[p] + 1
                dq.append(q)
    if best is None:
        return None
    k = best
    for x, y in same:
        for word in product(m.alabels, repeat=k):
            fx, fy = m.run(x, word), m.run(y, word)
            for o in m.olabels:
                if m.O[o][fx] != m.O[o][fy]:
                    return {"pair": (x, y), "word": list(word), "query": o,
                            "left": m.O[o][fx], "right": m.O[o][fy]}
    raise AssertionError("search inconsistency")


# ------------------------------------------------------------------ refinement

def refine(m, seed):
    """Coarsest refinement of the kernel of seed that is closed under the actions.

    Returns (classes, history): classes as lists in carrier order, ordered by first member;
    history is the number of classes after each round."""
    blk = {}
    canon = {}
    for s in m.states:
        blk[s] = canon.setdefault(seed(s), len(canon))
    history = [len(canon)]
    while True:
        canon2 = {}
        blk2 = {}
        for s in m.states:
            sig = (blk[s],) + tuple(blk[m.T[a][s]] for a in m.alabels)
            blk2[s] = canon2.setdefault(sig, len(canon2))
        if len(canon2) == len(canon):
            return classes_of(m, blk2), history
        history.append(len(canon2))
        blk, canon = blk2, canon2


def refine_from(m, partition_key, seed):
    """Resume refinement from the meet of an existing partition and a new seed (Lemma 4.10)."""
    return refine(m, lambda s: (partition_key(s), seed(s)))


def classes_of(m, blk):
    out = {}
    for s in m.states:
        out.setdefault(blk[s], []).append(s)
    return sorted(out.values(), key=lambda c: m.pos[c[0]])


def minimize_for_queries(m):
    return refine(m, lambda s: tuple(m.O[o][s] for o in m.olabels))


def class_key(classes):
    k = {}
    for i, c in enumerate(classes):
        for s in c:
            k[s] = i
    return k


# ------------------------------------------------------------------ safety and abstraction maps

def least_violation(m, starts, ok):
    """Least shortest word from the start states to a state outside ok (breadth first, actions in
    declaration order, start states in carrier order).  None if every reachable state is ok."""
    starts = sorted(starts, key=lambda s: m.pos[s])
    for s in starts:
        if not ok(s):
            return {"word": [], "state": s}
    pred = {s: None for s in starts}
    dq = deque(starts)
    while dq:
        s = dq.popleft()
        for a in m.alabels:
            t = m.T[a][s]
            if t in pred:
                continue
            pred[t] = (s, a)
            if not ok(t):
                word = []
                cur = t
                while pred[cur] is not None:
                    prev, b = pred[cur]
                    word.append(b)
                    cur = prev
                word.reverse()
                return {"word": word, "state": t, "from": cur}
            dq.append(t)
    return None


def check_abstraction_map(src, tgt, h):
    """h must commute with every action and preserve every query; least failing state first."""
    for s in src.states:
        for a in src.alabels:
            left = h(src.T[a][s])
            right = tgt.T[a][h(s)]
            if left != right:
                return {"state": s, "action": a, "map-then-act": right, "act-then-map": left}
        for o in src.olabels:
            if src.O[o][s] != tgt.O[o][h(s)]:
                return {"state": s, "query": o, "left": src.O[o][s], "right": tgt.O[o][h(s)]}
    return None


def check_implementation(audit, ideal, actual, din, dout, L, eta, pair_ok=None):
    """Affine contract d_out(actual(xh), ideal(x)) <= L d_in(xh, x) + eta over ordered audit pairs.

    Returns (worst, witness): worst is the least eta that makes the grade hold for this L, and the
    witness is the least failing ordered pair for the given eta (None if it holds)."""
    worst = None
    wit = None
    act = {x: actual(x) for x in audit}
    ide = {x: ideal(x) for x in audit}
    for xh in audit:
        for x in audit:
            if pair_ok is not None and not pair_ok(xh, x):
                continue
            out = dout(act[xh], ide[x])
            need = out - L * din(xh, x)
            if worst is None or need > worst:
                worst = need
            if wit is None and need > eta:
                wit = {"pair": (xh, x), "out": out, "in": din(xh, x)}
    return max(worst, F(0)), wit
