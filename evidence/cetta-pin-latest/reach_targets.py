#!/usr/bin/env python3
"""Print the make targets statically reachable (prerequisites, not recursive $(MAKE) calls) from the given goals.
usage (in cetta/): reach_targets.py <make args...> -- <goal...>"""
import re, subprocess, sys
i = sys.argv.index("--"); args, goals = sys.argv[1:i], sys.argv[i+1:]
db = subprocess.run(["make", "-pq", *args, ".mdinc-nothing"], capture_output=True, text=True).stdout
rules = {}
for line in db.splitlines():
    if line.startswith("#") or line.startswith("\t"):
        continue
    m = re.match(r"^([^\s:=#][^:=]*?):(?!=)\s*(.*)$", line)
    if m:
        for n in m.group(1).split():
            rules.setdefault(n, []).extend(m.group(2).split("|")[0].split())
seen, st = set(), list(goals)
while st:
    t = st.pop()
    if t in seen: continue
    seen.add(t); st.extend(rules.get(t, []))
print("\n".join(sorted(seen)))
