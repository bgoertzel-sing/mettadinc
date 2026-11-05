"""Example 4, part 4: did the news leak?  A labelled Markov chain with two quote actions.

leak:      an informed trader has learned the direction (each way with probability 1/2)
embargo:   the news is pending and nobody knows its direction yet
knows-up / knows-down: the informed trader picks off a tight quote (our ask is lifted, or our
           bid is hit) just before the move; a wide quote is left alone
pending:   the news is released without any informed trade
moved-up / moved-down: the move without a trade; picked-up / picked-down: the move after the
           informed trade.  The four outcome states are absorbing.  The desk observes only its
           report of the step: quiet, up, down, hit-up (our ask was lifted, then the mid rose),
           hit-down.
"""
from fractions import Fraction as F
from itertools import product

STATES = ["leak", "embargo", "knows-up", "knows-down", "pending", "moved-up", "moved-down", "picked-up",
          "picked-down"]
ACTS = ["tight", "wide"]
REPORTS = ["quiet", "up", "down", "hit-up", "hit-down"]
REPORT = {"leak": "quiet", "embargo": "quiet", "knows-up": "quiet", "knows-down": "quiet",
          "pending": "quiet", "moved-up": "up", "moved-down": "down", "picked-up": "hit-up",
          "picked-down": "hit-down"}
H = F(1, 2)


def kernel(x, a, acts=ACTS):
    if x == "leak":
        return {"knows-up": H, "knows-down": H}
    if x == "embargo":
        return {"pending": F(1)}
    if x == "knows-up":
        return {"picked-up": F(1)} if a == "tight" else {"moved-up": F(1)}
    if x == "knows-down":
        return {"picked-down": F(1)} if a == "tight" else {"moved-down": F(1)}
    if x == "pending":
        return {"moved-up": H, "moved-down": H}
    return {x: F(1)}


def bisimulation(states, acts, kern, report):
    """Coarsest probabilistic bisimulation by exact partition refinement."""
    block = {x: report[x] for x in states}
    while True:
        sig = {}
        for x in states:
            s = [block[x]]
            for a in acts:
                m = {}
                for y, p in kern(x, a).items():
                    m[block[y]] = m.get(block[y], F(0)) + p
                s.append(tuple(sorted((str(k), v) for k, v in m.items())))
            sig[x] = tuple(map(str, s))
        names = {}
        new = {x: names.setdefault(sig[x], len(names)) for x in states}
        if len(set(new.values())) == len(set(block.values())):
            classes = {}
            for x in states:
                classes.setdefault(new[x], []).append(x)
            return list(classes.values())
        block = new


def trace_space(states, acts, kern, report, reports):
    """Krylov basis of the test space x -> P_x(y0 a1 y1 ... ak yk), exact rationals.
    Returns (dimension, basis vectors with their test words)."""
    n = len(states)
    idx = {x: i for i, x in enumerate(states)}

    def op(a, y, v):            # (M_a Pi_y v)(x) = sum_z M_a(x, z) [o(z) = y] v(z)
        return tuple(sum(p * v[idx[z]] for z, p in kern(x, a).items() if report[z] == y) for x in states)

    def proj(y, v):
        return tuple(v[i] if report[x] == y else F(0) for i, x in enumerate(states))

    basis, words = [], []

    def add(v, w):
        # Gaussian elimination against the current basis (rows kept reduced)
        r = list(v)
        for b, piv in basis_red:
            if r[piv] != 0:
                f = r[piv] / b[piv]
                r = [ri - f * bi for ri, bi in zip(r, b)]
        if any(r):
            piv = next(i for i, c in enumerate(r) if c != 0)
            basis_red.append((r, piv))
            basis.append(v)
            words.append(w)
            return True
        return False

    basis_red = []
    # Krylov space of the operators applied to the all-ones vector, then the initial projectors
    one = tuple(F(1) for _ in states)
    frontier = [(one, ())]
    kry, kry_red, kry_words = [], [], []

    def add_k(v, w):
        r = list(v)
        for b, piv in kry_red:
            if r[piv] != 0:
                f = r[piv] / b[piv]
                r = [ri - f * bi for ri, bi in zip(r, b)]
        if any(r):
            piv = next(i for i, c in enumerate(r) if c != 0)
            kry_red.append((r, piv))
            kry.append(v)
            kry_words.append(w)
            return True
        return False

    add_k(one, ())
    while frontier:
        nxt = []
        for v, w in frontier:
            for a in acts:
                for y in reports:
                    u = op(a, y, v)
                    if add_k(u, ((a, y),) + w):
                        nxt.append((u, ((a, y),) + w))
        frontier = nxt
    for v, w in zip(kry, kry_words):
        for y0 in reports:
            add(proj(y0, v), (y0, w))
    return len(basis), basis, words


def trace_law(x, word, kern, report):
    """Law of (o(X0), ..., o(Xk)) under an action word."""
    dist = {((report[x],), x): F(1)}
    for a in word:
        nd = {}
        for (obs, z), p in dist.items():
            for z2, q in kern(z, a).items():
                key = (obs + (report[z2],), z2)
                nd[key] = nd.get(key, F(0)) + p * q
        dist = nd
    law = {}
    for (obs, z), p in dist.items():
        law[obs] = law.get(obs, F(0)) + p
    return law


def trace_witness(x, y, acts, kern, report, reports, maxlen=6):
    """Shortest word (actions in declaration order), then the least observation sequence in
    report order whose probabilities differ."""
    for k in range(maxlen + 1):
        for word in product(acts, repeat=k):
            lx, ly = trace_law(x, word, kern, report), trace_law(y, word, kern, report)
            if lx != ly:
                for obs in product(reports, repeat=k + 1):
                    if lx.get(obs, F(0)) != ly.get(obs, F(0)):
                        return word, obs, lx.get(obs, F(0)), ly.get(obs, F(0))
    return None


