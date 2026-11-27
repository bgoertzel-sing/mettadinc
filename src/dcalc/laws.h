/* Library Laws (t-2026-11-27-mettadinc-laws): finite laws with exact rational masses.
 * Spec (docs/e0 .../03_four_worked_examples/mettadinc_worked_examples.tex l.2172-2175):
 *   "(Indep L1 L2) is the product law, (Image $v e L) is the law of the expression e when $v is drawn
 *    from L, (Expect L) is a mean, and (LawOf m) is the law of a declared measure; Coin and Point
 *    remain the elementary laws."
 * Release placement (same file l.2180): "(Use Decisions Laws Families NatArith) ; Laws, DecisionProcess:
 *   PROPOSED" -> Laws is admitted beyond the first release only (registry opt-in, admit.c).
 * Implemented meaning (agrees with the reference evaluator metta_eval.py l.150-152, 223-258):
 *   (Point v)            -> {v:1}
 *   (Coin p)             -> {1:p, 0:1-p}, zero masses dropped; p a closed rational in [0,1]
 *   (Indep L1 .. Ln)     -> product law, values (Tuple v1 .. vn), masses multiplied
 *   (Image $x body L)    -> pushforward of L through body, equal values merged
 *   (Expect L)           -> sum of v*m over the support (values must be rationals)
 *   (LawOf m)            -> the Masses of the declared (Measure m (On C) (Masses ..)); the caller's leaf
 *                           expands a measure name to the internal form (%Masses (v q) ..), checked here
 *                           (masses non-negative, summing to 1)
 * Outside the fragment: a map call inside a law term (stoch.c answers Unsupported, not InvalidInput).
 * A DcLaw holds its support in insertion order; equal values (sx_equal) are merged. */
#ifndef DCALC_LAWS_H
#define DCALC_LAWS_H
#include <stddef.h>
#include "sexp.h"
#include "qrat.h"
typedef struct { size_t n, cap; Sx **val; DcQ *m; } DcLaw;
void dc_law_init(DcLaw *L);
void dc_law_free(DcLaw *L);
/* add mass m at value v (copied); merges with an equal value; m == 0 is dropped. -1 on OOM. */
int dc_law_add(DcLaw *L, const Sx *v, DcQ m, int *ovf);
/* Leaf evaluator for non-law subterms (Coin probability, Point value, Image body).
 * Returns a fresh Sx; sets *ok != 1 on failure. */
typedef Sx *(*DcLawLeaf)(const Sx *e, void *ctx, int *ok);
/* 1 if e is headed by a Laws primitive or Point/Coin */
int dc_law_head(const Sx *e);
/* Evaluate law expression e into out (initialised by the caller). 0 ok, -1 failure (why filled). */
int dc_law_eval(const Sx *e, DcLawLeaf leaf, void *ctx, DcLaw *out, int *ovf, char *why, size_t ws);
/* closed exact arithmetic on law values (Image bodies, Coin probabilities, (Expect L)); *ok = 0 when it does not evaluate */
Sx *dc_law_arith(const Sx *e, int *ok, int *ovf);
/* Expect: sum v*m; -1 if a support value is not a rational literal. */
int dc_law_expect(const DcLaw *L, DcQ *out, int *ovf);
#endif
