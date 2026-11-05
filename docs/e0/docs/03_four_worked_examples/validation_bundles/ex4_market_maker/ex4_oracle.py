#!/usr/bin/env python3
"""Oracle for Example 4 (a market maker across regime shifts).

Recomputes every number quoted for the example, in exact arithmetic unless a line says
otherwise:
  - the module's maps, evaluated by metta_eval.py, define the same processes, kernels, reward
    laws, tapes and monitor laws as the Python model (cell by cell);
  - calm: the risk-bucket quotient, the mirror, optimal policies and values;
  - toxic: the compression survives and the calm policy stays optimal, at lower values;
  - buyers: the compression fails on both obligations, the exact Kantorovich defect with its
    certificate, the calm policy is refuted, the mirror transfer and the pulled-back policy;
  - informed flow: freshness, averaging (means equal, laws not), coarse and refined optima,
    the toxicity signal and the wrong evaluation;
  - the news-leak tape: bisimulation, trace classes, minimal linear dimensions, the trace-event
    witness, behavioral distances and the modal test;
  - monitors: validity, blindness, chi-square, stream digests and the Estimated detections.

Run: python3 ex4_oracle.py        (about a minute; writes ex4_results.json)
"""
import hashlib
import json
import math
import time

from kantorovich import Behavioral
from metta_eval import World
import mm
from mm import (ACTIONS, BUYERS, CALM, F, GAMMA, HALF, Q, SELLERS, SPLIT_START, SPLIT_STATES, TOXIC,
                average_process, best_through, check_homomorphism, check_optimal, current_witness,
                evaluate, is_fresh, kernel, optimize, push, qval, regime_process, reward_law,
                sensor_channel, sensor_optimize, sensor_policy_value, split_process, start_value,
                tv_lump_defect, update_witness)
import monitors as mon
import news

RESULTS, FAILS, N = {}, [], [0]


def check(name, got, want):
    N[0] += 1
    ok = got == want
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": got {got!r}, want {want!r}"))
    if not ok:
        FAILS.append(name)
    RESULTS[name] = js(got)


