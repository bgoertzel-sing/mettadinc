Omega memory and goals in MeTTaDinC: validation bundle
4 November 2026

This bundle accompanies "Omega Memory and Goals in MeTTaDinC: A Practical Implementation Guide".
It contains the guide's eight patterns as one MeTTaDinC module file, the registry patch the guide
proposes, Python models of every pattern, a reference evaluator, and an oracle that recomputes
every number in the guide. Where the guide's text and this bundle differ, the bundle is
authoritative. Python 3.11 or later is assumed, with the standard library only.

Contents

  memory_goals.metta        the ten modules of the eight patterns, with their requests, among
                            them two negative fixtures whose required status is InvalidInput; the
                            regions between ";; @excerpt <name>" and ";; @end" are the excerpts
                            printed in the guide
  mg_registry_patch.json    the guide's registry patch: the Consumer declaration (Of; Accepts,
                            with its clause for Conditional results; Custody; Decode), the
                            CheckInterpretation request and its RecordWitness, the atoms of the
                            Accepts clause (added to Core), and the Pairs field of Implementation
  ex1_registry_patch.json   patches reused unchanged from "MeTTaDinC in Practice: Four Worked
  ex2_registry_patch.json   Examples" (NatArith and Meet; Families, Parameters, Like and
  ex4_registry_patch.json   ActionsOf; Laws, Monitors, Monitor, Stream, CheckMonitor, Detect)
  ex_check.py               static checker: parses the module and checks every form against the
                            registry with the patches applied
  models/                   Python models, one file per pattern (p1_open_items.py ...
                            p8_monitor.py), and the small library dclib.py they share
  mg_eval.py                reference evaluator: rebuilds the module's carriers, maps, machines,
                            representations, abstraction maps, block partitions, tolerances and
                            implementation contracts from the module text; reads Consumer
                            declarations, answers CheckInterpretation, records the binding of a
                            result and applies the gate's coverage rule (a test aid, not an
                            implementation of MeTTaDinC)
  mg_oracle.py              the oracle
  mg_results.json           the oracle's results, one entry per check
  streams/                  the two recorded streams of Pattern 8, pinned in the module by
                            SHA-256 digest

Running the oracle

  python3 mg_oracle.py

Part A computes every number of the patterns from the Python models with exact rational
arithmetic. Part B rebuilds every object of the module from the module text with mg_eval.py,
reruns the checks and compares them with Part A; it also answers the CheckInterpretation requests,
checks every Consumer declaration and the acceptance rule on the specification's combined Accepts
form, and applies the gate's coverage rule to bundles built from the module's results. Part A also
classifies two further goal changes on the model, a coarsening and a failed migration, so that all
six kinds of change are exercised. The oracle prints one line per check (195 in all, about 70
seconds on one core),
rewrites mg_results.json, and exits with a nonzero status if any check fails.

Running the static check

The checker needs the MeTTaDinC specification's validation package, which holds the registry and the
base checker (check_fixtures.py):

  MDINC_PACKAGE=/path/to/mettadinc_validation_package python3 ex_check.py \
      ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json \
      mg_registry_patch.json -- memory_goals.metta

The patches before "--" are applied in order. The first pass reports 10 modules, 318 declarations
and 92 run requests, all conforming to the registry with the patches. The second pass lists the
diagnostics against the unpatched registry, which are the forms that depend on the patches.

The streams

streams/stale_alt_seed1.json and streams/stale_null_seed1.json were generated once with seed 1
(stale with probability 1/5 and 1/20, 400 suggestions each) and are stored as data. Reproducing a
detection means replaying the stored stream, not rerunning the generator.
