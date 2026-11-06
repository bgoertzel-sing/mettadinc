#!/usr/bin/env python3
"""Count table and new SKIP/FAIL list for t-2026-11-06-mettadinc-cetta-pin-latest.
usage: new_skips.py <cetta-dir> <lane>=<e0-log>=<new-log> ...  -> prints counts, writes analysis/new-skips-<lane>.tsv"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from cetta_baseline_check import parse
cetta = sys.argv[1]; here = os.path.dirname(os.path.abspath(__file__))
for spec in sys.argv[2:]:
    lane, e0, new = spec.split("=")
    o, n = parse(e0, cetta), parse(new, cetta)
    miss = o["PASS"] - n["PASS"]; extra = n["PASS"] - o["PASS"]
    nskip = n["SKIP"] - o["SKIP"]; nfail = n["FAIL"] - o["FAIL"]; ntgt = n["targets"] - o["targets"]
    print(f"{lane}: 12da03b4 PASS {o['npass']} SKIP {sum(o['SKIP'].values())} FAIL {sum(o['FAIL'].values())} "
          f"targets {dict(o['targets'])} exit {o['exit']} final {o['final']}")
    print(f"{lane}: 4c285a97 PASS {n['npass']} SKIP {sum(n['SKIP'].values())} FAIL {sum(n['FAIL'].values())} "
          f"targets {dict(n['targets'])} exit {n['exit']} final {n['final']}")
    print(f"{lane}: E0 PASS lines not PASS now {sum(miss.values())}; new PASS lines {sum(extra.values())}; "
          f"new SKIP {sum(nskip.values())}; new FAIL {sum(nfail.values())}; new failed targets {dict(ntgt)}")
    allold = set(o["PASS"])
    with open(os.path.join(here, "analysis", f"new-skips-{lane}.tsv"), "w") as f:
        f.write("lane\tnew SKIP line (normalised)\treason\twas-PASS-at-12da03b4\n")
        reasons = {}
        for line, k in sorted(nskip.items()):
            m = re.match(r"^SKIP:?\s*(\S+)\s*\((.*)\)\s*$", line)
            test, why = (m.group(1), m.group(2)) if m else (line, "")
            was = "yes" if ("PASS: " + test) in allold else "no"
            reasons[(why, was)] = reasons.get((why, was), 0) + k
            f.write(f"{lane}\t{line}\t{why}\t{was}\n")
    for (why, was), k in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"   new SKIP x{k}: reason '{why}', was PASS at 12da03b4: {was}")
