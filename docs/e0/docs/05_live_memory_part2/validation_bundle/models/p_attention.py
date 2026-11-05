"""Approximate statistics: error propagation, contraction and periodic recomputation.

Attention decays by a factor d = 1/2 per tick and receives boosts on use, as in the OCO/2 decay
fixture a(t) = a(t0) d^floor((t - t0)/Delta).  The exact statistic is the rational attention value.
An implementation that rounds to an integer after every update makes an error of at most 1/2 per
update; because the update is a contraction with factor d, the error stays below (1/2)/(1 - d) = 1
for ever.  A running total of usage weights is not a contraction (factor 1): rounding errors add up
unless the total is recomputed exactly from the records every R updates.
"""
import random
from fractions import Fraction as Q


def rnd(x):
    return int(x + Q(1, 2)) if x >= 0 else -int(-x + Q(1, 2))     # round half away from zero


def attention(steps=5000, seed=3, d=Q(1, 2)):
    rng = random.Random(seed)
    exact, approx, worst = Q(0), 0, Q(0)
    for _ in range(steps):
        boost = rng.choice([0, 0, 0, 10, 20, 40]) + Q(rng.randint(0, 9), 10)
        exact = exact * d + boost
        approx = rnd(approx * d + boost)
        worst = max(worst, abs(approx - exact))
    return {"steps": steps, "max_error": float(worst), "within_bound": worst <= Q(1, 2) / (1 - d),
            "bound": str(Q(1, 2) / (1 - d))}


def totals(steps=100000, seed=4, R=100):
    rng = random.Random(seed)
    exact = Q(0)
    plain = 0
    anchored = 0
    worst_plain, worst_anchored = Q(0), Q(0)
    for t in range(1, steps + 1):
        w = Q(rng.randint(0, 99), 100)
        exact += w
        plain = plain + rnd(w)                      # rounds each increment
        anchored = anchored + rnd(w)
        if t % R == 0:
            anchored = rnd(exact)                   # recompute from the records
        worst_plain = max(worst_plain, abs(plain - exact))
        worst_anchored = max(worst_anchored, abs(anchored - exact))
    return {"steps": steps, "R": R, "max_error_plain": float(worst_plain),
            "final_error_plain": float(abs(plain - exact)),
            "max_error_anchored": float(worst_anchored), "anchored_bound": R / 2 + 0.5}


if __name__ == "__main__":
    print(attention())
    print(totals())
