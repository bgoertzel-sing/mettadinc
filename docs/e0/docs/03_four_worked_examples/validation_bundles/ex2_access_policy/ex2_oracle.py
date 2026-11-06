#!/usr/bin/env python3
"""Oracle for Example 2 (auditing an administrative access-control policy on 40-bit words).

Everything the example claims is computed from access_policy.metta.  policy_ir.py reads the module
into a typed intermediate form (IR) shared by the evaluator, the Boolean encoding and the decision
diagrams; obligations.py builds every satisfiability obligation from the IR and discharges it with
CaDiCaL 1.5.3, writing a DRAT proof for every unsatisfiable one.

  0. the source: digest, elaboration, admission checks
  1. translation validation: the direct interpreter of the source terms, the IR and the CNF agree
     on every word of the two-user instance; the independent Python model (rbac.py, circuits.py) is
     compared with the source as a differential check
  2. canonical witnesses from the start word (breadth-first, actions in declaration order)
  3. the CheckBlockPartition requests of the module: obligations, proofs, statuses
  4. exact reachable scopes (decision diagrams from the IR's guarded updates)
  5. the whole interface: forty read-off tests
  6. slicing for approve(bob), the vendor's slice, the behavioral quotients
  7. the vendor's slice as an over-approximation
  8. source mutations that restore the two authoring mistakes: the claims must change

Assurance.  With MDINC_TOOLS naming a directory that holds drat-trim/drat-trim and cake_lpr/cake_lpr,
every DRAT proof is converted to LRAT and checked by cake_lpr, and the results that rest on the
proofs are Checked.  Without the tools the oracle skips the checks that read the proof checker's
verdicts and reports those results as Conditional, with the assumption
(TrustedBackend cadical 1.5.3 SAT <digest of the obligations>).

Run: python3 ex2_oracle.py        (a few minutes; writes ex2_results.json and obligations/)
"""
import json
import os
import random
import sys
import time
from collections import deque

import numpy as np
from pysat.solvers import Solver

import policy_ir as pir
import obligations as ob
import rbac
from rbac import A, S, NU, W, USERS, ROLES, KINDS, describe
import circuits
import sat_obligations as so
import bdd_reach as br
import validate_small_lib as vs

RESULTS, FAILS, CHECKS = {}, [], [0]
CLAIMS = []
PROOFS = ob.tools_found()


def check(name, got, want):
    CHECKS[0] += 1
    ok = got == want
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": got {got!r}, want {want!r}"))
    if not ok:
        FAILS.append(name)
    RESULTS[name] = got


T0 = time.time()
SOURCE_TEXT = open("access_policy.metta").read()
SRC = pir.Source(SOURCE_TEXT)
EL = pir.Elaborator(SRC)
FIXED = pir.Policy(EL, "AccessPolicyFixed")
WRITTEN = pir.Policy(EL, "AccessPolicy")
IR = EL.ir
DIS = ob.Discharger("obligations")


def binding(mod, names):
    return {"module_digest": SRC.digest, "file": SRC.name, "module": mod, "declarations": names}


def claim(request, mod, names, status, values, method, assumptions=(), assurance=None, **extra):
    """A result record: status, assurance (Exact, Replayed, Witness, TrustedBackend), assumptions, binding."""
    if assurance is None:
        assurance = {"Refuted": "Witness", "Conditional": "TrustedBackend", "Unknown": None}.get(status, "Exact")
    rec = {"request": request, "status": status, "assurance": assurance, "values": values, "method": method,
           "assumptions": list(assumptions), "binding": binding(mod, names)}
    rec.update(extra)
    CLAIMS.append(rec)
    return rec


def pred(node):
    return eval("lambda x: " + IR.pyexpr(node))  # noqa: S307 -- generated from the IR


# ------------------------------------------------------------------ 0. the source
INIT = EL.const("AccessPolicyFixed", "start")
check("initial word", (INIT, describe(INIT)),
      (34672145, "alice: assigned {staff,admin} active {admin}; bob: assigned {staff,clerk} active {clerk}; "
                 "carol: assigned {staff} active {staff}"))
CANON = [rbac.label(a) for a in rbac.Policy().actions]
check("source: 80 actions in declaration order (kind, user, role) and 20 observers, in both modules",
      (FIXED.labels == CANON, WRITTEN.labels == CANON, len(FIXED.obs), len(WRITTEN.obs)), (True, True, 20, 20))
check("source: every action is a guarded update whose guard reads none of the bits it writes (admission)",
      all(g is not None for g in FIXED.guarded + WRITTEN.guarded) and all(FIXED.writes_ok + WRITTEN.writes_ok), True)
RESULTS["source"] = {"file": SRC.name, "digest": SRC.digest, "modules": list(SRC.modules),
                     "ir_nodes": len(IR.nodes), "run_requests": len(SRC.runs)}

# ------------------------------------------------------------------ 1. translation validation
check("translation validation: interpreter, IR and CNF agree on every word of the two-user instance "
      "(actions, queries, gate structure)", vs.source_pointwise(SRC),
      {"words": 1 << 20, "actions": [80, 80], "queries": [26, 26], "structure": [106, 106]})
check("translation validation: closure obligations of the two-user instance from the source "
      "(pointwise, solver = enumeration, total)", vs.source_obligations_pointwise(SRC), (240, 240, 240))
check("differential: independent model against the source on every word of the two-user instance "
      "(agree, total, first disagreement)", vs.model_against_source(SRC), (80, 80, None))
random.seed(20261103)
SAMPLE = [random.getrandbits(40) for _ in range(50000)]
frontier, seen = [INIT], {INIT}
for _ in range(2):
    nxt = []
    for x in frontier:
        for a in range(80):
            y = FIXED.step(x, a)
            if y not in seen:
                seen.add(y)
                nxt.append(y)
    frontier = nxt
