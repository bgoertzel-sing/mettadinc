# MeTTaDinC after M0-M7: independent system review

Task t-2026-11-14-mettadinc-system-review. Reviewer: ProtomegaTron. Base: `hive/t-2026-11-14-mettadinc-m7` at dd66f6b.
Branch: `hive/t-2026-11-14-mettadinc-system-review`. Date: 2026-11-14.

## Summary

The task was an independent review of MeTTaDinC (`dcalc`) after milestones M0-M7. It covers how the system works, whether
its claims hold up when I check them with my own code, where it departs from the plan, what is blocked, and what to do next.

**What I found:** the whole suite (`tools/dcalc-run-all.sh`) passes on the recorded base: 33 of 33 steps exit 0, in 14 min 24 s[^runall].
I wrote my own checkers in Python, with no repo code and without the repo's replayers. They recompute **at least 2 claims for
every milestone**: 82 checked values across M0-M7, plus 26 of 26 LRAT proofs replayed by my own RUP checker. Every value agrees
with both dcalc and the MILESTONES oracle. I also built **30 inputs of my own** (mutants and variants), giving at least 1
negative gate per milestone. In all but one case dcalc refuses the input or flips its verdict the way my own computation predicts.

**Two findings need a decision.** **D1 (defect, M7, beyond-release only):** a `Cases` map with two rows for the same input is
accepted and the first row wins, where every other loader rejects it (spec §5.4). **D2 (trust-boundary risk, M3):** the
proof-checker binary is only identity-checked when the optional sha256 pins are set; with them unset, a fake checker that
prints `s VERIFIED UNSAT` turns 4 symbolic claims into Checked. With the pins set (as in the suite) every fake is refused.

**Still open:** the four outside integrations stay Unsupported, because their dependencies do not exist yet[^blocked]. Three
F07 sub-features are not done (ClockRates beyond Uniform/Mean, and ConeOfInfluence, whose reason text is stale). There is one
approved deviation, an in-tree ROBDD instead of CUDD[^dec]. The `cetta/` submodule worktree is out of step with its pin (the
suite is unaffected). Ranked next steps (§5): fix D1, close D2, share one admission loader, then randomised differential tests
for M4/M6, whose coverage is fixture-sized and is the largest remaining risk.

No PDF was produced: there is no md2pdf, pandoc or Python `markdown` module on this host[^pdf].

## 1. Building and running the suite

Command (backend exports from `mdc-review/backend.exports.saved`, which pins cake_lpr and the CeTTa toolchain):

```
. /hive/protomega/work/mdc-review/backend.exports.saved
cd /hive/protomega/work/cetta-src/mettadinc
setsid nohup bash tools/dcalc-run-all.sh > /hive/protomega/work/mdc-review/runall.log 2>&1
```

Result: `dcalc-run-all: PASS`, `RUNALL_EXIT=0`[^runall]. Every one of the 33 steps exited 0:

| Step | wall s | Step | wall s | Step | wall s |
|---|---|---|---|---|---|
| build | 12.0 | m2_claims | 0.3 | m4_coverage_01 | 3.1 |
| test_boundaries | 0.2 | m2_gates | 1.3 | cetta_smoke | 635.0 |
| check_claims | 1.9 | m2_differential | 0.2 | m5_weakbarbed | 2.6 |
| negative_suite (10/10) | 3.4 | m2_screen | 0.2 | m5_gates | 5.8 |
| refuted_abs | 0.1 | m2_claimless | 0.3 | m6_gates | 2.4 |
| envelope | 0.4 | m3_incremental | 3.7 | m6rest_gates | 0.3 |
| limits | 0.3 | m3_gates | 1.4 | m6graded_gates | 82.3 |
| limits_sanitized | 26.8 | m3_tv | 66.6 | m7_gates | 0.6 |
| mutation | 3.5 | m4_gates | 0.5 | m7_replay | 0.9 |
| held | 0.1 | m4_estimates | 0.2 | | |
| registry_gen | 0.1 | m4_coverage | 3.3 | | |
| package | 1.1 | admission_mutations | 1.4 | | |

