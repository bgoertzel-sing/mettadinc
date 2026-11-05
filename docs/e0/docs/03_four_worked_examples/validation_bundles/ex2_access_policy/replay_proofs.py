#!/usr/bin/env python3
"""Replays the unsatisfiability proofs shipped with a worked-example bundle.

The archive exN_obligations.tar.xz holds, for every unsatisfiable obligation of the example, the
CNF that the oracle generated and the DRAT proof that CaDiCaL 1.5.3 wrote, together with index.json,
which lists each obligation's name, claim and CNF digest and the digest of the module file the
obligations were built from.  Satisfiable obligations are not in the archive: their models are
counterexamples or solutions, and the oracle replays those by evaluation.

The script needs neither python-sat nor the oracle.  It extracts the archive into a temporary
directory, compares the module digest with the module file given, checks the digest of every CNF,
converts each DRAT proof to LRAT with drat-trim and checks the LRAT proof with cake_lpr:

    drat-trim obligation.cnf obligation.drat -L obligation.lrat
    cake_lpr --CML_HEAP_SIZE=1024 --CML_STACK_SIZE=512 obligation.cnf obligation.lrat

Run: MDINC_TOOLS=/path/to/tools python3 replay_proofs.py exN_obligations.tar.xz MODULE.metta
     (MDINC_TOOLS holds drat-trim/drat-trim and cake_lpr/cake_lpr)
"""
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile

FLAGS = ["--CML_HEAP_SIZE=1024", "--CML_STACK_SIZE=512"]


def sha_file(path):
    return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    archive, module = sys.argv[1], sys.argv[2]
    tools = os.environ.get("MDINC_TOOLS", "")
    drat_trim = os.path.join(tools, "drat-trim", "drat-trim")
    cake = os.path.join(tools, "cake_lpr", "cake_lpr")
    if not (os.path.exists(drat_trim) and os.path.exists(cake)):
        sys.exit("set MDINC_TOOLS to a directory holding drat-trim/drat-trim and cake_lpr/cake_lpr")
    failures, verified, total = [], 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archive, "r:xz") as tar:
            for m in tar.getmembers():
                if m.name.startswith("/") or ".." in m.name.split("/") or not (m.isfile() or m.isdir()):
                    sys.exit(f"refusing archive member {m.name}")
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:                      # Python before 3.11.4 has no extraction filters
                tar.extractall(tmp)
        indexes = sorted(os.path.join(d, f) for d, _, fs in os.walk(tmp) for f in fs if f == "index.json")
        for ix in indexes:
            meta = json.load(open(ix))
            base = os.path.dirname(ix)
            rel = os.path.relpath(base, tmp)
            if "mutation" not in meta:
                if meta.get("module_digest") != sha_file(module):
                    failures.append(f"{rel}: the obligations were built from {meta.get('module_digest')}, "
                                    f"not from {module}")
                    continue
            for ob in meta["obligations"]:
                if ob["sat"] or "drat_lines" not in ob:
                    continue
                total += 1
                cnf = os.path.join(base, ob["name"] + ".cnf")
                drat = os.path.join(base, ob["name"] + ".drat")
                lrat = os.path.join(base, ob["name"] + ".lrat")
                if sha_file(cnf) != ob["cnf"]:
                    failures.append(f"{rel}/{ob['name']}: CNF digest mismatch")
                    continue
                p = subprocess.run([drat_trim, cnf, drat, "-L", lrat], capture_output=True, text=True)
                q = subprocess.run([cake] + FLAGS + [cnf, lrat], capture_output=True, text=True)
                verdict = (q.stdout.strip().splitlines() or [""])[-1]
                ok = any(line.strip() == "s VERIFIED" for line in p.stdout.splitlines()) and verdict == "s VERIFIED UNSAT"
                if ok:
                    verified += 1
                else:
                    failures.append(f"{rel}/{ob['name']}: {verdict or q.stderr.strip()[-80:]}")
                os.remove(lrat)
    for f in failures:
        print("FAIL " + f)
    print(f"{verified} of {total} proofs verified (drat-trim, cake_lpr)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