SAMPLE += sorted(seen)
XS = np.array(SAMPLE, dtype=np.uint64)
INTERP = pir.SourceInterpreter(SRC)
agree = 0
for pol, mod, written in ((FIXED, "AccessPolicyFixed", False), (WRITTEN, "AccessPolicy", True)):
    model = rbac.Policy(written=written)
    acts = [e for e in INTERP.machine_entries(mod, "Policy") if e[0] == "Action"]
    for i, ((_, lab, m, term), a) in enumerate(zip(acts, model.actions)):
        ys = INTERP.apply(m, term, XS)
        same = np.array_equal(ys, pol.step_array(XS, i)) and np.array_equal(ys, vs.vec_step(XS, a, written, NU)) and \
            all(pol.step(int(x), i) == model.step(int(x), a) == int(y) for x, y in zip(SAMPLE[:2000], ys[:2000]))
        agree += same
check("differential: interpreter, IR and independent model agree on a 40-bit sample (words, actions agreeing)",
      (len(SAMPLE), agree), (50119, 160))
check("translation validation: closure obligations at 20 bits (enumeration = CNF)", vs.closure_agreement(), (240, 240))
check("translation validation: two-copy obligations at 10 bits (enumeration = CNF)", vs.miter_agreement(), (2400, 2400))


# ------------------------------------------------------------------ 2. witnesses from the start word
def shortest_violation(pol, bad, max_depth=6, init=INIT):
    prev = {init: None}
    frontier = [init]
    for depth in range(1, max_depth + 1):
        nxt = []
        for x in frontier:
            for a in range(len(pol.labels)):
                y = pol.step(x, a)
                if y not in prev:
                    prev[y] = (x, a)
                    nxt.append(y)
        for y in nxt:
            if bad(y):
                w, z = [], y
                while prev[z] is not None:
                    z, a = prev[z]
                    w.append(a)
                return [pol.labels[a] for a in reversed(w)], y
        frontier = nxt
    return None, len(prev)


def replay(pol, word, init=INIT):
    """Run a word on the source twice: through the IR and through the direct interpreter."""
    x = init
    X = np.array([init], dtype=np.uint64)
    ents = {lab: (m, term) for k, lab, m, term in INTERP.machine_entries(pol.mod, "Policy") if k == "Action"}
    for lab in word:
        x = pol.step(x, pol.index(lab))
        X = INTERP.apply(*ents[lab], X)
    return x, int(X[0])


SOD = pred(EL.predicate("AccessPolicy", "sod-breach"))
CLERKLESS = pred(EL.predicate("AccessPolicy", "clerkless-approval"))
CONSISTENT = pred(EL.predicate("AccessPolicy", "consistent"))
w_sod = shortest_violation(WRITTEN, SOD)
check("written: shortest breach of separation of duty", w_sod[0], ["(assign bob auditor)", "(assign bob approver)"])
check("written: the breach replayed on the source ends at 34684433, where sod-breach holds",
      (replay(WRITTEN, w_sod[0]), bool(SOD(w_sod[1]))), ((34684433, 34684433), True))
w_clerk = shortest_violation(WRITTEN, CLERKLESS)
check("written: shortest approval without clerk", w_clerk[0],
      ["(assign bob approver)", "(revoke bob clerk)", "(activate bob approver)"])
w_wf = shortest_violation(WRITTEN, lambda x: not CONSISTENT(x))
check("written: shortest ill-formed configuration", w_wf[0], ["(assign bob approver)", "(revoke bob clerk)"])
none6 = shortest_violation(FIXED, CLERKLESS, max_depth=6)
check("fixed: no approval without clerk within 6 steps (states explored)", none6[0] is None, True)
check("fixed: configurations explored by the six-step search", none6[1], 26410)
RESULTS["fixed: states within 6 steps of the start word"] = none6[1]


def model_bfs(written, bad, depth=6):
    P = rbac.Policy(written=written)
    prev, frontier = {INIT: None}, [INIT]
    for _ in range(depth):
        nxt = []
        for x in frontier:
            for a in P.actions:
                y = P.step(x, a)
                if y not in prev:
                    prev[y] = (x, a)
                    nxt.append(y)
        for y in nxt:
            if bad(y):
                w, z = [], y
                while prev[z] is not None:
                    z, a = prev[z]
                    w.append(rbac.label(a))
                return list(reversed(w))
        frontier = nxt
    return None


check("differential: the independent model finds the same three witnesses",
      [model_bfs(True, rbac.sod), model_bfs(True, rbac.clerkless), model_bfs(True, lambda x: not rbac.consistent(x))],
      [w_sod[0], w_clerk[0], w_wf[0]])


# ------------------------------------------------------------------ 3. the module's CheckBlockPartition requests
def least_model(cnf, xvars):
    """Least start word of a satisfiable obligation: fix bits from the most significant down."""
    s = Solver(name="cadical153", bootstrap_with=cnf.clauses)
    fixed = []
    for v in reversed(xvars):
        fixed.append(-v if s.solve(assumptions=fixed + [-v]) else v)
    assert s.solve(assumptions=fixed)
    s.delete()
    return sum(1 << i for i, v in enumerate(xvars) if v in fixed)


