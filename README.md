# mettadinc
MeTTaDinC sublanguage on Cetta

## The MeTTaDinC epic

This repository is where MeTTaDinC is to be built on Cetta, following Ben Goertzel's MeTTaDinC documents and the
milestones M0–M7 of the Cetta work plan. It holds no implementation code yet, and no Cetta: milestone M0 adds Cetta as a
pinned submodule.

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
| [docs/e0/CETTA.md](docs/e0/CETTA.md) | Cetta pin (12da03b4), build record, test counts, extension points |
| [docs/e0/ORACLES.md](docs/e0/ORACLES.md) | The reference oracles' and evaluators' results, reproduced |
| [docs/e0/OPEN_QUESTIONS.md](docs/e0/OPEN_QUESTIONS.md) | Questions E0 raised for Ben |
| [docs/e0/tools/](docs/e0/tools/) | E0's scripts (crawl, assembly, milestone generation, Cetta baseline, oracle runs) |
| [docs/e0/evidence/](docs/e0/evidence/) | Cetta build and test logs, oracle outputs, the Drive crawl manifest |

### Ben's decisions

1. Adopt the bundles' proposed registry patches before M0.
2. Cetta "green" means no regression against E0's frozen baseline at Cetta commit 12da03b4.
3. Use CUDD 3.0.0 for M3.
