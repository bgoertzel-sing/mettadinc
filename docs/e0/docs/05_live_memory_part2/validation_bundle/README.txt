Omega memory and goals in MeTTaDinC, Part II: live memory through summary statistics
Validation bundle, 4 November 2026

This bundle accompanies "Omega Memory and Goals in MeTTaDinC, Part II: Live Memory through Summary
Statistics". It contains the six modules of Part II as one MeTTaDinC file, the registry patch that
Part II proposes, Python models of every pattern with symbolic checks in the Z3 solver, a reference
evaluator that rebuilds every request from the module text and decides it with the cvc5 solver,
negative fixtures that apply certificates to the wrong objects, and an oracle that runs all of it and
compares the results. Where the guide's text and this bundle differ, the
bundle is authoritative.

Requirements: Python 3.11 or later with numpy, scipy, z3-solver and cvc5
(pip install numpy scipy z3-solver cvc5). The results were produced with z3-solver 5.3.3 and
cvc5 1.4.2.

Contents

  live_memory.metta         the six modules of Part II with their requests; the regions between
                            ";; @excerpt <name>" and ";; @end" are the excerpts printed in the guide
  memory_goals.metta        Part I's module file; LiveArbitration imports two machines from its
                            module ClaimArbitration
  ls_registry_patch.json    Part II's registry patch: the libraries RationalArith, BoundedSets,
                            Statistics and Estimates, the Statistic, Store and Keyed declarations,
                            the View field of Keyed, the Matching field of Simulation, the
                            Population, Selection and Policy fields of Stream, the CheckStatistic,
                            EstimateRate and CompareRates requests, and the status rule: a symbolic
                            verdict without a checked proof is Conditional on
                            (TrustedBackend solver version logic obligation-digest)
  ex1_registry_patch.json   patches reused unchanged from "MeTTaDinC in Practice: Four Worked
  ex2_registry_patch.json   Examples" and from Part I
  ex4_registry_patch.json
  mg_registry_patch.json
  ex_check.py               static checker: parses the module files and checks every form against
                            the registry with the patches applied
  ls_eval.py                reference evaluator: rebuilds carriers, maps, machines, statistics,
                            stores, representations, simulations, block partitions, tolerances,
                            implementation contracts, streams and monitors from the module text;
                            values are Python values or cvc5 terms, so the same code evaluates on
                            concrete states and builds obligations on symbolic ones; it checks
                            the lifting premise, the target of a safety transfer and every stream
                            digest before computing anything, and reports each verdict with its
                            assurance (a test aid, not an implementation of MeTTaDinC)
  ls_oracle.py              the oracle
  ls_results.json           the oracle's results, one entry per check, and under "verdicts" every
                            verdict of the 37 requests with its status, assurance, assumptions and
                            binding; each Conditional verdict lists Z3's agreement under agreed_by
  models/                   Python models: cs.py (confidence sequences and e-processes),
                            p1_live.py (open items in real time), p2_live.py (context blocks),
                            p3_live.py (identity-bounded sets), p4_live.py (read sets and Bloom
                            filters), p6_live.py (arbitration runs mapped to Part I's model),
                            p_attention.py (error propagation), smt_live.py (Z3 encodings of
                            Patterns 1, 5, 6 and 7), estimates.py (rates, comparisons, monitors),
                            make_streams.py (how the two new streams were generated)
  part1_models/             dclib.py and p6_conflicts.py from Part I, used by p6_live.py
  streams/                  four frozen streams, pinned by SHA-256 digest

Running the oracle

  python3 ls_oracle.py

Part A recomputes every number of Part II from the Python models: the statistical procedures and
their simulations, the simulations of the live stores, and the symbolic obligations in Z3 on
encodings written by hand, and a simulation of Proposition 5.1 (one-sided claims without a common
rate). Part B reads live_memory.metta with ls_eval.py, answers all 37 requests from the module text
with cvc5, including two negative fixtures whose correct answer is InvalidInput, replays every
witness by evaluation, compares each verdict with Part A, runs differential tests of the module's
maps against the Python models, and checks that a copy of a stream changed under its declared
digest is refused, the third negative fixture. Symbolic verdicts are reported as Conditional on
cvc5, since no solver proof is checked; Z3 agrees with each of them, and the oracle records that
agreement under agreed_by. The oracle prints one line per check (94 in all, about 11 seconds on one
core), rewrites ls_results.json, and exits with a nonzero status if any check fails.

Running the static check

The checker needs the MeTTaDinC specification's validation package, which holds the registry and the
base checker (check_fixtures.py):

  MDINC_PACKAGE=/path/to/mettadinc_validation_package python3 ex_check.py \
      ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json \
      mg_registry_patch.json ls_registry_patch.json \
      -- memory_goals.metta live_memory.metta

The first pass reports 16 modules, 490 declarations and 129 run requests for the two files (6
modules, 172 declarations and 37 run requests are Part II's), all conforming to the registry with
the patches. The second pass lists the diagnostics against the unpatched registry, which are the
forms that depend on the patches.

The streams

The streams are stored as data; reproducing a result means replaying the stored stream, not
rerunning a generator.

  streams/context_receipts_seed2.json   2,000 simulated context-block receipts (Patterns 2 and 8)
  streams/stale_ten_seed1.json          2,000 suggestions, stale with probability 1/10
  streams/stale_alt_seed1.json          Part I: 400 suggestions, stale with probability 1/5
  streams/stale_null_seed1.json         Part I: 400 suggestions, stale with probability 1/20

live_memory.metta pins the first three by digest; Part I's module pins the fourth.