def run_partition(el, pols, mod, part_name, watch, budget, dis, tag, sample=None, interp=None):
    """Answer (CheckBlockPartition part (Of watch)) from the module: obligations, proofs, witnesses."""
    part = el.partition(mod, part_name)
    pol = pols[mod]
    ir = el.ir
    watch_pol = pir.Policy(el, mod, watch)
    assert watch_pol.labels == pol.labels, "the watch machine borrows the policy's actions"
    block = part["block"]
    inv = part["invariant"] if part["invariant"] is not None else block
    starts = part["members"]
    rec = {"partition": part_name, "of": watch, "module": mod, "scope": f"(Reach {part['scope_machine']} (From start))",
           "start_in_block": all(pred_of(ir, block)(s) for s in starts),
           "start_in_invariant": all(pred_of(ir, inv)(s) for s in starts)}
    unsat, sat = [], []
    for a, lab in enumerate(pol.labels):
        cnf, x = ob.closure(pol, inv, a)
        r = dis.solve(cnf, f"{tag}_closure_{a:02d}", f"{mod}.{part_name}: closure of "
                      f"{part['invariant_name'] or 'the block'} under {lab}")
        if sample is not None:
            _, satmask = cnf.evaluate(vs._inputs(x, sample))
            ivx = ir.eval(inv, sample)
            ivy = ir.eval(inv, pol.step_array(sample, a))
            rec.setdefault("sample_pointwise", 0)
            rec["sample_pointwise"] += bool(np.array_equal(satmask, ivx & ~ivy))
        (sat if r["sat"] else unsat).append((a, lab, r, cnf, x))
    rec["closure_unsat"] = len(unsat)
    rec["closure_sat"] = [lab for _, lab, _, _, _ in sat]
    rec["largest"] = (max(r["vars"] for _, _, r, _, _ in unsat + sat), max(r["clauses"] for _, _, r, _, _ in unsat + sat))
    records = [r for _, _, r, _, _ in unsat]
    if part["invariant"] is not None and not sat:
        cnf, x = ob.implication(ir, el.width, part["invariant"], block)
        r = dis.solve(cnf, f"{tag}_implies_block", f"{mod}.{part_name}: {part['invariant_name']} implies the block")
        rec["invariant_implies_block"] = not r["sat"]
        records.append(r)
    if not sat and rec["start_in_block"] and rec["start_in_invariant"] and rec.get("invariant_implies_block", True):
        a = ob.assurance(records)
        rec.update(status=a["status"], assumptions=a["assumptions"], proofs=len(records),
                   proofs_replayed=a["proofs_replayed"])
        return rec
    # the induction step failed: counterexamples to induction go to Resources, never to Witness
    ctis = sorted((least_model(cnf, x), a) for a, _, r, cnf, x in sat)
    rec["raw_model_first_cti"] = ob.model_word(sat[0][2]["model"], sat[0][4]) if sat else None
    rec["cti"] = (ctis[0][0], pol.labels[ctis[0][1]]) if ctis else None
    bad = pred_of(ir, ir.NOT(block))
    word, end = shortest_violation(pol, bad, max_depth=budget or 6)
    if word is not None:
        rec.update(status="Refuted", witness=word, state=end, replayed=replay_on(interp, pol, word, end))
    else:
        rec.update(status="Unknown", search={"unrollings": budget or 6, "configurations": end})
    return rec


def pred_of(ir, node):
    return eval("lambda x: " + ir.pyexpr(node))  # noqa: S307


def replay_on(interp, pol, word, end):
    x = np.array([INIT], dtype=np.uint64)
    ents = {lab: (m, term) for k, lab, m, term in interp.machine_entries(pol.mod, "Policy") if k == "Action"}
    for lab in word:
        x = interp.apply(*ents[lab], x)
    return int(x[0]) == end


def partition_requests(src):
    out = []
    for r in src.runs:
        if r[0] == "dc.run" and isinstance(r[2], list) and r[2][0] == "CheckBlockPartition":
            req = r[2]
            of = next(x[1] for x in req[2:] if isinstance(x, list) and x[0] == "Of")
            bud = next((x[1] for x in req[2:] if isinstance(x, list) and x[0] == "Budget"), None)
            out.append((r[1], req[1], of, int(bud[1]) if bud else None, pir.show(req)))
    return out


POLS = {"AccessPolicy": WRITTEN, "AccessPolicyFixed": FIXED}
REQS = partition_requests(SRC)
check("requests: the module's CheckBlockPartition requests",
      [(m, p, o, b) for m, p, o, b, _ in REQS],
      [("AccessPolicy", "NoBreach", "SoDWatch", None), ("AccessPolicy", "ClerksOnly", "ClerkWatch", None),
       ("AccessPolicy", "WellFormed", "Hygiene", None), ("AccessPolicyFixed", "NoBreach", "SoDWatch", None),
       ("AccessPolicyFixed", "ClerksOnly", "ClerkWatch", 6), ("AccessPolicyFixed", "ClerksOnlyProved", "ClerkWatch", None)])
PART = {}
for mod, pname, of, bud, text in REQS:
    tag = ("written" if mod == "AccessPolicy" else "fixed") + "_" + pname
    PART[(mod, pname)] = run_partition(EL, POLS, mod, pname, of, bud, DIS, tag, sample=XS[:20000], interp=INTERP)
    RESULTS[f"request: {mod} {text}"] = {k: v for k, v in PART[(mod, pname)].items()}
want_proved = "Checked" if PROOFS else "Conditional"
check("requests: statuses (written NoBreach, ClerksOnly, WellFormed; fixed NoBreach, ClerksOnly, ClerksOnlyProved)",
      [PART[(m, p)]["status"] for m, p, _, _, _ in REQS],
      ["Refuted", "Refuted", "Refuted", want_proved, "Unknown", want_proved])
check("requests: witnesses of the refuted requests (word, end state, replayed by the interpreter)",
      [(PART[("AccessPolicy", p)]["witness"], PART[("AccessPolicy", p)]["state"], PART[("AccessPolicy", p)]["replayed"])
       for p in ("NoBreach", "ClerksOnly", "WellFormed")],
      [(w_sod[0], 34684433, True), (w_clerk[0], w_clerk[1], True), (w_wf[0], w_wf[1], True)])
