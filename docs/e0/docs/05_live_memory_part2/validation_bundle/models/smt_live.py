"""Symbolic checks of the live statistics with the Z3 solver (linear real arithmetic, Booleans).

Each obligation is checked by asking the solver for a counterexample: "unsat" proves the
obligation for every real state in the declared domain and every action parameter; "sat" returns a
model, which is a concrete witness.  Witnesses quoted in the guide are designed values, verified
here by direct substitution.

A summary statistic is checked as a certificate (T, s, step, read):
  domain closed      every transition keeps a state of the domain in the domain
  read_q             q(x) = read_q(s(x))                        for every x in the domain
  step_a             s(T_a(x, p)) = step_a(s(x), p)             for every x and parameter p
"""
from fractions import Fraction as Q

import z3

R = z3.RealVal


def check(*constraints):
    s = z3.Solver()
    s.add(*constraints)
    return str(s.check())


def holds(expr):
    return z3.is_true(z3.simplify(expr))


def neq(u, w):
    if isinstance(u, tuple):
        return z3.Or(*[neq(p, q) for p, q in zip(u, w)])
    return u != w


def is_linear(expr):
    """True when no subterm of expr multiplies or divides two terms that both contain variables."""
    seen = set()

    def has_var(e):
        return any(z3.is_const(t) and t.decl().kind() == z3.Z3_OP_UNINTERPRETED for t in walk(e))

    def walk(e):
        stack = [e]
        while stack:
            t = stack.pop()
            yield t
            stack.extend(t.children())

    for t in walk(expr):
        if t.get_id() in seen:
            continue
        seen.add(t.get_id())
        if z3.is_mul(t) and sum(1 for c in t.children() if has_var(c)) > 1:
            return False
        if (z3.is_div(t) or t.decl().kind() == z3.Z3_OP_DIV) and has_var(t.children()[1]):
            return False
    return True


def certificate(dom, x, transitions, stat, steps, queries, reads):
    """transitions: name -> (params, param_domain, f(x, params) -> x').  Returns name -> 'unsat'."""
    out = {}
    for a, (ps, pdom, f) in transitions.items():
        out["closed_" + a] = check(dom(x), pdom, z3.Not(dom(f(x, ps))))
        out["step_" + a] = check(dom(x), pdom, neq(stat(f(x, ps)), steps[a](stat(x), ps)))
    for q in queries:
        out["read_" + q] = check(dom(x), neq(queries[q](x), reads[q](stat(x))))
    return out


# ====================================================================== Pattern 1: open items
CAP, WIN = R(7), R(2)


