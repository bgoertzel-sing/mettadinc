#!/usr/bin/env python3
"""Rhocalc lane at 4c285a97 (with SWI-Prolog) against E0's 12da03b4 rhocalc log, by name.

usage: rhocalc_diff.py <new 04_test_rhocalc.log> [<cetta dir>]
Uses tools/cetta_baseline_check.py's parser and normalisation (digits -> N, Cetta path -> <CETTA>).
Prints counts for both, the "<n> passed, <m> failed" summary lines, and the PASS/SKIP/FAIL lines and failed
make targets present in one log and not the other (multiset difference)."""
import os, re, sys
here = os.path.dirname(os.path.abspath(__file__))
repo = os.path.dirname(os.path.dirname(here))
sys.path.insert(0, os.path.join(repo, "tools"))
import cetta_baseline_check as c

OLD = os.path.join(repo, "docs/e0/evidence/cetta/07_test_rhocalc.log")
new = sys.argv[1]
cetta = sys.argv[2] if len(sys.argv) > 2 else os.path.join(repo, "cetta")
o, n = c.parse(OLD), c.parse(new, cetta)
def finals(p):
    return [l.strip() for l in open(p, errors="replace") if c.FINAL_RE.match(l.strip())]
for name, s, p in (("12da03b4 (E0)", o, OLD), ("4c285a97", n, new)):
    print(f"{name}: PASS {s['npass']} SKIP {sum(s['SKIP'].values())} FAIL {sum(s['FAIL'].values())} "
          f"failed-targets {sum(s['targets'].values())} exit {s['exit']}; summary lines: {finals(p)}")
# Pair PASS lines that differ only by the word "surface" becoming "syntax" (a rename upstream).
gone, added = o["PASS"] - n["PASS"], n["PASS"] - o["PASS"]
pairs = [(l, l.replace("surface", "syntax")) for l in sorted(gone) if "surface" in l and l.replace("surface", "syntax") in added]
print(f"\nPASS lines renamed only by 'surface' -> 'syntax' (counted in both lists below): {len(pairs)}")
print(f"PASS lines gone, not explained by that rename: {sum(gone.values()) - len(pairs)}")
print(f"PASS lines new, not explained by that rename: {sum(added.values()) - len(pairs)}")
for k in ("PASS", "SKIP", "FAIL", "targets"):
    gone, added = o[k] - n[k], n[k] - o[k]
    print(f"\n## {k}: in 12da03b4 and not in 4c285a97 ({sum(gone.values())})")
    renamed_old = {a for a, _ in pairs} if k == "PASS" else set()
    renamed_new = {b for _, b in pairs} if k == "PASS" else set()
    for l, m in sorted(gone.items()):
        print(f"- {l}" + (f" (x{m})" if m > 1 else "") + ("   [renamed: surface -> syntax]" if l in renamed_old else ""))
    print(f"\n## {k}: in 4c285a97 and not in 12da03b4 ({sum(added.values())})")
    for l, m in sorted(added.items()):
        print(f"+ {l}" + (f" (x{m})" if m > 1 else "") + ("   [renamed: surface -> syntax]" if l in renamed_new else ""))