def js(x):
    if isinstance(x, F):
        return str(x)
    if isinstance(x, dict):
        return {str(k): js(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [js(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(js(v) for v in x)
    return x


def s(x):
    return tuple(str(v) if isinstance(v, F) else v for v in x)


T0 = time.time()
W = World("market_maker.metta")
calm, tox, buy, sell = [regime_process(r) for r in (CALM, TOXIC, BUYERS, SELLERS)]

# ------------------------------------------------------------------ the module defines the model
for name, reg in (("CalmDesk", CALM), ("ToxicDesk", TOXIC), ("BuyersDesk", BUYERS), ("SellersDesk", SELLERS)):
    S, A, k, r, g = W.process("MarketDesk", name)
    same = all(k(q, a) == kernel(reg, q, a) and r(q, a) == reward_law(reg, q, a) for q in S for a in A)
    check(f"{name}: module kernels and reward laws equal the model on all 15 cells", (S, A, g, same),
          (Q, ACTIONS, GAMMA, True))
S, A, k, r, g = W.process("InformedFlow", "Split")
SP = split_process()
check("Split: module kernels and expected rewards equal the model on all 30 cells",
      (S == SPLIT_STATES, all(k(x, a) == SP.kernel(x, a) and sum(v * m for v, m in r(x, a).items()) == SP.reward(x, a)
                              for x in S for a in A)), (True, True))
pol_calm = W.instance("MarketDesk", "calm-policy")
pol_sell = W.instance("MarketDesk", "sellers-policy")
CALM_POLICY = {q: pol_calm(q) for q in Q}
SELL_POLICY = {q: pol_sell(q) for q in Q}

# ------------------------------------------------------------------ calm
codes = [0, 1, 2]
check("calm: Risk current and update witnesses (none)", (current_witness(calm, abs), update_witness(calm, abs, codes)),
      (None, None))
quot = mm.quotient(calm, abs, codes)
check("calm: quotient rows, one lot (bucket -> action -> (reward, row))",
      {a: (str(rw), {c: str(p) for c, p in row.items()}) for a, (rw, row) in quot[1].items()},
      {"tight": ("3/4", {1: "1/2", 0: "1/4", 2: "1/4"}),
       "wide": ("1/4", {1: "25/32", 0: "7/64", 2: "7/64"}),
       "lean": ("19/32", {1: "1/2", 0: "7/16", 2: "1/16"})})
check("calm: quotient rows, flat and two lots under tight",
      ({c: str(p) for c, p in quot[0]["tight"][1].items()}, {c: str(p) for c, p in quot[2]["tight"][1].items()}),
      ({0: "1/2", 1: "1/2"}, {2: "1/2", 1: "1/2"}))
check("calm: CalmMirror is a quotient arrow (an automorphism)", check_homomorphism(calm, calm, lambda q: -q),
      ("Checked", "Quotient"))
pc, Vc, rounds = optimize(calm)
check("calm: optimal policy (ties to the first action) and policy-iteration rounds", (pc, rounds),
      ({-2: "tight", -1: "lean", 0: "tight", 1: "lean", 2: "tight"}, 2))
check("calm: the declared calm-policy is that optimum", CALM_POLICY == pc, True)
check("calm: optimal values (-2, -1, 0)", (Vc[-2], Vc[-1], Vc[0]), (F(2033, 352), F(217, 32), F(2513, 352)))
cp, v, _ = best_through(calm, abs, codes, {0: F(1)})
check("calm: OptimizePolicy Through Risk equals the full optimum", (cp, v), ({0: "tight", 1: "lean", 2: "tight"}, F(2513, 352)))
check("calm: lean equals tight when flat and at the limits", all(
    calm.kernel(q, "lean") == calm.kernel(q, "tight") and calm.reward(q, "lean") == calm.reward(q, "tight")
    for q in (-2, 0, 2)), True)

# ------------------------------------------------------------------ toxic
check("toxic: Risk stays exact", (current_witness(tox, abs), update_witness(tox, abs, codes)), (None, None))
st, w, Vt = check_optimal(tox, CALM_POLICY)
check("toxic: CheckOptimal calm-policy", st, "Checked")
check("toxic: values of the calm policy (-2, -1, 0)", (Vt[-2], Vt[-1], Vt[0]), (F(1541, 704), F(189, 64), F(2181, 704)))
check("toxic: value lost at flat", Vc[0] - Vt[0], F(2845, 704))
tox34 = regime_process(mm.Regime("toxic34", CALM.ask, CALM.bid, theta=F(3, 4)))
p34, _, _ = optimize(tox34)
check("toxic at theta 3/4 instead of 1/2: the optimum changes only when flat, to wide",
      {q: a for q, a in p34.items() if a != pc[q]}, {0: "wide"})
check("toxic: fill laws equal calm's at every cell", all(mon.fill_law(TOXIC, q, a) == mon.fill_law(CALM, q, a)
                                                        for q in Q for a in ACTIONS), True)

# ------------------------------------------------------------------ buyers
check("buyers: InduceExact RiskBuyers refuted on current adequacy (pair, query, two rewards)",
      s(current_witness(buy, abs)), (-2, 2, "tight", "-3/16", "7/16"))
check("buyers: CheckUpdates RiskBuyers witness (pair, action, bucket, two masses)",
      s(update_witness(buy, abs, codes)), (-2, 2, "tight", 1, "1/4", "3/4"))
check("buyers: total-variation lumpability defect and where", s((tv_lump_defect(buy, abs)[0],) + tv_lump_defect(buy, abs)[1]),
      ("1/2", -2, 2, "tight"))


def d0_of(P):
    return lambda x, y: max(min(F(1), abs(P.reward(x, a) - P.reward(y, a))) for a in P.actions)


B = Behavioral(Q, ACTIONS, buy.kernel, d0_of(buy), GAMMA)
B.float_iterate()
B.exact()
cert = B.verify()
check("buyers: behavioral distances of the merged pairs at 9/10 (-2,2), (-1,1)",
      (B.dist(-2, 2), B.dist(-1, 1)), (F(56601, 73472), F(48015, 73472)))
check("buyers: MeasureBehavioral RiskBuyers interval and the pair attaining it",
      (max(B.dist(-2, 2), B.dist(-1, 1)), "(-2, 2)"), (F(56601, 73472), "(-2, 2)"))
check("buyers: immediate part d0 of the two pairs", (d0_of(buy)(-2, 2), d0_of(buy)(-1, 1)), (F(5, 8), F(13, 32)))
check("buyers: binding action and optimal coupling for (-2, 2)",
      (cert["potentials"][(-2, 2)][0], {str(k): str(v) for k, v in cert["couplings"][(-2, 2, "tight")].items()}),
      ("tight", {"(-2, 1)": "1/2", "(-2, 2)": "1/4", "(-1, 1)": "1/4"}))
pot = cert["potentials"][(-2, 2)][1]
check("buyers: Kantorovich potential for (-2, 2) under tight", {k: str(v) for k, v in pot.items()},
      {-2: "1", -1: "48015/73472", 1: "0", 2: "16871/73472"})
check("buyers: certificate size (couplings, potentials, pairs bound by d0)",
      (len(cert["couplings"]), sum(1 for v in cert["potentials"].values() if v[0] != "d0"),
       sum(1 for v in cert["potentials"].values() if v[0] == "d0")), (30, 5, 5))
st, w, Vb = check_optimal(buy, CALM_POLICY)
check("buyers: CheckOptimal calm-policy refuted (state, its action, Q, better action, Q)", (st, s(w)),
      ("Refuted", (1, "lean", "489418779/101884448", "tight", "503574367/101884448")))
pb, Vbs, _ = optimize(buy)
check("buyers: optimal policy", pb, {-2: "tight", -1: "lean", 0: "tight", 1: "tight", 2: "tight"})
check("buyers: optimal value at flat", Vbs[0], F(92970729, 21404480))
check("buyers: calm policy value at flat and at one lot long", (Vb[0], Vb[1]),
      (F(438585327, 101884448), F(489418779, 101884448)))
cpb, vb, _ = best_through(buy, abs, codes, {0: F(1)})
check("buyers: OptimizePolicy Through RiskBuyers (best bucket policy is the calm one)", (cpb, vb),
      ({0: "tight", 1: "lean", 2: "tight"}, F(438585327, 101884448)))
check("buyers: regret of the calm policy at flat and at one lot long (decimals)",
      (round(float(Vbs[0] - Vb[0]), 4), round(float(Vbs[1] - Vb[1]), 4)), (0.0388, 0.2585))
check("buyers -> sellers: Flip is a quotient arrow", check_homomorphism(buy, sell, lambda q: -q), ("Checked", "Quotient"))
check("identity calm -> buyers is not a homomorphism (state, action, rewards)",
      s(check_homomorphism(calm, buy, lambda q: q)[1]), ("reward", -2, "tight", "1/8", "-3/16"))
ps, Vss, _ = optimize(sell)
check("sellers: the declared sellers-policy is the sellers' optimum", SELL_POLICY == ps, True)
pulled = {q: SELL_POLICY[-q] for q in Q}
Vpull = evaluate(buy, pulled)
check("PullbackPolicy Flip sellers-policy: policy, and values equal the sellers' values at -q",
      (pulled, all(Vpull[q] == Vss[-q] for q in Q)), (pb, True))

# ------------------------------------------------------------------ informed flow
check("split: the flow is fresh", is_fresh(SP, 1, HALF), True)
avg = average_process(SP, HALF)
check("split: averaged kernels equal ToxicDesk's", all(avg.kernel(q, a) == tox.kernel(q, a) for q in Q for a in ACTIONS), True)
check("split: averaged expected rewards equal ToxicDesk's (CheckEqual ... (Compare Means))",
      all(avg.reward(q, a) == tox.reward(q, a) for q in Q for a in ACTIONS), True)


def avg_law(q, a):
    out = {}
    for f, wgt in HALF.items():
        for v, m in reward_law(mm.FLOW_REG[f], q, a).items():
            out[v] = out.get(v, F(0)) + wgt * m
    return out


def law_witness():
    for q in Q:
        for a in ACTIONS:
            la, lt = avg_law(q, a), reward_law(TOXIC, q, a)
            for v in sorted(set(la) | set(lt)):
                if la.get(v, F(0)) != lt.get(v, F(0)):
                    return (q, a, v, la.get(v, F(0)), lt.get(v, F(0)))


check("split: CheckEqual on reward laws refuted (state, action, P&L value, two masses)", s(law_witness()),
      (-2, "tight", "-1/4", "1/4", "0"))
check("split: InduceExact Coarse refuted on current adequacy",
      s(current_witness(SP, lambda x: x[0])), ((-2, "noise"), (-2, "informed"), "tight", "1/8", "-3/8"))
check("split: Coarse is update-compatible (the flow is fresh)", update_witness(SP, lambda x: x[0], Q), None)


# Proposition 6.2: what averaging a fresh factor preserves, and what it does not
def joint_laws(P, start, policy, T, visible=lambda x: x):
    """Exact laws, under a policy on visible histories, of the visible history (x_0, a_0, ..., x_T)
    and, for each history and its action, of the hidden part given that history."""
    paths = {((), x): m for x, m in start.items()}
    vis, hidden_given = {}, {}
    for t in range(T + 1):
        nxt = {}
        for (hist, x), m in paths.items():
            h = hist + (visible(x),)
            if t == T:
                vis[h] = vis.get(h, F(0)) + m
                continue
            a = policy(h)
            key = h + (a,)
            hidden_given.setdefault(key, {})
            hidden_given[key][x] = hidden_given[key].get(x, F(0)) + m
            for y, p in P.kernel(x, a).items():
                nxt[(key, y)] = nxt.get((key, y), F(0)) + m * p
        paths = nxt
    return vis, hidden_given


calm_memoryless = lambda h: CALM_POLICY[h[-1]]  # noqa: E731
moved = lambda h: "wide" if len(h) >= 3 and h[-1] != h[-3] else "tight"  # noqa: E731 -- depends on the history
same_laws, cond_means = [], []
for pol in (calm_memoryless, moved):
    vs, hid = joint_laws(SP, SPLIT_START, pol, 3, visible=lambda x: x[0])
    va, _ = joint_laws(avg, {0: F(1)}, pol, 3)
    same_laws.append(vs == va)
    ok = True
    for key, law in hid.items():
        tot = sum(law.values())
        q, a = key[-2], key[-1]
        ok &= sum(m * SP.reward(x, a) for x, m in law.items()) / tot == avg.reward(q, a)
    cond_means.append(ok)
check("Proposition 6.2: the visible states and actions of the first three steps have the same law in Split and in the "
      "averaged model (a memoryless and a history-dependent policy)", same_laws, [True, True])
check("Proposition 6.2: given every visible history, the conditional mean of the reward is the averaged reward",
      cond_means, [True, True])
lifted = {x: CALM_POLICY[x[0]] for x in SP.states}
check("Proposition 6.2: expected discounted return of the calm policy from flat (Split, averaged model)",
      (start_value(evaluate(SP, lifted), SPLIT_START), evaluate(avg, CALM_POLICY)[0]), (F(2181, 704), F(2181, 704)))
check("Proposition 6.2: the expected reward of tight at -2 as a function of the hidden flow (noise, informed) and in "
      "the averaged model; its law in Split and in the averaged model",
      ((SP.reward((-2, "noise"), "tight"), SP.reward((-2, "informed"), "tight")), avg.reward(-2, "tight"),
       {SP.reward((-2, f), "tight"): m for f, m in HALF.items()}, {avg.reward(-2, "tight"): F(1)}),
      ((F(1, 8), F(-3, 8)), F(-1, 8), {F(1, 8): F(1, 2), F(-3, 8): F(1, 2)}, {F(-1, 8): F(1)}))
cps, vcs, _ = best_through(SP, lambda x: x[0], Q, SPLIT_START)
check("split: OptimizePolicy Through Coarse (243 code policies)", (cps, vcs), (CALM_POLICY, F(2181, 704)))
pr, Vr, _ = optimize(SP)
diff = {x: a for x, a in pr.items() if a != CALM_POLICY[x[0]]}
check("split: refined optimum differs from the calm policy only at flat with informed flow", diff,
      {(0, "informed"): "wide"})
vr = start_value(Vr, SPLIT_START)
check("split: refined optimal value from flat", vr, F(401605, 96926))
ch = sensor_channel(F(1, 10))
spol, Ws = sensor_optimize(SP, HALF, ch, F(1, 20))
check("split: the signal policy differs from the calm policy only at flat with says-informed",
      {k: a for k, a in spol.items() if a != CALM_POLICY[k[0]]}, {(0, "says-informed"): "wide"})
Vtrue = sensor_policy_value(SP, HALF, ch, F(1, 20), spol)
check("split: EvaluatePolicy With Signal, net of cost (reduced and on hidden states)",
      (Ws[0], start_value(Vtrue, SPLIT_START)), (F(165927, 48463), F(165927, 48463)))
wpol, Ww = sensor_optimize(SP, HALF, ch, F(1, 20), substitute=True)
check("split: the wrong evaluation (reading taken for the flow) and that policy's true value",
      (Ww[0], start_value(sensor_policy_value(SP, HALF, ch, F(1, 20), wpol), SPLIT_START)),
      (F(176571, 48463), F(165927, 48463)))
check("split: the wrong evaluation is the refined optimum minus the discounted cost", Ww[0], vr - F(1, 20) / (1 - GAMMA))
_, W0 = sensor_optimize(SP, HALF, ch, F(0))
check("split: gross value of the signal and break-even cost per step",
      (W0[0], (W0[0] - vcs) * (1 - GAMMA)), (F(380317, 96926), F(28173781, 341179520)))
check("split: decimals (coarse, refined, signal net, wrong)",
      tuple(round(float(x), 4) for x in (vcs, vr, Ws[0], Ww[0])), (3.098, 4.1434, 3.4238, 3.6434))

# ------------------------------------------------------------------ the news-leak tape
dst, dobs, dacts, _ = W.machine("NewsLeak", "Desk")
wst, wobs, wacts, _ = W.machine("NewsLeak", "WideSeen")
rep = W.instance("NewsLeak", "report")
REP = {x: rep(x) for x in dst}


def kern_of(acts):
    rows = dict(acts)
    return lambda x, a: rows[a][x]


kd, kw = kern_of(dacts), kern_of(wacts)
check("tape: module rows and reports equal the model's",
      (dst == news.STATES, all(kd(x, a) == news.kernel(x, a) for x in dst for a in ("tight", "wide")),
       REP == news.REPORT), (True, True, True))
check("tape: WideSeen is the wide-only reachable scope from leak and embargo", wst,
      ["leak", "embargo", "knows-up", "knows-down", "pending", "moved-up", "moved-down"])
check("tape: bisimulation classes (Desk, WideSeen)",
      (len(news.bisimulation(dst, ["tight", "wide"], kd, REP)), len(news.bisimulation(wst, ["wide"], kw, REP))), (9, 7))
dimw, basis_w, _ = news.trace_space(wst, ["wide"], kw, REP, news.REPORTS)
dimd, basis_d, _ = news.trace_space(dst, ["tight", "wide"], kd, REP, news.REPORTS)
check("tape: MinimalLinear dimensions (WideSeen, Desk)", (dimw, dimd), (5, 9))
idx = {x: i for i, x in enumerate(wst)}
cls = {}
for x in wst:
    cls.setdefault(tuple(v[idx[x]] for v in basis_w), []).append(x)
check("tape: TracePartition WideSeen", sorted(cls.values()),
      sorted([["leak", "embargo"], ["knows-up"], ["knows-down"], ["pending"], ["moved-up"], ["moved-down"]]))
check("tape: CheckTrace MergeLeakWide (no separating word up to length 6)",
      news.trace_witness("leak", "embargo", ["wide"], kw, REP, news.REPORTS), None)
check("tape: CheckTrace MergeLeak on Desk refuted (word, event, leak, embargo)",
      s(news.trace_witness("leak", "embargo", ["tight", "wide"], kd, REP, news.REPORTS)),
      (("tight", "tight"), ("quiet", "quiet", "up"), "0", "1/2"))
dd0 = lambda x, y: F(int(REP[x] != REP[y]))
for g, want_d, want_w in ((F(1), F(1), F(1, 2)), (F(9, 10), F(81, 100), F(81, 200))):
    Bd = Behavioral(dst, ["tight", "wide"], kd, dd0, g); Bd.float_iterate(); Bd.exact(); Bd.verify()
    Bw = Behavioral(wst, ["wide"], kw, dd0, g); Bw.float_iterate(); Bw.exact(); Bw.verify()
    check(f"tape: behavioral d(leak, embargo) at discount {g} (Desk, WideSeen)",
          (Bd.dist("leak", "embargo"), Bw.dist("leak", "embargo")), (want_d, want_w))


def psi(z, g):
    return g * sum(p for y, p in kw(z, "wide").items() if REP[y] == "up")


def phi(x, g):
    return g * sum(p * abs(psi(z, g) - g / 2) for z, p in kw(x, "wide").items())


check("tape: the modal test phi at discount 1 and 9/10 (leak, embargo)",
      ((phi("leak", F(1)), phi("embargo", F(1))), (phi("leak", F(9, 10)), phi("embargo", F(9, 10)))),
      ((F(1, 2), F(0)), (F(81, 200), F(0))))

# ------------------------------------------------------------------ monitors
mlaw = lambda m: W.instance("ShiftMonitors", ["markout", m])(0)
check("monitors: module markout laws (calm, toxic, buyers)", (mlaw("calm"), mlaw("toxic"), mlaw("buyers")),
      ({"adverse": F(1, 2), "favorable": F(1, 2)}, {"adverse": F(3, 4), "favorable": F(1, 4)},
       {"adverse": F(1, 2), "favorable": F(1, 2)}))
fl = lambda m: W.instance("ShiftMonitors", ["fills", m])
check("monitors: module fill laws equal the model's", all(
    fl(m)((q, a)) == mon.fill_law(reg, q, a) for m, reg in (("calm", CALM), ("toxic", TOXIC), ("buyers", BUYERS))
    for q in Q for a in ACTIONS), True)
M_mark = mon.markout_monitor(F(1, 2), "Markouts")
M_markb = mon.markout_monitor(F(0), "MarkoutsBuyers")
M_fill = mon.fill_monitor(BUYERS, "Fills")
M_fillt = mon.fill_monitor(TOXIC, "FillsToxic")
check("monitors: validity (null expectation of every factor)",
      [set(M.validity().values()) for M in (M_mark, M_fill, M_fillt, M_markb)], [{F(1)}] * 4)
check("monitors: blind (Markouts, Fills, FillsToxic, MarkoutsBuyers)",
      [M.blind() for M in (M_mark, M_fill, M_fillt, M_markb)], [False, False, True, True])
check("monitors: markout factors and chi-square",
      ({o: M_mark.factor("fill", o) for o in mon.MARKOUT}, M_mark.chi2("fill")),
      ({"adverse": F(3, 2), "favorable": F(1, 2)}, F(1, 4)))
check("monitors: fill factors at flat with a tight quote and chi-square",
      ({o: M_fill.factor((0, "tight"), o) for o in [(0, 0), (0, 1), (1, 0), (1, 1)]}, M_fill.chi2((0, "tight"))),
      ({(0, 0): F(3, 4), (0, 1): F(1, 4), (1, 0): F(9, 4), (1, 1): F(3, 4)}, F(9, 16)))
check("monitors: KL per observation, nats (decimals; markout, fills at flat tight)",
      (round(M_mark.kl("fill"), 4), round(M_fill.kl((0, "tight")), 4)), (0.1308, 0.2616))
check("monitors: Wald's approximation of markouts needed to reach 200 (decimal)",
      round(math.log(200) / M_mark.kl("fill"), 1), 40.5)
streams = {}
text = open("market_maker.metta").read()
for name in ("toxic", "buyers", "calm"):
    path = f"streams/{name}_seed1.json"
    raw = open(path, "rb").read()
    dig = "sha256:" + hashlib.sha256(raw).hexdigest()
    check(f"stream {name}: digest declared in the module", dig in text, True)
    rows = json.loads(raw)["rows"]
    streams[name] = [dict(zip(["step", "q", "quote", "ask", "bid", "markouts"], r)) for r in rows]
check("streams: rows and fills (toxic, buyers, calm)",
      [(len(v), sum(r["ask"] + r["bid"] for r in v)) for v in streams.values()],
      [(4000, 3172), (4000, 1985), (4000, 3045)])


def detect(stream, level):
    k = 2
    out = {}
    for M, kind in ((M_mark, "markout"), (M_fill, "fill")):
        out[M.name] = mon.run_monitor(M, stream, kind, level / k)
    fired = [(r[0], name) for name, r in out.items() if r[0] is not None]
    return out, (min(fired) if fired else None)


out, first = detect(streams["toxic"], F(1, 100))
check("Detect on ToxicTape: first monitor and step", first, (40, "Markouts"))
step, e, used, peak = out["Markouts"]
check("Detect on ToxicTape: markouts used and the exact e-value at the crossing",
      (used, e, e >= 200), (35, F(3 ** 27, 2 ** 35), True))
check("Detect on ToxicTape: the fill monitor never fires (blind to toxicity)", out["Fills"][0], None)
out, first = detect(streams["buyers"], F(1, 100))
check("Detect on BuyersTape: first monitor and step", first, (39, "Fills"))
check("Detect on BuyersTape: the markout monitor never fires", out["Markouts"][0], None)
out, first = detect(streams["calm"], F(1, 100))
check("Detect on CalmTape: no monitor fires in 4000 steps", first, None)
check("Detect on CalmTape: largest e-values reached (decimals)",
      (round(float(out["Markouts"][3]), 3), round(float(out["Fills"][3]), 3)), (1.602, 2.25))

RESULTS["_assurance"] = {
    "policy": "every Checked or Refuted result of this example is an exact computation on the processes of "
              "market_maker.metta (exact rational arithmetic, policy iteration, Krylov iteration) or a replayed "
              "certificate (couplings, Kantorovich potentials, tables of Q-values, modal tests); the floating-point "
              "stage only finds candidate couplings; Detect results are Estimated, with the stream digests; no "
              "result rests on a solver, so none is Conditional",
    "conditional": []}
RESULTS["_summary"] = {"checks": N[0], "failures": FAILS, "seconds": round(time.time() - T0, 1)}
json.dump(RESULTS, open("ex4_results.json", "w"), indent=1)
print(f"\n{N[0]} checks, {len(FAILS)} failures, {time.time() - T0:.1f} s")
raise SystemExit(1 if FAILS else 0)
