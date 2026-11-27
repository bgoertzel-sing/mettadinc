/* Library Laws (t-2026-11-27-mettadinc-laws): finite laws with exact rational masses.
 * Reference semantics: docs/e0 metta_eval.py l.223-248.
 *   (Point v)            -> {v:1}
 *   (Coin p)             -> {1:p, 0:1-p}, zero masses dropped
 *   (Indep L1 .. Ln)     -> product law, values (Tuple v1 .. vn), masses multiplied
 *   (Image $x body L)    -> pushforward of L through body, equal values merged
 *   (Expect L)           -> sum of v*m over the support (values must be rationals)
 *   (LawOf e)            -> the law denoted by e
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
