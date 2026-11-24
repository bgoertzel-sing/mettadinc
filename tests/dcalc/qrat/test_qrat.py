#!/usr/bin/env python3
"""Unit test for src/dcalc/qrat.c (D1): random add/sub/mul/div/cmp on rationals
from tiny to ~600-bit, checked exactly against Python fractions, in both the
normal mode (int64 fast path + bignum fallback) and the forced-bignum mode.
usage: test_qrat.py DRIVER [N]   prints QRAT: PASS/FAIL, exit 0 on PASS."""
import random, subprocess, sys
from fractions import Fraction as F
drv = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
rnd = random.Random(20261124)
EDGE = [0, 1, -1, 2**31 - 1, 2**32, 2**63 - 1, -(2**63 - 1), 2**63, 2**64 + 1, 2**127 - 1, 2**128]
def rint():
    k = rnd.random()
    if k < 0.15: return rnd.choice(EDGE)
    bits = rnd.choice([3, 20, 40, 62, 63, 64, 65, 100, 127, 128, 129, 200, 600])
    v = rnd.getrandbits(bits)
    return -v if rnd.random() < 0.4 else v
def rq():
    d = 0
    while d == 0: d = abs(rint())
    return F(rint(), d)
def s(q): return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"
lines, want = [], []
for _ in range(N):
    op = rnd.choice(["add", "sub", "mul", "div", "cmp"]); a, b = rq(), rq()
    if op == "div" and b == 0: b = F(1)
    lines.append(f"{op} {s(a)} {s(b)}")
    r = {"add": lambda: s(a + b), "sub": lambda: s(a - b), "mul": lambda: s(a * b),
         "div": lambda: s(a / b), "cmp": lambda: str((a > b) - (a < b))}[op]()
    want.append(r)
lines.append("div 1 0"); want.append("OVF1")
bad = 0
for mode in ([], ["big"]):
    out = subprocess.run([drv] + mode, input="\n".join(lines) + "\n", capture_output=True, text=True, timeout=120).stdout.split("\n")
    for i, w in enumerate(want):
        got = out[i] if i < len(out) else "<missing>"
        if got != w:
            bad += 1
            if bad <= 5: print(f"MISMATCH mode={mode or ['normal']} line={lines[i][:120]} want={w[:60]} got={got[:60]}")
print(f"QRAT: {'PASS' if bad == 0 else 'FAIL'} ({len(want)} cases x 2 modes, {bad} mismatches)")
sys.exit(1 if bad else 0)
