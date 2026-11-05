"""Example 2: proof obligations built from the source's intermediate form, and the proof pipeline.

Every obligation is generated from policy_ir: a CNF over the input bits of one or two words,
produced by the Tseitin encoder from the elaborated maps of access_policy.metta.  The solver is
CaDiCaL 1.5.3 through python-sat, which also writes a DRAT proof of every unsatisfiable obligation.
When drat-trim and cake_lpr are found (MDINC_TOOLS names a directory holding drat-trim/drat-trim and
cake_lpr/cake_lpr), each proof is converted to LRAT by drat-trim and checked by cake_lpr.

Assurance (the package's policy for Checked): a result that rests on unsatisfiable obligations is
Checked when every one of their proofs was replayed by cake_lpr; otherwise it is Conditional, with
the assumption (TrustedBackend cadical 1.5.3 SAT <digest>), where the digest is that of the sorted
list of the obligations' CNF digests.  A satisfiable obligation is never evidence by itself: its
model is a counterexample to induction or a candidate witness, and the oracle replays every
witness by evaluating the source.
"""
import hashlib
import json
import os
import subprocess

from pysat.solvers import Solver

from policy_ir import CNF

TOOLS = os.environ.get("MDINC_TOOLS", "")
SOLVER = ("cadical", "1.5.3")
CAKE_FLAGS = ["--CML_HEAP_SIZE=1024", "--CML_STACK_SIZE=512"]


def tools_found(tools=TOOLS):
    return bool(tools) and os.path.exists(os.path.join(tools, "drat-trim", "drat-trim")) and \
        os.path.exists(os.path.join(tools, "cake_lpr", "cake_lpr"))


def sha(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def replay(tools, cnf_path, drat_path, lrat_path):
    """DRAT -> LRAT with drat-trim, then cake_lpr on the LRAT file.  Returns (drat_trim_ok, verdict)."""
    p = subprocess.run([os.path.join(tools, "drat-trim", "drat-trim"), cnf_path, drat_path, "-L", lrat_path],
                       capture_output=True, text=True)
    ok = any(line.strip() == "s VERIFIED" for line in p.stdout.splitlines())
    q = subprocess.run([os.path.join(tools, "cake_lpr", "cake_lpr")] + CAKE_FLAGS + [cnf_path, lrat_path],
                       capture_output=True, text=True)
    out = q.stdout.strip().splitlines()
    return ok, (out[-1] if out else q.stderr.strip()[-80:])


class Discharger:
    """Solves obligations, writes each CNF and DRAT proof, replays the proofs when the tools are
    there, and keeps an index (name, claim, CNF digest, size, answer, replay verdicts)."""

    def __init__(self, out="obligations", tools=TOOLS, keep_files=True):
        self.out, self.tools, self.keep = out, tools, keep_files
        self.replay = tools_found(tools)
        self.index = []
        if keep_files:
            os.makedirs(out, exist_ok=True)

    def solve(self, cnf, name, claim, proof=True):
        dimacs = cnf.dimacs()
        rec = {"name": name, "claim": claim, "vars": cnf.n, "clauses": len(cnf.clauses), "cnf": sha(dimacs)}
        s = Solver(name="cadical153", with_proof=proof, bootstrap_with=cnf.clauses)
        rec["sat"] = s.solve()
        model = s.get_model() if rec["sat"] else None
        if not rec["sat"] and proof:
            lines = s.get_proof()
            rec["drat_lines"] = len(lines)
            if self.keep:
                base = os.path.join(self.out, name)
                with open(base + ".cnf", "w") as f:
                    f.write(dimacs)
                with open(base + ".drat", "w") as f:
                    f.write("\n".join(lines) + "\n")
                if self.replay:
                    rec["drat_trim"], rec["cake_lpr"] = replay(self.tools, base + ".cnf", base + ".drat", base + ".lrat")
                    os.remove(base + ".lrat")
        s.delete()
        rec["replayed"] = bool(rec.get("drat_trim")) and rec.get("cake_lpr") == "s VERIFIED UNSAT"
        self.index.append(dict(rec))
        rec["model"] = model
        return rec

    def write_index(self, extra=None):
        if self.keep:
            with open(os.path.join(self.out, "index.json"), "w") as f:
                json.dump({"solver": list(SOLVER), "replayed_with": "drat-trim -L, cake_lpr " + " ".join(CAKE_FLAGS)
                           if self.replay else None, "obligations": self.index, **(extra or {})}, f, indent=1)


def assurance(records):
    """D2 status of a result that rests on these unsatisfiable obligations."""
    if all(r["replayed"] for r in records):
        return {"status": "Checked", "assumptions": [], "proofs_replayed": len(records)}
    digest = sha("\n".join(sorted(r["cnf"] for r in records)))
    return {"status": "Conditional", "proofs_replayed": sum(r["replayed"] for r in records),
            "assumptions": [f"(TrustedBackend {SOLVER[0]} {SOLVER[1]} SAT {digest})"]}


# ------------------------------------------------------------------------------------ obligations
def xor(c, a, b):
    return -c.AND([-c.AND([a, -b]), -c.AND([-a, b])])


def step_lits(c, pol, a, xin):
    memo = {}
    return [c.lit(b, xin, memo) for b in pol.bits[a]]


def closure(pol, inv, a):
    """inv(x) and not inv(T_a x): unsatisfiable when inv is closed under action a."""
    c = CNF(pol.ir)
    x = c.inputs(pol.el.width)
    y = step_lits(c, pol, a, x)
    ix = c.lit(inv, x, {})
    iy = c.lit(inv, y, {})
    c.assert_lit(ix)
    c.assert_lit(-iy)
    return c, x


def implication(ir, width, p, q):
    """p(x) and not q(x): unsatisfiable when p implies q."""
    c = CNF(ir)
    x = c.inputs(width)
    memo = {}
    c.assert_lit(c.lit(p, x, memo))
    c.assert_lit(-c.lit(q, x, memo))
    return c, x


def miter(pol, keep, a):
    """Two words that agree on the bits in keep, whose successors under a disagree on them."""
    c = CNF(pol.ir)
    x, xp = c.inputs(pol.el.width), c.inputs(pol.el.width)
    for i in keep:
        c.assert_lit(-xor(c, x[i], xp[i]))
    y, yp = step_lits(c, pol, a, x), step_lits(c, pol, a, xp)
    c.assert_clause([xor(c, y[i], yp[i]) for i in keep])
    return c, x, xp


def readoff(pol, word, obs, i):
    """The query obs after the action word differs from bit i of the start word."""
    c = CNF(pol.ir)
    x = c.inputs(pol.el.width)
    y = x
    for a in word:
        y = step_lits(c, pol, a, y)
    o = c.lit(obs, y, {})
    c.assert_lit(xor(c, o, x[i]))
    return c, x


def model_word(model, xvars):
    pos = {v for v in model if v > 0}
    return sum(1 << i for i, v in enumerate(xvars) if v in pos)