check("fixed: consistent is closed under all 80 actions", PART[("AccessPolicyFixed", "ClerksOnlyProved")]["closure_unsat"], 80)
check("fixed: no breach is closed under all 80 actions (1-inductive)", PART[("AccessPolicyFixed", "NoBreach")]["closure_unsat"], 80)
check("fixed: clerks-only alone fails induction at the four approver activations",
      PART[("AccessPolicyFixed", "ClerksOnly")]["closure_sat"], [f"(activate {u} approver)" for u in USERS])
check("written: consistent fails induction exactly at the two buggy rules", PART[("AccessPolicy", "WellFormed")]["closure_sat"],
      [f"(assign {u} approver)" for u in USERS] + [f"(revoke {u} clerk)" for u in USERS])
check("written: no breach fails induction at the approver assignments", PART[("AccessPolicy", "NoBreach")]["closure_sat"],
      [f"(assign {u} approver)" for u in USERS])
check("fixed: the closure obligations agree with the source on a 40-bit sample (NoBreach, ClerksOnlyProved)",
      (PART[("AccessPolicyFixed", "NoBreach")]["sample_pointwise"], PART[("AccessPolicyFixed", "ClerksOnlyProved")]["sample_pointwise"]),
      (80, 80))
check("source: largest closure obligation, NoBreach and ClerksOnlyProved (variables, clauses)",
      (PART[("AccessPolicyFixed", "NoBreach")]["largest"], PART[("AccessPolicyFixed", "ClerksOnlyProved")]["largest"]),
      ((59, 62), (104, 269)))
fixed_cti = PART[("AccessPolicyFixed", "ClerksOnly")]
check("fixed: ClerksOnly under (Unrollings 6): least counterexample to induction from minimized solver models, search",
      (fixed_cti["cti"], fixed_cti["search"]), ((4, "(activate alice approver)"), {"unrollings": 6, "configurations": 26410}))
RESULTS["raw solver model of the first counterexample to induction (written NoBreach)"] = \
    PART[("AccessPolicy", "NoBreach")]["raw_model_first_cti"]
check("written: NoBreach, least counterexample to induction from minimized solver models (word, action)",
      PART[("AccessPolicy", "NoBreach")]["cti"], (10752, "(assign bob approver)"))


def least_cti(pol, prop):
    for x in range(1 << 16):
        if prop(x):
            for a in range(len(pol.labels)):
                if not prop(pol.step(x, a)):
                    return x, pol.labels[a]
    return None


check("fixed: least counterexample to induction for clerks-only", least_cti(FIXED, lambda x: not CLERKLESS(x)),
      (4, "(activate alice approver)"))
imp = []
for name, target in (("imp_nosod", "sod-breach"), ("imp_noclerk", "clerkless-approval")):
    cnf, _ = ob.implication(IR, EL.width, EL.predicate("AccessPolicyFixed", "consistent"),
                            IR.NOT(EL.predicate("AccessPolicyFixed", target)))
    r = DIS.solve(cnf, f"fixed_{name}", f"AccessPolicyFixed: consistent implies not {target}")
    imp.append(r)
check("consistent implies no breach and clerks only", tuple(not r["sat"] for r in imp), (True, True))
check("fixed: proofs behind ClerksOnlyProved and NoBreach (closure and implication obligations)",
      (PART[("AccessPolicyFixed", "ClerksOnlyProved")]["proofs"], PART[("AccessPolicyFixed", "NoBreach")]["proofs"]),
      (81, 80))
if PROOFS:
    check("fixed: every closure proof checked by drat-trim and cake_lpr",
          [PART[("AccessPolicyFixed", p)]["proofs_replayed"] == PART[("AccessPolicyFixed", p)]["proofs"]
           for p in ("ClerksOnlyProved", "NoBreach")], [True, True])
indep = {}
for written, inv_name, inv_enc in ((False, "consistent", circuits.enc_consistent), (False, "nosod", circuits.enc_no_sod)):
    rows = []
    for a, c, tag in so.closure_obligations(written, inv_name, inv_enc):
        s = Solver(name="cadical153", bootstrap_with=c.clauses)
        rows.append((s.solve(), c.n, len(c.clauses)))
        s.delete()
    indep[inv_name] = rows
check("fixed: largest closure obligation (variables, clauses)",
      (max(r[1] for r in indep["consistent"]), max(r[2] for r in indep["consistent"])), (104, 269))
check("differential: the independent encoder's closure obligations are all unsatisfiable too (consistent, no breach)",
      (sum(not r[0] for r in indep["consistent"]), sum(not r[0] for r in indep["nosod"])), (80, 80))
for (m, p), rec in PART.items():
    if rec["status"] in ("Checked", "Conditional"):
        claim(f"CheckBlockPartition {p} (Of {rec['of']})", m, [p, rec["of"], "Policy", "start"], rec["status"],
              {"closure_proofs": rec["closure_unsat"], "implication": rec.get("invariant_implies_block")},
              "inductive invariant; closure obligations from the source, DRAT proofs" +
              (" replayed (drat-trim, cake_lpr)" if rec["assumptions"] == [] else " not replayed"),
              rec["assumptions"], assurance="Replayed" if rec["status"] == "Checked" else "TrustedBackend",
              scope=rec["scope"])
    elif rec["status"] == "Refuted":
        claim(f"CheckBlockPartition {p} (Of {rec['of']})", m, [p, rec["of"], "Policy", "start"], "Refuted",
              {"witness": rec["witness"], "state": rec["state"]}, "breadth-first search from start; witness replayed "
              "by evaluating the source", scope=rec["scope"], resources={"counterexample_to_induction": rec["cti"]})
    else:
        claim(f"CheckBlockPartition {p} (Of {rec['of']}) (Budget (Unrollings 6))", m, [p, rec["of"], "Policy", "start"],
              "Unknown", {}, "induction failed; bounded search", scope=rec["scope"],
              resources={"counterexample_to_induction": rec["cti"], "search": rec["search"]})

