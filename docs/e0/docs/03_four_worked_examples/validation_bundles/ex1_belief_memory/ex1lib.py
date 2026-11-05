"""Belief-memory compaction (Example 1): model and exact algorithms.

Everything is exact: distances are Fractions, tables of rationals are stored as integer ranks
into a sorted list of the distinct values, and the discounted distance is computed with
Fractions.  Declaration order is the order a MeTTaDinC module would declare: states enumerate
(Product Count Count) with p major; actions are pos, neg, decay; queries are strength,
confidence (graded interface) or status (decision interface).
"""
from fractions import Fraction as F
from collections import deque
import math
import numpy as np

C = 15
COUNTS = list(range(C + 1))
STATES = [(p, n) for p in COUNTS for n in COUNTS]
N = len(STATES)
IDX = {s: i for i, s in enumerate(STATES)}
ACTIONS = ["pos", "neg", "decay"]


def strength(p, n):
    return F(p, p + n) if p + n else F(1, 2)


def confidence(p, n):
    return F(p + n, p + n + 4)


def status(p, n):
    t = p + n
    if t >= 4 and p >= 2 * n:
        return "Believed"
    if t >= 4 and n >= 2 * p:
        return "Disbelieved"
    return "Uncertain"


def pos(p, n):
    return (min(p + 1, C), n)


def neg(p, n):
    return (p, min(n + 1, C))


