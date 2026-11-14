# State-dependent method pushforwards: what the specification does not give (m6-graded step 3)

Task t-2026-11-13-mettadinc-m6-graded asks for this list instead of an implementation.
Line numbers refer to docs/e0/docs/01_language_specification/mettadinc_language_spec.txt.

## What the specification says
- Def 3.10 (l.884-887) and section 10.2 (l.2775-2780): a transfer is a state pullback
  phi : X_B -> X_A with, *for each b in X_B*, a method pushforward iota_b : Meth_A(phi b) -> Meth_B(b);
  this is a Poly morphism p_B -> p_A of method polynomials p = sum_x y^Meth(x).
- Composition (l.2778-2780): phi_AC = phi_AB o phi_BC, iota_AC,c(a) = iota_BC,c(iota_AB,phi_BC(c)(a)).
- Prop 10.4 (l.2862-2866): transfer-hive coherence is stated only for pushforwards that are
  bijections *that do not depend on the state*.

## What is not in the specification
1. **No syntax for a state-indexed pushforward.** The declaration table (l.4624) and every example
   (l.3559-3565, l.3626, l.3653-3656; validation fixture skill_hive.metta l.19-22, 58, 78-79) give
   (MethodPushforward f) with f one Map Methods_A -> Methods_B. Nothing says how iota_b is written,
   e.g. a Map from (Product States_B Methods_A) or a table per state.
2. **No state-dependent method sets.** (MethodSystem S (States X) (Methods M) ...) (l.4623) has one
   method carrier M for every state, so Meth(x) is constant. The polynomial sum_x y^Meth(x) with
   varying Meth(x), and partial methods (methods unavailable in some states), cannot be declared.
3. **No checking rule for well-typedness of iota_b.** Totality is defined only for a constant
   carrier; nothing says whether iota_b must land in Meth_B(b) or what answer a value outside
   it gets.
4. **No composition rule for the request.** l.2780 gives the mathematics, but ComposeTransfers
   (registry) composes Map pushforwards only. Nothing says how a composite of indexed
   pushforwards is reported (as a table per state or otherwise).
5. **No coherence statement beyond Prop 10.4.** For state-dependent or non-bijective pushforwards the
   derived correspondence of a transfer hive (KernelOf over Edge transfers) is not defined; dcalc
   answers Unsupported naming the Prop 10.4 hypotheses (ops_transfers.c, review-2 F5), and keeps doing so.
6. **No response-law / metric definition with indexed methods.** CheckTransfer's defect
   max_{b,a} d(r_A(phi b, a), r_B(b, iota a)) (section 10.2, response defects l.2785-2788) has a ranges over Meth_A(phi b); with constant
   carriers this is all of M_A. The quantifier range for varying Meth is not stated in the
   request semantics.

## Current dcalc behaviour (unchanged by m6-graded)
MethodPushforward is read as one Map M_A -> M_B, which is state-independent by construction.
Transfer hives refuse non-bijective pushforwards as Unsupported (Prop 10.4 hypotheses only).
No state-dependent form is accepted or invented.

## Decision needed before implementing
A declaration form for iota_b and for varying Meth(x) (items 1-2). Items 3-6 follow from that choice.
