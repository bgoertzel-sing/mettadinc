"""Anytime-valid estimates for rates read from receipts, and e-processes for monitors.

Confidence sequence.  For binary events X_1, X_2, ... that are conditionally Bernoulli(p) given
the past, the uniform-prior (Beta(1,1)) mixture of likelihood ratios

    M_n(p) = B(S_n + 1, n - S_n + 1) / (p^S_n (1 - p)^(n - S_n)),     S_n = X_1 + ... + X_n,

is a nonnegative martingale with M_0 = 1 under p, so by Ville's inequality
P(exists n: M_n(p) >= 1/alpha) <= alpha.  The set {p : M_n(p) < 1/alpha} is therefore a confidence
sequence: it contains the true rate at every n simultaneously with probability at least 1 - alpha
(Robbins 1970; Howard, Ramdas, McAuliffe and Sekhon 2021).

E-processes for monitors.  Against the null rate p0, a fixed alternative q gives the factor
(q/p0)^x ((1-q)/(1-p0))^(1-x); a finite mixture averages several such products; the continuous
mixture uses q uniform on (p0, 1).  Each is a nonnegative supermartingale whenever the conditional
rate is at most p0, so Ville's inequality bounds the false-alarm probability by alpha.
"""
import math

import numpy as np
from scipy.special import betaln, betainc

LOG = math.log


def log_mix(S, n, p):
    """log M_n(p) for the Beta(1,1) mixture."""
    if p <= 0:
        return 0.0 if S == 0 else math.inf
    if p >= 1:
        return 0.0 if S == n else math.inf
    return float(betaln(S + 1, n - S + 1)) - S * LOG(p) - (n - S) * LOG(1 - p)


def cs_interval(S, n, alpha, iters=200):
    """The confidence-sequence interval at time n: {p : log M_n(p) < log(1/alpha)}."""
    thr = LOG(1 / alpha)
    phat = S / n if n else 0.5
    lo = 0.0
    if S > 0:
        a, b = 0.0, phat          # log_mix(a) = inf > thr, log_mix(phat) < thr
        for _ in range(iters):
            m = (a + b) / 2
            if log_mix(S, n, m) >= thr:
                a = m
            else:
                b = m
        lo = a
    hi = 1.0
    if S < n:
        a, b = phat, 1.0
        for _ in range(iters):
            m = (a + b) / 2
            if log_mix(S, n, m) >= thr:
                b = m
            else:
                a = m
        hi = b
    return lo, hi


def zero_failure_upper(n, alpha):
    """Upper end of the confidence sequence after n events with no failure (closed form)."""
    return 1 - (alpha / (n + 1)) ** (1 / n)


def clopper_pearson_zero_upper(n, alpha):
    """Fixed-n one-sided Clopper-Pearson upper bound after n events with no failure."""
    return 1 - alpha ** (1 / n)


def coverage(p, runs, steps, alpha, seed):
    """Fraction of simulated runs in which the true rate ever leaves the confidence sequence."""
    rng = np.random.default_rng(seed)
    X = rng.random((runs, steps)) < p
    S = np.cumsum(X, axis=1)
    n = np.arange(1, steps + 1)
    logM = betaln(S + 1, n - S + 1) - S * np.log(p) - (n - S) * np.log(1 - p)
    return float(np.mean(np.max(logM, axis=1) >= np.log(1 / alpha)))


# ------------------------------------------------------------------ e-processes for monitors
def log_e_fixed(S, n, p0, q):
    return S * LOG(q / p0) + (n - S) * LOG((1 - q) / (1 - p0))


def log_e_finite_mixture(S, n, p0, qs):
    vals = [log_e_fixed(S, n, p0, q) for q in qs]
    m = max(vals)
    return m + LOG(sum(math.exp(v - m) for v in vals) / len(qs))


def log_e_uniform_mixture(S, n, p0):
    """q uniform on (p0, 1): E_n = B(S+1, n-S+1) P(Beta(S+1, n-S+1) > p0) / ((1-p0) p0^S (1-p0)^(n-S))."""
    tail = float(betainc(n - S + 1, S + 1, 1 - p0))     # = 1 - I_{p0}(S+1, n-S+1)
    if tail <= 0:
        return -math.inf
    return float(betaln(S + 1, n - S + 1)) + LOG(tail) - LOG(1 - p0) - S * LOG(p0) - (n - S) * LOG(1 - p0)


def first_crossing(obs, logE, alpha):
    """First time the e-process reaches 1/alpha, or None."""
    thr = LOG(1 / alpha)
    S = 0
    for t, x in enumerate(obs, 1):
        S += x
        if logE(S, t) >= thr:
            return t
    return None


def false_alarm_rate(p, p0, runs, steps, alpha, seed, kind, qs=None):
    """Fraction of runs at rate p (<= p0) in which the e-process ever reaches 1/alpha."""
    rng = np.random.default_rng(seed)
    X = rng.random((runs, steps)) < p
    S = np.cumsum(X, axis=1)
    n = np.arange(1, steps + 1)
    if kind == "fixed":
        q = qs[0]
        logE = S * np.log(q / p0) + (n - S) * np.log((1 - q) / (1 - p0))
    elif kind == "finite":
        parts = [S * np.log(q / p0) + (n - S) * np.log((1 - q) / (1 - p0)) for q in qs]
        stack = np.stack(parts)
        m = np.max(stack, axis=0)
        logE = m + np.log(np.mean(np.exp(stack - m), axis=0))
    else:
        tail = betainc(n - S + 1, S + 1, 1 - p0)
        with np.errstate(divide="ignore"):
            logE = betaln(S + 1, n - S + 1) + np.log(tail) - np.log(1 - p0) - S * np.log(p0) \
                - (n - S) * np.log(1 - p0)
    return float(np.mean(np.max(logE, axis=1) >= np.log(1 / alpha)))


