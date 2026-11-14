# M7: blocked integrations (Unsupported + listed)

Task t-2026-11-14-mettadinc-m7. These four M7 items depend on outside components that are
not pinned yet. Spec section 16.2 (mettadinc_language_spec.txt l.4194-4200) and
validation_package/DEPENDENCIES.json ("not pinned" entries, l.44-46) list them as
unpinned. dcalc does not pretend to implement them: a request that needs one gets no Checked
or Refuted answer.

| Item | Spec | Blocked on | What dcalc does today |
|---|---|---|---|
| Finite OmegaPLN differential oracle | 14.1 (l.3948-3960) | the finite OmegaPLN reference interpreter (unpinned) | No OmegaPLN request or oracle hook exists. Shared fixtures are checked only against the Python oracle verify_mettadinc.py. |
| MeTTaProN kernel import | 14.2 | the MeTTaProN shared kernel IR (unpinned) | Under `--beyond-release`, `(TransitionKernel K ... (Import MeTTaProN name))` answers **Unsupported**, citing this blocked dependency (api.c dc_eval_request; fixture tests/dcalc/m7/fixtures/r6_mettapron_import.metta, a run_m7_gates `blocked:` row). The release path is unchanged: it answers InvalidInput "undeclared name MeTTaProN". |
| omegaPLN evidence adapter | 14.3 (l.3973-3997) | the adapter target (unpinned) | No adapter. Results keep their own envelope (Status, Scope, Assurance). Estimated-to-exact wPLN channel test for gate 7 = can't test yet. |
| Hyperseed proof-plan registry | 14.5 (l.4009-4013) | the registry (unpinned) | Results are not exported as warrants. Envelopes already carry status, claim kind, scope and dependencies, which is what the registry would consume. |

## Not done (built in part, honest Unsupported for the rest; review 2, finding 4)
These are not blocked on an outside component; they are simply not implemented in M7. Each
answers **Unsupported** (never a false Checked):

| Item | What M7 does | Not done | Where |
|---|---|---|---|
| ClockRates measure (F07) | Exact mean clock rates under a declared `(Uniform)` law | A law declared as `(Product ...)` with full support, or a full-support non-uniform `(Masses ...)` law, answers Unsupported. A law without full support (e.g. 7 of 8 points, or a zero-mass factor) is InvalidInput. | src/dcalc/ops_sym.c l.1345-1346 |
| ClockRates kind (F07) | `(Kind Mean)` | Any other kind (e.g. `SupNorm`) answers Unsupported. | src/dcalc/ops_sym.c l.1348 |
| ConeOfInfluence (third request of the F07 fixture) | none | Answers Unsupported. Its reason text still says "symbolic engine not built yet (M3 in progress)"; the symbolic cone engine is not part of M7. | src/dcalc/ops_sym.c l.1402 |

## Resolved (review 1, finding 6)
The plan says blocked items should answer **Unsupported**. Under `--beyond-release`, a
TransitionKernel that imports from MeTTaProN now answers Unsupported. The check runs in
api.c dc_eval_request before admission, so the shared admission code (admit.c/model.c) is
unchanged and the release path still answers InvalidInput. Fixture:
tests/dcalc/m7/fixtures/r6_mettapron_import.metta, checked by the run_m7_gates `blocked:` row.

## Re-check when a dependency gets pinned
1. Add the pin to docs/M7-DEPENDENCIES.json (remove it from "not pinned"); docs/e0 stays as delivered.
2. Add a known-answer canary through the production path (EXPERIMENT_SANITY_GATE).
3. Only then let the request return Checked/Refuted.
