# mettadinc
MeTTaDinC sublanguage on Cetta

## The MeTTaDinC epic

This repository is where MeTTaDinC is to be built on Cetta, following Ben Goertzel's MeTTaDinC documents and the
milestones M0–M7 of the Cetta work plan. It holds the M0 core: the `dcalc` checker in `src/dcalc/` (C, built and
tested by `tools/dcalc-run-all.sh`) with its independent replay checker and suites in `tests/dcalc/`; M1–M4 are built
on it (M3's symbolic carriers need the pinned proof backend, see [docs/PROOF-BACKEND.md](docs/PROOF-BACKEND.md); M4's stochastic
fragment answers only with `dcalc --beyond-release`, release 1 still answers Unsupported, gates in `tests/dcalc/m4/`); M5's nondeterministic
fragment (simulation, safety transfer, outcome sets and probabilities) also answers only with `dcalc --beyond-release`,
gates and an independent replayer in `tests/dcalc/m5/`; M6 (Contracts, Hives, Transfers; crisp profile, `--beyond-release` only) has gates and an independent replayer in `tests/dcalc/m6/`; M6-rest (general LCR as an exact LP, the Fork merge model, CompleteHive with the completed hive as `(Output C Hive)`, associators, an arrow-kind table that is documentation only; `--beyond-release` only) has gates, probes and an independent replayer in `tests/dcalc/m6rest/` (`python3 tests/dcalc/m6rest/run_m6rest_gates.py`, also a dcalc-run-all step); M6-graded (graded kernel hives with rational degrees in [0, 1] under the Łukasiewicz algebra of Def 3.3/Def 10.1: coherence, holonomy, ConsensusCost, LeastCoherentRefinement, associators and CompleteHive; `Then` over two Checked simulations by relational composition; a "not in the spec" list for state-dependent pushforwards; `--beyond-release` only) has gates, probes and independent replayers in `tests/dcalc/m6graded/` (`python3 tests/dcalc/m6graded/run_m6graded_gates.py`, also the dcalc-run-all step m6graded_gates). Optional Python dependency: `sympy` (`pip install sympy`) enables the probes' separate LP cross-check of LeastCoherentRefinement; without it that cross-check prints a SKIP line with the reason and the replayer's LP certificate check still runs. M7 (the beyond-release fragments of the Cetta plan: availability and neural-audit rows, arithmetic probes, patterns, snapshot receipts, Hyperseed schemas and methods with cross-file imports (M01), and exact mean clock rates under a full-support product law (F07 `ClockRates`); `--beyond-release` only) has negative gates in `tests/dcalc/mutations/run_m7_gates.py` (also the dcalc-run-all step m7_gates) and independent replayers in `tests/dcalc/m7/` (`sh tests/dcalc/m7/run_m7_replay.sh`, also the dcalc-run-all step m7_replay). Items that wait on unpinned dependencies (OmegaPLN oracle, MeTTaProN kernel IR, adapter, proof-plan registry) are listed in [docs/M7-BLOCKED.md](docs/M7-BLOCKED.md) with what dcalc does for each today (a MeTTaProN kernel import answers Unsupported); M7 pins live in [docs/M7-DEPENDENCIES.json](docs/M7-DEPENDENCIES.json), not in `docs/e0/`. Cetta is the git submodule
`cetta/`, pinned to the plan's commit and unmodified (see "M0 prerequisites" below); fetch it with
`git submodule update --init`.

`docs/e0/` holds the reviewed delivery of hive task t-2026-11-05-mettadinc-e0 (E0: ingest, milestones, Cetta pin),
byte for byte. To verify it:

```sh
cd docs/e0 && sha256sum -c SHA256SUMS
```

### Ben's documents

- Source: the public Google Drive folder https://drive.google.com/drive/folders/1QNkx4elmZw0qUf7oQADHkZXr28ERsybW
- Unmodified local copies, with title, URL, export date, size and sha256 for each file:
  [docs/e0/docs/SOURCES.md](docs/e0/docs/SOURCES.md)
- [Executive summary](docs/e0/docs/MeTTaDinC_executive_summary.md) and [explainer](docs/e0/docs/MeTTaDinC_explainer.md)
- [01 Language specification](docs/e0/docs/01_language_specification/mettadinc_language_spec.pdf)
- [02 Cetta implementation guide](docs/e0/docs/02_cetta_implementation_guide/mettadinc_cetta_implementation_guide.pdf)
- [03 Four worked examples](docs/e0/docs/03_four_worked_examples/mettadinc_worked_examples.pdf)
- [04 Omega memory and goals, part 1](docs/e0/docs/04_omega_memory_goals_part1/mettadinc_omega_memory_goals.pdf)
- [05 Live memory, part 2](docs/e0/docs/05_live_memory_part2/mettadinc_live_memory.pdf)
- [06 WMTM worked example](docs/e0/docs/06_wmtm_worked_example/mettadinc_wmtm_worked_example.pdf)