def detection_times(p, p0, runs, steps, alpha, seed, kind, qs=None):
    """Detection time per run (steps + 1 when there is no detection within the horizon)."""
    rng = np.random.default_rng(seed)
    X = rng.random((runs, steps)) < p
    S = np.cumsum(X, axis=1)
    n = np.arange(1, steps + 1)
    if kind == "fixed":
        q = qs[0]
        logE = S * np.log(q / p0) + (n - S) * np.log((1 - q) / (1 - p0))
    elif kind == "finite":
        parts = [S * np.log(q / p0) + (n - S) * np.log((1 - q) / (1 - p0)) for q in qs]
        stack = np.stack(parts)
        m = np.max(stack, axis=0)
        logE = m + np.log(np.mean(np.exp(stack - m), axis=0))
    else:
        tail = betainc(n - S + 1, S + 1, 1 - p0)
        with np.errstate(divide="ignore"):
            logE = betaln(S + 1, n - S + 1) + np.log(tail) - np.log(1 - p0) - S * np.log(p0) \
                - (n - S) * np.log(1 - p0)
    hit = logE >= np.log(1 / alpha)
    first = np.where(hit.any(axis=1), hit.argmax(axis=1) + 1, steps + 1)
    return first


def drift(p, p0, q):
    """Expected increment of the log e-value per observation at rate p for alternative q."""
    return p * LOG(q / p0) + (1 - p) * LOG((1 - q) / (1 - p0))


def upper_ends(p, alpha, nmax):
    """Upper ends of the confidence sequence at n = 1, ..., nmax when the observed number of events
    is p n rounded half up (computed exactly from the fraction p).  Vectorized bisection: the log
    mixture increases in the rate above S/n, so the upper end is the rate above S/n at which it
    reaches log(1/alpha)."""
    from fractions import Fraction
    q = Fraction(p).limit_denominator(10 ** 6)
    n = np.arange(1, nmax + 1, dtype=np.int64)
    S = (2 * n * q.numerator + q.denominator) // (2 * q.denominator)
    thr = LOG(1 / alpha)
    a = S / n
    b = np.ones(nmax)
    nf, Sf = n.astype(float), S.astype(float)
    base = betaln(Sf + 1, nf - Sf + 1)
    for _ in range(80):
        c = (a + b) / 2
        with np.errstate(divide="ignore", invalid="ignore"):
            lm = base - Sf * np.log(c) - (nf - Sf) * np.log1p(-c)
        below = lm < thr
        a = np.where(below, c, a)
        b = np.where(below, b, c)
    b[S == n] = 1.0
    return n, b


def sample_size(p, target, alpha, nmax=40000):
    """The number of events from which on the upper end of the confidence sequence stays at or
    below target when the observed number of events is p n rounded half up.  The upper end is not
    monotone in n because of the rounding, so this is one past the last n in 1..nmax at which the
    upper end exceeds target; the scan range must reach well past that point."""
    n, U = upper_ends(p, alpha, nmax)
    over = np.nonzero(U > target)[0]
    if len(over) == 0:
        return 1
    last = int(n[over[-1]])
    if last > nmax // 4:
        raise ValueError("scan range too short for this target")
    return last + 1


if __name__ == "__main__":
    print(cs_interval(3, 100, 0.05), cs_interval(0, 1000, 0.01), zero_failure_upper(1000, 0.01))
    print(coverage(0.05, 400, 2000, 0.05, 1))
    print(drift(0.1, 0.05, 0.2), drift(0.2, 0.05, 0.2))
    print(sample_size(0.05, 0.10, 0.01))


# ------------------------------------------------------------------ one-sided claims without a common rate
def one_sided_bound(p_star, alpha):
    """Part II, Proposition 5.1: for rows read in an order fixed before their labels, the
    probability that the upper end of the Beta(1,1) mixture sequence ever falls below p_star while
    the running average of the rows' conditional rates is at least p_star is at most
    p_star / (1/alpha - 1 + p_star)."""
    return p_star / (1 / alpha - 1 + p_star)


def one_sided_errors(p_star, alpha, runs, steps, seed, scheme):
    """Fraction of runs in which the upper end falls below p_star at some row although every
    conditional rate is at least p_star.  The event 'upper_n < p_star' is computed exactly as
    'S_n/n < p_star and log M_n(p_star) >= log(1/alpha)', since the sequence's interval at n
    contains S_n/n.  Schemes: 'common' (every rate p_star), 'spread' (each row's rate drawn
    independently from [p_star, 3 p_star]), 'runs' (rate p_star, but 0.9 right after a 1, so the
    labels come in runs)."""
    rng = np.random.default_rng(seed)
    thr = LOG(1 / alpha)
    u = rng.random((runs, steps))
    if scheme == "common":
        X = (u < p_star).astype(np.int64)
    elif scheme == "spread":
        X = (u < rng.uniform(p_star, 3 * p_star, (runs, steps))).astype(np.int64)
    elif scheme == "runs":
        X = np.zeros((runs, steps), dtype=np.int64)
        prev = np.zeros(runs, dtype=bool)
        for t in range(steps):
            rate = np.where(prev, 0.9, p_star)
            X[:, t] = u[:, t] < rate
            prev = X[:, t] == 1
    else:
        raise ValueError(scheme)
    S = np.cumsum(X, axis=1)
    n = np.arange(1, steps + 1)[None, :]
    logM = betaln(S + 1, n - S + 1) - S * np.log(p_star) - (n - S) * np.log(1 - p_star)
    below = (S < p_star * n) & (logM >= thr)
    return float(np.mean(below.any(axis=1)))