def p1():
    a, e, d = z3.Reals("a e d")
    closed = z3.Bool("closed")
    x = (a, closed, e)                                   # age, closed, time since the reply
    dom = lambda s: z3.And(s[0] >= 0, s[2] >= 0, s[2] <= s[0])
    wait = ((d,), d >= 0, lambda s, p: (s[0] + p[0], s[1], s[2] + p[0]))
    reply = ((), z3.BoolVal(True), lambda s, p: (s[0], z3.BoolVal(True), z3.If(s[1], s[2], R(0))))
    T = {"wait": wait, "reply": reply}
    queries = {"suggest": lambda s: z3.And(z3.Not(s[1]), s[0] <= CAP), "open": lambda s: z3.Not(s[1])}
    out = {}
    # the event statistic (age, closed)
    ev = certificate(dom, x, T, lambda s: (s[0], s[1]),
                     {"wait": lambda t, p: (t[0] + p[0], t[1]), "reply": lambda t, p: (t[0], z3.BoolVal(True))},
                     queries, {"suggest": lambda t: z3.And(z3.Not(t[1]), t[0] <= CAP), "open": lambda t: z3.Not(t[1])})
    out.update({"event_" + k: v for k, v in ev.items()})

    # the joint statistic (closed, past, v): closed items are all alike; an open item keeps its age
    # until it is past seven days
    def joint_stat(s):
        live = z3.And(z3.Not(s[1]), s[0] <= CAP)
        return (s[1], z3.And(z3.Not(s[1]), s[0] > CAP), z3.If(live, s[0], R(0)))

    def joint_wait(t, p):
        past = z3.And(z3.Not(t[0]), z3.Or(t[1], t[2] + p[0] > CAP))
        live = z3.And(z3.Not(t[0]), z3.Not(z3.Or(t[1], t[2] + p[0] > CAP)))
        return (t[0], past, z3.If(live, t[2] + p[0], R(0)))
    jo = certificate(dom, x, T, joint_stat,
                     {"wait": joint_wait, "reply": lambda t, p: (z3.BoolVal(True), z3.BoolVal(False), R(0))},
                     queries, {"suggest": lambda t: z3.And(z3.Not(t[0]), z3.Not(t[1])), "open": lambda t: z3.Not(t[0])})
    out.update({"joint_" + k: v for k, v in jo.items()})

    # the coarsest statistic for suggest alone: dead (closed or past seven days), or the live age
    def eng_stat(s):
        dead = z3.Or(s[1], s[0] > CAP)
        return (dead, z3.If(dead, R(0), s[0]))

    def eng_wait(t, p):
        dead = z3.Or(t[0], t[1] + p[0] > CAP)
        return (dead, z3.If(dead, R(0), t[1] + p[0]))
    en = certificate(dom, x, {"wait": wait, "reply": reply}, eng_stat,
                     {"wait": eng_wait, "reply": lambda t, p: (z3.BoolVal(True), R(0))},
                     {"suggest": queries["suggest"]}, {"suggest": lambda t: z3.Not(t[0])})
    out.update({"engine_" + k: v for k, v in en.items()})
    a2 = z3.Real("a2")
    gap = CAP - a2 + (a2 - a) / 2                        # a wait that separates two live ages
    out["engine_live_ages_separated"] = check(a >= 0, a2 > a, a2 <= CAP,
                                              z3.Not(z3.And(gap >= 0, a + gap <= CAP, a2 + gap > CAP)))

    # the window view (age, closed and reply within two days)
    a_, e2, c2 = z3.Real("a_"), z3.Real("e2"), z3.Bool("c2")
    y = (a_, c2, e2)
    W = lambda s: (s[0], z3.And(s[1], s[2] <= WIN))
    same = z3.Not(neq(W(x), W(y)))
    now_refuted = z3.And(dom(x), dom(y), same, queries["suggest"](x) != queries["suggest"](y))
    out["window_now"] = check(now_refuted)
    wit = [(a, R(3)), (closed, z3.BoolVal(False)), (e, R(0)), (a_, R(3)), (c2, z3.BoolVal(True)), (e2, R(Q(5, 2)))]
    out["window_now_witness_ok"] = holds(z3.substitute(now_refuted, *wit))
    upd_refuted = z3.And(dom(x), dom(y), d >= 0, same, neq(W(wait[2](x, (d,))), W(wait[2](y, (d,)))))
    out["window_updates"] = check(upd_refuted)
    wit2 = [(a, R(3)), (closed, z3.BoolVal(True)), (e, R(Q(1, 2))), (a_, R(3)), (c2, z3.BoolVal(True)),
            (e2, R(Q(19, 10))), (d, R(Q(1, 5)))]
    out["window_updates_witness_ok"] = holds(z3.substitute(upd_refuted, *wit2))
    return out