# ------------------------------------------------------------------ 4. reachable scopes (decision diagrams)
REACH = {}
for mod, pol, written, want in (("AccessPolicyFixed", FIXED, False, 38418640), ("AccessPolicy", WRITTEN, True, 436285824)):
    man = br.build(NU)
    bdd, names, X, R, rounds = br.reach_ir(pol, INIT, man)
    cons = br.node_bdd(bdd, X, IR, EL.predicate(mod, "consistent"), {})
    some_admin = br.OR(bdd, [X[A(u, 4)] for u in range(NU)])
    key = "written" if written else "fixed"
    check(f"{key}: reachable configurations", int(R.count(nvars=W)), want)
    if not written:
        check("fixed: reachable = consistent and some admin assigned", R == (cons & some_admin), True)
        check("fixed: 79^4 - 27^4", 79 ** 4 - 27 ** 4, want)
    else:
        check("written: reachable but ill-formed", int((R & ~cons).count(nvars=W)), 397867184)
    _, _, _, R2, _ = br.reach(written, manager=man)
    REACH[key] = (R == R2)
    RESULTS[f"{key}: decision-diagram nodes, rounds"] = (len(R), rounds)
    del bdd, R, R2, cons, some_admin, man
check("differential: the reachable sets from the source equal those of the independent model (fixed, written)",
      (REACH["fixed"], REACH["written"]), (True, True))
check("fixed: decision-diagram nodes and image rounds of the reachable set", RESULTS["fixed: decision-diagram nodes, rounds"], (171, 3))


# ------------------------------------------------------------------ 5. the whole interface is discrete
def tests(u):
    k = lambda kind, r: f"({kind} {USERS[u]} {ROLES[r]})"  # noqa: E731
    return {S(u, 0): ([k("deactivate", 1), k("deactivate", 2), k("deactivate", 3)], "read"),
            S(u, 1): ([k("deactivate", 2)], "write"), S(u, 2): ([], "approve"),
            S(u, 3): ([], "audit"), S(u, 4): ([], "configure"),
            A(u, 0): ([k("deactivate", 1), k("deactivate", 2), k("deactivate", 3), k("deactivate", 0), k("activate", 0)], "read"),
            A(u, 1): ([k("deactivate", 2), k("deactivate", 1), k("activate", 1)], "write"),
            A(u, 2): ([k("deactivate", 3), k("deactivate", 2), k("activate", 2)], "approve"),
            A(u, 3): ([k("deactivate", 2), k("deactivate", 3), k("activate", 3)], "audit"),
            A(u, 4): ([k("deactivate", 4), k("activate", 4)], "configure")}


read_off = {}
for pol, key in ((FIXED, "fixed"), (WRITTEN, "written")):
    obs = dict(pol.obs)
    recs = []
    for u in range(NU):
        for i, (word, p) in tests(u).items():
            cnf, _ = ob.readoff(pol, [pol.index(l) for l in word], obs[f"({p} {USERS[u]})"], i)
            recs.append(DIS.solve(cnf, f"{key}_readoff_bit{i:02d}", f"{pol.mod}: bit {i} read off by "
                                  f"{' '.join(word) or 'the empty word'} then ({p} {USERS[u]})"))
    read_off[key] = recs
check("forty (word, query) tests read off the forty bits (both policies)",
      all(not r["sat"] for k in read_off for r in read_off[k]) and all(len(read_off[k]) == 40 for k in read_off), True)
wi = ob.assurance(read_off["fixed"])
check("WholeInterface and LiveInterface: status of the forty read-off proofs", wi["status"], want_proved)
WI_ASSURANCE = "Replayed" if wi["status"] == "Checked" else "TrustedBackend"
claim("WholeInterface (MinimizeForQueries Policy)", "AccessPolicyFixed", ["WholeInterface", "Policy"], wi["status"],
      {"classes": "2^40 (discrete)", "tests": 40}, "forty read-off tests, one obligation each", wi["assumptions"],
      assurance=WI_ASSURANCE)
claim("LiveInterface (MinimizeForQueries LivePolicy)", "AccessPolicyFixed", ["LiveInterface", "LivePolicy", "Live"],
      wi["status"], {"classes": 38418640}, "the forty read-off tests on the reachable scope; scope size from the "
      "decision diagrams", wi["assumptions"], assurance=WI_ASSURANCE)
assign_bits = EL.encoding("AccessPolicyFixed", "assignments")
obs_fixed = FIXED.obs


def first_now_witness():
    """Least pair (0, y) with the same assignments code and some observer that differs."""
    Y = np.arange(1 << 12, dtype=np.uint64)
    codes = np.stack([IR.eval(b, Y) for b in assign_bits], axis=1)
    same = (codes == codes[0]).all(axis=1)
    for y in np.nonzero(same)[0][1:]:
        for lab, node in obs_fixed:
            v = IR.eval(node, np.array([0, y], dtype=np.uint64))
            if v[0] != v[1]:
                return 0, int(y), lab
    return None


check("CheckNow AssignmentsOnly refuted: least pair and query", first_now_witness(), (0, 32, "(read alice)"))
claim("CheckNow AssignmentsOnly", "AccessPolicyFixed", ["AssignmentsOnly", "assignments", "Policy"], "Refuted",
      {"pair": [0, 32], "query": "(read alice)"}, "witness replayed by evaluating the source")


# ------------------------------------------------------------------ 6. slicing for approve(bob)
def cone_ir(pol, seed):
    C = set(seed)
    changed = True
    while changed:
        changed = False
        for a in range(len(pol.labels)):
            for i in list(C):
                d = IR.support(pol.bits[a][i])
                if not d <= C:
                    C |= d
                    changed = True
    return sorted(C)


