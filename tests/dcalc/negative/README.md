# M0 negative acceptance suite (AC4)

`python3 tests/dcalc/negative/run_negative.py` runs the ten entries of the
negative acceptance suite in `docs/e0/MILESTONES.md` (M0 section) through the
`build/dcalc/dcalc` CLI and exits 0 only if every entry passes.

The rule from the milestone text: an entry whose request needs a later
milestone is answered Unsupported until that milestone, and a binding
failure is InvalidInput from M0 on. Entries 9 and 10 may also be Unknown.

| # | Entry | Fixture | Requests matched | M0 status | Why |
|---|---|---|---|---|---|
| 1 | Keyed index with the statistic of a machine with fewer queries | `05_live_memory_part2/.../live_memory.metta:103,115` | `CheckStatistic EngineAsItems` | InvalidInput, field `Item` | binding: `EngineStat` is of `EngineTime`, not of the Store's item machine `ItemTime`, and there is no `(View ...)` |
| 2 | CheckSafety via a simulation of another machine | `live_memory.metta:357` | `CheckSafety NormFirst ... (Via StutterWeighted)` | InvalidInput, field `Via` | binding: `StutterWeighted` targets `Weighted`, not `NormFirst` |
| 3 | Receipt stream that does not match its declared digest | copy of `06_wmtm_worked_example/validation_bundle`, with every `stale` label in `streams/replies_gate.json` set to 0 | `EstimateRate (On RepliesGate) ...` | InvalidInput, field `Digest` | binding: the file's sha256 differs from `(Digest "sha256:...")`. The untouched bundle must give no InvalidInput |
| 4 | Access policy approver rule reads the auditor session | `03_four_worked_examples/.../access_policy.metta:23` | every `AccessPolicy` request | Unsupported | needs parameterised maps and block partitions (later milestone) |
| 5 | anti-nag passes CheckNow but fails interpretation | `04_omega_memory_goals_part1/.../memory_goals.metta:526,528,576` | `AntiAsNag`, `NagForAntiNag` | Unsupported | needs a non-enumerated profile and CheckInterpretation |
| 6 | E2 does not transport to a policy withholding first proposals | `wmtm_example.metta` | every `WMTM*` request | Unsupported | needs stochastic profiles and estimates |
| 7 | Consumer accepting only some Conditional backends | `memory_goals.metta:39-41` | `Consumer` | Unsupported | Conditional/TrustedBackend is outside M0 |
| 8 | Literal congruence under an indiscrete code tolerance | `01_.../fixtures/hypotheses.metta` (LiteralCongruence) | C01, C02, C03 | Checked, Checked, Refuted | the M0 claims themselves. C03's witness is the literal congruence failure |
| 9 | Adaptive probe certificate limits | `fixtures/certificate_limits.metta:6,32-36` | `AdaptiveProbe` | Unsupported (Unknown allowed) | M4 |
| 10 | Unattained supremum | `fixtures/certificate_limits.metta:40,54-57` | `UnattainedSupremum` | Unsupported (Unknown allowed) | M4 |

Binding validation (entries 1-3) is in `src/dcalc/binding.c`. It runs on the
raw module source before admission and before the profile gate, so a binding
error is reported even on a module that is otherwise outside M0. Names that a
module imports from another module in the same file (`Import ... (Only ...)`)
are resolved. A name imported from another file is not checked, and it is
not reported as an error.
