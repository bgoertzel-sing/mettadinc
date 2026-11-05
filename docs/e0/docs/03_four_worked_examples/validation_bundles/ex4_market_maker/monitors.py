"""Example 4, part 5: monitors for the regime shift.

A monitor observes one stream (markouts after fills, or the fill outcome of each posted quote)
and multiplies likelihood ratios of a declared alternative against a declared null law.  Each
factor uses the law given the quote that was posted before the outcome, so the product is a
nonnegative martingale under the null for every quoting policy, and Ville's inequality bounds
the probability that it ever reaches 1/delta by delta.

Exact claims about a monitor (validity, blindness, chi-square) are checked here; detections on a
stream are Estimated results.  The streams are generated once with a seeded generator and stored
as data, so another implementation replays the same stream rather than the same generator.
"""
import json
import math
import random
from fractions import Fraction as F

from mm import (ACTIONS, BUYERS, CALM, FLOW_REG, Q, kernel, offsets, outcomes, optimize,
                regime_process)

MARKOUT = ["adverse", "favorable"]


def markout_law(theta):
    """Markout of one fill: the mid moves one tick against the maker with probability (1+theta)/2."""
    p = (1 + theta) / 2
    return {"adverse": p, "favorable": 1 - p}


def fill_law(reg, q, a):
    return {(A, B): p for p, A, B in outcomes(reg, q, a)}


class Monitor:
    def __init__(self, name, null, alt, contexts):
        """null(ctx), alt(ctx): laws (dicts) of the observation given the context."""
        self.name, self.null, self.alt, self.contexts = name, null, alt, list(contexts)

    def validity(self):
        """E_null[LR | ctx] for every context (1 when alt << null, at most 1 always)."""
        out = {}
        for c in self.contexts:
            n, a = self.null(c), self.alt(c)
            out[c] = sum(a[o] for o in a if n.get(o, F(0)) > 0)
        return out

    def blind(self):
        return all(self.null(c) == self.alt(c) for c in self.contexts)

    def chi2(self, c):
        n, a = self.null(c), self.alt(c)
        return sum(a[o] ** 2 / n[o] for o in a if a[o]) - 1

    def kl(self, c):
        n, a = self.null(c), self.alt(c)
        return sum(float(a[o]) * math.log(float(a[o] / n[o])) for o in a if a[o])

    def factor(self, c, o):
        return self.alt(c).get(o, F(0)) / self.null(c)[o]


def markout_monitor(alt_theta, name):
    return Monitor(name, lambda c: markout_law(F(0)), lambda c: markout_law(alt_theta), ["fill"])


def fill_monitor(alt_reg, name):
    ctx = [(q, a) for q in Q for a in ACTIONS]
    return Monitor(name, lambda c: fill_law(CALM, *c), lambda c: fill_law(alt_reg, *c), ctx)


def simulate(regime, steps, seed, policy=None, informed_share=None):
    """A stream of (step, q, quote, ask_fill, bid_fill, markouts) under a regime.  With
    informed_share the step's flow is informed with that probability (theta 1 for its fills),
    otherwise noise; markouts are drawn per fill from the fill's theta."""
    rng = random.Random(seed)
    pol = policy or optimize(regime_process(CALM))[0]
    q, rows = 0, []
    for t in range(steps):
        a = pol[q]
        oa, ob = offsets(q, a)
        pa = regime.ask[oa] if oa else F(0)
        pb = regime.bid[ob] if ob else F(0)
        A = int(rng.random() < pa)
        B = int(rng.random() < pb)
        if informed_share is not None:
            informed = rng.random() < informed_share
            theta = F(1) if informed else F(0)
        else:
            theta = regime.theta
        marks = []
        for _ in range(A + B):
            p_adv = (1 + theta) / 2
            marks.append("adverse" if rng.random() < p_adv else "favorable")
        rows.append({"step": t + 1, "q": q, "quote": a, "ask": A, "bid": B, "markouts": marks})
        q = q - A + B
    return rows


def run_monitor(mon, stream, kind, level):
    """Exact e-process along a stored stream; returns (first step reaching 1/level or None,
    the e-value there or the final e-value, number of observations used)."""
    e, used, peak = F(1), 0, F(1)
    for r in stream:
        if kind == "markout":
            for o in r["markouts"]:
                e *= mon.factor("fill", o)
                used += 1
        else:
            e *= mon.factor((r["q"], r["quote"]), (r["ask"], r["bid"]))
            used += 1
        peak = max(peak, e)
        if e >= 1 / level:
            return r["step"], e, used, peak
    return None, e, used, peak