approve_bob = dict(FIXED.obs)["(approve bob)"]
CONE = cone_ir(FIXED, IR.support(approve_bob))
check("cone of approve(bob)", CONE, [0, 4, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 24, 29, 30, 34, 39])
check("cone of approve(bob), policy as written", cone_ir(WRITTEN, IR.support(dict(WRITTEN.obs)["(approve bob)"])), CONE)
check("source: the declared encoding bob-cone gathers exactly the cone",
      EL.encoding("AccessPolicyFixed", "bob-cone") == [IR.BIT(i) for i in CONE], True)


def deps(a, i, written):
    k, u, r = a
    close = rbac.CLOSE_WRITTEN if written else rbac.CLOSE
    oa = {S(v, 4) for v in range(NU) if v != u}
    if k == "assign" and i == A(u, r):
        return {i} | oa | {0: set(), 1: {A(u, 0)}, 2: {A(u, 1), S(u, 3) if written else A(u, 3)},
                           3: {A(u, 0), A(u, 2)}, 4: {A(u, 0)}}[r]
    if k == "revoke" and i in {A(u, q) for q in close[r]} | {S(u, q) for q in close[r]}:
        return {i} | oa
    if k == "activate" and i == S(u, r):
        return {i, A(u, r)} | ({S(u, 3)} if r == 2 else {S(u, 2)} if r == 3 else set())
    if k == "deactivate" and i == S(u, r):
        return set()
    return {i}


def cone_model(seed, written):
    P = rbac.Policy(written=written)
    C, changed = set(seed), True
    while changed:
        changed = False
        for a in P.actions:
            for i in list(C):
                d = deps(a, i, written)
                if not d <= C:
                    C |= d
                    changed = True
    return sorted(C)


check("differential: the independent model's cone is the same (both policies)",
      (cone_model({S(1, 2)}, False), cone_model({S(1, 2)}, True)), (CONE, CONE))


def miter_results(keep, prove):
    sat, recs = [], []
    for a, lab in enumerate(FIXED.labels):
        cnf, _, _ = ob.miter(FIXED, keep, a)
        r = DIS.solve(cnf, f"fixed_miter{len(keep)}_{a:02d}", f"AccessPolicyFixed: two words agreeing on the "
                      f"{len(keep)} bits agree after {lab}", proof=prove)
        if r["sat"]:
            sat.append(lab)
        else:
            recs.append(r)
    return sat, recs


cone_sat, cone_recs = miter_results(CONE, True)
check("cone projection: all 80 two-copy obligations unsatisfiable", cone_sat, [])
check("cone projection: largest two-copy obligation (variables, clauses)",
      (max(r["vars"] for r in cone_recs), max(r["clauses"] for r in cone_recs)), (178, 312))
bob10_sat, _ = miter_results(list(range(10, 20)), False)
check("bob's ten bits: the obligations fail for bob's assignments and revocations", bob10_sat,
      [f"(assign bob {r})" for r in ROLES] + [f"(revoke bob {r})" for r in ROLES])
mit = ob.assurance(cone_recs)
check("BobSlice: status from the support computation; the two-copy proofs as a second certificate",
      ("Checked", mit["status"]), ("Checked", want_proved))
BOBSLICE = claim("BobSlice (InduceExact BobCone)", "AccessPolicyFixed", ["BobSlice", "BobCone", "bob-cone", "BobApproves"], "Checked",
      {"states": 1 << 17, "acting_actions": None}, "support of every update term of the 17 cone bits lies in the cone "
      "(an exact computation on the IR); second certificate: 80 two-copy obligations, " + mit["status"],
      second_certificate={"status": mit["status"], "assumptions": mit["assumptions"]})
code10 = lambda x: (x >> 10) & 0x3FF  # noqa: E731
wit = None
for x in range(1 << 12):
    for y in range(x + 1, 1 << 12):
        if code10(x) == code10(y):
            for a, lab in enumerate(FIXED.labels):
                if code10(FIXED.step(x, a)) != code10(FIXED.step(y, a)):
                    wit = (x, y, lab, code10(FIXED.step(x, a)), code10(FIXED.step(y, a)))
                    break
        if wit:
            break
    if wit:
        break
check("bob's ten bits: canonical update witness", wit, (0, 512, "(assign bob staff)", 0, 1))
bx, by = 1 << S(1, 2), (1 << S(1, 2)) | (1 << S(0, 4))
a_rs = FIXED.index("(revoke bob staff)")
check("bob's ten bits: behavioral witness (revoke bob staff) from 131072 and 131584",
      (bx, by, rbac.bit(FIXED.step(bx, a_rs), S(1, 2)), rbac.bit(FIXED.step(by, a_rs), S(1, 2))), (131072, 131584, 1, 0))
claim("InduceExact BobOnly", "AccessPolicyFixed", ["BobOnly", "bob-bits", "BobApproves"], "Refuted",
      {"pair": [0, 512], "action": "(assign bob staff)", "codes": [0, 1]}, "witness replayed by evaluating the source")
claim("CheckBehavioral BobOnly", "AccessPolicyFixed", ["BobOnly", "bob-bits", "BobApproves"], "Refuted",
      {"pair": [131072, 131584], "word": ["(revoke bob staff)"], "query": "(approve bob)"},
      "witness replayed by evaluating the source")

K = len(CONE)
n = 1 << K
EMB = np.array([sum(((s >> j) & 1) << CONE[j] for j in range(K)) for s in range(n)], dtype=np.uint64)


def proj(Y):
    out = np.zeros(Y.shape, dtype=np.int64)
    for j, i in enumerate(CONE):
        out |= (((Y >> np.uint64(i)) & np.uint64(1)).astype(np.int64)) << j
    return out


succ = []
for a in range(80):
    sa = proj(FIXED.step_array(EMB, a))
    if not np.array_equal(sa, np.arange(n)):
        succ.append(sa)
