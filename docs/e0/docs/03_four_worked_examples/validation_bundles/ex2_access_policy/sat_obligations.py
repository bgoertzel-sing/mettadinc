import os, subprocess, time, json, sys
from pysat.solvers import Solver
from circuits import *

TOOLS = os.environ.get("MDINC_TOOLS", "")   # directory holding drat-trim/ and cake_lpr/; set by the oracle
OUT = "obligations"
os.makedirs(OUT, exist_ok=True)


def solve(clauses, nvars, name, check_proof=True):
    s = Solver(name="cadical153", with_proof=True, bootstrap_with=clauses)
    t0 = time.time(); sat = s.solve(); t1 = time.time()
    res = {"name": name, "vars": nvars, "clauses": len(clauses), "sat": sat, "solve_s": round(t1 - t0, 4)}
    if sat:
        res["model"] = s.get_model()
    else:
        proof = s.get_proof()
        cnf = os.path.join(OUT, name + ".cnf"); drat = os.path.join(OUT, name + ".drat"); lrat = os.path.join(OUT, name + ".lrat")
        with open(cnf, "w") as f:
            f.write(f"p cnf {nvars} {len(clauses)}\n")
            for cl in clauses:
                f.write(" ".join(map(str, cl)) + " 0\n")
        with open(drat, "w") as f:
            f.write("\n".join(proof) + "\n")
        res["drat_lines"] = len(proof)
        if check_proof:
            p = subprocess.run([f"{TOOLS}/drat-trim/drat-trim", cnf, drat, "-L", lrat], capture_output=True, text=True)
            res["drat_trim"] = "s VERIFIED" in p.stdout
            q = subprocess.run([f"{TOOLS}/cake_lpr/cake_lpr", "--CML_HEAP_SIZE=1024", "--CML_STACK_SIZE=512", cnf, lrat],
                               capture_output=True, text=True)
            res["cake_lpr"] = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else q.stderr.strip()[-80:]
            res["lrat_lines"] = sum(1 for _ in open(lrat))
    s.delete()
    return res


def closure_obligations(written, inv_name, inv_enc, nu=NU):
    out = []
    P = Policy(written=written, nu=nu)
    for a in P.actions:
        c = CNF()
        x = c.inputs(10 * nu)
        y = enc_step(c, x, a, written, nu)
        ix = inv_enc(c, x, nu); iy = inv_enc(c, y, nu)
        c.clauses.append([ix]); c.clauses.append([-iy])
        tag = f"{'written' if written else 'fixed'}_{inv_name}_{a[0]}_{USERS[a[1]]}_{ROLES[a[2]]}"
        out.append((a, c, tag))
    return out


if __name__ == "__main__":
    summary = {}
    for written, inv_name, inv_enc in ((False, "consistent", enc_consistent), (False, "nosod", enc_no_sod),
                                       (False, "noclerkless", enc_no_clerkless), (True, "consistent", enc_consistent)):
        results = []
        t0 = time.time()
        for a, c, tag in closure_obligations(written, inv_name, inv_enc):
            r = solve(c.clauses, c.n, tag, check_proof=not written)
            r["action"] = label(a)
            if r["sat"]:
                m = set(v for v in r["model"] if v > 0)
                r["cti"] = sum(1 << i for i in range(W) if (i + 2) in m)   # inputs are vars 2..41
                del r["model"]
            results.append(r)
        unsat = [r for r in results if not r["sat"]]
        sat = [r for r in results if r["sat"]]
        key = f"{'written' if written else 'fixed'}|{inv_name}"
        summary[key] = {"unsat": len(unsat), "sat": len(sat), "seconds": round(time.time() - t0, 1),
                        "max_vars": max(r["vars"] for r in results), "max_clauses": max(r["clauses"] for r in results),
                        "proof_lines": sum(r.get("drat_lines", 0) for r in unsat),
                        "all_verified": all(r.get("cake_lpr") == "s VERIFIED UNSAT" for r in unsat) if not written else None,
                        "sat_actions": [(r["action"], r["cti"]) for r in sat]}
        print(key, json.dumps(summary[key])[:600])
    json.dump(summary, open("sat_summary.json", "w"), indent=1)
