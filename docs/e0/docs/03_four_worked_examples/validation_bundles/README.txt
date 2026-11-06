MeTTaDinC in Practice: four worked examples -- validation package, 4 November 2026.

This package accompanies the document "MeTTaDinC in Practice: Four Worked Examples"
(mettadinc_worked_examples.pdf). Each directory is one example's bundle: its module file, its
registry patch (and the patches of earlier examples that it reuses), the static checker, the
Python model, the oracle and the oracle's results. Each directory has its own README.

  ex1_belief_memory/   Example 1: compacting an agent's belief memory
  ex2_access_policy/   Example 2: auditing an administrative access-control policy
  ex3_skill_share/     Example 3: sharing skills between robots with different camera frames
  ex4_market_maker/    Example 4: a market maker across regime shifts

Python 3.11 or later is assumed.

Oracles. In a bundle directory, "python3 exN_oracle.py" recomputes every number the document
quotes for that example, prints one line per check, writes exN_results.json, and exits with a
nonzero status if any check fails.

  example   checks   running time         needs
  1         92       about two minutes    numpy, networkx, python-sat
  2         69       about two minutes    numpy, python-sat, dd
  3         57       a few seconds        nothing beyond the standard library
  4         87       about two seconds    numpy, scipy

Proofs. Examples 1 and 2 use a satisfiability solver (CaDiCaL 1.5.3 through python-sat), and every
unsatisfiable answer comes with a DRAT proof, written with its CNF to obligations/. With MDINC_TOOLS
naming a directory that holds drat-trim/drat-trim and cake_lpr/cake_lpr, the oracles convert each
proof to LRAT and check it, and the results that rest on the proofs are Checked. Without the tools
they skip the checks that read the proof checker's verdicts (Example 1 then makes 91 checks,
Example 2 67) and report those results as Conditional, with the assumption
(TrustedBackend cadical 1.5.3 SAT sha256:...). Both bundles also ship the obligations of the run
that wrote their results (exN_obligations.tar.xz) and replay_proofs.py, which replays them with the
two tools alone.

Static checks. ex_check.py needs the specification's validation package (the directory that
holds check_fixtures.py and the registry), named by MDINC_PACKAGE. The patches are listed first,
then "--", then the module file:

  1  python3 ex_check.py ex1_registry_patch.json -- belief_memory.metta
  2  python3 ex_check.py ex2_registry_patch.json -- access_policy.metta
  3  python3 ex_check.py ex1_registry_patch.json ex3_registry_patch.json -- skill_share.metta
  4  python3 ex_check.py ex1_registry_patch.json ex2_registry_patch.json \
         ex4_registry_patch.json -- market_maker.metta

The first pass must report that all forms conform to the registry with the proposed patches.
The second pass lists the diagnostics against the unpatched registry, which are exactly the
forms that depend on the patches.

Packaging. tools/make_package.py (in the working tree, not in this package) copies the files of
each bundle, reruns its oracle and static check, and writes the zips.
