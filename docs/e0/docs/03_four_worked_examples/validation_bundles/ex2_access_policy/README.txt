Example 2: auditing an administrative access-control policy on forty-bit words
(MeTTaDinC worked example), 4 November 2026.

access_policy.metta      the policy as written (AccessPolicy) and corrected (AccessPolicyFixed), with
                         the audit's partitions, slices and requests; forms marked PROPOSED need the patch
ex2_registry_patch.json  the proposed registry additions (indexed families, Gather, Invariant, ...)
ex_check.py              static check against the registry plus the patch:
                           MDINC_PACKAGE=/path/to/validation/package python3 ex_check.py \
                             ex2_registry_patch.json -- access_policy.metta

The source route (every obligation, witness and reachable set of the oracle comes from here):
policy_ir.py             reads access_policy.metta, resolves imports, expands the Families forms and
                         elaborates every map into a typed intermediate form (IR): Boolean terms over
                         the bits of a word, and guarded updates for the actions; also the Tseitin
                         encoder of the IR, and a direct interpreter of the source terms on arrays
obligations.py           closure, implication, two-copy and read-off obligations built from the IR;
                         solving with CaDiCaL 1.5.3, DRAT proofs, and the proof replay
bdd_reach.py             exact reachable sets with decision diagrams (dd), from the IR's guarded
                         updates (and, for comparison, from the independent model)
validate_small_lib.py    translation validation on the two-user (20-bit) instance of the same source:
                         interpreter, IR and CNF agree on every word, action, observer and closure
                         obligation; also the comparisons of the independent model below

The independent model (kept as a differential check; it does not read the module):
rbac.py                  the policy as executable Python (bit layout, actions, observers)
circuits.py              a hand-written Tseitin encoder for the same obligations
sat_obligations.py       the closure obligations of the hand-written encoder

ex2_oracle.py            recomputes and checks every quoted number (69 checks, about two minutes;
                         67 without the proof tools); needs numpy, python-sat and dd.  It also
                         applies two source mutations that restore the example's authoring mistakes
                         and requires the affected claims to change.  Set MDINC_TOOLS to a directory
                         holding drat-trim/drat-trim and cake_lpr/cake_lpr to convert every DRAT
                         proof to LRAT and check it; then the proved claims are Checked.  Without the
                         tools they are reported as Conditional, with a
                         (TrustedBackend cadical 1.5.3 SAT sha256:...) assumption.
ex2_results.json         the oracle's output, with the status, assumptions and source binding
                         (module digest, declarations) of every claim
ex2_obligations.tar.xz   the obligations of the run that wrote ex2_results.json: the CNF and DRAT
                         proof of every unsatisfiable obligation (those of the two mutated sources in
                         mutations/), with index.json (names, claims, digests, module digest)
replay_proofs.py         replays the shipped proofs without python-sat:
                           MDINC_TOOLS=/path/to/tools python3 replay_proofs.py \
                             ex2_obligations.tar.xz access_policy.metta

Proof pipeline used: drat-trim at 2e3b2dc0ecf938addbd779d42877b6ed69d9a985 (DRAT to LRAT, option -L),
cake_lpr at 033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2 (cake_lpr.S sha256 d20ceae0...cc78f7), run as
    cake_lpr --CML_HEAP_SIZE=1024 --CML_STACK_SIZE=512 obligation.cnf obligation.lrat
(the default 4096 MiB heap and stack could not be allocated on a 7 GB machine).
