"""Pattern 4 on a live store: read sets at scale.

Results are derived from evidence items; each result records the set of items it read.  Withdrawing
an item makes every current result that read it stale until it is revalidated.  Two statistics
answer the restart question "which results need revalidation":
  index   evidence id -> ids of current results that read it (exact)
  bloom   one Bloom filter per result over its read set (conservative: no missed revalidation,
          some unnecessary ones, at a rate close to (1 - exp(-k n / m))^k)
"""
import hashlib
import math
import random


class Bloom:
    def __init__(self, m, k):
        self.m, self.k, self.bits = m, k, 0

    def _idx(self, x):
        h = hashlib.blake2b(str(x).encode(), digest_size=8 * self.k).digest()
        return [int.from_bytes(h[8 * i:8 * i + 8], "little") % self.m for i in range(self.k)]

    def add(self, x):
        for i in self._idx(x):
            self.bits |= 1 << i

    def __contains__(self, x):
        return all(self.bits >> i & 1 for i in self._idx(x))


def simulate(seed=1, n_evidence=100000, n_results=10000, min_reads=5, max_reads=50,
             withdrawals=2000, bits_per_item=10, k=7):
    rng = random.Random(seed)
    reads = {}
    index = {}
    blooms = {}
    for r in range(n_results):
        rs = set(rng.sample(range(n_evidence), rng.randint(min_reads, max_reads)))
        reads[r] = rs
        for e in rs:
            index.setdefault(e, set()).add(r)
        bf = Bloom(bits_per_item * len(rs), k)
        for e in rs:
            bf.add(e)
        blooms[r] = bf
    stale_true, stale_index, stale_bloom = set(), set(), set()
    fp_trials = fp_hits = 0
    for _ in range(withdrawals):
        e = rng.randrange(n_evidence)
        truly = {r for r, rs in reads.items() if e in rs}
        stale_true |= truly
        stale_index |= index.get(e, set())
        hit = {r for r, bf in blooms.items() if e in bf}
        stale_bloom |= hit
        fp_trials += n_results - len(truly)
        fp_hits += len(hit - truly)
    expected_fp = (1 - math.exp(-k / bits_per_item)) ** k
    return {"results": n_results, "evidence": n_evidence, "withdrawals": withdrawals,
            "index_exact": stale_index == stale_true,
            "bloom_missed": len(stale_true - stale_bloom),
            "bloom_unnecessary": len(stale_bloom - stale_true),
            "stale_true": len(stale_true), "flagged_total": len(stale_bloom),
            "fp_hits": fp_hits, "fp_trials": fp_trials,
            "fp_rate": fp_hits / fp_trials, "fp_expected": expected_fp}


if __name__ == "__main__":
    print(simulate(n_results=2000, withdrawals=500))