check("slice: actions that act on the 17 cone bits", len(succ), 34)
BOBSLICE["values"]["acting_actions"] = len(succ)
obs = IR.eval(approve_bob, EMB).astype(np.int64)


def refine(obs, succ, mask=None):
    blk = obs.copy() if mask is None else np.where(mask, obs, -1)
    count = lambda b: len(np.unique(b[mask] if mask is not None else b))  # noqa: E731
    hist = [count(blk)]
    while True:
        sig = np.stack([blk] + [blk[sa] for sa in succ], axis=1)
        _, nb = np.unique(sig, axis=0, return_inverse=True)
        nb = nb.reshape(-1)
        if mask is not None:
            nb = np.where(mask, nb, -1)
        if count(nb) == hist[-1]:
            return hist
        blk = nb
        hist.append(count(nb))


hist = refine(obs, succ)
check("approve(bob) quotient on all words (classes by round)", hist,
      [2, 4, 38, 702, 8737, 46487, 85180, 102159, 109243, 113073, 114226, 114250])
man = br.build(NU)
bdd, names, X, R, _ = br.reach_ir(FIXED, INIT, man)
P17 = bdd.exist([names[i] for i in range(W) if i not in CONE], R)
mask = np.array([bdd.let({names[i]: bool((int(EMB[s]) >> i) & 1) for i in CONE}, P17) == bdd.true for s in range(n)])
check("reachable cone configurations", int(mask.sum()), 1528)
check("reachable cone configurations are closed under the slice", all(mask[sa[mask]].all() for sa in succ), True)
live_hist = refine(obs, succ, mask)
check("approve(bob) quotient on the reachable configurations (classes by round)", live_hist,
      [2, 4, 19, 109, 346, 685, 974, 1123, 1160])
claim("BobQuotient (MinimizeForQueries BobApproves)", "AccessPolicyFixed", ["BobQuotient", "BobApproves"], "Checked",
      {"classes": hist[-1], "rounds": len(hist) - 1}, "partition refinement on the enumerated 2^17-state slice")
claim("BobLiveQuotient (MinimizeForQueries BobApprovesLive)", "AccessPolicyFixed", ["BobLiveQuotient", "BobApprovesLive", "Live"],
      "Checked", {"classes": live_hist[-1], "cone_configurations": int(mask.sum())},
      "partition refinement on the reachable cone configurations (decision diagrams)")
claim("Defects BobOnly", "AccessPolicyFixed", ["BobOnly", "bob-bits", "BobApproves"], "Checked",
      {"now": 0, "update": 1, "behavioral": 1}, "current defect by the support of approve(bob); update and behavioral "
      "defects attained by replayed witnesses")
del bdd, R, P17, man


# ------------------------------------------------------------------ 7. the ten bits as an over-approximation
def abstract_reach(pol):
    def succ_c(c):
        out = {c}
        for a, lab in enumerate(pol.labels):
            if lab.split()[1] == "bob":
                for oa in (0, 1):
                    out.add((pol.step((c << 10) | (oa << S(0, 4)), a) >> 10) & 0x3FF)
        return out
    start = (INIT >> 10) & 0x3FF
    seen, q = {start}, deque([start])
    while q:
        for d in succ_c(q.popleft()):
            if d not in seen:
                seen.add(d)
                q.append(d)
    xs = [c << 10 for c in seen]
    return (len(seen), sum(1 for x in xs if rbac.bit(x, A(1, 2)) and rbac.bit(x, A(1, 3))),
            sum(1 for x in xs if rbac.bit(x, S(1, 2)) and not rbac.bit(x, A(1, 1))),
            sum(1 for x in xs if not rbac.consistent_user(x, 1)))


check("bob's abstraction, fixed policy: configurations, breaches, clerkless, ill-formed", abstract_reach(FIXED), (79, 0, 0, 0))
check("bob's abstraction, policy as written", abstract_reach(WRITTEN), (145, 54, 12, 66))

# ------------------------------------------------------------------ 8. source mutations restore the two mistakes
MUTATIONS = {
    "M1": ("the corrected approver rule reads the auditor session again",
           "(approver (And (holds $u clerk $x) (Not (holds $u auditor $x))))       ; the assignment",
           "(approver (And (holds $u clerk $x) (Not (active $u auditor $x))))       ; the assignment"),
    "M2": ("revoking clerk keeps approver again",
           "(clerk    (drop $u clerk (drop $u approver $x)))                    ; cascades",
           "(clerk    (drop $u clerk $x))                    ; cascades"),
}
MUT = {}
for key, (what, old, new) in MUTATIONS.items():
    assert SOURCE_TEXT.count(old) == 1, key
    msrc = pir.Source(SOURCE_TEXT.replace(old, new))
    mel = pir.Elaborator(msrc)
    mpols = {"AccessPolicy": pir.Policy(mel, "AccessPolicy"), "AccessPolicyFixed": pir.Policy(mel, "AccessPolicyFixed")}
    mdis = ob.Discharger(os.path.join("obligations", "mutations", key))
    minterp = pir.SourceInterpreter(msrc)
    out = {"what": what, "digest": msrc.digest}
    for pname, of in (("NoBreach", "SoDWatch"), ("ClerksOnlyProved", "ClerkWatch")):
        out[pname] = run_partition(mel, mpols, "AccessPolicyFixed", pname, of, None, mdis, f"{key}_{pname}",
                                   interp=minterp)
    out["model_against_source"] = vs.model_against_source(msrc)
    out["consistent_violation"] = shortest_violation(mpols["AccessPolicyFixed"],
                                                     lambda x: not pred_of(mel.ir, mel.predicate("AccessPolicyFixed",
                                                                                                 "consistent"))(x))[0]
    base = {r["name"].split("_")[-1]: r["cnf"] for r in DIS.index if "_closure_" in r["name"]
            and r["name"].startswith("fixed_" + ("NoBreach" if key == "M1" else "ClerksOnlyProved"))}
    mine = {r["name"].split("_")[-1]: r["cnf"] for r in mdis.index if "_closure_" in r["name"]
            and r["name"].startswith(f"{key}_" + ("NoBreach" if key == "M1" else "ClerksOnlyProved"))}
    out["changed_obligations"] = [FIXED.labels[int(k)] for k in sorted(base) if base[k] != mine.get(k)]
    MUT[key] = out
    mdis.write_index({"mutation": key, "what": what, "module_digest": msrc.digest})
