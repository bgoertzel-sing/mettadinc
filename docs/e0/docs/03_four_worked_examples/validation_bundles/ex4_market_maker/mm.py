"""Example 4 model: a market maker's quoting problem across regime shifts.

Inventory q in -2..2 (lots).  Quotes: tight (one tick each side), wide (two ticks each side),
lean (one tick on the side that reduces the position, two on the side that grows it; at q = 0
lean is tight).  At q = +2 no bid is shown, at q = -2 no ask.  Each step a buyer lifts the ask
and a seller hits the bid independently, with probabilities that depend on the regime and the
offset.  A fill earns its offset minus the adverse-selection cost theta of the regime; holding
q' after the step costs kappa |q'|.  Discount 9/10.  Everything is an exact rational.
"""
from fractions import Fraction as F
from itertools import product

Q = [-2, -1, 0, 1, 2]
ACTIONS = ["tight", "wide", "lean"]
GAMMA = F(9, 10)
KAPPA = F(1, 4)


class Regime:
    def __init__(self, name, ask, bid, theta=F(0), kappa=KAPPA):
        self.name, self.ask, self.bid, self.theta, self.kappa = name, ask, bid, theta, kappa

    def __repr__(self):
        return f"Regime({self.name})"


def offsets(q, a):
    """(ask offset, bid offset); 0 means the side is not shown."""
    if a == "tight" or (a == "lean" and q == 0):
        oa, ob = 1, 1
    elif a == "wide":
        oa, ob = 2, 2
    else:                                   # lean
        oa, ob = (1, 2) if q > 0 else (2, 1)
    if q == 2:
        ob = 0
    if q == -2:
        oa = 0
    return oa, ob


def outcomes(reg, q, a):
    """[(probability, ask_filled, bid_filled)] with positive probability, in (A, B) order."""
    oa, ob = offsets(q, a)
    pa = reg.ask[oa] if oa else F(0)
    pb = reg.bid[ob] if ob else F(0)
    out = []
    for A, B in product((0, 1), repeat=2):
        p = (pa if A else 1 - pa) * (pb if B else 1 - pb)
        if p:
            out.append((p, A, B))
    return out


def pnl(reg, q, a, A, B):
    oa, ob = offsets(q, a)
    q2 = q - A + B
    return A * (oa - reg.theta) + B * (ob - reg.theta) - reg.kappa * abs(q2)


def kernel(reg, q, a):
    row = {}
    for p, A, B in outcomes(reg, q, a):
        q2 = q - A + B
        row[q2] = row.get(q2, F(0)) + p
    return row


def reward_law(reg, q, a):
    law = {}
    for p, A, B in outcomes(reg, q, a):
        v = pnl(reg, q, a, A, B)
        law[v] = law.get(v, F(0)) + p
    return law


def reward(reg, q, a):
    return sum(p * v for v, p in reward_law(reg, q, a).items())


H, E = F(1, 2), F(1, 8)
CALM = Regime("calm", {1: H, 2: E}, {1: H, 2: E})
TOXIC = Regime("toxic", {1: H, 2: E}, {1: H, 2: E}, theta=F(1, 2))
BUYERS = Regime("buyers", {1: F(3, 4), 2: F(3, 16)}, {1: F(1, 4), 2: F(1, 16)})
SELLERS = Regime("sellers", {1: F(1, 4), 2: F(1, 16)}, {1: F(3, 4), 2: F(3, 16)})
NOISE = Regime("noise", {1: H, 2: E}, {1: H, 2: E}, theta=F(0))
INFORMED = Regime("informed", {1: H, 2: E}, {1: H, 2: E}, theta=F(1))
REGIMES = [CALM, TOXIC, BUYERS, SELLERS]


