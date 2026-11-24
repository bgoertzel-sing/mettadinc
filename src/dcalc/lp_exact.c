#include "lp_exact.h"
#include "qrat.h"   /* D1: tableau in arbitrary-precision DcQ */
#include <stdlib.h>

#define LP_MAXIT 20000
int dc_lp_max(int nr, int nv, const DcRat *A, const DcRat *b, const DcRat *c, DcRat *x, DcRat *y, DcRat *val, int *ovf) {
    size_t qmark = dc_q_arena_mark();   /* D1: big intermediates are freed on return */
    int nc = nv + nr + 1, rc = 0;   /* columns: x | slacks | rhs */
    DcQ zero = dc_q(0, 1, ovf), one = dc_q(1, 1, ovf);
    if (nr < 0 || nv < 0 || nr > 100000 || nv > 100000) return 3;
    for (int i = 0; i < nr; i++) if (b[i].n < 0) return 3;
    DcQ *T = malloc(sizeof(DcQ) * ((size_t)(unsigned)nr + 1u) * (size_t)(unsigned)nc);
    int *bas = malloc(sizeof(int) * (size_t)(unsigned)(nr ? nr : 1));
    if (!T || !bas) { free(T); free(bas); return -1; }
#define E(i, j) T[(size_t)(i) * (size_t)nc + (size_t)(j)]
    for (int i = 0; i <= nr; i++) for (int j = 0; j < nc; j++) E(i, j) = zero;
    for (int i = 0; i < nr; i++) {
        for (int j = 0; j < nv; j++) E(i, j) = dc_q_from_rat(A[(size_t)i * (size_t)nv + (size_t)j]);
        E(i, nv + i) = one; E(i, nc - 1) = dc_q_from_rat(b[i]); bas[i] = nv + i;
    }
    for (int j = 0; j < nv; j++) E(nr, j) = dc_q_sub(zero, dc_q_from_rat(c[j]), ovf);
    for (int it = 0;; it++) {
        if (*ovf) { rc = 4; break; }
        if (it >= LP_MAXIT) { rc = 2; break; }
        int pc = -1;   /* Bland: lowest-index column with negative reduced cost */
        for (int j = 0; j < nc - 1 && pc < 0; j++) if (E(nr, j).n < 0) pc = j;
        if (pc < 0) break;
        int pr = -1; DcQ best = zero;
        for (int i = 0; i < nr; i++) if (E(i, pc).n > 0) {
            DcQ t = dc_q_div(E(i, nc - 1), E(i, pc), ovf);
            int k = pr < 0 ? -1 : dc_q_cmp(t, best);
            if (pr < 0 || k < 0 || (k == 0 && bas[i] < bas[pr])) { pr = i; best = t; }
        }
        if (pr < 0) { rc = 1; break; }
        DcQ pv = E(pr, pc);
        for (int j = 0; j < nc; j++) if (E(pr, j).n) E(pr, j) = dc_q_div(E(pr, j), pv, ovf);
        for (int i = 0; i <= nr; i++) if (i != pr && E(i, pc).n) {
            DcQ f = E(i, pc);
            for (int j = 0; j < nc; j++) if (E(pr, j).n) E(i, j) = dc_q_sub(E(i, j), dc_q_mul(f, E(pr, j), ovf), ovf);
        }
        bas[pr] = pc;
    }
    if (rc == 0) {
        for (int j = 0; j < nv; j++) x[j] = dc_q_to_rat(zero, ovf);
        for (int i = 0; i < nr; i++) if (bas[i] < nv) x[bas[i]] = dc_q_to_rat(E(i, nc - 1), ovf);
        for (int i = 0; i < nr; i++) y[i] = dc_q_to_rat(E(nr, nv + i), ovf);
        *val = dc_q_to_rat(E(nr, nc - 1), ovf);
    }
#undef E
    free(T); free(bas); dc_q_arena_release(qmark);
    return rc == 4 ? 0 : rc;   /* overflow: *ovf is set and the caller refuses */
}
