Example 3: sharing skills between robots whose cameras see the bay in different frames
(MeTTaDinC worked example), 4 November 2026.

skill_share.metta        three modules: SkillShare (progress task), SkillShareDock (docking task),
                         PalletBay (an extra pallet in C's bay), with their requests; forms marked
                         PROPOSED need the patch
ex3_registry_patch.json  proposed additions: TransportSkill, FindTransfers, GaugeFrom
ex1_registry_patch.json  the NatArith library (Le, Lt, ...) proposed with Example 1, used here too
ex_check.py              static check against the registry plus both patches:
                           MDINC_PACKAGE=/path/to/validation/package python3 ex_check.py \
                             ex1_registry_patch.json ex3_registry_patch.json -- skill_share.metta
d4.py                    the bay, the dihedral group on cells and directions, the two tasks
robots.py                robots as method systems in their own camera frames
hive.py                  transfers, transfer-hive checks, derived kernel hives, closure and cost
metta_eval.py            a small reference evaluator for the maps of the module (the same file as in
                         Examples 1 and 4)
ex3_oracle.py            recomputes and checks every quoted number (57 checks, a few seconds); it also
                         checks that the module's responses, free cells, transfers, symmetries and
                         skills are those of the Python model at every cell and command
ex3_results.json         the oracle's output