Failures: none. `cetta_smoke` clones the pinned CeTTa submodule (4c285a97), applies the 13 patches in `upstream/cetta/`
and runs 4 MeTTa smoke files (graded, held, smoke, surface); all 4 pass. I confirmed that `build/cetta-dcalc` HEAD~13 is
4c285a97[^pin]. The slow steps are cetta_smoke (a full CeTTa build), m6graded_gates and m3_tv.

Sanity gate (docs/EXPERIMENT_SANITY_GATE.md): before trusting my own checkers I ran canaries through them. `canary_eight.py`
gives check_eight.py 3 tampered envelopes, and it refuses all 3. `canary_lrat4.py` gives lrat.py 4 known-answer cases plus
4 mutation kinds x 8 proofs, refused 8/8 each, with 0 disagreements against cake_lpr. The canary needed 4 versions; the
checker never changed, only mutations that were not real negatives were replaced (see §3.3)[^findings].

## 2. How the system works, in plain terms

A MeTTaDinC file declares a **module** (`DC.Module`): carriers (finite sets of states or values), maps and kernels
(deterministic, nondeterministic, stochastic or graded transitions), observations, and **representations**: proposed
encodings or abstractions of the system. The file then asks **requests** about those representations, for example "does
this encoding answer the query now?", "does it stay correct after every update?" or "how far apart are x and y?".

`dcalc` (C, `src/dcalc/`) answers each request in a fixed pipeline[^src]:

1. **Parse** (`sexp.c`) and **check names and shapes against the registry** (`registry*.c`, generated from
   `registry/mettadinc_registry.json`). Anything malformed, partial, out of range or undeclared stops here as
   `InvalidInput`, with `file:line:col`.
2. **Admit** (`admit.c`, `model.c`): build the finite model, and refuse profiles or features outside the current release.
   Release 1 answers `Unsupported`; `--beyond-release` enables M4-M7.
3. **Generate obligations** (`obligations.c`) and **solve** them with the per-feature operators (`ops_*.c`): partition
   refinement, exact rational fixpoints (`rat.c`), the ROBDD plus CNF/LRAT path for symbolic carriers (`bdd.c`), exact
   LP (`lp_exact.c`), and so on.
4. **Emit an envelope** (`records.c`): `Status` (Checked / Refuted / Unknown / Unsupported / InvalidInput), the `Claim`,
   a `Binding` to the module digest, a `Value`, `Evidence` (a witness or a certificate), `Assumptions`, and `Assurance`
   (the policy, and whether the evidence was replayed).

The central rule: **Checked or Refuted only with replayable evidence**. A Refuted answer carries a concrete witness, and a
Checked answer carries a certificate (an exact kernel, a prefixpoint, or an LRAT proof replayed by cake_lpr). When the
evidence can't be produced, the answer is Unknown or Unsupported, never a guess.

### 2.1 The milestones, one example each

| M | What it adds (plain terms) | One example (fixture, request, answer) |
|---|---|---|
| M0 | Strict certificate boundaries: every answer is bound to a module digest; malformed or partial input is refused, not repaired | `hypotheses.metta` LiteralCongruence `(InduceExact Blurred)`: Refuted with CongruenceWitness (Pair 0 1), action hop (C03) |
| M1 | Registry, syntax, staging and result plumbing: one registry drives parsing, admission and envelopes | `hypotheses.metta` Staged `(CheckBehavioral Merge01 (Horizon (Steps 2)))`: Refuted, because states 0 and 1 differ on their 3-step report trace |
| M2 | Graded deterministic core on tables: defects, horizons, exact quotients and graded (Lukasiewicz) closure | `graded_closure.metta`: closure raises bracket 34/45 to 41/45, closed A-C entry 4/5 (G01, G03) |
| M3 | Symbolic carriers and incrementality: 40-bit machines via ROBDD plus CNF/LRAT, without enumerating 2^40 states | `forty_bits.metta` `ParityQuotient`: Checked, 8 blocks, observable dimension 3 (F04) |
| M4 | Stochastic dynamics, linear realizations, estimates (beyond release) | `seven_state.metta` `(MeasureBehavioral MergeXY (Discount (Rat 9 10)))`: 81/200 (S04) |
| M5 | Nondeterminism and simulation: outcome sets, fair schedulers, abstraction by simulation | `access_protocol.metta` `Lockout`: Unknown, because the abstract counterexample (1 step) is spurious; the concrete needs 3 (Y04) |
| M6 | Composition kernel, hives, merges, graded kernels, contracts | `parity_triangle.metta` `(Holonomy Triangle (Cycle M1 M2 M3))`: the swap, so `CheckKernelCoherence` is Refuted (T01/T02) |
| M7 | Hyperseed, observer discovery, integration | `neural_audit.metta` `(CheckNow SymbolicNew)`: Refuted with witness ((0 0),(0 1)): first-bit readout cannot answer XOR (N02) |

