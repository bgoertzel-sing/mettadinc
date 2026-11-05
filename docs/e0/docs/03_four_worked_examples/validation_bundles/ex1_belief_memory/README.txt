Example 1: compacting an agent's belief memory (MeTTaDinC worked example), 4 November 2026.

belief_memory.metta      the four modules (BeliefMemory, GentleMemory, AgentMemory, ReceiptLedger)
                         with their requests; forms marked PROPOSED need the registry patch
ex1_registry_patch.json  the proposed registry additions the example uses
ex_check.py              static check of the modules against the registry plus the patch:
                           MDINC_PACKAGE=/path/to/validation/package python3 ex_check.py \
                             ex1_registry_patch.json -- belief_memory.metta
metta_eval.py            a small reference evaluator for the maps of the module files
ex1lib.py                the model and the exact algorithms (pair-graph fixpoints, canonical witnesses)
ex1_oracle.py            recomputes every quoted number and checks it (92 checks, about two minutes;
                         91 without the proof tools); needs numpy, networkx and python-sat.  It first
                         checks, state by state, that the module's maps define the model, and builds
                         every table and obligation from the module-derived machines.  Every
                         solver refutation is written to obligations/ as a CNF with its DRAT proof;
                         set MDINC_TOOLS to a directory holding drat-trim/drat-trim and
                         cake_lpr/cake_lpr to convert each proof to LRAT and check it.  Without the
                         tools the optimality claims that rest on a refutation are reported as
                         Conditional, with a (TrustedBackend cadical 1.5.3 SAT sha256:...) assumption.
ex1_results.json         the oracle's output, with the status and assumptions of every frontier claim
ex1_obligations.tar.xz   the obligations of the run that wrote ex1_results.json: the CNF and DRAT
                         proof of each of the nine refutations, the colorings, cliques and center sets
                         that certify each frontier value, and index.json (names, claims, digests)
replay_proofs.py         replays the shipped proofs without python-sat:
                           MDINC_TOOLS=/path/to/tools python3 replay_proofs.py \
                             ex1_obligations.tar.xz belief_memory.metta

Proof tools used: drat-trim at 2e3b2dc0ecf938addbd779d42877b6ed69d9a985 (DRAT to LRAT, option -L) and
cake_lpr at 033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2, run as
    cake_lpr --CML_HEAP_SIZE=1024 --CML_STACK_SIZE=512 obligation.cnf obligation.lrat