DECAYS = {
    "floor-halve": lambda p, n: (p // 2, n // 2),
    "ceil-halve": lambda p, n: ((p + 1) // 2, (n + 1) // 2),
    "floor-halve-if-t>=8": lambda p, n: (p // 2, n // 2) if p + n >= 8 else (p, n),
    "gentle": lambda p, n: ((p + 1) // 2, (n + 1) // 2) if p + n >= 8 else (p, n),
    "minus-one": lambda p, n: (max(p - 1, 0), max(n - 1, 0)),
}


def successors(decay, states=STATES, idx=IDX, acts=None):
    fs = acts if acts is not None else [pos, neg, DECAYS[decay]]
    return [np.array([idx[f(*s)] for s in states], dtype=np.int64) for f in fs]


# ---------------------------------------------------------------- observation distances
SV = [strength(*s) for s in STATES]
CV = [confidence(*s) for s in STATES]
D0_FRAC = [[max(abs(SV[i] - SV[j]), abs(CV[i] - CV[j])) for j in range(N)] for i in range(N)]
VALS = sorted({v for row in D0_FRAC for v in row})
RANK = {v: k for k, v in enumerate(VALS)}
R0 = np.array([[RANK[v] for v in row] for row in D0_FRAC], dtype=np.int64)


def query_values(i):
    return (SV[i], CV[i])


# ---------------------------------------------------------------- distance tables (ranks)
def horizon_table(succ, h, R=R0):
    """Rank table of the horizon-h behavioral distance: max over words of length <= h."""
    D = R.copy()
    for _ in range(h):
        D2 = R.copy()
        for s in succ:
            np.maximum(D2, D[np.ix_(s, s)], out=D2)
        D = D2
    return D


def fixpoint_table(succ, R=R0):
    """Rank table of the undiscounted behavioral distance and the number of rounds."""
    D = R.copy()
    rounds = 0
    while True:
        D2 = R.copy()
        for s in succ:
            np.maximum(D2, D[np.ix_(s, s)], out=D2)
        rounds += 1
        if np.array_equal(D2, D):
            return D, rounds
        D = D2


def discounted_table(succ, gamma, D0=None):
    """Exact discounted behavioral distance (Fractions), deterministic dynamics:
    d(x,y) = max(d0(x,y), gamma * max_a d(T_a x, T_a y)); iterate from d0 until stable."""
    if D0 is None:
        D0 = np.array(D0_FRAC, dtype=object)
    D = D0.copy()
    rounds = 0
    while True:
        best = None
        for s in succ:
            sub = D[np.ix_(s, s)]
            best = sub if best is None else np.maximum(best, sub)
        D2 = np.maximum(D0, best * gamma)
        rounds += 1
        if (D2 == D).all():
            return D, rounds
        D = D2


def val(D, i, j):
    x = D[i, j]
    return VALS[x] if isinstance(x, (int, np.integer)) else x


# ---------------------------------------------------------------- partitions and encodings
def classes_of(code):
    groups = {}
    for i, c in enumerate(code):
        groups.setdefault(c, []).append(i)
    return list(groups.values())


def weakness(blocks, n=N):
    return F(sum(len(b) ** 2 for b in blocks), n * n)


def defect(blocks, D):
    best = 0
    for b in blocks:
        if len(b) > 1:
            sub = D[np.ix_(b, b)]
            m = sub.max()
            if m > best:
                best = m
    return best


def defect_val(blocks, D):
    m = defect(blocks, D)
    if D.dtype == object:
        return m if m != 0 else F(0)
    return VALS[int(m)]


def update_witness(code, succ, action_names=ACTIONS):
    """Canonical update witness for crisp codes: least same-code pair (declaration order),
    then the first action in declaration order whose successors get different codes."""
    for i in range(N):
        for j in range(i + 1, N):
            if code[i] != code[j]:
                continue
            for a, s in enumerate(succ):
                if code[s[i]] != code[s[j]]:
                    return (STATES[i], STATES[j], action_names[a], code[s[i]], code[s[j]])
    return None


# ---------------------------------------------------------------- canonical word witnesses
def violating_pairs(bound, R=R0, crisp_obs=None):
    """Boolean N x N array: the observation distance of the pair exceeds the bound."""
    if crisp_obs is not None:
        o = np.array([hash(v) for v in crisp_obs])
        return o[:, None] != o[None, :]
    lim = max((k for k, v in enumerate(VALS) if v <= bound), default=-1)
    return R > lim


def shortest_violation_lengths(succ, viol, horizon=None):
    """For every ordered pair, the length of the shortest word leading to a violating pair
    (reverse multi-source BFS on the pair graph); -1 when none exists within the horizon."""
    NN = N * N
    dist = np.full(NN, -1, dtype=np.int64)
    flat = viol.reshape(-1)
    q = deque(np.nonzero(flat)[0].tolist())
    dist[flat] = 0
    # reverse adjacency: pred[(s_i, s_j)] contains (i, j)
    preds = [[] for _ in range(NN)]
    for s in succ:
        tgt = (s[:, None] * N + s[None, :]).reshape(-1)
        for src, t in enumerate(tgt.tolist()):
            preds[t].append(src)
    while q:
        u = q.popleft()
        if horizon is not None and dist[u] >= horizon:
            continue
        for v in preds[u]:
            if dist[v] < 0:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist.reshape(N, N)


def least_word(succ, i, j, viol, length):
    """Least word (numeric order, actions in declaration order) of the given length from the
    pair (i, j) to a violating pair: BFS with actions explored in declaration order."""
    start = (i, j)
    prev = {start: None}
    frontier = [start]
    for depth in range(length + 1):
        for u in frontier:
            if depth == length and viol[u[0], u[1]]:
                w = []
                while prev[u] is not None:
                    u, a = prev[u]
                    w.append(a)
                return list(reversed(w))
        if depth == length:
            break
        nxt = []
        for u in frontier:
            for a, s in enumerate(succ):
                v = (int(s[u[0]]), int(s[u[1]]))
                if v not in prev:
                    prev[v] = (u, a)
                    nxt.append(v)
        frontier = nxt
    return None


def canonical_witness(code, succ, viol, horizon=None, dist=None):
    """Shortest word first, then the least same-code pair, then the least word."""
    if dist is None:
        dist = shortest_violation_lengths(succ, viol, horizon)
    best = None
    for i in range(N):
        for j in range(i + 1, N):
            if code[i] == code[j] and dist[i, j] >= 0:
                if horizon is not None and dist[i, j] > horizon:
                    continue
                if best is None or dist[i, j] < best[0]:
                    best = (int(dist[i, j]), i, j)
    if best is None:
        return None
    L, i, j = best
    w = least_word(succ, i, j, viol, L)
    return {"length": L, "pair": (STATES[i], STATES[j]), "word": [ACTIONS[a] for a in w]}


def run(state, word, decay):
    f = {"pos": pos, "neg": neg, "decay": DECAYS[decay]}
    out = [state]
    for a in word:
        state = f[a](*state)
        out.append(state)
    return out


# ---------------------------------------------------------------- crisp refinement
def refine_counts(seed, succ, max_rounds=None):
    """Partition refinement from a seed labelling; returns the list of class counts by round
    (round 0 is the seed) and the final labelling."""
    blk = list(seed)
    canon = {}
    blk = [canon.setdefault(b, len(canon)) for b in blk]
    hist = [len(canon)]
    r = 0
    while max_rounds is None or r < max_rounds:
        sig = [(blk[i],) + tuple(blk[int(s[i])] for s in succ) for i in range(N)]
        canon = {}
        nb = [canon.setdefault(x, len(canon)) for x in sig]
        r += 1
        if len(canon) == hist[-1]:
            break
        blk = nb
        hist.append(len(canon))
    return hist, blk


# ---------------------------------------------------------------- encodings
def rnd(x, g):
    return math.floor(x * g + F(1, 2))


def rounded_tv(g_s, g_c=None):
    g_c = g_s if g_c is None else g_c
    return lambda p, n: (rnd(strength(p, n), g_s), rnd(confidence(p, n), g_c))


def bucketing(intervals):
    lookup = {}
    for k, (a, b) in enumerate(intervals):
        for v in range(a, b + 1):
            lookup[v] = k
    return lambda p, n: (lookup[p], lookup[n])


B7 = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 5), (6, 9), (10, 15)]

ENCODINGS = {
    "RoundedTV20": rounded_tv(20),
    "RoundedTV10": rounded_tv(10),
    "Buckets7": bucketing(B7),
    "Capped7": lambda p, n: (min(p, 7), min(n, 7)),
    "StatusOnly": status,
}


def code_of(enc):
    return [enc(*s) for s in STATES]
