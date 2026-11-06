"""Estimated claims: rates from receipt logs, paired comparison of policies, monitors on streams."""
import json
import os

import cs
import p2_live as P2

HERE = os.path.dirname(os.path.abspath(__file__))
PART1_STREAMS = os.path.join(HERE, "..", "streams")


def receipt_estimates(snapshots=2000, seed=2, alpha=0.01):
    log = P2.receipt_log(snapshots, seed)
    out = {"snapshots": snapshots, "alpha": alpha, "rates": {}, "paired": {}}
    for p in ("recency", "relevance", "protected", "consumer"):
        out["rates"][p] = {}
        for k in P2.KINDS:
            S = sum(1 for r in log if not r[p][k])
            lo, hi = cs.cs_interval(S, snapshots, alpha)
            out["rates"][p][k] = {"misses": S, "lo": lo, "hi": hi}
    # paired comparison for the anchor consumer: relevance against consumer-aware, on the same snapshots
    b = sum(1 for r in log if not r["relevance"]["A"] and r["consumer"]["A"])
    c = sum(1 for r in log if r["relevance"]["A"] and not r["consumer"]["A"])
    lo, hi = cs.cs_interval(b, b + c, alpha) if b + c else (0.0, 1.0)
    out["paired"] = {"relevance_misses_consumer_serves": b, "relevance_serves_consumer_misses": c,
                     "share_lo": lo, "share_hi": hi}
    out["max_required_cost"] = max(r["required_cost"] for r in log)
    return out


def load_stream(name):
    data = json.load(open(os.path.join(PART1_STREAMS, name + ".json")))
    col = data["schema"].index("stale")
    return [row[col] for row in data["rows"]]


def monitor_comparison(alpha=0.01, p0=0.05, runs=1000, steps=2000, seed=11):
    qs_fixed = [0.2]
    qs_finite = [0.1, 0.2, 0.4]
    out = {"drift_fixed_at": {}, "detect": {}, "false_alarm": {}}
    for p in (0.1, 0.2, 0.3):
        out["drift_fixed_at"][str(p)] = cs.drift(p, p0, 0.2)
    for p in (0.1, 0.2, 0.3):
        row = {}
        for kind, qs in (("fixed", qs_fixed), ("finite", qs_finite), ("uniform", None)):
            t = cs.detection_times(p, p0, runs, steps, alpha, seed, kind, qs)
            det = t <= steps
            row[kind] = {"detected": float(det.mean()),
                         "median": float(sorted(t)[len(t) // 2]) if det.mean() > 0.5 else None}
        out["detect"][str(p)] = row
    for kind, qs in (("fixed", qs_fixed), ("finite", qs_finite), ("uniform", None)):
        out["false_alarm"][kind] = cs.false_alarm_rate(p0, p0, 2000, steps, alpha, seed + 1, kind, qs)
    return out


def part1_streams(alpha=0.01, p0=0.05):
    out = {}
    for name in ("stale_alt_seed1", "stale_null_seed1"):
        obs = load_stream(name)
        S, n = sum(obs), len(obs)
        lo, hi = cs.cs_interval(S, n, alpha)
        out[name] = {"n": n, "stale": S, "lo": lo, "hi": hi,
                     "uniform_mixture_detect": cs.first_crossing(obs, lambda s, t: cs.log_e_uniform_mixture(s, t, p0), alpha),
                     "finite_mixture_detect": cs.first_crossing(obs, lambda s, t: cs.log_e_finite_mixture(s, t, p0, [0.1, 0.2, 0.4]), alpha),
                     "fixed_detect": cs.first_crossing(obs, lambda s, t: cs.log_e_fixed(s, t, p0, 0.2), alpha)}
    return out


def tables(alpha=0.01):
    zero = {str(n): {"anytime": cs.zero_failure_upper(n, alpha), "fixed_n": cs.clopper_pearson_zero_upper(n, alpha)}
            for n in (100, 1000, 10000, 100000)}
    sizes = {}
    for p, target in ((0.01, 0.02), (0.05, 0.10), (0.05, 0.075), (0.2, 0.25)):
        sizes[f"{p}->{target}"] = cs.sample_size(p, target, alpha)
    return {"zero_failure": zero, "sample_size": sizes}


if __name__ == "__main__":
    print(json.dumps(receipt_estimates(), indent=1)[:2000])
    print(json.dumps(part1_streams(), indent=1))
    print(json.dumps(tables(), indent=1))
    print(json.dumps(monitor_comparison(runs=300), indent=1))
