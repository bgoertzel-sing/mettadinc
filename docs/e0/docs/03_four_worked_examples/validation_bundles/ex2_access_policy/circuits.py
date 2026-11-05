"""A small deterministic Tseitin encoder for the policy's maps and obligations."""
from rbac import *


class CNF:
    def __init__(self):
        self.n = 1                     # variable 1 is the constant True
        self.clauses = [[1]]
        self.cache = {}

    def fresh(self):
        self.n += 1
        return self.n

    T = 1
    F = -1

    def AND(self, lits):
        lits = [l for l in lits if l != self.T]
        if any(l == self.F for l in lits):
            return self.F
        if not lits:
            return self.T
        if len(lits) == 1:
            return lits[0]
        if any(-l in lits for l in lits):
            return self.F
        key = ("and", tuple(sorted(set(lits))))
        if key in self.cache:
            return self.cache[key]
        g = self.fresh()
        for l in lits:
            self.clauses.append([-g, l])
        self.clauses.append([g] + [-l for l in lits])
        self.cache[key] = g
        return g

    def OR(self, lits):
        return -self.AND([-l for l in lits])

    def NOT(self, l):
        return -l

    def ITE(self, c, t, e):
        if c == self.T:
            return t
        if c == self.F:
            return e
        if t == e:
            return t
        return self.OR([self.AND([c, t]), self.AND([-c, e])])

    def XOR(self, a, b):
        return self.OR([self.AND([a, -b]), self.AND([-a, b])])

    def inputs(self, w):
        return [self.fresh() for _ in range(w)]


def enc_other_admin(c, x, u, nu):
    return c.OR([x[S(v, 4)] for v in range(nu) if v != u])


def enc_pre(c, x, u, r, written):
    if r == 0:
        return c.T
    if r == 1:
        return x[A(u, 0)]
    if r == 2:
        return c.AND([x[A(u, 1)], -(x[S(u, 3)] if written else x[A(u, 3)])])
    if r == 3:
        return c.AND([x[A(u, 0)], -x[A(u, 2)]])
    return x[A(u, 0)]


def enc_step(c, x, a, written, nu):
    k, u, r = a
    y = list(x)
    close = CLOSE_WRITTEN if written else CLOSE
    if k == "assign":
        g = c.AND([enc_other_admin(c, x, u, nu), enc_pre(c, x, u, r, written)])
        y[A(u, r)] = c.OR([g, x[A(u, r)]])
    elif k == "revoke":
        g = enc_other_admin(c, x, u, nu)
        for q in close[r]:
            y[A(u, q)] = c.AND([-g, x[A(u, q)]])
            y[S(u, q)] = c.AND([-g, x[S(u, q)]])
    elif k == "activate":
        parts = [x[A(u, r)]]
        if r == 2:
            parts.append(-x[S(u, 3)])
        if r == 3:
            parts.append(-x[S(u, 2)])
        g = c.AND(parts)
        y[S(u, r)] = c.OR([g, x[S(u, r)]])
    else:
        y[S(u, r)] = c.F
    return y


def enc_consistent(c, x, nu):
    parts = []
    for u in range(nu):
        for r in range(NR):
            parts.append(c.OR([-x[S(u, r)], x[A(u, r)]]))
        parts.append(c.OR([-x[A(u, 1)], x[A(u, 0)]]))
        parts.append(c.OR([-x[A(u, 2)], x[A(u, 1)]]))
        parts.append(c.OR([-x[A(u, 3)], x[A(u, 0)]]))
        parts.append(c.OR([-x[A(u, 4)], x[A(u, 0)]]))
        parts.append(c.OR([-x[A(u, 2)], -x[A(u, 3)]]))
    return c.AND(parts)


def enc_no_sod(c, x, nu):
    return c.AND([c.OR([-x[A(u, 2)], -x[A(u, 3)]]) for u in range(nu)])


def enc_no_clerkless(c, x, nu):
    return c.AND([c.OR([-x[S(u, 2)], x[A(u, 1)]]) for u in range(nu)])


def enc_some_admin(c, x, nu):
    return c.OR([x[A(u, 4)] for u in range(nu)])