### E0's files

| Path | What |
|---|---|
| [docs/e0/MILESTONES.md](docs/e0/MILESTONES.md) | M0–M7 with claims, fixtures, negative tests, dependencies and the first-release map |
| [docs/e0/CETTA.md](docs/e0/CETTA.md) | E0's Cetta pin (12da03b4, since superseded by 4c285a97), build record, test counts, extension points |
| [docs/e0/ORACLES.md](docs/e0/ORACLES.md) | The reference oracles' and evaluators' results, reproduced |
| [docs/e0/OPEN_QUESTIONS.md](docs/e0/OPEN_QUESTIONS.md) | Questions E0 raised for Ben |
| [docs/e0/tools/](docs/e0/tools/) | E0's scripts (crawl, assembly, milestone generation, Cetta baseline, oracle runs) |
| [docs/e0/evidence/](docs/e0/evidence/) | Cetta build and test logs, oracle outputs, the Drive crawl manifest |

### M0 prerequisites (hive task t-2026-11-05-mettadinc-m0-prep)

| Path | What |
|---|---|
| [registry/mettadinc_registry.json](registry/mettadinc_registry.json) | The one registry M0–M3 build against: the package registry with the bundle patches ex1, ex2, ex3, ex4, mg, ls and wx adopted (decision 1). Its sha256, the registry digest, is in [registry/DIGEST](registry/DIGEST); inputs, copies, revisions, resolutions and the coordinated-change table are in [registry/SOURCES.md](registry/SOURCES.md). Rebuild or verify with `python3 tools/adopt_registry.py [--check]` and the --supersede options recorded in SOURCES.md |
| [validation/check_fixtures.py](validation/check_fixtures.py) | Working copy of the package checker, reading the adopted registry; `cd validation && python3 check_fixtures.py` |
| [tools/check_bundles.py](tools/check_bundles.py) | Each bundle's own ex_check.py check against the adopted registry alone, no patch; must report 0 diagnostics |
| [tools/run-oracles.sh](tools/run-oracles.sh) | The reference oracles, on a copy: 157 / 305 / 195 / 94 / 99 |
| [cetta/](cetta/) | Submodule: zariuq/CeTTa `main` pinned to 4c285a97 (previously 12da03b4; [docs/CETTA-PIN.md](docs/CETTA-PIN.md)), green at 4c285a97 with build overrides (see [docs/CETTA-LATEST.md](docs/CETTA-LATEST.md)); `tools/check-vendored-cetta.sh` checks the gitlink equals the pin and the checkout is at it and clean |
| [tools/cetta-baseline.sh](tools/cetta-baseline.sh) | Decision 2's "green": builds the cetta/ submodule checkout (core, then python), runs the three gates and compares with [tools/cetta-baseline.expected](tools/cetta-baseline.expected), which since the pin move is frozen from the 4c285a97 run evidence/cetta-pin-latest/cetta-baseline/latest-run3-swipl (green at 4c285a97 with build overrides, see [docs/CETTA-LATEST.md](docs/CETTA-LATEST.md); until 87ebf79 it was derived from E0's frozen logs at 12da03b4). Set `MDINC_MAKE_ARGS` to the build overrides and `MDINC_SWIPL_DIR` to a SWI-Prolog 9.x prefix as recorded there. Exit 0 green, 1 regression, 2 build/setup failure. Set `MDINC_GMP_PREFIX` if the system has no GMP headers (see the script's header) |

### Ben's decisions

1. Adopt the bundles' proposed registry patches before M0.
2. Cetta "green" means no regression against E0's frozen baseline at Cetta commit 12da03b4. (Since the pin moved to 4c285a97, by hive task t-2026-11-06-mettadinc-cetta-pin-latest, the frozen baseline is "green at 4c285a97 with build overrides (see [docs/CETTA-LATEST.md](docs/CETTA-LATEST.md))".)
3. Use CUDD 3.0.0 for M3.
   *Deviation (kept after the M3 review, t-2026-11-11-mettadinc-m3-tv-suite):* M3 uses a small in-tree ROBDD,
   [`src/dcalc/bdd.c`](src/dcalc/bdd.c), not CUDD, because:
   - every Checked answer carries an LRAT proof that cake_lpr replays, so a BDD bug cannot yield a false Checked;
     the CNF behind each proof is itself checked against an independent semantics by the translation-validation
     suite (`tests/dcalc/tv_m3.py`, `tests/dcalc/tv_mut.py`, run by `tools/dcalc-run-all.sh`);
   - the forty-bit run takes about 0.25 s;
   - CUDD 3.0.0 (2015) is an older external C dependency;
   - `bdd.c` sits behind the narrow interface of MILESTONES §2.5, so CUDD can be swapped in if a later fixture is too slow.
   The access-policy mutation gate moves to the milestone that admits Families (M3 review 3).
