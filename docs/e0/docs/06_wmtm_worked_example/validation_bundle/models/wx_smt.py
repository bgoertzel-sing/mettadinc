"""Z3 encodings, written by hand, of every symbolic request of the worked example: the deployed
store's item machine with Part II's event and joint statistics and window view, the two-day nag
index, and the release's record, engine index, nag indexes and rebuild, with the minimality of
the engine index.  Each obligation is "unsat" when it holds for every real state, or "sat" with a
model when it fails (for the refuted representations, "sat" means a witness exists).  These
encodings are independent of the module text; the reference evaluator builds its own from the
module and decides them with cvc5.
"""
import z3

R = z3.RealSort()


def check(*cs):
    s = z3.Solver()
    s.add(*cs)
    r = s.check()
    return "unsat" if r == z3.unsat else ("sat" if r == z3.sat else "unknown")


def model(*cs):
    s = z3.Solver()
    s.add(*cs)
    assert s.check() == z3.sat
    return s.model()


def tup_ne(u, w):
    return z3.Or(*[a != b for a, b in zip(u, w)])


def mx(a, b):
    return z3.If(a >= b, a, b)


# ------------------------------------------------------------------ items
def item3(tag):
    a, e = z3.Reals(f"a{tag} e{tag}")
    c = z3.Bool(f"c{tag}")
    return (a, c, e), z3.And(a >= 0, e >= 0, e <= a)


def domain3(y):
    a, c, e = y
    return z3.And(a >= 0, e >= 0, e <= a)


def domain4(y):
    a, c, e, r = y
    return z3.And(a >= 0, e >= 0, e <= a, r >= 0)


def item4(tag):
    a, e, r = z3.Reals(f"a{tag} e{tag} r{tag}")
    c = z3.Bool(f"c{tag}")
    return (a, c, e, r), z3.And(a >= 0, e >= 0, e <= a, r >= 0)


def wait3(x, d):
    a, c, e = x
    return (a + d, c, e + d)


def reply3(x):
    a, c, e = x
    return (a, True, z3.If(c, e, 0))


def wait4(x, d):
    a, c, e, r = x
    return (a + d, c, e + d, mx(0, r - d))


def reply4(x):
    a, c, e, r = x
    return (a, True, z3.If(c, e, 0), r)


def snooze4(x, s):
    a, c, e, r = x
    return (a, c, e, mx(r, s))


def suggest4(x):
    a, c, e, r = x
    return z3.And(z3.Not(c), a <= 7, r <= 0)


def open4(x):
    return z3.Not(x[1])


# ------------------------------------------------------------------ saturation indexes
def sat(k, a, c):
    return (z3.Not(c), z3.And(z3.Not(c), a > k), z3.If(z3.And(z3.Not(c), a <= k), a, 0))


def sat_wait(k, code, d):
    o, t, v = code
    t2 = z3.And(o, z3.Or(t, v + d > k))
    return (o, t2, z3.If(z3.And(o, z3.Not(z3.Or(t, v + d > k))), v + d, 0))


def sat_close(code):
    return (z3.BoolVal(False), z3.BoolVal(False), z3.RealVal(0))


def sat_nag(code):
    o, t, v = code
    return z3.And(o, z3.Not(t))


def store_statistics():
    """The deployed store: closure of Part II's item machine, the event and joint statistics, and
    the two refutations of the window view (a witness exists now, and one after a wait)."""
    x, dom = item3("x")
    d = z3.Real("d")
    a, c, e = x
    out = {}
    out["closed wait"] = check(dom, d >= 0, z3.Not(domain3(wait3(x, d))))
    out["closed reply"] = check(dom, z3.Not(domain3(reply3(x))))
    ev = lambda y: (y[0], y[1])
    out["event step wait"] = check(dom, d >= 0, tup_ne(ev(wait3(x, d)), (a + d, c)))
    out["event step reply"] = check(dom, tup_ne(ev(reply3(x)), (a, z3.BoolVal(True))))
    out["event read suggest"] = check(dom, z3.And(z3.Not(ev(x)[1]), ev(x)[0] <= 7) != z3.And(z3.Not(c), a <= 7))
    out["event read open"] = check(dom, z3.Not(ev(x)[1]) != z3.Not(c))

    def joint3(y):
        a, c, e = y
        return (c, z3.And(z3.Not(c), a > 7), z3.If(z3.And(z3.Not(c), a <= 7), a, 0))

    def j3_wait(v, d):
        c, t, w = v
        dead = z3.Or(t, w + d > 7)
        return (c, z3.And(z3.Not(c), dead), z3.If(z3.And(z3.Not(c), z3.Not(dead)), w + d, 0))

    j3_reply = (z3.BoolVal(True), z3.BoolVal(False), z3.RealVal(0))
    j = joint3(x)
    out["joint step wait"] = check(dom, d >= 0, tup_ne(joint3(wait3(x, d)), j3_wait(j, d)))
    out["joint step reply"] = check(dom, tup_ne(joint3(reply3(x)), j3_reply))
    out["joint read suggest"] = check(dom, z3.And(z3.Not(j[0]), z3.Not(j[1])) != z3.And(z3.Not(c), a <= 7))
    out["joint read open"] = check(dom, z3.Not(j[0]) != z3.Not(c))
    # the window view (a, closed and the reply at most two days old): refuted now and on updates
    y, domy = item3("y")
    view = lambda z: (z[0], z3.And(z[1], z[2] <= 2))
    sug = lambda z: z3.And(z3.Not(z[1]), z[0] <= 7)
    out["window now (witness exists)"] = check(dom, domy, z3.Not(tup_ne(view(x), view(y))), sug(x) != sug(y))
    out["window updates (witness exists)"] = check(dom, domy, d >= 0, z3.Not(tup_ne(view(x), view(y))),
                                                   tup_ne(view(wait3(x, d)), view(wait3(y, d))))
    return out


