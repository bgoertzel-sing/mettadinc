# Listed disagreements (CLI --beyond-release vs independent oracle)

Each entry: minimal input file, both answers, which side the spec supports and why.
No C fixes in this task (order stop-line).

## D1 kant_disc: MeasureBehavioral with a discount answers Unsupported ("rational overflow (int64)")

- File: `D1_kant_disc_int64_overflow.metta` (4 states, 2 actions, discount 9/10), shrunk from
  seed 2, case 169 of the 200-case run (5 of the 6 hits had discount 9/10, 1 had 1/2).
- CLI: `(Status Unsupported)`, `(Reason "MeasureBehavioral: rational overflow (int64)")`.
- Oracle (oracle_stoch.exact_distance; strategy iteration, then an exact check that the result
  is a fixed point of Phi_g, which is unique for g < 1 by Thm 4.2(2)): `Checked`, defect 9/10.
- Hand check: merge sends s1 to s0. From s0 action a goes to s3 (report 1); from s1 it goes to
  s1 (report 0). So d(s0,s1) >= g * d0(s3,s1) = 9/10, and every distance is at most
  g * 1 when the reports agree, so d(s0,s1) = 9/10 exactly.
- Spec side: the oracle, with one caveat. Table 2 (Section 2.2, l.440) defines Unsupported as
  "the request, profile or argument combination is outside the capability manifest". The CLI
  answers this same request and argument combination Checked on other inputs, so this status is
  not about capability. Where the spec covers unresolved claims, it gives Unknown, not
  Unsupported: l.512-517 (no certificate reaches the value -> "Unknown with the certified
  interval", Section 4.4) and l.578-582 (a budget ends -> "Unknown with a record of the work
  completed"). The exact value 9/10 has a simple certificate (see the hand check). The spec has
  no text on internal arithmetic overflow ("overflow" does not appear), so the strongest claim is:
  the expected answer is Checked 9/10; failing that, Unknown with an interval; Unsupported matches
  no rule. (l.2425 allows Unsupported for policy-class trace requests on stochastic machines,
  but that is a different request.)

## D3 CheckLinearArrow: a Signed arrow is accepted without the normalization L eta' = eta

- File: `D3_signed_arrow_normalization.metta` (3-state machine, a renamed copy as target).
  Arrow `E` is the exact permutation matrix; arrow `L` is 2 x that matrix (every row sums to 2).
- CLI: both `(Status Checked)`, `(Valid True)`; L gets grade (Lambda 2) (Rho 0).
- Oracle: E Checked, grade (1, 0). L is not a linear arrow, because the target is a stochastic
  machine (eta' = 1) and L 1 = 2 != 1 = eta, so the answer is Refuted (Valid False).
- Spec side: the oracle. Def 3.8 says a linear arrow "is a matrix L with L eta' = eta", and
  l.2465 says "CheckLinearArrow L replays the intertwining residuals, the normalization
  L eta' = eta and ...". Code (read only): st_check_lin in src/dcalc/stoch.c tests the row sum
  only when Kind is Positive, so a Signed row with any sum passes.

## D2 CheckLinearArrow: a nonzero entry between states with different reports is Refuted instead of graded

- File: `D2_obs_residual_refuted.metta`. Source and target are 2-state absorbing machines
  (s0/t0 report 0, s1/t1 report 1). Positive arrow L: s0 -> (t0 1/2, t1 1/2), s1 -> t1.
- CLI: `(Status Refuted)`, `(Valid False)`, `(Grade (Lambda 1) (Rho 0))`,
  `(Failure observation report differs at (s0 t1))`.
- Oracle (oracle.linear_arrow): L >= 0, L 1 = 1 = eta, R_a = M_a L - L M'_a = 0,
  S_0 = E_0 L - L E'_0 = [[0, 1/2], [0, 0]], so ||S_y|| = 1/2. Answer: Checked, grade (1, 1/2),
  a positive arrow that is not exact.
- Spec side: the oracle. Def 3.8 asks only for L eta' = eta (plus L >= 0 when positive), and puts
  the observation residual S_y = Pi_y L - L Pi'_y into rho ("rho >= max(max_a ||R_a||, max_y ||S_y||)").
  An arrow whose S_y is nonzero is therefore a valid arrow with rho > 0, not an invalid one.
  Code (read only): st_check_lin in src/dcalc/stoch.c rejects any nonzero entry across differing
  observations. Note also that the reported Rho 0 is below the Def 3.8 lower bound 1/2, so even the
  printed grade is not a valid grade for L.

## D2 arrow: CheckLinearArrow refutes an arrow whose source and target reports differ

- File: `D2_linear_arrow_obs_refuted.metta`. Two one-state machines: A0 reports 0, B0 reports 1,
  and L = [[1]], declared Positive. Built by hand as the smallest case of the pattern; all 65
  arrow disagreements in the pilots (seed 4, 30 random and 30 exact cases) follow it.
- CLI: `(Status Refuted)`, `(Value (LinearArrow Positive (Valid False) (Grade (Lambda 1) (Rho 0))))`,
  with `(Failure observation report differs at (A0 B0))`.
- Oracle (oracle_linear.arrow_grade): `Checked`, grade (lambda 1, rho 1). L eta' = eta holds
  (the row sums to 1). R_a = 0. S_0 = Pi_0 L - L Pi'_0 = 1 - 0 = 1, so rho = 1.
- Spec side: the oracle. Definition 3.8 (l.817-835) requires only L eta' = eta for a linear
  arrow. The projector residual S_y is part of the grade: rho >= max(max_a ||R_a||, max_y ||S_y||).
  Section 7.3 bullet 2 (l.2465) says CheckLinearArrow "replays the intertwining residuals, the
  normalization L eta' = eta and, when declared, positivity, and returns the grade (lambda, rho)".
  It has no rule that refutes an arrow because observations differ. The CLI has two separate
  problems: (a) it sets Valid False and Refuted on a valid arrow; (b) the Rho it reports leaves
  out S_y (Rho 0 here, where the spec gives 1), and its certificate text names only the K_a
  residual. As a consequence, Then on such arrows answers InvalidInput where Proposition 3.9
  gives a composed grade.

## D2 side settled (21:52): spec Def 3.8, read in full

Def 3.8 defines a linear arrow as any L with L eta' = eta. S_y = Pi_y L - L Pi'_y is part of the
grade (rho >= max_y ||S_y||). "Positive" means L >= 0 and a stochastic target, with no condition on
observations. Line 2434 ("satisfies M L = L M-bar and preserves observations") describes the exact
example in 7.3, where rho = 0 and therefore S_y = 0. It is not a validity rule. The comment above
st_check_lin in stoch.c ("observation preservation") states an implementation choice that the spec
does not contain. Verdict: spec side is the oracle (Checked, rho includes S_y). Whether the spec or
the code should change is for the report reader to decide. Files D2_obs_residual_refuted.metta and
D2_linear_arrow_obs_refuted.metta both show D2 (a third copy, d_lin_obs.metta, was removed as a duplicate).
- Scale (seed 6, 200 cases per family): random family arrow_L 148 / arrow_K 144 / Then 156
  disagreements; exact family arrow_K 149 / Then 149 (arrow_L there is a permutation that keeps
  observations, 0 disagreements). Every arrow disagreement is CLI Refuted vs oracle Checked
  with S_y != 0; every Then disagreement is CLI InvalidInput vs oracle Checked, and in each one
  an input arrow is a D2 arrow. The obs family (arrows with L(x,z) != 0 only when the reports
  agree, so S_y = 0): 200 cases, 0 disagreements on arrows and on Then, rho > 0 in all of them.
- Note for the reviewer: the CLI's rule is deliberate (stoch.c comment near l.470 lists
  "observation preservation" as a condition), and spec l.2434 says the 7.3 example realization
  "preserves observations". That sentence describes one example, though, not the definition.
  Whether a projector residual should make the arrow invalid or only add to rho is Ben's call.
  By Def 3.8 as written, it only adds to rho.

## N1 (spec gap, not counted as a disagreement): PositiveRealization with a rejected candidate

- The CLI answers `Checked` with `(Interval l u)` where u = min(candidate size if replayed,
  LumpedQuotient size); a rejected candidate is listed as `(Candidate L Rejected ...)` but the
  result stays Checked, bounded by the lumped (bisimulation) quotient.
- This is sound: the lumped quotient is an exact positive realization, so it bounds the positive
  dimension. Spec l.2469-2476 only describes the supplied-candidate path ("without one the request
  returns Unknown after its budget") and does not say what a rejected candidate should do or that
  the lumped quotient may be used. The oracle follows the CLI here; the spec should state the rule.

## D4 CheckImplementation: the OneMinusAbsoluteDifference distance is not clipped at 1
- Minimal input: d_con_clip.metta (one audited point, f(0) = 0, f-hat(0) = 2, requested grade (0, 1)).
  D4_contract_distance_unclipped.metta is the same bug with two audited points.
- CLI: Refuted, "an audited pair violates the affine bound". Oracle: Checked, Grade 0 1.
- Spec l.686-694: tolerance beta = max(0, 1 - |p - p'|), so the distance 1 - beta = min(1, |p - p'|) = 1 <= 0*0 + 1.
  ops_contracts.c ct_dist (l.33) uses |p - q| without the clip. The spec supports the oracle.
  Review 1 F5: the shared tolerance distance dc_tol_dist (model.c:562, case DC_TOL_ONE_MINUS_ABS) also
  returns the unclipped |a - b|, so a fix must cover both ct_dist and dc_tol_dist, or the M2 graded path
  stays inconsistent with the registry definition max(0, 1 - |p - p'|).
- Scale: run_con.py seed 1 x30 and seed 100 x200 (C1 104, C2 126, ThenContracts 122 disagreements out of 200).
  Replaying both runs with an unclipped oracle distance leaves 0 mismatches, so this is the only cause.
  Every ThenContracts disagreement is InvalidInput because an input contract was Refuted by D4.

## D5 MeasureBehavioral: the defect only compares each state with its representative
- Status: FIXED (t-2026-11-19-mettadinc-d5-behavioral-classpairs). st_defect (stoch.c) now takes the maximum of d(x, y)
  over every pair x < y with the same code (horizon and unbounded paths). The witness is the first pair in carrier order
  that attains the maximum (here a, c); the Pair, depth-h Test and modal witness use it. Both requests now give
  Checked, BehavioralDefect 1, Pair a c. gate.sh asserts this; mutate_gate.sh mutant d5_rep_only restores the old rule.
- Minimal input: d_kant_classpairs.metta (a -> p, c -> q, b -> 1/2 p + 1/2 q; encoding sends a, b, c to b).
- CLI: Checked, BehavioralDefect 1/2 (horizon 1 and unbounded). Oracle: 1 = d_beh(a, c).
- Spec Def 4.4(3) and l.1080: delta_beh is "the largest behavioral distance between two states with the same
  code", i.e. the maximum over all same-code pairs. The CLI takes the maximum over x of d(x, rep(x)), which
  is smaller when a class has 3 or more states. The spec supports the oracle.
- Found as run_diff.py seed 100 case 177 (horizon 3: CLI 17/192 = d(s0, s1), oracle 5/48 = d(s0, s2)).
  1 in 200 cases, because few random encodings merge 3 or more states at positive distance.

## PositiveRealization (run_pos.py): no disagreements
- seed 1 x30 and seed 100 x200 (exact permutation 48, bisimulation quotient 102, random candidate 50): 0 disagreements.
  Expected interval [signed minimum, min(k, lumped quotient size)] with Replayed, or [signed minimum, lumped] with Rejected (see N1).
