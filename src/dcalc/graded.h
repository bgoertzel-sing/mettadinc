/* M2 graded deterministic engine on tables (spec Def 4.1, Thm 4.2(5), Def 4.4).
 * Distances d = 1 - alpha as exact rationals over n*n state pairs (row-major).
 * Two engines compute the behavioral distance: the reference engine iterates
 * d_{k+1} = max(d0, g * max_a d_k(Ta x, Ta x')) from d_0 = d0 (Phi^{h+1}(1));
 * the specialized engine takes shortest paths in the synchronous pair graph.
 * Every function returns 0, or -1 when a rational overflowed (*ovf set). */
#ifndef DCALC_GRADED_H
#define DCALC_GRADED_H
#include "ops_internal.h"
#include "rat.h"
/* d0(x,x') = max_j d_j(o_j x, o_j x'); a literal port contributes 0 or 1. */
int dc_g_seed(const DcModule *m, const DcView *v, DcRat *d0);
/* dq(x,x') = code distance of q x, q x' under the representation's code tolerance. */
int dc_g_codes(const DcModule *m, int ri, DcRat *dq);
/* horizon < 0: unbounded.  g in (0,1]. */
int dc_g_beh_ref(const DcView *v, const DcRat *d0, DcRat g, int horizon, DcRat *out);
int dc_g_beh_bfs(const DcView *v, const DcRat *d0, DcRat g, int horizon, DcRat *out);
/* max over pairs of (a - b)+, and the argmax pair (-1,-1 when the max is 0). */
DcRat dc_g_excess(size_t n, const DcRat *a, const DcRat *b, int *px, int *py);
/* delta_upd = max_a max_{x,x'} (dq(Ta x,Ta x') - dq(x,x'))+ with the argmax pair and action. */
DcRat dc_g_update_defect(const DcView *v, const DcRat *dq, int *px, int *py, int *pa);
/* Clock-rate screen (Prop 4.8): returns max_a sup_x dq(x,T_a x); sup/mean per action. */
DcRat dc_g_clock_rates(const DcView *v, const DcRat *dq, DcRat *sup, DcRat *mean, int *ovf);
#endif