Release 1 (no flag) supports M0-M3: the MILESTONES plan marks 9 + 36 + 6 claims Supported in R1. M4-M7 claims are answered
only under `--beyond-release`; without the flag they are `Unsupported` (verified: `certificate_limits.metta` gives 8/8
Unsupported in R1; `reads.metta` gives "Profile Dynamics Nondeterministic is outside the first release")[^findings].

## 3. Independent checks

All my checkers are in `docs/review/checks/` (copied from `mdc-review/mycheck/`). They are plain Python with exact
`fractions`; they import no repo code and do not call the repo's replayers (`replay.py`, `verify_mettadinc.py`). Each one
recomputes the answer from the fixture semantics and compares it with dcalc's envelope or with the MILESTONES oracle.
Fresh rerun at 17:04: all 8 checkers exit 0 with 0 mismatches[^counts].

### 3.1 Claims recomputed (at least 2 per milestone)

| M | Checker | Claims recomputed | OK |
|---|---|---|---|
| M0 | check_eight.py, check_m012.py | E05 (UpdateWitness under swap replays), E08, E09; H12 (homomorphism, not surjective); C01-C03 (CongruenceWitness (0,1) under hop) | all |
| M1 | check_eight.py, check_m012.py | EightState defects Current 0 / Update 1 / Behavioral 1, the 24-entry kernel and both witnesses; Staged at horizons 0/1/2 (exact kernel match), H08-H10 | all |
| M2 | check_m2.py | G01 brackets 34/45 -> 41/45, G02 threshold not transitive, G03 closed A-C = 4/5, G04 Alpha not transitive; H05-H08 | 7/7 |
| M3 | check_m3.py, lrat.py | F03/F04 8 blocks (brute force for n = 4..14, Reach(0) exact at n = 40); **26/26 LRAT proofs** replayed by my own RUP checker, each CNF hash checked against its proof-store name | 14/14, 26/26 |
| M4 | check_m4.py | S01 7 bisimulation classes, S02 6 trace classes, S03 1/2, S04 81/200, S05, S06 rank 5; L01-L03 (3, 3/5); O01 1/2, O03/O04 (all 2187 policy trees: 1); U01-U04 (1-2^-20, 7/8, depth 7 at 127/128, 1/3) | 16/16 |
| M5 | check_m5.py (own s-expr reader) | Reads D01-D04 ({Agree}, {Agree,Differ}, 1, 1/2); AccessProtocol Y01 Refuted (witness fail S0 vs S2), Y02 Checked, Y03 Checked, Y04 Unknown (abstract 1 step, concrete 3) | 8/8 |
| M6 | check_m6.py | T01/T02 holonomy = swap, so incoherent; A01 (6, 1/2), A02 Checked, A03 Refuted at input 0 (gap 1/2) | 9/9 |
| M7 | check_m7.py | W01/W02 merged pairs; N01-N06 (witness ((0 0),(0 1)), masses 1/2/1/2, turnover 1/2, accuracy 1/2 vs 1, 4 and 2 classes) | 9/9 |

Caveats, stated honestly: in S03/S04 my coupling search covers only the two extremal couplings (enough for this 2x2
support, not a general LP). S06 uses a Hankel-rank argument, and S07 is not checked. The M3 count at n = 40 is extrapolated
from small n; the symbolic answer itself is backed by the 26 LRAT proofs. N04's "new" accuracy follows trivially from the
readout semantics. In check_m5/m6/m7 the expected values are hard-coded from the oracle, not parsed from it.

