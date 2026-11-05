"""Transfer hives and derived kernel hives for the three robots."""
from fractions import Fraction as F
from itertools import product
from robots import *


class Transfer:
    def __init__(self, name, src, tgt, f, iota=None):
        self.name, self.src, self.tgt, self.f = name, src, tgt, f
        self.phi = lambda y: CELL_MAP[f](*y)                       # target state -> source state
        self.iota = iota if iota is not None else dir_map(inverse(f))   # source command -> target command

    def defect(self, metric="TV"):
        worst, wit = F(0), None
        for y in self.tgt.states:
            for m in DIRS:
                a, b = self.src.resp(self.phi(y), m), self.tgt.resp(y, self.iota[m])
                d = (F(int(a != b)) if metric == "TV" else abs(a - b))
                if d > worst:
                    worst, wit = d, (y, m, a, b)
        return worst, wit

    def least_witness(self, bound=F(0), metric="TV"):
        for y in self.tgt.states:                                    # carrier order, then method order
            for m in DIRS:
                a, b = self.src.resp(self.phi(y), m), self.tgt.resp(y, self.iota[m])
                d = (F(int(a != b)) if metric == "TV" else abs(a - b))
                if d > bound:
                    return (y, m, self.iota[m], a, b)
        return None


def group_closure(gens):
    G = {"id"}
    frontier = set(gens) | {"id"}
    G |= frontier
    changed = True
    while changed:
        changed = False
        for a in list(G):
            for b in list(G):
                c = compose(a, b)
                if c not in G:
                    G.add(c); changed = True
    return sorted(G, key=ORDER.index)


def is_symmetry(robot, g):
    return all(robot.resp(CELL_MAP[g](*x), dir_map(g)[m]) == robot.resp(x, m) for x in robot.states for m in DIRS)


def perm_of(dm):
    return tuple(dm[d] for d in DIRS)


def conj_methods(t, g):
    """iota^-1 g iota as a permutation of the source robot's commands (g a target gauge element)."""
    inv = {v: k for k, v in t.iota.items()}
    gm = dir_map(g)
    return {m: inv[gm[t.iota[m]]] for m in DIRS}


def holonomy_pair(edges):
    """Composite transfer around the cycle, based at the source of edges[0]."""
    ab, bc, ca = edges
    phi = lambda x: ab.phi(bc.phi(ca.phi(x)))
    iota = {m: ca.iota[bc.iota[ab.iota[m]]] for m in DIRS}
    base = ab.src
    phim = {x: phi(x) for x in base.states}
    g_state = next((g for g in ORDER if all(CELL_MAP[g](*x) == phim[x] for x in base.states)), None)
    inv = {v: k for k, v in iota.items()}
    g_meth = next((g for g in ORDER if dir_map(g) == inv), None)
    return phim, iota, g_state, g_meth


def check_transfer_hive(edges, gauges):
    """Returns (status, detail): gauges are lists of generator element names per robot name."""
    robots = [edges[0].src, edges[1].src, edges[2].src]
    G = {r.name: group_closure(gauges.get(r.name, [])) for r in robots}
    for t in edges:
        d, w = t.defect()
        if d > 0:
            return "Refuted", ("edge", t.name, t.least_witness())
    for r in robots:
        for g in G[r.name]:
            if not is_symmetry(r, g):
                return "Refuted", ("gauge", r.name, g)
    for t in edges:
        GiM = {perm_of(dir_map(g)) for g in G[t.src.name]}
        conj = [perm_of(conj_methods(t, g)) for g in G[t.tgt.name]]
        if set(conj) != GiM:
            bad = next(g for g in G[t.tgt.name] if perm_of(conj_methods(t, g)) not in GiM) if any(c not in GiM for c in conj) else None
            return "Refuted", ("intertwining", t.name, bad, G[t.src.name], G[t.tgt.name])
    phim, iota, gs, gm = holonomy_pair(edges)
    if gs is None or gm is None or gs != gm or gs not in G[edges[0].src.name]:
        moved = next(x for x in edges[0].src.states if phim[x] != x)
        return "Refuted", ("holonomy", gs, gm, moved, phim[moved])
    return "Checked", ("holonomy", gs)


# ---------------------------------------------------------------- derived kernel hives
def kernel_hive(edges, gauges=None, saturate=False):
    robots = [edges[0].src, edges[1].src, edges[2].src]
    G = {r.name: group_closure((gauges or {}).get(r.name, [])) for r in robots}
    def alpha(r, x, xp, sat):
        gs = G[r.name] if sat else ["id"]
        return max(1 - max(F(int(r.resp(x, m) != r.resp(xp, dir_map(g)[m]))) for m in DIRS) for g in gs)
    nodes = [(r.name, x) for r in robots for x in r.states]
    rob = {r.name: r for r in robots}
    A = {}
    for r in robots:
        for x in r.states:
            for xp in r.states:
                A[(r.name, x, xp)] = alpha(r, x, xp, saturate)
    corr = {}
    for t in edges:
        i, j = t.src, t.tgt
        for x in i.states:
            for y in j.states:
                corr[(i.name, x, j.name, y)] = 1 - max(F(int(i.resp(x, m) != j.resp(y, t.iota[m]))) for m in DIRS)
    def raw(a, b):
        (i, x), (j, y) = a, b
        if i == j:
            return A[(i, x, y)]
        if (i, x, j, y) in corr:
            return corr[(i, x, j, y)]
        return corr[(j, y, i, x)]
    H = {}
    for a in nodes:
        for b in nodes:
            if a[0] == b[0] or not saturate:
                H[(a, b)] = raw(a, b)
            else:   # alpha_i o c_ij o alpha_j
                i, j = a[0], b[0]
                H[(a, b)] = max(min(A[(i, a[1], u)], raw((i, u), (j, v)), A[(j, v, b[1])])
                                for u in rob[i].states for v in rob[j].states)
    return nodes, H


def transitive(nodes, H):
    for a in nodes:
        for k in nodes:
            hak = H[(a, k)]
            if hak == 0:
                continue
            for b in nodes:
                if max(F(0), hak + H[(k, b)] - 1) > H[(a, b)]:
                    return False, (a, k, b)
    return True, None


def closure(nodes, H):
    C = dict(H)
    for k in nodes:
        for a in nodes:
            cak = C[(a, k)]
            if cak == 0:
                continue
            for b in nodes:
                v = cak + C[(k, b)] - 1
                if v > C[(a, b)]:
                    C[(a, b)] = v
    return C


def consensus_cost(nodes, H):
    C = closure(nodes, H)
    w = F(1, len(nodes))
    return sum(w * w * (C[(a, b)] - H[(a, b)]) for a in nodes for b in nodes), C
