# Evidence: t-2026-11-24-mettadinc-m0-gap-g

Base: mettadinc main 61eb9ba (merge of PR #51, the cases-logic rebase; contains the bool-observe, typeform-maps,
like-machines and body-maps lowerings). Change: src/dcalc/model.c (commit 6d1cdaf) admits a (To Bool) map with a
type-form From when an Observe port of a Crisp machine names it (repro g). Host: pop-os, gcc 11.4. Base binary sha256
82473fff8700aef95c9201cdea3963d27728e394cff8a77ced3f703161186806; new binary sha256
9b596cc5df764aff6102170ddca3746ac302c7ae742db036c577d59c70ae0dbc. The order text was not available locally; the scope
(close repro g, nothing else) was inferred from the WIP commit, the sibling evidence and examples_e2e finding 5.

| file | what |
|---|---|
| gate_new.txt | tests/dcalc/m0_gap_g/run_m0_gap_g.py on this branch: 135 PASS |
| gate_on_base_binary.txt | the same gate with the 61eb9ba binary: 106 FAIL (G1, GG1-3, doc04 AnchorMigration Unsupported "field From"; the near misses NF2, NW1-3, NE1, NU1, NU2 Unsupported "field From" instead of their twins' answers). The unchanged near misses NT1, NF1, NG1, NA1 pass there |
| gate_on_mutant_first.txt, mutant_first.diff | meaning mutant: after tabulation every state gets the first state's value (constant observation): 24 FAIL (GG1 RF, GG2 R1/H12/H13; by hand, reference and twin) |
| gate_on_mutant_reversed.txt, mutant_reversed.diff | meaning mutant: state i gets the value of state n-1-i: 12 FAIL (GG2 R1/H13/H12I; GG1's same is a palindrome T F F T, so it does not see this one) |
| gate_sanitized.txt | the gate with an ASan/UBSan build of this branch (-fsanitize=address,undefined -fno-sanitize-recover=all): 135 PASS |
| sanitizer_direct.txt | the sanitized binary run directly (stderr kept) on both fixtures, repro g and memory_goals.metta, both modes: 8 runs, exit 0, empty stderr (the gate runner discards stderr, so this is the sanitizer check proper) |
| bytediff.txt, bytediff_lines.diff | every tracked .metta outside cetta/ (267 files) run alone in release and --beyond-release mode, 61eb9ba binary vs new binary (tests/dcalc/m0_like/metta_bytediff.py): 8 of 534 outputs differ: doc04 memory_goals.metta and its copies in the 05 and 06 bundles (AnchorMigration NaiveMigration Unsupported -> Refuted, CellMigration Unsupported -> Checked, both modes; no other line changes) and repro g (G1 Unsupported -> Checked). The new gate fixtures were untracked when this ran |
| run_e2e.log, e2e_tsv.diff | run_e2e.py on this branch: only out/mg_release.tsv and out/mg_beyond.tsv change, rows 43-44 (AnchorMigration): Refuted and Checked, doc04's answers. make_tables.py then reclassifies doc04 rows 43-44 GAP -> match (totals: match 4 -> 6, GAP 2 -> 0 per mode) |
| dcalc-run-all.log, dcalc-run-all.env | tools/dcalc-run-all.sh on this branch (with the new m0_gap_g step) with the pinned proof backend (tools/dcalc-proof-backend.sh: CaDiCaL 3.0.1, cake_lpr 033aad5, same sha256 pins as evidence/m0-body-maps) and the E0 GMP prefix (projects/mettadinc/tools/env.sh); CeTTa submodule at its pin 4c285a97 |

## Does AnchorMigration now give doc04's answer?

Yes, on memory_goals.metta verbatim, in both modes: NaiveMigration Refuted with witness state (absent none), action
repair, Left (present new), Right (present old), which is the state and action of the reference evaluator and of
mg_results.json ("B AnchorMigration: NaiveMigration"); CellMigration Checked with the commutation table
(present old) -> (present new), (absent none) -> (absent none). doc04 s6.4 l.1422 and l.1425 give Refuted and Checked.

With rows 43-48 matching and row 49 VALUE, every library-free doc04 request now reaches a decision procedure.

## Caveat on what the doc04 rows prove

Both mutants also give doc04's answers and witness on AnchorMigration (gate_on_mutant_*.txt: the doc04 rows pass).
Matching doc04 therefore does not by itself show that the Bool observations are tabulated correctly; the GG fixtures,
checked by hand, by the reference evaluator and against declared-carrier twins, do.

## Wiring

The gate runs as step m0_gap_g in tools/dcalc-run-all.sh, after m0_cases_logic, as the sibling m0 gates do.
tests/dcalc/differential/gate.sh and mutate_gate.sh (the M4/M6 differential gate) are not touched: none of the m0
gates is wired there, and the mutants for this change are recorded here as for m0-body-maps.

Files changed besides the gate and this directory: tests/dcalc/examples_e2e/out/mg_{release,beyond}.tsv (regenerated),
doc04_omega_memory_goals.md (make_tables.py), README.md (totals; GAP class text; update note under finding 5),
repro/m0_blocker_g_bool_typeform_from.metta (header comment only), tools/dcalc-run-all.sh (one step).
