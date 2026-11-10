/* M2 graded deterministic engine (see graded.h). */
#include "graded.h"
#include <stdlib.h>
#include <string.h>

static const DcRat ZERO = {0, 1}, ONE = {1, 1};

int dc_g_seed(const DcModule *m, const DcView *v, DcRat *d0) {
    size_t n = v->n; int ovf = 0;
    for (size_t i = 0; i < n * n; i++) d0[i] = ZERO;
    for (size_t k = 0; k < v->nobs; k++)
        for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++) {
            int a = v->obs[k][x], b = v->obs[k][y];
            DcRat d = v->obs_tol[k] >= 0 ? dc_tol_dist(m, v->obs_tol[k], a, b, &ovf) : (a == b ? ZERO : ONE);
            d0[x * n + y] = dc_rat_max(d0[x * n + y], d);
        }
    return ovf ? -1 : 0;
}

int dc_g_codes(const DcModule *m, int ri, DcRat *dq) {
    const DcRepr *r = &m->rep[ri]; const int *enc = m->map[r->encode].table;
    size_t n = m->car[m->mach[r->machine].states].n; int ovf = 0;
    for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++) {
        int a = enc[x], b = enc[y];
        dq[x * n + y] = r->tol >= 0 ? dc_tol_dist(m, r->tol, a, b, &ovf) : (a == b ? ZERO : ONE);
    }
    return ovf ? -1 : 0;
}

int dc_g_beh_ref(const DcView *v, const DcRat *d0, DcRat g, int horizon, DcRat *out) {
    size_t n = v->n, N = n * n; int ovf = 0;
    DcRat *nx = malloc((N ? N : 1) * sizeof *nx); if (!nx) return -1;
    memcpy(out, d0, N * sizeof *out);                       /* Phi(1) = alpha_0 */
    long rounds = horizon >= 0 ? horizon : (long)N + 1;     /* unbounded: exact after N rounds */
    for (long t = 0; t < rounds; t++) {
        int changed = 0;
        for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++) {
            DcRat best = d0[x * n + y];
            for (size_t a = 0; a < v->nact; a++) {
                DcRat s = dc_rat_mul(g, out[(size_t)v->act[a][x] * n + v->act[a][y]], &ovf);
                best = dc_rat_max(best, s);
            }
            if (dc_rat_cmp(best, out[x * n + y])) changed = 1;
            nx[x * n + y] = best;
        }
        memcpy(out, nx, N * sizeof *out);
        if (!changed && horizon < 0) break;
    }
    free(nx); return ovf ? -1 : 0;
}

int dc_g_beh_bfs(const DcView *v, const DcRat *d0, DcRat g, int horizon, DcRat *out) {
    size_t n = v->n, N = n * n; int ovf = 0;
    int *dist = malloc((N ? N : 1) * sizeof *dist), *qu = malloc((N ? N : 1) * sizeof *qu);
    if (!dist || !qu) { free(dist); free(qu); return -1; }
    for (size_t s = 0; s < N; s++) {
        for (size_t i = 0; i < N; i++) dist[i] = -1;
        size_t h = 0, t = 0; dist[s] = 0; qu[t++] = (int)s; DcRat best = ZERO;
        while (h < t) {
            int p = qu[h++]; DcRat gk = ONE;
            for (int k = 0; k < dist[p]; k++) gk = dc_rat_mul(gk, g, &ovf);
            best = dc_rat_max(best, dc_rat_mul(gk, d0[p], &ovf));
            if (horizon >= 0 && dist[p] >= horizon) continue;
            size_t x = (size_t)p / n, y = (size_t)p % n;
            for (size_t a = 0; a < v->nact; a++) {
                size_t q = (size_t)v->act[a][x] * n + v->act[a][y];
                if (dist[q] < 0) { dist[q] = dist[p] + 1; qu[t++] = (int)q; }
            }
        }
        out[s] = best;
    }
    free(dist); free(qu); return ovf ? -1 : 0;
}

DcRat dc_g_excess(size_t n, const DcRat *a, const DcRat *b, int *px, int *py) {
    DcRat best = ZERO; int ovf = 0; *px = *py = -1;
    for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++) {
        DcRat e = dc_rat_sub(a[x * n + y], b[x * n + y], &ovf);
        if (dc_rat_cmp(e, best) > 0) { best = e; *px = (int)x; *py = (int)y; }
    }
    return best;
}

DcRat dc_g_update_defect(const DcView *v, const DcRat *dq, int *px, int *py, int *pa) {
    size_t n = v->n; DcRat best = ZERO; int ovf = 0; *px = *py = *pa = -1;
    for (size_t a = 0; a < v->nact; a++)
        for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++) {
            DcRat e = dc_rat_sub(dq[(size_t)v->act[a][x] * n + v->act[a][y]], dq[x * n + y], &ovf);
            if (dc_rat_cmp(e, best) > 0) { best = e; *px = (int)x; *py = (int)y; *pa = (int)a; }
        }
    return best;
}

/* Clock-rate screen (spec Prop 4.8).  For each action a: the sup rate
 * s_a = max_x dq(x, T_a x) and the uniform mean rate r_a = (1/n) sum_x dq(x, T_a x).
 * When dq is a metric, d(Tx,Ty) <= d(Tx,x) + d(x,y) + d(y,Ty), so the update
 * defect is at most 2 max_a s_a.  Returns max_a s_a; fills sup[a] and mean[a]
 * when non-NULL.  Iterates states exactly as dc_g_update_defect does. */
DcRat dc_g_clock_rates(const DcView *v, const DcRat *dq, DcRat *sup, DcRat *mean, int *ovf) {
    size_t n = v->n; DcRat best = ZERO;
    for (size_t a = 0; a < v->nact; a++) {
        DcRat s = ZERO, sum = ZERO;
        for (size_t x = 0; x < n; x++) {
            DcRat d = dq[x * n + (size_t)v->act[a][x]];
            s = dc_rat_max(s, d); sum = dc_rat_add(sum, d, ovf);
        }
        if (sup) sup[a] = s;
        if (mean) mean[a] = n ? dc_rat_div(sum, dc_rat((int64_t)n, 1, ovf), ovf) : ZERO;
        best = dc_rat_max(best, s);
    }
    return best;
}