m1, m2 = MUT["M1"], MUT["M2"]
check("mutation M1 (approver rule reads the auditor session): NoBreach of the corrected module is Refuted, "
      "with the breach and its end state, replayed on the mutated source",
      (m1["NoBreach"]["status"], m1["NoBreach"]["closure_sat"], m1["NoBreach"]["witness"], m1["NoBreach"]["state"],
       m1["NoBreach"]["replayed"]),
      ("Refuted", [f"(assign {u} approver)" for u in USERS], ["(assign bob auditor)", "(assign bob approver)"], 34684433, True))
check("mutation M1: the invariant consistent of ClerksOnlyProved fails at the approver assignments, "
      "and the same breach is its least reachable violation",
      (m1["ClerksOnlyProved"]["closure_sat"], m1["ClerksOnlyProved"]["status"], m1["consistent_violation"]),
      ([f"(assign {u} approver)" for u in USERS], "Unknown", ["(assign bob auditor)", "(assign bob approver)"]))
check("mutation M2 (revoking clerk keeps approver): ClerksOnlyProved is Refuted, with its witness, replayed on the mutated source",
      (m2["ClerksOnlyProved"]["status"], m2["ClerksOnlyProved"]["closure_sat"], m2["ClerksOnlyProved"]["witness"],
       m2["ClerksOnlyProved"]["replayed"]),
      ("Refuted", [f"(revoke {u} clerk)" for u in USERS],
       ["(assign bob approver)", "(revoke bob clerk)", "(activate bob approver)"], True))
check("mutation M2: NoBreach keeps its status (the mutation does not touch separation of duty)",
      m2["NoBreach"]["status"], want_proved)
check("mutations: the differential check against the independent model also fails (first disagreement)",
      (m1["model_against_source"][2], m2["model_against_source"][2]),
      (("AccessPolicyFixed", "(assign alice approver)", 524298), ("AccessPolicyFixed", "(revoke alice clerk)", 524292)))
check("mutations: new module digests, and the closure obligations that change are exactly those of the mutated rule",
      (m1["digest"] != SRC.digest, m2["digest"] != SRC.digest, m1["changed_obligations"], m2["changed_obligations"]),
      (True, True, [f"(assign {u} approver)" for u in USERS], [f"(revoke {u} clerk)" for u in USERS]))
for key in MUT:
    for pname in ("NoBreach", "ClerksOnlyProved"):
        r = MUT[key][pname]
        RESULTS[f"mutation {key}: {pname}"] = {k: v for k, v in r.items()}
        claim(f"CheckBlockPartition {pname} (Of {r['of']}) [mutation {key}]", "AccessPolicyFixed",
              [pname, r["of"], "Policy", "start"], r["status"],
              {k: r[k] for k in ("witness", "state") if k in r}, "the same pipeline on the mutated source",
              r.get("assumptions", []), assurance="Replayed" if r["status"] == "Checked" else None,
              mutation=MUTATIONS[key][0], scope=r["scope"])
        CLAIMS[-1]["binding"]["module_digest"] = MUT[key]["digest"]

# ------------------------------------------------------------------ results
check("proofs: unsatisfiable obligations of the audit that carry a DRAT proof",
      sum(1 for r in DIS.index if "drat_lines" in r), 619)
if PROOFS:
    check("proofs: every one of them converted to LRAT by drat-trim and checked by cake_lpr",
          sum(1 for r in DIS.index if r["replayed"]), 619)
DIS.write_index({"module": SRC.name, "module_digest": SRC.digest})
RESULTS["seconds"] = round(time.time() - T0, 1)
RESULTS["proofs_checked"] = PROOFS
RESULTS["proofs"] = {"unsat_obligations": sum(1 for r in DIS.index if not r["sat"]),
                     "with_drat_proof": sum(1 for r in DIS.index if "drat_lines" in r),
                     "replayed": sum(1 for r in DIS.index if r["replayed"])}
RESULTS["claims"] = CLAIMS
RESULTS["_assurance"] = {
    "policy": "Checked: exact computation on the elaborated source, or an unsatisfiability proof replayed by "
              "drat-trim (DRAT to LRAT) and cake_lpr on an obligation built from the source; Conditional: a solver "
              "answer whose proof was not replayed, with a TrustedBackend assumption; Refuted: a witness replayed "
              "by evaluating the source",
    "tools": {"drat-trim": "2e3b2dc0ecf938addbd779d42877b6ed69d9a985", "cake_lpr": "033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2"}
    if PROOFS else None,
    "conditional": [c["request"] for c in CLAIMS if c["status"] == "Conditional"]}
with open("ex2_results.json", "w") as f:
    json.dump(RESULTS, f, indent=1, default=str)
print(f"{CHECKS[0] - len(FAILS)} checks passed, {len(FAILS)} failed, {RESULTS['seconds']} s, proofs checked: {PROOFS}"
      f" ({RESULTS['proofs']['replayed']} of {RESULTS['proofs']['with_drat_proof']} proofs replayed)")
sys.stdout.flush()
sys.stderr.flush()
# Leave without interpreter teardown: the decision-diagram manager of dd checks for live nodes in
# its destructor, and at shutdown the order in which globals are released is arbitrary.
os._exit(1 if FAILS else 0)
