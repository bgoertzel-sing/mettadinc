#!/usr/bin/env python3
"""M1 acceptance 1, 2 and 5: package fixtures through dcalc.

1. `dcalc --admit` on every fixture file of the package (one universe): one
   row per module, Admitted or Unsupported (profile or library outside the
   first release); InvalidInput anywhere fails.
2. Every fixture file is evaluated twice (`dcalc FILE`); the outputs must be
   byte-identical (the diff is printed when they are not).
5. Every manifest claim marked release1=Unsupported must be answered
   Unsupported by its run.
Writes build/package/{rows.md,claims.md,run1/,run2/}.  Exit 1 on failure.
"""
import json, os, re, shutil, subprocess, sys, difflib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "docs/e0/docs/01_language_specification/validation_package")
FIX = os.path.join(PKG, "fixtures")
DCALC = os.environ.get("DCALC", os.path.join(ROOT, "build/dcalc/dcalc"))
OUT = os.path.join(ROOT, "build/package")


def norm(s):
    return " ".join(s.replace("(", " ( ").replace(")", " ) ").split())


def main():
    shutil.rmtree(OUT, True); os.makedirs(OUT)
    files = sorted(f for f in os.listdir(FIX) if f.endswith(".metta"))
    bad = 0
    adm = subprocess.run([DCALC, "--admit"] + [os.path.join(FIX, f) for f in files],
                         capture_output=True, text=True, timeout=60)
    rows = [l.split(" ", 4) for l in adm.stdout.splitlines() if l.startswith("module ")]
    diags = [l for l in adm.stdout.splitlines() if l.startswith("diag ")]
    reg = [l.split()[1] for l in adm.stdout.splitlines() if l.startswith("registry ")]
    with open(os.path.join(OUT, "rows.md"), "w") as f:
        f.write("registry %s\n\n| module | verdict | reason |\n|---|---|---|\n" % (reg[0] if reg else "?"))
        for r in rows:
            f.write("| %s | %s | %s |\n" % (r[1], r[2], r[4] if len(r) > 4 else ""))
    nver = {}
    for r in rows: nver[r[2]] = nver.get(r[2], 0) + 1
    if adm.returncode != 0 or diags or "InvalidInput" in nver:
        print("FAIL admission: rc=%d, %d diagnostics" % (adm.returncode, len(diags))); bad += 1
        for d in diags[:10]: print("  " + d)
    print("admission: %d modules %s" % (len(rows), nver))
    outs = {}
    for run in ("run1", "run2"):
        os.makedirs(os.path.join(OUT, run))
        for fn in files:
            p = subprocess.run([DCALC, os.path.join(FIX, fn)], capture_output=True, timeout=120)
            open(os.path.join(OUT, run, fn + ".out"), "wb").write(p.stdout + b"--stderr--\n" + p.stderr)
            outs.setdefault(fn, []).append(p.stdout + p.stderr)
    ndiff = 0
    for fn in files:
        a, b = outs[fn]
        if a != b:
            ndiff += 1; bad += 1
            print("FAIL %s differs between runs:" % fn)
            for l in list(difflib.unified_diff(a.decode().splitlines(), b.decode().splitlines(), lineterm=""))[:20]: print("  " + l)
    print("serialization: %d files, two runs, %d differ" % (len(files), ndiff))
    claims = json.load(open(os.path.join(PKG, "manifest.json")))["claims"]
    lines = {}
    for fn in files:
        for l in outs[fn][0].decode().splitlines():
            if " => " in l:
                h, env = l.split(" => ", 1)
                mod, rq = h.split(" ", 1)
                m = re.search(r"\(Status ([A-Za-z]+)\)", env)
                lines[(fn, mod, norm(rq))] = m.group(1) if m else "?"
    cnt, miss = {}, 0
    with open(os.path.join(OUT, "claims.md"), "w") as f:
        f.write("| claim | module | request | release1 | dcalc status | result |\n|---|---|---|---|---|---|\n")
        for c in claims:
            st = lines.get((c["fixture"], c["module"], norm(c["request"])))
            if st is None: miss += 1
            ok = True
            if c["release1"] == "Unsupported": ok = st == "Unsupported"
            if not ok: bad += 1; print("FAIL %s %s: release1 Unsupported, dcalc %s" % (c["id"], c["request"][:60], st))
            k = (c["release1"], st); cnt[k] = cnt.get(k, 0) + 1
            f.write("| %s | %s | `%s` | %s | %s | %s |\n" % (c["id"], c["module"], c["request"], c["release1"], st, "PASS" if ok else "FAIL"))
    print("claims: %d, (release1, dcalc status) counts %s, %d without a run line" % (len(claims), sorted(cnt.items(), key=str), miss))
    print("package: %s" % ("PASS" if not bad else "FAIL (%d)" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
