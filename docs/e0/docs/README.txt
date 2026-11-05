MeTTaDinC and Omega memory and goals: review package, 4 November 2026
=====================================================================

This package holds the six documents of the MeTTaDinC series, each as a compiled PDF with its
pure-ASCII LaTeX source, together with the validation material that backs its claims. The
documents build on one another in the order of the folders.

  folder                          document                                              pages
  01_language_specification       MeTTaDinC: An Executable Language for                 86
                                  Observer-Relative Abstraction, Evidence, and
                                  Composition (specification draft)
  02_cetta_implementation_guide   Implementing MeTTaDinC in Cetta: A Coding-Agent       30
                                  Specification and Work Plan
  03_four_worked_examples         MeTTaDinC in Practice: Four Worked Examples           79
  04_omega_memory_goals_part1     Omega Memory and Goals in MeTTaDinC: A Practical      66
                                  Implementation Guide (Part I)
  05_live_memory_part2            Omega Memory and Goals in MeTTaDinC, Part II: Live    53
                                  Memory through Summary Statistics
  06_wmtm_worked_example          Omega Memory and Goals in MeTTaDinC, worked example:  45
                                  WMTM's Open-Item Store, from Journal to Gate

All six are dated 4 November 2026.

What each folder contains

  01  The specification (PDF and .tex) and its validation package in validation_package/: the
      machine-readable registry of declarations and requests, the fixture modules for every
      example, the claims manifest, an exact-arithmetic oracle with its results, the static
      checker check_fixtures.py, and pinned tool versions. The other documents' static checks
      need this folder (see "Running the checks" below).
  02  The coding-agent implementation guide for hosting MeTTaDinC in the Cetta runtime (PDF and
      .tex). It has no separate bundle; it relies on the validation package of 01, and its
      negative acceptance suite points to fixtures in the bundles of 03 to 06.
  03  The four worked examples (PDF and .tex) and one validation bundle per example in
      validation_bundles/ex1_... to ex4_..., each with its module file, registry patches, Python
      model, oracle and results; validation_bundles/README.txt lists running times and
      requirements.
  04  Part I (PDF and .tex) and its bundle in validation_bundle/: eight patterns of Omega's memory
      and goal machinery as finite MeTTaDinC models, with an oracle and a reference evaluator.
  05  Part II (PDF and .tex) and its bundle: summary statistics whose obligations the cvc5 and Z3
      solvers decide for every state of real-valued carriers, plus anytime-valid estimates and
      monitors.
  06  The worked example of Part II (PDF and .tex) and its bundle: the method applied end to end to
      a SIMULATED eight-week deployment of WMTM's goal engine.

Status of the material

  - No MeTTaDinC runtime exists yet. Every MeTTaDinC result in documents 03 to 06 was obtained
    from the module text by a reference evaluator written in Python (a test aid, not an
    implementation) and, independently, from Python models; each bundle's oracle compares the two.
  - All documents follow one assurance policy, stated in Section 2 of the specification. A result
    is Checked only when the core established it by an exact method or by a certificate it
    replayed. A verdict that rests on a solver's answer without a checked proof is Conditional,
    with the assumption (TrustedBackend solver version logic obligation-digest); agreement of a
    second solver is recorded under agreed_by as evidence and discharges nothing. A result derived
    from Conditional premises carries their assumptions. Consumers declare which Conditional
    results they accept, and a gate counts any other Conditional result as inadequate coverage.
  - The symbolic verdicts of 05 and 06 were obtained from cvc5 on obligations built from the
    module text and from Z3 on encodings written by hand; no proof is checked, so they are
    Conditional on cvc5, and each oracle records Z3's agreement under agreed_by in its results
    file.
  - Forms marked PROPOSED in the module files are not in the specification's registry; each
    bundle's registry patch (*_registry_patch.json) defines them, and the static checker reports
    exactly which forms depend on a patch.
  - Document 06 uses simulated data only. Nothing in the package describes a change made to a
    running Omega or WMTM system.
  - Where a document's text and its bundle differ, the bundle is authoritative.

Running the checks

  Python 3.11 or later. Requirements differ by bundle and are listed in each README; the bundles
  of 05 and 06 need numpy, scipy, z3-solver and cvc5.

  Oracles: in each bundle folder, run its oracle (for example "python3 wx_oracle.py" in
  06_wmtm_worked_example/validation_bundle). Each prints one line per check and exits with a
  nonzero status if any check fails. The oracles and their check counts:

    01  validation_package/oracle/verify_mettadinc.py   157 checks; check_fixtures.py checks
                                                         every fixture against the registry
    03  ex1_oracle.py to ex4_oracle.py                   92, 69, 57 and 87 checks (305 in all;
                                                         91 and 67 for Examples 1 and 2 when
                                                         the proof checkers are not installed)
    04  mg_oracle.py                                     195 checks, about 70 seconds
    05  ls_oracle.py                                     94 checks, about 11 seconds
    06  wx_oracle.py                                     99 checks, about 12 seconds

  Examples 1 and 2 of 03 check their DRAT proofs when MDINC_TOOLS names a directory holding
  drat-trim/drat-trim and cake_lpr/cake_lpr, built from the commits pinned in
  01_language_specification/validation_package/DEPENDENCIES.json; without the two tools the
  results that rest on those proofs are reported as Conditional.

  Static checks: the checker ex_check.py in every bundle of 03 to 06 imports the specification's
  checker, so point MDINC_PACKAGE at the specification's validation package (adjust the relative
  path to the bundle's depth), for example from 06_wmtm_worked_example/validation_bundle:

    MDINC_PACKAGE=../../01_language_specification/validation_package python3 ex_check.py \
        ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json \
        mg_registry_patch.json ls_registry_patch.json wx_registry_patch.json \
        -- memory_goals.metta live_memory.metta wmtm_example.metta

  The exact command for each bundle is in its README.

Suggested reading order

  For the language: 01, then 03 for worked use, then 02 for the implementation plan.
  For Omega's memory and goals: 04, then 05, then 06.
