"""Writes the two new frozen streams of Part II (run once; the files are stored as data).

  context_receipts_seed2.json   2,000 simulated context-block receipts: for each snapshot and each
                                policy, whether the fresh, open and anchor consumers were served
  stale_ten_seed1.json          2,000 simulated goal suggestions, stale with probability 1/10
"""
import hashlib
import json
import os
import random

import p2_live as P2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "streams")
POLICIES = ("recency", "relevance", "protected", "consumer")


def digest(path):
    return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()


def write(name, data):
    path = os.path.join(OUT, name + ".json")
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    return digest(path)


def receipts(n=2000, seed=2):
    log = P2.receipt_log(n, seed)
    schema = ["snapshot", "required_cost"] + [f"{p}_{k}" for p in POLICIES for k in P2.KINDS]
    rows = [[i + 1, r["required_cost"]] + [int(r[p][k]) for p in POLICIES for k in P2.KINDS]
            for i, r in enumerate(log)]
    prov = {"generator": "p2_live.receipt_log", "seed": seed, "snapshots": n, "items": 60, "budget": 1500,
            "note": "simulated workload; 1 = served, 0 = missed"}
    return write("context_receipts_seed2", {"schema": schema, "provenance": prov, "rows": rows})


def stale_ten(n=2000, seed=1, p=0.1):
    rng = random.Random(seed)
    rows = [[i + 1, int(rng.random() < p)] for i in range(n)]
    prov = {"generator": "random.Random", "seed": seed, "suggestions": n, "stale_probability": "1/10"}
    return write("stale_ten_seed1", {"schema": ["suggestion", "stale"], "provenance": prov, "rows": rows})


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("context_receipts_seed2", receipts())
    print("stale_ten_seed1", stale_ten())
