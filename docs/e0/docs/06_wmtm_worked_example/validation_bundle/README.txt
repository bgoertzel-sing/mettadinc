Omega memory and goals in MeTTaDinC, worked example: WMTM's open-item store, from journal to gate
Validation bundle, 4 November 2026

This bundle accompanies "Omega Memory and Goals in MeTTaDinC, Worked Example: WMTM's Open-Item
Store, from Journal to Gate", which applies the method of Part II ("Live Memory through Summary
Statistics") end to end to the open items of WMTM's goal engine. The deployment is SIMULATED:
eight weeks of the engine's log-only phase, generated from a fixed seed. No data from a running
WMTM system were used. Where the text and this bundle differ, the bundle is authoritative.

Requirements: Python 3.11 or later with numpy, scipy, z3-solver and cvc5
(pip install numpy scipy z3-solver cvc5). The results were produced with numpy 2.5.3,
scipy 1.18.1, z3-solver 5.3.3 and cvc5 1.4.2.

Contents

  wmtm_example.metta        the three modules of the example (WMTMStore, WMTMRelease,
                            WMTMReceipts) with their 33 requests; the regions between
                            ";; @excerpt <name>" and ";; @end" are the excerpts printed in the text
  wmtm_example.template.metta
                            the same file with {DIGEST:<stream>} placeholders, from which
                            wmtm_example.metta is written once the stream digests are known
  make_module.py            regenerates the twelve streams in streams/ from the seed and writes
                            wmtm_example.metta from the template with their digests; on an
                            unchanged bundle it changes nothing
  live_memory.metta         Part II's module file; WMTMStore and WMTMRelease import from its
                            module LiveOpenItems
  memory_goals.metta        Part I's module file, imported by live_memory.metta
  wx_registry_patch.json    the example's registry patch: the Scheme and MeanTimeToFalseAlarm
                            arguments of Detect (the Shiryaev-Roberts changepoint scheme), with
                            Level made optional and four result fields added
  ls_registry_patch.json    Part II's patch, which also supplies the View field of Keyed and the
                            Population, Selection and Policy fields of Stream
  ex1_registry_patch.json   patches reused from "MeTTaDinC in Practice: Four Worked Examples" and
  ex2_registry_patch.json   from Part I
  ex4_registry_patch.json
  mg_registry_patch.json
  ex_check.py               static checker: parses the module files and checks every form against
                            the registry with the patches applied
  ls_eval.py                Part II's reference evaluator, extended to the changepoint scheme of
                            Detect. It checks the premise of every lift, the target of every safety
                            transfer and the digest of every stream before computing anything, and
                            reports each verdict with its assurance: Conditional on
                            (TrustedBackend cvc5 ...) when an obligation went to the solver, Checked
                            when exact evaluation decided it, Refuted with a replayed witness (a
                            test aid, not an implementation of MeTTaDinC)
  wx_oracle.py              the oracle
  wx_results.json           the oracle's results ("results", one entry per check), the derived
                            facts the text quotes ("facts"), and every verdict of the 33 requests
                            ("verdicts") with its status, assurance, assumptions and binding; each
                            Conditional verdict lists Z3's agreement under agreed_by
  models/wx_sim.py          the simulated deployment: the journal, the two record designs, the
                            daily cycle, the review of proposals and closings, the audits, the
                            changepoint monitor in the loop with its confirmation rule, the
                            rollback and re-parse, and the frozen streams
  models/wx_facts.py        derived facts: counts, the regression, the monitors' traces, the
                            decomposition of stale proposals, the planning sizes, the ground truth
  models/wx_smt.py          Z3 encodings, written by hand, of the example's statistics, the
                            minimality of the release's engine index and the rebuild
  models/cs.py              Part II's confidence sequences and sample sizes
  streams/                  the twelve frozen streams; ten are pinned by SHA-256 digest in
                            WMTMReceipts, each with its population, selection rule and policy, and
                            the journal and the proposal log are read by the oracle

Running the oracle

  python3 wx_oracle.py

Part A regenerates the deployment from its seed, writes the twelve streams again into a temporary
directory and compares them byte for byte with the shipped ones, and recomputes the numbers of the
text: the counts of the run, the regression, its confirmation and the two monitors (including a
counterfactual run without the rollback), the estimates, the ground truth they are checked
against, the decomposition of the stale proposals, the planning figures, and the symbolic
obligations of the example's statistics in Z3. Part B reads the three module files with
ls_eval.py, answers all 33 requests of the example from the module text (cvc5 for the symbolic
ones, the pinned streams for the others), replays every witness, compares each verdict and number
with Part A, runs four differential tests (the conformance replay of all 8,966 daily decisions of
the frozen journal through the module's maps, a randomized test of the snooze semantics against a
direct implementation, the rebuild of the release's indexes from the durable records for all 1,362
keys, and a replay of the frozen journal through the release's engine index with snoozes given on
proposals, which leaves every key's first proposal and so the key receipts of E2 unchanged), and
checks that a copy of RepliesGate whose stale labels were all set to 0 under the declared digest is
refused with InvalidInput. Symbolic verdicts are Conditional on cvc5, since no solver proof is
checked; the oracle checks that Z3 reaches the same verdict on every obligation and records that
agreement under agreed_by. The oracle prints one line per check (99 in all, about 12 seconds on one
core), rewrites wx_results.json, and exits with a nonzero status if any check fails.

Running the static check

  MDINC_PACKAGE=/path/to/mettadinc_validation_package python3 ex_check.py \
      ex1_registry_patch.json ex2_registry_patch.json ex4_registry_patch.json \
      mg_registry_patch.json ls_registry_patch.json wx_registry_patch.json \
      -- memory_goals.metta live_memory.metta wmtm_example.metta

It reports the modules, declarations and run requests of the three files (the example's own are 3
modules, 85 declarations and 33 run requests), all conforming to the registry with the patches,
and then lists the diagnostics against the unpatched registry. Without wx_registry_patch.json it
reports three errors, all on the Detect request that selects the changepoint scheme.

Regenerating the streams

  python3 models/wx_sim.py [directory]

runs the eight weeks from the seed 20261104, prints the alarm and its confirmation, and writes the
twelve streams with their digests into the directory given, by default streams_regenerated/ beside
streams/, so that the shipped streams are not overwritten. The ground truth stays inside the
simulation and reaches the streams only as the review's labels, the audit's findings and the column
"truth" of the journal, which the record designs never read.