# ====================================================================== Pattern 5: goals
def p5():
    a, a2, d = z3.Reals("a a2 d")
    op, op2, ben, ben2 = z3.Bools("op op2 ben ben2")
    nag = lambda o, x: z3.And(o, x <= 2)
    nag3 = lambda o, x: z3.And(o, x <= 3)
    days_left = lambda o, x: z3.If(o, z3.If(2 - x > 0, 2 - x, R(0)), R(0))
    out = {}

    def determines(new, old):
        """Is the old answer a function of the new one?  'unsat' means yes."""
        same = z3.Not(neq(new(op, a, ben), new(op2, a2, ben2)))
        return check(a >= 0, a2 >= 0, same, neq(old(op, a, ben), old(op2, a2, ben2)))

    old = lambda o, x, b: (nag(o, x),)
    dl = lambda o, x, b: (nag(o, x), days_left(o, x))
    bf = lambda o, x, b: (nag(o, x), z3.And(nag(o, x), b))
    c3 = lambda o, x, b: (nag3(o, x),)
    out["days_left_preserves_old"] = determines(dl, old)
    out["days_left_converse"] = determines(old, dl)
    out["ben_first_preserves_old"] = determines(bf, old)
    out["ben_first_converse"] = determines(old, bf)
    out["cap3_preserves_old"] = determines(c3, old)
    out["cap3_converse"] = determines(old, c3)

    def ev(f, o, x, b):
        vals = []
        for t in f(op, a, ben):
            v = z3.simplify(z3.substitute(t, (op, z3.BoolVal(o)), (a, R(x)), (ben, z3.BoolVal(b))))
            vals.append(str(v))
        return vals
    out["w_days_left"] = ev(dl, True, 0, True) + ev(dl, True, 1, True)
    out["w_ben_first"] = ev(bf, True, 0, True) + ev(bf, True, 0, False)
    out["w_cap3_old"] = ev(c3, True, 1, True) + ev(old, True, 1, True) + ev(c3, True, Q(5, 2), True) \
        + ev(old, True, Q(5, 2), True)
    out["w_cap3_new"] = ev(old, True, Q(5, 2), True) + ev(c3, True, Q(5, 2), True) \
        + ev(old, True, Q(7, 2), True) + ev(c3, True, Q(7, 2), True)
    # the goal's coarsest statistic saturates at its threshold; the deadline schema is a migration
    x = (op, a)
    dom = lambda s: s[1] >= 0
    T = {"wait": ((d,), d >= 0, lambda s, p: (s[0], s[1] + p[0])),
         "close": ((), z3.BoolVal(True), lambda s, p: (z3.BoolVal(False), s[1]))}

    def deadline(s):
        expired = s[1] > 2
        return (s[0], expired, z3.If(expired, R(0), 2 - s[1]))

    def deadline_wait(t, p):
        expired = z3.Or(t[1], t[2] - p[0] < 0)
        return (t[0], expired, z3.If(expired, R(0), t[2] - p[0]))
    mig = certificate(dom, x, T, deadline,
                      {"wait": deadline_wait, "close": lambda t, p: (z3.BoolVal(False), t[1], t[2])},
                      {"nag": lambda s: nag(s[0], s[1])}, {"nag": lambda t: z3.And(t[0], z3.Not(t[1]))})
    out.update({"deadline_" + k: v for k, v in mig.items()})

    def sat_k(k):
        def stat(s):
            return (s[0], z3.And(s[0], s[1] > k), z3.If(z3.And(s[0], s[1] <= k), s[1], R(0)))

        def wait(t, p):
            past = z3.And(t[0], z3.Or(t[1], t[2] + p[0] > k))
            live = z3.And(t[0], z3.Not(z3.Or(t[1], t[2] + p[0] > k)))
            return (t[0], past, z3.If(live, t[2] + p[0], R(0)))
        return stat, wait
    close_abs = lambda t, p: (z3.BoolVal(False), z3.BoolVal(False), R(0))
    st2, w2 = sat_k(2)
    s2 = certificate(dom, x, T, st2, {"wait": w2, "close": close_abs},
                     {"nag": lambda s: nag(s[0], s[1])}, {"nag": lambda t: z3.And(t[0], z3.Not(t[1]))})
    out.update({"saturate_at_2_" + k: v for k, v in s2.items()})
    # the same statistic also serves the days-left goal: a refinement at no cost in memory
    dl_read = lambda t: (z3.And(t[0], z3.Not(t[1])), z3.If(z3.And(t[0], z3.Not(t[1])), 2 - t[2], R(0)))
    out["saturate_at_2_serves_days_left"] = check(dom(x), neq((nag(op, a), days_left(op, a)), dl_read(st2(x))))
    st3, w3 = sat_k(3)
    s3 = certificate(dom, x, T, st3, {"wait": w3, "close": close_abs},
                     {"nag": lambda s: nag(s[0], s[1]), "nag3": lambda s: nag3(s[0], s[1])},
                     {"nag": lambda t: z3.And(t[0], z3.Not(t[1]), t[2] <= 2),
                      "nag3": lambda t: z3.And(t[0], z3.Not(t[1]))})
    out.update({"saturate_at_3_" + k: v for k, v in s3.items()})
    # the two-day statistic cannot serve the three-day goal: equal codes, different nag3 answers
    y = (op2, a2)
    out["two_for_both_now"] = check(dom(x), dom(y), z3.Not(neq(st2(x), st2(y))),
                                    z3.Or(nag(op, a) != nag(op2, a2), nag3(op, a) != nag3(op2, a2)))
    wit = [(op, z3.BoolVal(True)), (a, R(Q(5, 2))), (op2, z3.BoolVal(True)), (a2, R(Q(7, 2)))]
    out["two_for_both_witness_ok"] = holds(z3.substitute(z3.And(z3.Not(neq(st2(x), st2(y))),
                                                                nag3(op, a) != nag3(op2, a2)), *wit))
    # saturating at the threshold is the coarsest choice: two open ages at most k are separated
    for k in (2, 3):
        gap = k - a2 + (a2 - a) / 2
        out[f"saturate_at_{k}_ages_separated"] = check(a >= 0, a2 > a, a2 <= k,
                                                       z3.Not(z3.And(gap >= 0, a + gap <= k, a2 + gap > k)))
    return out


