"""Example 2: an administrative role-based access-control policy on 40-bit words.

Users alice, bob, carol, dave (u = 0..3); roles staff, clerk, approver, auditor, admin (r = 0..4).
Bit 10u + r is "u is assigned r"; bit 10u + 5 + r is "u has r active".  Bit 0 is the least
significant bit of the word's numeric value.  Actions are declared kind-major (assign, revoke,
activate, deactivate), then user, then role; this is the order of canonical witnesses.
"""
USERS = ["alice", "bob", "carol", "dave"]
ROLES = ["staff", "clerk", "approver", "auditor", "admin"]
KINDS = ["assign", "revoke", "activate", "deactivate"]
NU, NR = 4, 5
W = 10 * NU


def A(u, r):
    return 10 * u + r


def S(u, r):
    return 10 * u + 5 + r


def bit(x, i):
    return (x >> i) & 1


def other_admin(x, u, nu=NU):
    return any(bit(x, S(v, 4)) for v in range(nu) if v != u)


PRE = {  # can-assign preconditions on the target user (fixed policy)
    0: lambda x, u: True,
    1: lambda x, u: bit(x, A(u, 0)) == 1,
    2: lambda x, u: bit(x, A(u, 1)) == 1 and bit(x, A(u, 3)) == 0,
    3: lambda x, u: bit(x, A(u, 0)) == 1 and bit(x, A(u, 2)) == 0,
    4: lambda x, u: bit(x, A(u, 0)) == 1,
}
PRE_WRITTEN = dict(PRE)
PRE_WRITTEN[2] = lambda x, u: bit(x, A(u, 1)) == 1 and bit(x, S(u, 3)) == 0   # checks the session
CLOSE = {0: [0, 1, 2, 3, 4], 1: [1, 2], 2: [2], 3: [3], 4: [4]}               # revocation cascades
CLOSE_WRITTEN = dict(CLOSE)
CLOSE_WRITTEN[1] = [1]                                                        # forgets approver
DSD = {2: lambda x, u: bit(x, S(u, 3)) == 0, 3: lambda x, u: bit(x, S(u, 2)) == 0}


class Policy:
    def __init__(self, written=False, nu=NU):
        self.pre = PRE_WRITTEN if written else PRE
        self.close = CLOSE_WRITTEN if written else CLOSE
        self.nu = nu
        self.actions = [(k, u, r) for k in KINDS for u in range(nu) for r in range(NR)]

    def step(self, x, a):
        k, u, r = a
        if k == "assign":
            return x | (1 << A(u, r)) if other_admin(x, u, self.nu) and self.pre[r](x, u) else x
        if k == "revoke":
            if not other_admin(x, u, self.nu):
                return x
            for q in self.close[r]:
                x &= ~((1 << A(u, q)) | (1 << S(u, q)))
            return x
        if k == "activate":
            ok = bit(x, A(u, r)) == 1 and DSD.get(r, lambda x, u: True)(x, u)
            return x | (1 << S(u, r)) if ok else x
        return x & ~(1 << S(u, r))


def label(a):
    k, u, r = a
    return f"({k} {USERS[u]} {ROLES[r]})"


GRANTS = {"read": [0, 1, 2, 3], "write": [1, 2], "approve": [2], "audit": [3], "configure": [4]}
PERMS = list(GRANTS)


def can(x, p, u):
    return any(bit(x, S(u, r)) for r in GRANTS[p])


def sod(x, nu=NU):
    return any(bit(x, A(u, 2)) and bit(x, A(u, 3)) for u in range(nu))


def clerkless(x, nu=NU):
    return any(bit(x, S(u, 2)) and not bit(x, A(u, 1)) for u in range(nu))


def consistent_user(x, u):
    a = [bit(x, A(u, r)) for r in range(NR)]
    s = [bit(x, S(u, r)) for r in range(NR)]
    if any(s[r] and not a[r] for r in range(NR)):
        return False
    if (a[1] and not a[0]) or (a[2] and not a[1]) or (a[3] and not a[0]) or (a[4] and not a[0]):
        return False
    return not (a[2] and a[3])


def consistent(x, nu=NU):
    return all(consistent_user(x, u) for u in range(nu))


INIT = sum(1 << i for i in (A(0, 0), A(0, 4), S(0, 4), A(1, 0), A(1, 1), S(1, 1), A(2, 0), S(2, 0)))


def describe(x, nu=NU):
    out = []
    for u in range(nu):
        a = [ROLES[r] for r in range(NR) if bit(x, A(u, r))]
        s = [ROLES[r] for r in range(NR) if bit(x, S(u, r))]
        if a or s:
            out.append(f"{USERS[u]}: assigned {{{','.join(a)}}} active {{{','.join(s)}}}")
    return "; ".join(out) if out else "empty"
