MeTTaDinC validation package, 4 November 2026
============================================

This package accompanies two documents: "MeTTaDinC: An Executable Language for
Observer-Relative Abstraction, Evidence, and Composition" (specification draft)
and "Implementing MeTTaDinC in Cetta" (coding-agent guide).  The documents print
excerpts of the fixtures below; where an excerpt and a fixture differ, the
fixture is authoritative.

Contents
  registry/mettadinc_registry.json   declarations, requests, argument types and
                                   defaults, result fields, statuses, profiles,
                                   and the first-release capability manifest
  fixtures/*.metta                 complete MeTTaDinC modules for every example
  manifest.json                    each claim: fixture form, required status,
                                   oracle values, first-release expectation
  oracle/verify_mettadinc.py         exact-arithmetic oracle (156 checks)
  oracle/mettadinc_oracle_results.json   machine-readable oracle results
  oracle/oracle_report.txt         the oracle's printed report
  check_fixtures.py                static checker: registry conformance, name
                                   resolution, profiles, manifest versus oracle,
                                   and the "until" entries of claims that need a
                                   replay capability (a witness type or a
                                   certificate kind) not every release has
  DEPENDENCIES.json                tool versions and pinned external commits

Running
  cd oracle && python3 verify_mettadinc.py      (writes the results JSON)
  cd .. && python3 check_fixtures.py          (exit status 0 when consistent)

What the tools establish
  The oracle recomputes, in exact arithmetic, every mathematical value quoted in
  the documents and checks the counterexamples that justify the theorem
  hypotheses; it uses no floating point, and the one linear-programming optimum
  (the parity-triangle refinement) is proved by exact primal and dual
  solutions.  The checker confirms that every fixture uses only registered
  declarations, requests, arguments and names, and that every manifest claim
  names a real fixture form and agrees with the oracle.  Neither tool runs
  MeTTaDinC: no MeTTaDinC implementation exists yet, and passing these checks is
  not conformance.  An implementation conforms when it returns, for every
  manifest claim it supports, the stated status and values with replayable
  evidence, and Unsupported for every claim marked Unsupported in its release.
  The negative acceptance fixtures (the literal-congruence, adaptive-policy and
  unattained-supremum modules here, and the binding fixtures of the
  application bundles) are part of that test.
