# M7: blocked integrations (Unsupported + listed)

Task t-2026-11-14-mettadinc-m7. These four M7 items depend on outside components that are
not pinned yet. Spec section 16.2 (mettadinc_language_spec.txt l.4194-4200) and
validation_package/DEPENDENCIES.json ("not pinned" entries, l.44-46) list them as
unpinned. dcalc does not pretend to implement them: a request that needs one gets no Checked
or Refuted answer.

| Item | Spec | Blocked on | What dcalc does today |
|---|---|---|---|
| Finite OmegaPLN differential oracle | 14.1 (l.3948-3960) | the finite OmegaPLN reference interpreter (unpinned) | No OmegaPLN request or oracle hook exists. Shared fixtures are checked only against the Python oracle verify_mettadinc.py. |
| MeTTaProN kernel import | 14.2 | the MeTTaProN shared kernel IR (unpinned) | `(TransitionKernel K ... (Import MeTTaProN name))` is rejected at admission as **InvalidInput** "undeclared name MeTTaProN" (admit.c check_expr), **not** Unsupported. See the open item below. |
| omegaPLN evidence adapter | 14.3 (l.3973-3997) | the adapter target (unpinned) | No adapter. Results keep their own envelope (Status, Scope, Assurance). Estimated-to-exact wPLN channel test for gate 7 = can't test yet. |
| Hyperseed proof-plan registry | 14.5 (l.4009-4013) | the registry (unpinned) | Results are not exported as warrants. Envelopes already carry status, claim kind, scope and dependencies, which is what the registry would consume. |

## Open item (needs a decision)
The plan says blocked items should answer **Unsupported**. For a MeTTaProN kernel import,
dcalc currently answers InvalidInput because admission treats the library name as an
undeclared symbol. Making it Unsupported means changing shared admission code
(admit.c/model.c Import handling), so it was not done inside M7 without review.
Probe fixture: work/tmp/m7_blk/kern.metta.

## Re-check when a dependency gets pinned
1. Add the pin to DEPENDENCIES.json (remove it from "not pinned").
2. Add a known-answer canary through the production path (EXPERIMENT_SANITY_GATE).
3. Only then let the request return Checked/Refuted.
