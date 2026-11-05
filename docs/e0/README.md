# MeTTaDinC E0: ingest, milestones, Cetta pin (hive task t-2026-11-05-mettadinc-e0)

This folder is laid out as `projects/mettadinc/` of the hive workspace. The sidecar cannot commit arbitrary workspace paths, so it is delivered here for a human or the chief of staff to copy in. Nothing here is MeTTaDinC implementation code, and nothing was committed to Cetta or any code repository.

| Path | What |
|---|---|
| `docs/` | Every file of the public Drive folder 1QNkx4elmZw0qUf7oQADHkZXr28ERsybW (6 documents as PDF + LaTeX source + pdftotext export; every validation package and bundle, unmodified), and the two Google Docs exported as .md, .txt and .pdf |
| `docs/SOURCES.md` | title, URL, export date, page count, size and sha256 for all 189 files |
| `MILESTONES.md` | M0–M7 from the Cetta work plan, quoted with page references; per-milestone claims with fixture file:line; negative tests; dependencies; algorithms and certificate formats; the 45/78 first-release map; all 123 claims in Appendix A |
| `CETTA.md` | pin (12da03b4, which the plan names), build record, test counts, extension points as file:line |
| `ORACLES.md` | the reference oracles' and evaluators' results: 157 / 305 / 195 / 94 / 99, all reproduced |
| `OPEN_QUESTIONS.md` | 12 questions for Ben |
| `tools/` | crawl.py (Drive crawl), assemble.py (docs/ and SOURCES.md), gen_milestones.py (MILESTONES.md), baseline.sh (Cetta baseline), run_oracles.sh, jdiff.py, env.sh |
| `evidence/` | Cetta build and test logs, oracle outputs, Drive crawl manifest |

`SHA256SUMS` covers every file in this folder.