# ====================================================================== Pattern 6: arbitration
THC, THP = R(Q(4, 5)), R(Q(1, 2))
NONE, VERIFY, CONSOLIDATE, HOLD = 0, 1, 2, 3


def p6():
    c, p, lam, dl = z3.Reals("c p lam dl")
    chk, cons = z3.Bools("chk cons")
    x = (c, chk, cons, p)
    dom = lambda s: z3.And(s[0] >= 0, s[0] <= 1, s[3] >= 0, s[3] <= 1)

    # the live goals read the real confidence and pressure
    def throughput(s):
        return z3.If(s[2], NONE, z3.If(z3.Or(s[0] >= THC, s[3] >= THP), CONSOLIDATE, NONE))

    def verify_first(s):
        return z3.If(s[2], NONE, z3.If(z3.Not(s[1]), VERIFY, z3.If(s[0] >= THC, CONSOLIDATE, HOLD)))

    def forbidden(s, m):
        return z3.And(m == CONSOLIDATE, z3.Not(s[1]))

    def weighted(s):
        t, v = throughput(s), verify_first(s)
        return z3.If(t != NONE, t, z3.If(v != NONE, v, HOLD))

    def norm_first(s):
        t, v = throughput(s), verify_first(s)
        return z3.If(z3.And(t != NONE, z3.Not(forbidden(s, t))), t,
                     z3.If(z3.And(v != NONE, z3.Not(forbidden(s, v))), v, HOLD))

    def act(rule):
        def f(s, prm):
            m = rule(s)
            return (s[0], z3.Or(s[1], m == VERIFY), z3.Or(s[2], m == CONSOLIDATE), s[3])
        return f

    # the abstract machine of Pattern 6 on classes (high, checked, consolidated, deadline)
    def a_throughput(t):
        return z3.If(t[2], NONE, z3.If(z3.Or(t[0], t[3]), CONSOLIDATE, NONE))

    def a_verify(t):
        return z3.If(t[2], NONE, z3.If(z3.Not(t[1]), VERIFY, z3.If(t[0], CONSOLIDATE, HOLD)))

    def a_rule(kind):
        def r(t):
            th, v = a_throughput(t), a_verify(t)
            if kind == "weighted":
                return z3.If(th != NONE, th, z3.If(v != NONE, v, HOLD))
            okt = z3.And(th != NONE, z3.Not(z3.And(th == CONSOLIDATE, z3.Not(t[1]))))
            okv = z3.And(v != NONE, z3.Not(z3.And(v == CONSOLIDATE, z3.Not(t[1]))))
            return z3.If(okt, th, z3.If(okv, v, HOLD))
        return r

    def a_act(kind):
        def f(t, prm):
            m = a_rule(kind)(t)
            return (t[0], z3.Or(t[1], m == VERIFY), z3.Or(t[2], m == CONSOLIDATE), t[3])
        return f
    h = lambda s: (s[0] >= THC, s[1], s[2], s[3] >= THP)
    out = {}
    ev_real = lambda s, prm: (s[0] + prm[0] * (1 - s[0]), s[1], s[2], s[3])
    pr_real = lambda s, prm: (s[0], s[1], s[2], z3.If(s[3] + prm[0] > 1, R(1), s[3] + prm[0]))
    ev_abs = lambda t: (z3.BoolVal(True), t[1], t[2], t[3])
    dl_abs = lambda t: (t[0], t[1], t[2], z3.BoolVal(True))
    out["evidence_stutter_or_step"] = check(dom(x), lam >= 0, lam <= 1,
                                            neq(h(ev_real(x, (lam,))), h(x)), neq(h(ev_real(x, (lam,))), ev_abs(h(x))))
    out["pressure_stutter_or_step"] = check(dom(x), dl >= 0,
                                            neq(h(pr_real(x, (dl,))), h(x)), neq(h(pr_real(x, (dl,))), dl_abs(h(x))))
    out["domain_closed"] = check(dom(x), lam >= 0, lam <= 1, dl >= 0,
                                 z3.Or(z3.Not(dom(ev_real(x, (lam,)))), z3.Not(dom(pr_real(x, (dl,))))))
    for kind, rule in (("weighted", weighted), ("norm_first", norm_first)):
        out["act_commutes_" + kind] = check(dom(x), neq(h(act(rule)(x, ())), a_act(kind)(h(x), ())))
        out["goals_factor_" + kind] = check(dom(x), rule(x) != a_rule(kind)(h(x)))
    # the shared query: a state is unlawful when its rule picks a forbidden move
    a_forbidden = lambda t, m: z3.And(m == CONSOLIDATE, z3.Not(t[1]))
    for kind, rule in (("weighted", weighted), ("norm_first", norm_first)):
        out["unlawful_preserved_" + kind] = check(dom(x), forbidden(x, rule(x)) != a_forbidden(h(x), a_rule(kind)(h(x))))
    # the two evidence obligations without the product: lam (1 - c) is replaced by a fresh t with
    # 0 <= t <= 1 - c, which every lam in [0, 1] satisfies (the range lemma, one line by hand);
    # the obligations are then in linear arithmetic
    t = z3.Real("t")
    ev_lin = lambda s: (s[0] + t, s[1], s[2], s[3])
    t_range = z3.And(t >= 0, t <= 1 - c)
    lin_match = z3.And(dom(x), t_range, neq(h(ev_lin(x)), h(x)), neq(h(ev_lin(x)), ev_abs(h(x))))
    lin_closed = z3.And(dom(x), t_range, z3.Not(dom(ev_lin(x))))
    out["evidence_linear_match"] = check(lin_match)
    out["evidence_linear_closed"] = check(lin_closed)
    out["evidence_linear_forms"] = is_linear(lin_match) and is_linear(lin_closed)
    out["evidence_original_nonlinear"] = not is_linear(z3.And(dom(x), neq(h(ev_real(x, (lam,))), h(x))))
    out["evidence_range_lemma"] = check(dom(x), lam >= 0, lam <= 1,
                                        z3.Not(z3.And(lam * (1 - c) >= 0, lam * (1 - c) <= 1 - c)))
    out["norm_first_never_forbidden"] = check(dom(x), forbidden(x, norm_first(x)))
    out["weighted_can_be_forbidden"] = check(dom(x), forbidden(x, weighted(x)))
    out["evidence_realizable"] = holds(z3.substitute(ev_real(x, (lam,))[0] >= THC, (c, R(0)), (lam, R(Q(9, 10)))))
    # a live run for the weighted rule: from the start, one deadline step of 1/2 makes the rule
    # consolidate an unchecked claim
    start = (R(0), z3.BoolVal(False), z3.BoolVal(False), R(0))
    s1 = pr_real(start, (R(Q(1, 2)),))
    out["weighted_live_run_deadline"] = holds(forbidden(s1, weighted(s1)))
    s2 = ev_real(start, (R(Q(4, 5)),))
    out["weighted_live_run_evidence"] = holds(forbidden(s2, weighted(s2)))
    out["start_lawful"] = holds(z3.Not(z3.Or(forbidden(start, weighted(start)), forbidden(start, norm_first(start)))))
    return out


