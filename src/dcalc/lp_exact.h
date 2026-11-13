/* M6-rest: exact rational linear programming for the Hives library (LeastCoherentRefinement, general case).
 * maximize c.x subject to A x <= b, x >= 0, with every b_i >= 0 (the origin is feasible, so no phase 1).
 * Dense tableau simplex with Bland's rule (cannot cycle); every entry is a DcRat.  Rational overflow sets
 * *ovf and the caller answers Unsupported naming the limit, never a wrong value.  On success x[0..nv) is an
 * optimal vertex and y[0..nr) an optimal dual (y >= 0, A^T y >= c, b.y = c.x) read from the slack reduced
 * costs; the caller re-checks both independently before it reports them.
 * Returns 0 optimal, 1 unbounded, 2 iteration cap, 3 bad input (b < 0), -1 out of memory. */
#ifndef DCALC_LP_EXACT_H
#define DCALC_LP_EXACT_H
#include "rat.h"
int dc_lp_max(int nr, int nv, const DcRat *A, const DcRat *b, const DcRat *c, DcRat *x, DcRat *y, DcRat *val, int *ovf);
#endif
