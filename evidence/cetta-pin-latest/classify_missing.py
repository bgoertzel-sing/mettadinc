#!/usr/bin/env python3
"""Classify the test lines that were PASS at 12da03b4 (E0's frozen logs) and are not PASS in a 4c285a97 run.

usage: classify_missing.py <cetta-dir> <lane> <e0-log> <new-log> <reachable-targets-file> [<rhocalc-e0-log>]
Prints a TSV: lane, normalised line, category, detail.  Standard library + git only.
Categories:
  now-skip            the same test prints a SKIP line in the new run (the reason is in the detail)
  rhocalc-suite       the line is one of the rhocalc suite's (E0's 07 log); test-rhocalc is no longer reached from
                      test-correctness at 4c285a97, and its own lane stops before any test (see the rhocalc lane)
  gone-upstream       the test's text/file is in the 12da03b4 tree and not in the 4c285a97 tree (removed or renamed)
  not-reached:<tgt>   still defined at 4c285a97 in Makefile target <tgt>, which is not reached from the lane's goals
  reached:<tgt>       defined in a target that is reached, but its PASS line is absent (investigate: blocked or failed)
  unlocated           text found at 4c285a97 but not attributable to one Makefile target (generated or composed)
"""
import collections, re, subprocess, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from cetta_baseline_check import parse  # noqa: E402

OLD, NEW = "12da03b4b055bfecff2add505e7e1ad4125bb352", "4c285a97fd8c60e3c3fccd5ccd3b3e5e0ebccb4c"
cetta, lane, e0log, newlog, reachf = sys.argv[1:6]
rholog = sys.argv[6] if len(sys.argv) > 6 else None
reach = set(open(reachf).read().split())
old, new = parse(e0log, cetta), parse(newlog, cetta)
rho = parse(rholog, cetta)["PASS"] if rholog else collections.Counter()
missing = old["PASS"] - new["PASS"]

def frag(line):
    body = line.split(":", 1)[1].strip() if ":" in line else line
    parts = [p.strip() for p in re.split(r"N|<CETTA>", body) if len(p.strip()) >= 6]
    return max(parts, key=len) if parts else body

def git_grep(rev, s):
    r = subprocess.run(["git", "-C", cetta, "grep", "-l", "-F", "-e", s, rev, "--"], capture_output=True, text=True)
    return [l.split(":", 1)[1] for l in r.stdout.splitlines()]

def path_of(line):
    m = re.match(r"^PASS:?\s+((?:tests|examples|lib|langdef|experiments)/\S+)", line)
    return m.group(1) if m else None

def exists(rev, p):
    return subprocess.run(["git", "-C", cetta, "cat-file", "-e", f"{rev}:{p}"], capture_output=True).returncode == 0

mk = open(os.path.join(cetta, "Makefile"), errors="replace").read().splitlines()
TGT = re.compile(r"^([A-Za-z0-9_.%/$()-][^:=\s]*)\s*:(?!=)")
def targets_with(s):
    out = []
    for i, l in enumerate(mk):
        if s in l:
            for j in range(i, -1, -1):
                m = TGT.match(mk[j])
                if m and not mk[j].startswith("\t"):
                    out.append(m.group(1)); break
    return sorted(set(out))

newskip = {}
for l in new["SKIP"]:
    p = path_of("PASS: " + l.split(":", 1)[1].strip()) if ":" in l else None
    if p: newskip[p] = l
for line, n in sorted(missing.items()):
    p = path_of(line)
    if p and p in newskip:
        cat, det = "now-skip", newskip[p]
    elif line in rho and lane != "rhocalc":
        cat, det = "rhocalc-suite", "also printed by test-rhocalc at 12da03b4"
    else:
        f = frag(line)
        if p:
            o, nw = exists(OLD, p), exists(NEW, p)
            if o and not nw:
                cat, det = "gone-upstream", f"file {p} removed or renamed"
                print(f"{lane}\t{line}\t{cat}\t{det}\tx{n}"); continue
            f = p
        inold, innew = git_grep(OLD, f), git_grep(NEW, f)
        if inold and not innew:
            cat, det = "gone-upstream", f"text '{f}' in {','.join(inold[:2])} at 12da03b4, nowhere at 4c285a97"
        elif innew:
            ts = targets_with(f)
            if ts:
                r = [t for t in ts if t in reach]
                cat = ("reached:" + ",".join(r)) if r else ("not-reached:" + ",".join(ts[:3]))
                det = f"Makefile; files {','.join(innew[:2])}"
            else:
                cat, det = "unlocated", f"text '{f}' in {','.join(innew[:3])}"
        else:
            cat, det = "unlocated", f"text '{f}' found in neither tree by git grep"
    print(f"{lane}\t{line}\t{cat}\t{det}\tx{n}")