# ---------------------------------------------------------------- generic decision processes
class Process:
    """A finite discounted decision process with exact rational data.
    kernel(x, a) -> {x': p}; reward(x, a) -> expected reward."""

    def __init__(self, name, states, actions, kernel, reward, gamma=GAMMA):
        self.name, self.states, self.actions = name, list(states), list(actions)
        self._k, self._r, self.gamma = kernel, reward, gamma
        self._kc, self._rc = {}, {}

    def kernel(self, x, a):
        if (x, a) not in self._kc:
            self._kc[(x, a)] = self._k(x, a)
        return self._kc[(x, a)]

    def reward(self, x, a):
        if (x, a) not in self._rc:
            self._rc[(x, a)] = self._r(x, a)
        return self._rc[(x, a)]


def regime_process(reg):
    return Process(reg.name, Q, ACTIONS, lambda q, a: kernel(reg, q, a), lambda q, a: reward(reg, q, a))


def solve(A, b):
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = next(r for r in range(c, n) if M[r][c] != 0)
        M[c], M[p] = M[p], M[c]
        inv = 1 / M[c][c]
        M[c] = [v * inv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c]
                M[r] = [vr - f * vc for vr, vc in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def evaluate(P, pol):
    """Exact value of a stationary deterministic policy: V = r_pi + gamma P_pi V."""
    S = P.states
    idx = {x: i for i, x in enumerate(S)}
    A = [[F(int(i == j)) for j in range(len(S))] for i in range(len(S))]
    b = [F(0)] * len(S)
    for x in S:
        a = pol[x]
        b[idx[x]] = P.reward(x, a)
        for y, p in P.kernel(x, a).items():
            A[idx[x]][idx[y]] -= P.gamma * p
    v = solve(A, b)
    return {x: v[idx[x]] for x in S}


def qval(P, V, x, a):
    return P.reward(x, a) + P.gamma * sum(p * V[y] for y, p in P.kernel(x, a).items())


def optimize(P, start=None):
    """Exact policy iteration.  Improvement keeps the current action on ties, otherwise takes the
    first maximizing action in declaration order; starts from the first action everywhere."""
    pol = dict(start) if start else {x: P.actions[0] for x in P.states}
    rounds = 0
    while True:
        V = evaluate(P, pol)
        rounds += 1
        new = {}
        for x in P.states:
            qs = {a: qval(P, V, x, a) for a in P.actions}
            best = max(qs.values())
            new[x] = pol[x] if qs[pol[x]] == best else next(a for a in P.actions if qs[a] == best)
        if new == pol:
            return pol, V, rounds
        pol = new


def check_optimal(P, pol):
    """Bellman optimality check of a declared policy.  Witness: least state (declaration order),
    then the first action in declaration order whose Q-value exceeds the policy's."""
    V = evaluate(P, pol)
    for x in P.states:
        qp = qval(P, V, x, pol[x])
        for a in P.actions:
            qa = qval(P, V, x, a)
            if qa > qp:
                return ("Refuted", (x, pol[x], qp, a, qa), V)
    return ("Checked", None, V)


def greedy_table(P, V):
    """Q-values of every state and action under V (the improvement step of the certificate)."""
    return {(x, a): qval(P, V, x, a) for x in P.states for a in P.actions}


# ---------------------------------------------------------------- representations (machine view)
# The machine view of a decision process observes the expected reward of every action
# (one query per action, value tolerance 1 - min(1, |r - r'|)).

def pairs(states):
    return [(x, y) for i, x in enumerate(states) for y in states[i + 1:]]


def current_witness(P, code):
    """Least same-code pair and first query (action) whose expected rewards differ."""
    for x, y in pairs(P.states):
        if code(x) == code(y):
            for a in P.actions:
                if P.reward(x, a) != P.reward(y, a):
                    return (x, y, a, P.reward(x, a), P.reward(y, a))
    return None


def push(row, code):
    out = {}
    for y, p in row.items():
        out[code(y)] = out.get(code(y), F(0)) + p
    return out


def update_witness(P, code, codes):
    """Least same-code pair, first action, least class whose pushed masses differ."""
    for x, y in pairs(P.states):
        if code(x) == code(y):
            for a in P.actions:
                px, py = push(P.kernel(x, a), code), push(P.kernel(y, a), code)
                for c in codes:
                    if px.get(c, F(0)) != py.get(c, F(0)):
                        return (x, y, a, c, px.get(c, F(0)), py.get(c, F(0)))
    return None


def tv_lump_defect(P, code):
    best = (F(0), None)
    for x, y in pairs(P.states):
        if code(x) == code(y):
            for a in P.actions:
                px, py = push(P.kernel(x, a), code), push(P.kernel(y, a), code)
                tv = sum(abs(px.get(c, F(0)) - py.get(c, F(0))) for c in set(px) | set(py)) / 2
                if tv > best[0]:
                    best = (tv, (x, y, a))
    return best


def quotient(P, code, codes):
    """Quotient process when the representation is exact (rows and rewards per class)."""
    assert current_witness(P, code) is None and update_witness(P, code, codes) is None
    rep = {}
    for x in P.states:
        rep.setdefault(code(x), x)
    return {c: {a: (P.reward(rep[c], a), push(P.kernel(rep[c], a), code)) for a in P.actions} for c in codes}


def code_policies(P, code, codes):
    """Every deterministic policy that sees only the code, with its exact value."""
    out = []
    for choice in product(P.actions, repeat=len(codes)):
        cp = dict(zip(codes, choice))
        pol = {x: cp[code(x)] for x in P.states}
        out.append((cp, evaluate(P, pol)))
    return out


def best_through(P, code, codes, start_law):
    """Best code policy for the expected value under a start law; ties by enumeration order."""
    best = None
    for cp, V in code_policies(P, code, codes):
        v = sum(p * V[x] for x, p in start_law.items())
        if best is None or v > best[1]:
            best = (cp, v, V)
    return best


def check_homomorphism(P1, P2, h):
    """h maps P1's states to P2's: rewards preserved and pushed rows equal (same action labels)."""
    for x in P1.states:
        for a in P1.actions:
            if P1.reward(x, a) != P2.reward(h(x), a):
                return ("Refuted", ("reward", x, a, P1.reward(x, a), P2.reward(h(x), a)))
            px = push(P1.kernel(x, a), h)
            py = P2.kernel(h(x), a)
            for z in P2.states:
                if px.get(z, F(0)) != py.get(z, F(0)):
                    return ("Refuted", ("row", x, a, z, px.get(z, F(0)), py.get(z, F(0))))
    surj = set(map(h, P1.states)) == set(P2.states)
    return ("Checked", "Quotient" if surj else "Homomorphism")


# ---------------------------------------------------------------- hidden informed flow
FLOW = ["noise", "informed"]
FLOW_REG = {"noise": NOISE, "informed": INFORMED}
HALF = {"noise": F(1, 2), "informed": F(1, 2)}
SPLIT_STATES = [(q, f) for q in Q for f in FLOW]          # Product Inv Flow, declared order


def split_process(prior=HALF):
    """States (q, flow); the flow is redrawn from the prior every step (a fresh factor)."""
    def k(x, a):
        q, f = x
        row = {}
        for q2, p in kernel(FLOW_REG[f], q, a).items():
            for f2 in FLOW:
                if prior[f2]:
                    row[(q2, f2)] = row.get((q2, f2), F(0)) + p * prior[f2]
        return row
    return Process("split", SPLIT_STATES, ACTIONS, k, lambda x, a: reward(FLOW_REG[x[1]], x[0], a))


def is_fresh(P, hidden, prior):
    """The hidden component of the successor is distributed as prior, independently of the
    visible component, for every state and action."""
    for x in P.states:
        for a in P.actions:
            row = P.kernel(x, a)
            vis = {}
            for (q2, f2), p in row.items():
                vis[q2] = vis.get(q2, F(0)) + p
            for (q2, f2), p in row.items():
                if p != vis[q2] * prior[f2]:
                    return False
    return True


def average_process(P, prior):
    """Average a process with a fresh hidden factor over that factor (exact for coarse policies)."""
    def k(q, a):
        row = {}
        for f, w in prior.items():
            for (q2, f2), p in P.kernel((q, f), a).items():
                row[q2] = row.get(q2, F(0)) + w * p
        return row
    return Process("average", Q, ACTIONS, k, lambda q, a: sum(w * P.reward((q, f), a) for f, w in prior.items()))


def same_process(P1, P2):
    for x in P1.states:
        for a in P1.actions:
            if P1.reward(x, a) != P2.reward(x, a) or P1.kernel(x, a) != P2.kernel(x, a):
                return ("Refuted", (x, a))
    return ("Checked", None)


def start_value(V, law):
    return sum(p * V[x] for x, p in law.items())


SPLIT_START = {(0, "noise"): F(1, 2), (0, "informed"): F(1, 2)}

READINGS = ["says-noise", "says-informed"]


def sensor_channel(err):
    return {"noise": {"says-noise": 1 - err, "says-informed": err},
            "informed": {"says-noise": err, "says-informed": 1 - err}}


def sensor_policy_value(P, prior, channel, cost, pol):
    """True value of a policy pol[(q, reading)] in the split process (hidden flow, noisy
    reading drawn each step before acting), net of the per-step sensor cost; exact linear solve
    on the hidden states (q, flow)."""
    S = P.states
    idx = {x: i for i, x in enumerate(S)}
    n = len(S)
    A = [[F(int(i == j)) for j in range(n)] for i in range(n)]
    b = [F(0)] * n
    for x in S:
        q, f = x
        b[idx[x]] -= cost
        for r, pr in channel[f].items():
            if not pr:
                continue
            a = pol[(q, r)]
            b[idx[x]] += pr * P.reward(x, a)
            for y, p in P.kernel(x, a).items():
                A[idx[x]][idx[y]] -= P.gamma * pr * p
    v = solve(A, b)
    return {x: v[idx[x]] for x in S}


def sensor_optimize(P, prior, channel, cost, substitute=False):
    """Best policy on (q, reading) for a fresh hidden factor, by exact policy iteration on the
    reduced process over q.  With substitute=True the evaluation wrongly treats the reading as
    the hidden state (the trap of the regime laboratory)."""
    preading = {r: sum(prior[f] * channel[f][r] for f in FLOW) for r in READINGS}
    post = {r: {f: (prior[f] * channel[f][r] / preading[r]) if preading[r] else F(0) for f in FLOW}
            for r in READINGS}
    if substitute:
        post = {r: {f: F(int(f == {"says-noise": "noise", "says-informed": "informed"}[r])) for f in FLOW}
                for r in READINGS}
    # reduced process on q: the reading is part of the decision context
    def rbar(q, r, a):
        return sum(post[r][f] * reward(FLOW_REG[f], q, a) for f in FLOW)

    def kbar(q, a):                       # fills do not depend on the flow
        return kernel(NOISE, q, a)
    pol = {(q, r): ACTIONS[0] for q in Q for r in READINGS}
    idx = {q: i for i, q in enumerate(Q)}
    while True:
        A = [[F(int(i == j)) for j in range(len(Q))] for i in range(len(Q))]
        b = [F(0)] * len(Q)
        for q in Q:
            b[idx[q]] -= cost
            for r in READINGS:
                a = pol[(q, r)]
                b[idx[q]] += preading[r] * rbar(q, r, a)
                for q2, p in kbar(q, a).items():
                    A[idx[q]][idx[q2]] -= P.gamma * preading[r] * p
        v = solve(A, b)
        W = {q: v[idx[q]] for q in Q}
        new = {}
        for q in Q:
            for r in READINGS:
                qs = {a: rbar(q, r, a) + P.gamma * sum(p * W[q2] for q2, p in kbar(q, a).items()) for a in ACTIONS}
                best = max(qs.values())
                cur = pol[(q, r)]
                new[(q, r)] = cur if qs[cur] == best else next(a for a in ACTIONS if qs[a] == best)
        if new == pol:
            return pol, W
        pol = new