# ====================================================================== Pattern 7: continuous MetaMo
def p7():
    gi, g1, a, c, nu, rho = z3.Reals("gi g1 a c nu rho")
    x = (gi, g1, a, c, nu, rho)
    dom = z3.And(gi >= Q(1, 4), gi <= 1, g1 >= 0, g1 <= 1, a >= 0, a <= 1, c >= 0, c <= 1,
                 z3.Or(nu == 0, nu == 1), z3.Or(rho == 0, rho == 1))

    def psi(s):
        gi_, g1_, a_, c_, nu_, rho_ = s
        return (gi_, g1_, (nu_ + g1_) / 2, (rho_ + gi_) / 2, nu_, rho_)

    def clip(v):
        return z3.If(v < 0, R(0), z3.If(v > 1, R(1), v))

    def decide(s, variant):
        gi_, g1_, a_, c_, nu_, rho_ = s
        g1n = clip(g1_ + (a_ - c_) / 2)
        low = gi_ - Q(1, 4)
        if variant == "plain":
            lowered = z3.If(low < Q(1, 4), R(Q(1, 4)), low)
        else:
            floor = z3.If(gi_ >= Q(1, 2), R(Q(1, 2)), R(Q(1, 4)))
            lowered = z3.If(low < floor, floor, low)
        gin = z3.If(z3.And(a_ >= Q(3, 4), g1_ >= Q(3, 4)), lowered,
                    z3.If(c_ >= Q(3, 4), z3.If(gi_ + Q(1, 4) > 1, R(1), gi_ + Q(1, 4)), gi_))
        return (gin, g1n, a_, c_, nu_, rho_)
    out = {}
    out["floor_keeps_safe_region"] = check(dom, gi >= Q(1, 2), decide(psi(x), "floor")[0] < Q(1, 2))
    out["plain_leaves_safe_region"] = check(dom, gi >= Q(1, 2), decide(psi(x), "plain")[0] < Q(1, 2))
    wit = [(gi, R(Q(1, 2))), (g1, R(1)), (a, R(0)), (c, R(0)), (nu, R(1)), (rho, R(0))]
    out["plain_witness_gi_after"] = str(z3.simplify(z3.substitute(decide(psi(x), "plain")[0], *wit)))
    settled = z3.And(a == (nu + g1) / 2, c == (rho + gi) / 2)
    ideal = decide(psi(x), "floor")
    actual = psi(decide(x, "floor"))
    out["settled_goal_weights_agree"] = check(dom, settled, z3.Or(ideal[0] != actual[0], ideal[1] != actual[1]))
    opt = z3.Optimize()
    opt.add(dom)
    dgi = z3.If(ideal[0] >= actual[0], ideal[0] - actual[0], actual[0] - ideal[0])
    dg1 = z3.If(ideal[1] >= actual[1], ideal[1] - actual[1], actual[1] - ideal[1])
    obj = z3.If(dgi >= dg1, dgi, dg1)
    hnd = opt.maximize(obj)
    opt.check()
    out["order_swap_goal_sup"] = str(opt.upper(hnd))
    m = opt.model()
    out["order_swap_goal_argmax"] = [str(m.eval(v)) for v in x]
    return out