### 3.2 Negative gates on my own inputs (at least 1 per milestone)

Every input below is my own mutant or variant, kept in `docs/review/inputs/`. Each was run through `build/dcalc/dcalc`,
with `--beyond-release` for M4-M7. "Expected" is what my own computation, or the spec rule, says should happen.

| M | My input | Change | dcalc answer | As expected? |
|---|---|---|---|---|
| M0 | mut_m0_partial | `split` no longer total (row 2 removed) | InvalidInput "Map split: not total; no value for 2" | yes |
| M0 | mut_m0_undef | Encode names an undeclared map | InvalidInput "undeclared name nosuchmap", file:line:col | yes |
| M0 | mut_m0_ghostrepr | request names an unknown representation | InvalidInput for that request only; the others stay Checked | yes |
| M0 | m0_bad_codeswap | code-swap set to the identity (no longer a homomorphism) | SecondChecked Refuted; Composed InvalidInput (it depends on a non-Checked part) | yes |
| M1 | mut_m1_badhead | request head `InduceExactly` | InvalidInput "unregistered request" for that request only | yes |
| M1 | mut_m1_badprofile | `(Profile Quantum)` | InvalidInput "unknown profile shorthand" | yes |
| M2 | m2_out_of_range | graded entry 11/10 | InvalidInput "malformed SymmetricTable entry" (not clipped) | yes |
| M2 | m2_alpha_closed | A-C set to 4/5 (already closed) | CheckTransitive flips to Checked | yes |
| M2 | mut_m2_leave | update goes outside its carrier | InvalidInput "value outside carrier Three" (plan neg #7) | yes |
| M2 | mut_m2_overlap_eq/_ne | repeated Table key | InvalidInput "Table key at row 1 repeated" (even when the outputs agree) | yes |
| M3 | m3_bad_successor | wrong claimed successor in ZeroTailReach | OnReach Checked -> Refuted, Stability witness word 0 | yes |
| M3 | fake checkers (exit 1 / silent / wrong sha256) | proof checker replaced | 4 symbolic claims demoted to Conditional; no false Checked | yes (but see D2) |
| M4 | m4_mass_not_one | row masses 1/2 + 1/3 | InvalidInput "row mass is not exactly 1" (not renormalised) | yes |
| M4 | m4_negative_mass | masses 3/2 and -1/2 (sum 1) | InvalidInput "bad Mass (nonnegative rational)" | yes |
| M4 | mut_m4_leak14 | leak 1/4 instead of 1/2 | 37/64; Refuted at depth 17; 1/5 discounted, as my closed forms predict | yes |
| M5 | m5_missing_move | abstract loses Start->Locked | CheckSimulation Refuted (UnmatchedMove S2/Start, fail); Safe Unknown, nothing transferred | yes |
| M5 | mut_m5_wrongtarget | Safe aimed at Protocol | InvalidInput "targets Abstract, not Protocol" | yes |
| M6 | m6_triangle_unmeasured | one correspondence Unmeasured | Coherence Unknown (no zero-fill); Holonomy etc. Unsupported | yes |
| M6 | m6_triangle_coherent | M3->M1 set to Equal | holonomy = identity; Coherence Checked, cost 0 | yes |
| M6 | m6_affine_tight | Direct grade (6, 49/100) | Refuted at input 0, gap 1/2 (the bound is tight) | yes |
| M7 | m7_unbound_op | readout calls unbound `xorq` | InvalidInput "unknown head xorq" at 11:71 | yes |
| M7 | mut_avail_injective | bias map made injective | Bias Checked, DefaultZero stays Refuted | yes |
| M7 | **mut_m7_caseoverlap_ne/_eq** | Cases with two rows for `Absent` | **accepted; the first row wins** (Refuted instead of InvalidInput) | **no: defect D1** |

### 3.3 How my own checkers were sanity-gated

The LRAT canary needed four versions. In v1, two mutations (negating a literal in a clause the proof never uses, and
swapping two unit hints) still left a valid proof, so they were not real negatives. v2/v3 compared against cake_lpr and
agreed 32/32, but swap and rotate mutants are also accepted by cake_lpr, so they don't count as negatives either. In v4,
4 known-answer cases match the expected answer and cake_lpr, and drop_hint, replace_hint, flip_used_cnf_lit and
drop_used_cnf_clause are each refused 8/8, with 0 disagreements. Only the mutations were changed; the checker never was[^findings].

## 4. Assessment

### 4.1 Defects and trust-boundary findings

**D1, a defect (M7, `--beyond-release` only).** `m7_case()` in `src/dcalc/ops_m7.c` (l.28-35) returns the **first**
`Cases` row matching the element and never looks for a second one; `m7_codomain_bad()` (l.59-64) only checks the codomain.
So a Map with `(Absent 0) (Absent 5)` is accepted and source order decides the value. This breaks spec §5.4 as the other
loaders enforce it: `model.c:323-330` ("overlapping cases are rejected even when they agree"), `ops_nondet.c:75` and
`stoch.c:76/89` all reject duplicates. Repro: `docs/review/inputs/mut_m7_caseoverlap_ne.metta` and `_eq.metta` give
Refuted where InvalidInput is expected. It is unreachable in release 1 (the profile answers Unsupported). Fix: reject
duplicate case keys in M7 map admission, or reuse the model.c loader, and add both mutants under `tests/dcalc/mutations/m7/`.

**D2, a trust-boundary risk (M3; medium).** The proof-backend binaries are only identity-checked when
`DCALC_CADICAL_SHA256` / `DCALC_CAKE_LPR_SHA256` are set (`ops_sym.c:564-566`; documented as "optional" in
`docs/PROOF-BACKEND.md:17,23`). With the pins unset, my fake checker `fake_cake_lie.sh`, which prints `s VERIFIED UNSAT`
and exits 0, turns the 4 forty_bits symbolic claims into **Checked**. Fake checkers that exit 1 or print nothing are still
refused (Conditional), and **with the pins set every fake is refused**. The hash goes into each Proof form, so an audit
after the fact can catch it, but nothing refuses it at run time. Fix: compile the pinned hashes in as defaults, or answer
Conditional instead of Checked whenever no pin is set.

### 4.2 Deviations and "ours" shapes

- **ROBDD instead of CUDD 3.0.0 (M3)**: a deliberate deviation from README "Ben's decisions" #3, approved by andy on 2026-11-11.
  This is safe because every Checked answer still needs an LRAT proof replayed by cake_lpr (subject to D2)[^dec].
- **Table keys**: dcalc rejects *any* repeated Table key, even when the outputs agree. The plan's M2 negative #8 only asks
  this for overlapping cases with equal outputs; dcalc is stricter, which is safe.
- **Clock-rate screen (OQ 2)**: internal, uncertified tooling that is never Checked, as decided[^dec].
- **Access-policy mutation gate (M3 gate 5)**: moved to the milestone that admits Families, as decided[^dec].
- **M4-M7 sit behind `--beyond-release`**. Release 1 is M0-M3 (51 claims); M4-M7 claims are 0 of them Supported in R1 by plan.

### 4.3 Blocked (outside components that do not exist yet)[^blocked]

The finite OmegaPLN differential oracle (spec 14.1), the MeTTaProN kernel import (14.2; it answers Unsupported, with a fixture),
the omegaPLN evidence adapter (14.3) and the Hyperseed proof-plan registry (14.5). Ben confirmed on 2026-11-10 that none of
these exist yet (OQ 6). dcalc answers Unsupported for them and never gives a false Checked.

### 4.4 Not done (in scope, not built)[^blocked]

ClockRates (F07) beyond a `(Uniform)` law and `(Kind Mean)`; ConeOfInfluence (the third F07 request) is Unsupported, and its
reason text still says "symbolic engine not built yet (M3 in progress)", which is stale (`ops_sym.c` l.1402).

### 4.5 Risks

1. **Fixture-sized coverage (highest).** Every claim I checked is on a small hand-built fixture. The stochastic, LP and
   graded paths (M4/M6) have no randomised differential test against an independent oracle.
2. D2 (unpinned checker identity).
3. D1-type gaps: admission checks are duplicated per profile loader (model.c, ops_nondet.c, stoch.c, ops_m7.c), so one
   loader can miss a rule. D1 is an example.
4. **Stale `cetta/` worktree**: the superproject pins 4c285a97 but 12da03b is checked out (`git status` shows ` M cetta`).
   The suite is unaffected because `cetta_smoke` clones the pin into `build/cetta-dcalc` (HEAD~13 = 4c285a97, plus 13
   patches)[^pin], but `tools/cetta-baseline.sh` would build the wrong commit. Fix: `git submodule update`.
5. Cost: `cetta_smoke` takes 635 s of the 864 s suite, which makes the full gate slow to iterate on.

## 5. Next steps, ranked

1. **Fix D1** (small, removes a real spec violation): reject duplicate `Cases` keys in `ops_m7.c` map admission (or route
   M7 maps through the `model.c` loader); add `mut_m7_caseoverlap_ne/_eq` to `tests/dcalc/mutations/m7/` as InvalidInput gates.
2. **Close D2**: compile the pinned cadical / cake_lpr sha256 values in as defaults, or demote to Conditional whenever no
   pin is set; add a gate that runs `fake_cake_lie.sh` with the pins unset and requires no Checked.
3. **Factor admission rules into one shared loader** (Table/Cases totality, duplicates, codomain, mass checks) used by
   model.c, ops_nondet.c, stoch.c and ops_m7.c, so a D1-type gap can't recur per profile.
4. **Randomised differential testing for M4/M6** against an independent oracle (small random kernels, exact rationals),
   starting with Kantorovich distances, trace classes, linear dimension (incl. S07 positive), graded composition.
5. **Run `git submodule update`** so `cetta/` matches its 4c285a97 pin, and note the pin in README.
6. **Refresh the stale ConeOfInfluence reason text** (`ops_sym.c` l.1402) and decide whether ClockRates beyond
   Uniform/Mean is in scope for a later milestone.
7. **Speed up the gate**: cache the patched CeTTa build in `cetta_smoke` (635 s of 864 s) keyed on pin + patch hashes.
8. **When a blocked dependency gets pinned**, follow `docs/M7-BLOCKED.md` "Re-check": pin, canary, then allow Checked.

## Sources

[^runall]: `mdc-review/runall.log` (resources table l.366-401, `RUNALL_EXIT=0` l.402); command in §1.
[^blocked]: `docs/M7-BLOCKED.md` (blocked integrations, "Not done" table, resolved review-1 finding 6).
[^dec]: `DECISIONS.md` in the task attachments (`.runtime/hive/attachments/t-2026-11-14-mettadinc-system-review/`): OQ 2, OQ 3/12, OQ 6, M3 ROBDD decision, M3 review-3 gate-5 note.
[^pdf]: `command -v md2pdf pandoc` and a filesystem search found neither; `python3 -c "import markdown, weasyprint"` fails (`mdc-review/pdf_find.txt`).
[^pin]: `git ls-tree HEAD cetta` -> 4c285a97; `git -C build/cetta-dcalc rev-parse HEAD~13` -> 4c285a97, `rev-list --count HEAD~13..HEAD` = 13; `tools/dcalc-cetta-smoke.sh` l.2-6.
[^findings]: `mdc-review/FINDINGS.md` (timestamped running notes for every check, mutant and finding in this review).
[^src]: `src/dcalc/` (sexp.c, registry*.c, admit.c, model.c, obligations.c, ops_*.c, rat.c, bdd.c, lp_exact.c, records.c); `README.md`; `docs/e0/MILESTONES.md` (M0 l.161, M6 l.716, M7 l.805).
[^counts]: `docs/review/counts.txt` and `mycheck/counts_*.log` (17:04 rerun: per-checker exit 0, 0 mismatches). The 82 checked values = check_eight 9 (status, the 3 defects, the 24-entry kernel as one value, 2 witness replays, 4 request verdicts; it prints these lines rather than OK lines, so counts.txt shows ok=0, and it ends `FAILS 0`) + check_m012 10 + check_m2 7 + check_m3 14 + check_m4 16 + check_m5 8 + check_m6 9 + check_m7 9. The 30 own inputs = the 31 files in `docs/review/inputs/` minus `m4_us_base.metta`, which is a base fixture, not a mutant.
