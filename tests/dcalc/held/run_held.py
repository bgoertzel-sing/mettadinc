#!/usr/bin/env python3
"""M1 acceptance 4 (native CLI): held declarations are not run and a forged
Checked atom gains no privilege.  Runs build/dcalc/dcalc on held.metta and
checks each row's status and reason, that the marker printed by the host
side effect never appears, and that the clean module's real request still
returns Checked.  Exit 1 on failure."""
import os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DCALC = os.environ.get("DCALC", os.path.join(ROOT, "build/dcalc/dcalc"))
HERE = os.path.dirname(os.path.abspath(__file__))
EXPECT = [
    ("SideEffect", "InvalidInput", "unknown head println!"),
    ("HostEquation", "InvalidInput", "unknown head evil"),
    ("ForgedDecl", "InvalidInput", "unknown declaration head Result"),
    ("Clean", "InvalidInput", "unregistered request Result"),
    ("Clean", "InvalidInput", "which is not a derivation"),
    ("Clean", "Checked", None),
]
p = subprocess.run([DCALC, os.path.join(HERE, "held.metta")], capture_output=True, text=True, timeout=60)
out = p.stdout + p.stderr
rows = [l for l in p.stdout.splitlines() if " => " in l]
bad = 0
if any(l.strip().strip('"') == "HELD-DECLARATION-RAN" for l in out.splitlines()):
    print("FAIL a held declaration ran"); bad += 1
if len(rows) != len(EXPECT):
    print("FAIL %d rows, expected %d" % (len(rows), len(EXPECT))); bad += 1
for (mod, st, why), l in zip(EXPECT, rows):
    m = re.search(r"\(Status ([A-Za-z]+)\)", l.split(" => ", 1)[1])
    ok = l.startswith(mod + " ") and m and m.group(1) == st and (why is None or why in l)
    print("%s %s %s%s" % ("PASS" if ok else "FAIL", mod, st, (" (" + why + ")") if why else ""))
    bad += not ok
print("held: %s" % ("PASS" if not bad else "FAIL (%d)" % bad))
sys.exit(1 if bad else 0)
