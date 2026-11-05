"""Pattern 8: monitoring the goal engine on a recorded stream.

Each goal suggestion is labelled stale (1) if the item it concerns had already been closed by an
event before the suggestion was made, else 0.  The label is computed from the event log, so no
human rating is needed.  Null: stale with probability 1/20 (the rate the release was accepted at).
Alternative: 1/5 (the failure mode of the first live review).  The likelihood-ratio factor is 4 for
a stale suggestion and 16/19 for a fresh one; the product is a nonnegative martingale with mean one
under the null, and Ville's inequality bounds the chance it ever reaches 1/alpha by alpha.
"""
import hashlib
import json
import math
import os
import random
from fractions import Fraction as F

P0 = F(1, 20)
P1 = F(1, 5)
FACTOR = {1: P1 / P0, 0: (1 - P1) / (1 - P0)}
HERE = os.path.dirname(os.path.abspath(__file__))
STREAMS = os.path.join(HERE, "..", "streams")


def validity():
    return P0 * FACTOR[1] + (1 - P0) * FACTOR[0]


def kl_nats():
    p, q = float(P1), float(P0)
    return p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))


def simulate(p, n, seed):
    rng = random.Random(seed)
    return [1 if rng.random() < float(p) else 0 for _ in range(n)]


def write_streams():
    os.makedirs(STREAMS, exist_ok=True)
    out = {}
    for name, p in (("stale_alt_seed1", P1), ("stale_null_seed1", P0)):
        obs = simulate(p, 400, 1)
        data = {"schema": ["suggestion", "stale"],
                "provenance": {"generator": "p8_monitor.simulate", "stale_probability": str(p),
                               "suggestions": 400, "seed": 1},
                "rows": [[i + 1, x] for i, x in enumerate(obs)]}
        path = os.path.join(STREAMS, name + ".json")
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        out[name] = digest(path)
    return out


def load(name):
    data = json.load(open(os.path.join(STREAMS, name + ".json")))
    col = data["schema"].index("stale")
    return [row[col] for row in data["rows"]]


def digest(path):
    return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()


def detect(obs, alpha=F(1, 100)):
    e = F(1)
    for t, x in enumerate(obs, 1):
        e *= FACTOR[x]
        if e >= 1 / alpha:
            return {"fired": True, "step": t, "stale": sum(obs[:t]), "evalue": e}
    return {"fired": False, "steps": len(obs), "final": e, "max": None}


def max_evalue(obs):
    e = F(1)
    best = e
    for x in obs:
        e *= FACTOR[x]
        best = max(best, e)
    return best


def results():
    out = {"validity": validity(), "kl": kl_nats(), "wald": math.log(100) / kl_nats()}
    for name in ("stale_alt_seed1", "stale_null_seed1"):
        path = os.path.join(STREAMS, name + ".json")
        obs = load(name)
        out[name] = {"digest": digest(path), "detect": detect(obs), "stale": sum(obs),
                     "max": max_evalue(obs)}
    return out


if __name__ == "__main__":
    if not os.path.exists(os.path.join(STREAMS, "stale_alt_seed1.json")) or "--write" in __import__("sys").argv:
        print(write_streams())
    r = results()
    for k, v in r.items():
        print(k, v)