def p7_run():
    """The plain decision rule leaves the safe region on a reachable run; exact rational arithmetic."""
    clip = lambda v: max(Q(0), min(Q(1), v))

    def psi(s):
        gi, g1, a, c, nu, rho = s
        return (gi, g1, (nu + g1) / 2, (rho + gi) / 2, nu, rho)

    def decide(s, variant):
        gi, g1, a, c, nu, rho = s
        if a >= Q(3, 4) and g1 >= Q(3, 4):
            floor = Q(1, 4) if variant == "plain" else (Q(1, 2) if gi >= Q(1, 2) else Q(1, 4))
            gin = max(floor, gi - Q(1, 4))
        elif c >= Q(3, 4):
            gin = min(Q(1), gi + Q(1, 4))
        else:
            gin = gi
        return (gin, clip(g1 + (a - c) / 2), a, c, nu, rho)
    out = {}
    for variant in ("plain", "floor"):
        s = (Q(3, 4), Q(1, 2), Q(1, 2), Q(1, 2), Q(0), Q(0))
        s = (s[0], s[1], s[2], s[3], Q(1), Q(0))           # (stimulus 1 0)
        trace = []
        for _ in range(4):
            s = decide(psi(s), variant)
            trace.append(str(s[0]))
        out[variant] = trace
    return out


if __name__ == "__main__":
    for f in (p1, p5, p6, p7, p7_run):
        print(f.__name__, f())
