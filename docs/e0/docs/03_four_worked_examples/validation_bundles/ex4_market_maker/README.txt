Example 4: a market maker across regime shifts (MeTTaDinC worked example), 4 November 2026.

market_maker.metta       four modules with their requests; forms marked PROPOSED need the patches
                           MarketDesk     the quoting problem in calm, toxic, buyers' and sellers'
                                          markets; the risk-bucket compression; the mirror; policy
                                          optimality and the pulled-back policy
                           InformedFlow   toxic flow as a hidden distinction; averaging; coarse and
                                          refined optima; a noisy toxicity signal with a price
                           NewsLeak       did the news leak?  trace and behavioral claims, minimal
                                          linear dimensions (no patch needed except the Like field)
                           ShiftMonitors  likelihood-ratio monitors and Estimated detections
ex4_registry_patch.json  proposed additions: the Laws library, DecisionProcess, extended Decisions
                         requests, CheckOptimal, PullbackPolicy, the Monitors library
                         (make_patch.py writes it)
ex1_registry_patch.json  the NatArith library (Lt, Max, ...) proposed with Example 1
ex2_registry_patch.json  the Families library (Parameters, Switch) and the Like field, Example 2
ex_check.py              static check against the registry plus the three patches:
                           MDINC_PACKAGE=/path/to/validation/package python3 ex_check.py \
                             ex1_registry_patch.json ex2_registry_patch.json \
                             ex4_registry_patch.json -- market_maker.metta
metta_eval.py            a small reference evaluator for the maps of the module (laws, parameters;
                         the same file as in Examples 1 and 3)
mm.py                    the Python model: regimes, decision processes, exact policy iteration,
                         optimality witnesses, representation witnesses, homomorphisms, the
                         informed-flow split, the signal and the wrong evaluation
kantorovich.py           exact Kantorovich behavioral distances: rational simplex, couplings,
                         potentials and the fixed-point verification
news.py                  the news-leak tape: bisimulation, Krylov trace space, trace witnesses
monitors.py              monitor laws, validity, blindness, chi-square, the stream generator and
                         the exact e-process along a stored stream
streams/*.json           the three simulated streams (data; the module pins their digests)
ex4_oracle.py            recomputes and checks every quoted number (87 checks, about two seconds;
                         needs numpy and scipy for the float stage of the distance computation)
ex4_results.json         the oracle's output