def nag_index_v1():
    """The deployed store's two-day nag index on Part II's item (a, c, e)."""
    x, dom = item3("x")
    d = z3.Real("d")
    a, c, e = x
    enc = lambda y: sat(2, y[0], y[1])
    out = {}
    out["step wait"] = check(dom, d >= 0, tup_ne(enc(wait3(x, d)), sat_wait(2, enc(x), d)))
    out["step reply"] = check(dom, tup_ne(enc(reply3(x)), sat_close(enc(x))))
    out["read nag"] = check(dom, sat_nag(enc(x)) != z3.And(z3.Not(c), a <= 2))
    return out


def release_indexes():
    x, dom = item4("x")
    d, s = z3.Reals("d s")
    a, c, e, r = x
    out = {}
    # closure of the release's item machine under its three action families
    out["closed wait"] = check(dom, d >= 0, z3.Not(domain4(wait4(x, d))))
    out["closed reply"] = check(dom, z3.Not(domain4(reply4(x))))
    out["closed snooze"] = check(dom, s >= 0, z3.Not(domain4(snooze4(x, s))))
    # the carried-over engine index as a representation of the new machine: a witness exists
    y0, domy0 = item4("w")
    carried = lambda v: (v[1], z3.And(z3.Not(v[1]), v[0] > 7), z3.If(z3.And(z3.Not(v[1]), v[0] <= 7), v[0], 0))
    out["carried index now (witness exists)"] = check(dom, domy0, z3.Not(tup_ne(carried(x), carried(y0))),
                                                      suggest4(x) != suggest4(y0))
    # the durable record (a, c, r)
    rec = lambda y: (y[0], y[1], y[3])
    rec_wait = lambda v, d: (v[0] + d, v[1], mx(0, v[2] - d))
    rec_reply = lambda v: (v[0], z3.BoolVal(True), v[2])
    rec_snooze = lambda v, s: (v[0], v[1], mx(v[2], s))
    rec_suggest = lambda v: z3.And(z3.Not(v[1]), v[0] <= 7, v[2] <= 0)
    out["record step wait"] = check(dom, d >= 0, tup_ne(rec(wait4(x, d)), rec_wait(rec(x), d)))
    out["record step reply"] = check(dom, tup_ne(rec(reply4(x)), rec_reply(rec(x))))
    out["record step snooze"] = check(dom, s >= 0, tup_ne(rec(snooze4(x, s)), rec_snooze(rec(x), s)))
    out["record read suggest"] = check(dom, rec_suggest(rec(x)) != suggest4(x))
    out["record read open"] = check(dom, z3.Not(rec(x)[1]) != open4(x))

    # the engine index: closed; dead (open, a + r > 7); live (a, r)
    def joint(y):
        a, c, e, r = y
        live = z3.And(z3.Not(c), a + r <= 7)
        return (c, z3.And(z3.Not(c), a + r > 7), z3.If(live, a, 0), z3.If(live, r, 0))

    def j_wait(v, d):
        c, t, w, u = v
        dead = z3.Or(t, w + d > 7)
        live = z3.And(z3.Not(c), z3.Not(dead))
        return (c, z3.And(z3.Not(c), dead), z3.If(live, w + d, 0), z3.If(live, mx(0, u - d), 0))

    def j_snooze(v, s):
        c, t, w, u = v
        dead = z3.Or(t, w + mx(u, s) > 7)
        live = z3.And(z3.Not(c), z3.Not(dead))
        return (c, z3.And(z3.Not(c), dead), z3.If(live, w, 0), z3.If(live, mx(u, s), 0))

    j_reply = lambda v: (z3.BoolVal(True), z3.BoolVal(False), z3.RealVal(0), z3.RealVal(0))
    j_suggest = lambda v: z3.And(z3.Not(v[0]), z3.Not(v[1]), v[3] <= 0)
    out["engine step wait"] = check(dom, d >= 0, tup_ne(joint(wait4(x, d)), j_wait(joint(x), d)))
    out["engine step reply"] = check(dom, tup_ne(joint(reply4(x)), j_reply(joint(x))))
    out["engine step snooze"] = check(dom, s >= 0, tup_ne(joint(snooze4(x, s)), j_snooze(joint(x), s)))
    out["engine read suggest"] = check(dom, j_suggest(joint(x)) != suggest4(x))
    out["engine read open"] = check(dom, z3.Not(joint(x)[0]) != open4(x))

    # minimality: distinct live codes are separated by a wait, and a live code is separated from
    # the dead class by waiting out its snooze
    y, domy = item4("y")
    lx = z3.And(z3.Not(x[1]), x[0] + x[3] <= 7)
    ly = z3.And(z3.Not(y[1]), y[0] + y[3] <= 7)
    w1 = z3.If(x[3] <= y[3], x[3], y[3])                    # wait out the shorter snooze
    w2 = 7 - z3.If(x[0] <= y[0], x[0], y[0])                 # take the younger item to the cap
    sep1 = suggest4(wait4(x, w1)) != suggest4(wait4(y, w1))
    sep2 = suggest4(wait4(x, w2)) != suggest4(wait4(y, w2))
    out["live codes separated (different snooze)"] = check(dom, domy, lx, ly, x[3] != y[3], z3.Not(sep1))
    out["live codes separated (same snooze, different age)"] = check(
        dom, domy, lx, ly, x[3] == y[3], x[0] != y[0], z3.Not(sep2))
    dead_y = z3.And(z3.Not(y[1]), y[0] + y[3] > 7)
    out["live separated from dead"] = check(
        dom, domy, lx, dead_y, z3.Not(suggest4(wait4(x, x[3])) != suggest4(wait4(y, x[3]))))
    # a dead item stays out of reach under every wait and snooze, so the dead class is one class
    out["dead stays out of reach under wait"] = check(
        domy, dead_y, d >= 0, z3.Not(z3.And(z3.Not(suggest4(wait4(y, d))),
                                            wait4(y, d)[0] + wait4(y, d)[3] > 7)))
    out["dead stays out of reach under snooze"] = check(
        domy, dead_y, s >= 0, z3.Not(z3.And(z3.Not(suggest4(snooze4(y, s))),
                                            snooze4(y, s)[0] + snooze4(y, s)[3] > 7)))

    # the nag indexes on the release item: the snooze leaves them unchanged
    for k, name in ((2, "two"), (3, "three")):
        enc = lambda y, k=k: sat(k, y[0], y[1])
        out[f"nag {name} step wait"] = check(dom, d >= 0, tup_ne(enc(wait4(x, d)), sat_wait(k, enc(x), d)))
        out[f"nag {name} step reply"] = check(dom, tup_ne(enc(reply4(x)), sat_close(enc(x))))
        out[f"nag {name} step snooze"] = check(dom, s >= 0, tup_ne(enc(snooze4(x, s)), enc(x)))
        out[f"nag {name} read"] = check(dom, sat_nag(enc(x)) != z3.And(z3.Not(c), a <= k))
    # the two-day index cannot serve the three-day goal: a witness, and the designed one
    y4, domy4 = item4("z")
    same2 = z3.Not(tup_ne(sat(2, x[0], x[1]), sat(2, y4[0], y4[1])))
    differ3 = z3.And(z3.Not(x[1]), x[0] <= 3) != z3.And(z3.Not(y4[1]), y4[0] <= 3)
    out["two-day index for the three-day goal"] = check(dom, domy4, same2, differ3)
    designed = [x[0] == z3.RealVal("5/2"), x[1] == False, y4[0] == z3.RealVal("7/2"), y4[1] == False]
    out["designed witness (5/2, 7/2)"] = check(dom, domy4, same2, differ3, *designed)
    # the rebuild: the new index is a function of the durable record
    rebuild = lambda v: sat(3, v[0], v[1])
    out["rebuild from the record"] = check(dom, tup_ne(rebuild(rec(x)), sat(3, a, c)))

    def rebuild_joint(v):
        a, c, r = v
        live = z3.And(z3.Not(c), a + r <= 7)
        return (c, z3.And(z3.Not(c), a + r > 7), z3.If(live, a, 0), z3.If(live, r, 0))
    out["engine index rebuilt from the record"] = check(dom, tup_ne(rebuild_joint(rec(x)), joint(x)))
    return out


def window_witness_values():
    """Part II's window view: the witnesses the evaluator reports replay by direct evaluation."""
    return None


if __name__ == "__main__":
    print(store_statistics())
    print(nag_index_v1())
    for k, v in release_indexes().items():
        print(f"{k:55s} {v}")
