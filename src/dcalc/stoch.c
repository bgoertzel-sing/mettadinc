/* M4 (opt-in, beyond the first release): requests on a Dynamics Stochastic
 * module.  Declarations are read from m->source (model.c skips them when
 * m->stochastic is set).  Exact rationals only (rat.h); any overflow answers
 * Unsupported naming the limit. */
#include "ops_internal.h"
#include "ops_run.h"
#include "model.h"
#include "rat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ST_NM 64
#define ST_MAXE 64
#define ST_MAXD 16
typedef struct { char name[ST_NM]; int n; char el[ST_MAXE][ST_NM]; } StCar;
typedef struct { char name[ST_NM]; int from, to; int tab[ST_MAXE]; } StMap;
typedef struct { char name[ST_NM]; int from, to; DcRat p[ST_MAXE][ST_MAXE]; } StKer;
typedef struct { char name[ST_NM]; int states, nobs, nact; char ol[4][ST_NM]; int om[4]; char al[4][ST_NM]; int ak[4]; } StMach;
typedef struct { char name[ST_NM]; int mach, enc; } StRepr;
typedef struct { char name[ST_NM]; int src, tgt; char kind[ST_NM]; DcRat a[ST_MAXE][ST_MAXE]; } StLin;
typedef struct {
    int ncar, nmap, nker, nmach, nrep, nlin;
    StCar car[ST_MAXD]; StMap map[ST_MAXD]; StKer ker[ST_MAXD]; StMach mach[ST_MAXD]; StRepr rep[ST_MAXD]; StLin lin[ST_MAXD];
} StMod;

static int st_err(char *err, size_t es, const char *what, const char *nm) { snprintf(err, es, "%s %s", what, nm ? nm : ""); return -1; }
static const Sx *st_field(const Sx *d, const char *h) { for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], h)) return d->items[i]; return NULL; }
static const char *st_name(const Sx *f, size_t k) { return f && f->kind == SX_LIST && f->n > k && f->items[k]->kind == SX_SYM ? f->items[k]->text : NULL; }
#define ST_FIND(arr, cnt) for (int i = 0; i < cnt; i++) if (!strcmp(arr[i].name, nm)) return i; return -1;
static int st_car(const StMod *s, const char *nm) { if (!nm) return -1; ST_FIND(s->car, s->ncar) }
static int st_mapi(const StMod *s, const char *nm) { if (!nm) return -1; ST_FIND(s->map, s->nmap) }
static int st_keri(const StMod *s, const char *nm) { if (!nm) return -1; ST_FIND(s->ker, s->nker) }
static int st_machi(const StMod *s, const char *nm) { if (!nm) return -1; ST_FIND(s->mach, s->nmach) }
static int st_repi(const StMod *s, const char *nm) { if (!nm) return -1; ST_FIND(s->rep, s->nrep) }
static int st_lini(const StMod *s, const char *nm) { if (!nm) return -1; ST_FIND(s->lin, s->nlin) }
static int st_el(const StCar *c, const Sx *x) { if (!x || x->kind != SX_SYM) return -1; for (int i = 0; i < c->n; i++) if (!strcmp(c->el[i], x->text)) return i; return -1; }

/* ---- reader: carriers, maps, kernels, machines, representations, linear arrows ---- */
static int st_rat(const Sx *v, DcRat *o) { return dc_sx_rat(v, o); }
static int st_read(const Sx *src, StMod *s, char *err, size_t es) {
    memset(s, 0, sizeof *s);
    for (size_t i = 2; i < src->n; i++) {
        const Sx *d = src->items[i];
        if (d->kind != SX_LIST || d->n < 2 || d->items[0]->kind != SX_SYM) continue;
        const char *h = d->items[0]->text, *nm = st_name(d, 1);
        if (!strcmp(h, "Profile") || !strcmp(h, "Use") || !strcmp(h, "Derive")) continue;
        if (!nm || strlen(nm) >= ST_NM) return st_err(err, es, "declaration without a usable name:", h);
        if (!strcmp(h, "Carrier")) {
            if (s->ncar == ST_MAXD) return st_err(err, es, "too many carriers at", nm);
            const Sx *en = st_field(d, "Enum"); StCar *c = &s->car[s->ncar];
            if (!en) return st_err(err, es, "carrier is not an enumeration:", nm);
            snprintf(c->name, ST_NM, "%s", nm);
            for (size_t k = 1; k < en->n; k++) {
                if (en->items[k]->kind != SX_SYM || strlen(en->items[k]->text) >= ST_NM) return st_err(err, es, "bad element in carrier", nm);
                if (c->n == ST_MAXE) return st_err(err, es, "carrier too large (limit 64):", nm);
                if (st_el(c, en->items[k]) >= 0) return st_err(err, es, "duplicate element in carrier", nm);
                snprintf(c->el[c->n++], ST_NM, "%s", en->items[k]->text);
            }
            s->ncar++;
        } else if (!strcmp(h, "Map")) {
            if (s->nmap == ST_MAXD) return st_err(err, es, "too many maps at", nm);
            StMap *mp = &s->map[s->nmap]; snprintf(mp->name, ST_NM, "%s", nm);
            mp->from = st_car(s, st_name(st_field(d, "From"), 1)); mp->to = st_car(s, st_name(st_field(d, "To"), 1));
            const Sx *cs = st_field(d, "Cases");
            if (mp->from < 0 || mp->to < 0 || !cs) return st_err(err, es, "map needs (From C) (To C) (Cases ...):", nm);
            for (int k = 0; k < ST_MAXE; k++) mp->tab[k] = -1;
            for (size_t k = 1; k < cs->n; k++) {
                const Sx *cc = cs->items[k];
                int a = cc->kind == SX_LIST && cc->n == 2 ? st_el(&s->car[mp->from], cc->items[0]) : -1;
                int b = a >= 0 ? st_el(&s->car[mp->to], cc->items[1]) : -1;
                if (a < 0 || b < 0 || mp->tab[a] >= 0) return st_err(err, es, "bad or duplicate case in map", nm);
                mp->tab[a] = b;
            }
            for (int k = 0; k < s->car[mp->from].n; k++) if (mp->tab[k] < 0) return st_err(err, es, "map is not total:", nm);
            s->nmap++;
        } else if (!strcmp(h, "TransitionKernel")) {
            if (s->nker == ST_MAXD) return st_err(err, es, "too many kernels at", nm);
            StKer *K = &s->ker[s->nker]; snprintf(K->name, ST_NM, "%s", nm);
            K->from = st_car(s, st_name(st_field(d, "From"), 1)); K->to = st_car(s, st_name(st_field(d, "To"), 1));
            if (K->from < 0 || K->to < 0) return st_err(err, es, "kernel needs (From C) (To C):", nm);
            int seen[ST_MAXE] = {0}, ovf = 0;
            for (int a = 0; a < ST_MAXE; a++) for (int b = 0; b < ST_MAXE; b++) K->p[a][b] = dc_rat(0, 1, &ovf);
            for (size_t k = 2; k < d->n; k++) {
                const Sx *rw = d->items[k]; if (!sx_head_is(rw, "Row")) continue;
                int a = rw->n >= 2 ? st_el(&s->car[K->from], rw->items[1]) : -1;
                if (a < 0 || seen[a]) return st_err(err, es, "bad or duplicate Row in kernel", nm);
                seen[a] = 1; DcRat sum = dc_rat(0, 1, &ovf); int got[ST_MAXE] = {0};
                for (size_t j = 2; j < rw->n; j++) {
                    const Sx *ms = rw->items[j]; DcRat w;
                    int b = sx_head_is(ms, "Mass") && ms->n == 3 ? st_el(&s->car[K->to], ms->items[1]) : -1;
                    if (b >= 0 && got[b]) return st_err(err, es, "duplicate outcome key in kernel", nm);
                    if (b >= 0) got[b] = 1;
                    if (b >= 0 && ms->items[2]->kind == SX_SYM && strpbrk(ms->items[2]->text, ".eE")) return st_err(err, es, "float probability (use (Rat p q)) in kernel", nm);
                    if (b < 0 || st_rat(ms->items[2], &w) || w.n < 0) return st_err(err, es, "bad Mass (nonnegative rational) in kernel", nm);
                    K->p[a][b] = dc_rat_add(K->p[a][b], w, &ovf); sum = dc_rat_add(sum, w, &ovf);
                }
                if (ovf) return st_err(err, es, "rational overflow (int64) in kernel", nm);
                if (dc_rat_cmp(sum, dc_rat(1, 1, &ovf))) return st_err(err, es, "row mass is not exactly 1 in kernel", nm);
            }
            for (int a = 0; a < s->car[K->from].n; a++) if (!seen[a]) return st_err(err, es, "kernel has a missing Row:", nm);
            s->nker++;
        } else if (!strcmp(h, "Machine")) {
            if (s->nmach == ST_MAXD) return st_err(err, es, "too many machines at", nm);
            StMach *M = &s->mach[s->nmach]; snprintf(M->name, ST_NM, "%s", nm);
            M->states = st_car(s, st_name(st_field(d, "States"), 1));
            if (M->states < 0) return st_err(err, es, "machine needs (States C):", nm);
            for (size_t k = 2; k < d->n; k++) {
                const Sx *f = d->items[k]; const char *l = st_name(f, 1), *t = st_name(f, 2);
                if (sx_head_is(f, "Observe")) {
                    int mi = st_mapi(s, t);
                    if (!l || mi < 0 || M->nobs == 4 || s->map[mi].from != M->states) return st_err(err, es, "bad Observe in machine", nm);
                    snprintf(M->ol[M->nobs], ST_NM, "%s", l); M->om[M->nobs++] = mi;
                } else if (sx_head_is(f, "Action")) {
                    int ki = st_keri(s, t), mpi = ki < 0 ? st_mapi(s, t) : -1;
                    if (ki < 0 && mpi >= 0 && s->map[mpi].from == M->states && s->map[mpi].to == M->states && s->nker < ST_MAXD) {
                        /* V03: a deterministic Map used as an action is the 0/1 kernel of that map */
                        StKer *K = &s->ker[s->nker]; memset(K, 0, sizeof *K); snprintf(K->name, ST_NM, "%s", t);
                        K->from = K->to = M->states; int ovf0 = 0;
                        for (int x = 0; x < s->car[M->states].n; x++) for (int y = 0; y < s->car[M->states].n; y++)
                            K->p[x][y] = dc_rat(y == s->map[mpi].tab[x] ? 1 : 0, 1, &ovf0);
                        ki = s->nker++;
                    }
                    if (!l || ki < 0 || M->nact == 4 || s->ker[ki].from != M->states || s->ker[ki].to != M->states) return st_err(err, es, "bad Action (kernel on the states) in machine", nm);
                    snprintf(M->al[M->nact], ST_NM, "%s", l); M->ak[M->nact++] = ki;
                }
            }
            s->nmach++;
        } else if (!strcmp(h, "Representation")) {
            if (s->nrep == ST_MAXD) return st_err(err, es, "too many representations at", nm);
            StRepr *P = &s->rep[s->nrep]; snprintf(P->name, ST_NM, "%s", nm);
            P->mach = st_machi(s, st_name(st_field(d, "Of"), 1)); P->enc = st_mapi(s, st_name(st_field(d, "Encode"), 1));
            if (P->mach < 0 || P->enc < 0) return st_err(err, es, "representation needs (Of Machine) (Encode map):", nm);
            if (s->map[P->enc].from != s->mach[P->mach].states)   /* the image may be another carrier (V01: fitness classes) */
                return st_err(err, es, "representation encoding must start at the machine states:", nm);
            s->nrep++;
        }
        else if (!strcmp(h, "LinearArrow")) {
            if (s->nlin == ST_MAXD) return st_err(err, es, "too many linear arrows at", nm);
            StLin *L = &s->lin[s->nlin]; snprintf(L->name, ST_NM, "%s", nm);
            L->src = st_machi(s, st_name(st_field(d, "Source"), 1)); L->tgt = st_machi(s, st_name(st_field(d, "Target"), 1));
            const char *kd = st_name(st_field(d, "Kind"), 1); const Sx *mx = st_field(d, "Matrix");
            const Sx *rows = mx && mx->n == 2 && sx_head_is(mx->items[1], "Rows") ? mx->items[1] : NULL;
            if (L->src < 0 || L->tgt < 0 || !kd || strlen(kd) >= ST_NM || !rows)
                return st_err(err, es, "linear arrow needs (Source M) (Target M) (Kind K) (Matrix (Rows ...)):", nm);
            snprintf(L->kind, ST_NM, "%s", kd);
            const StCar *cs = &s->car[s->mach[L->src].states], *ct = &s->car[s->mach[L->tgt].states];
            int seen[ST_MAXE] = {0}, ovf = 0;
            for (int a = 0; a < ST_MAXE; a++) for (int b = 0; b < ST_MAXE; b++) L->a[a][b] = dc_rat(0, 1, &ovf);
            for (size_t k = 1; k < rows->n; k++) {
                const Sx *rw = rows->items[k];
                int a = rw->kind == SX_LIST && rw->n >= 1 ? st_el(cs, rw->items[0]) : -1;
                if (a < 0 || seen[a]) return st_err(err, es, "bad or duplicate row in linear arrow", nm);
                seen[a] = 1;
                for (size_t j = 1; j < rw->n; j++) {
                    const Sx *e = rw->items[j]; DcRat w;
                    int b = e->kind == SX_LIST && e->n == 2 ? st_el(ct, e->items[0]) : -1;
                    if (b < 0 || st_rat(e->items[1], &w)) return st_err(err, es, "bad matrix entry in linear arrow", nm);
                    L->a[a][b] = dc_rat_add(L->a[a][b], w, &ovf);
                }
            }
            if (ovf) return st_err(err, es, "rational overflow (int64) in linear arrow", nm);
            s->nlin++;
        }
    }
    return 0;
}

/* ---- S01: probabilistic bisimulation = strong lumping refined from the joint observation ---- */
static int st_obsclass(const StMod *s, const StMach *M, int *oc) {
    int n = s->car[M->states].n, k = 0;
    for (int x = 0; x < n; x++) {
        oc[x] = -1;
        for (int y = 0; y < x && oc[x] < 0; y++) {
            int same = 1;
            for (int j = 0; j < M->nobs; j++) if (s->map[M->om[j]].tab[x] != s->map[M->om[j]].tab[y]) same = 0;
            if (same) oc[x] = oc[y];
        }
        if (oc[x] < 0) oc[x] = k++;
    }
    return k;
}
static DcRat st_blockmass(const StKer *K, int n, const int *blk, int x, int b, int *ovf) {
    DcRat m = dc_rat(0, 1, ovf);
    for (int t = 0; t < n; t++) if (blk[t] == b) m = dc_rat_add(m, K->p[x][t], ovf);
    return m;
}
/* Returns the number of blocks; blk[x] is the block of state x; rounds counts refinement rounds. */
static int st_lump(const StMod *s, const StMach *M, int *blk, int *rounds, int *ovf) {
    int n = s->car[M->states].n, nb = st_obsclass(s, M, blk), nb2, b2[ST_MAXE];
    *rounds = 0;
    for (;;) {
        nb2 = 0;
        for (int x = 0; x < n; x++) {
            b2[x] = -1;
            for (int y = 0; y < x && b2[x] < 0; y++) {
                if (blk[y] != blk[x]) continue;
                int same = 1;
                for (int a = 0; a < M->nact && same; a++)
                    for (int b = 0; b < nb && same; b++)
                        if (dc_rat_cmp(st_blockmass(&s->ker[M->ak[a]], n, blk, x, b, ovf),
                                       st_blockmass(&s->ker[M->ak[a]], n, blk, y, b, ovf))) same = 0;
                if (same) b2[x] = b2[y];
            }
            if (b2[x] < 0) b2[x] = nb2++;
        }
        (*rounds)++;
        memcpy(blk, b2, sizeof(int) * (size_t)n);
        if (nb2 == nb) return nb;
        nb = nb2;
    }
}

/* ---- S02/S05/S06: Tzeng-style basis of the test-vector span ----
 * beta(y)(s) = [obs s = y];  beta(y a w)(s) = [obs s = y] * sum_t K_a(s,t) beta(w)(t).
 * Breadth-first closure under v -> D_y K_a v, keeping only vectors independent of
 * the span so far (exact Gaussian elimination).  The span has dimension <= n, so the
 * closure stops after at most n rounds; trace equivalence is equality on every basis
 * vector, and the dimension is the minimal linear (weighted-automaton) dimension. */
typedef struct {
    int n, dim;
    DcRat v[ST_MAXE][ST_MAXE];     /* basis vectors as found (test vectors) */
    DcRat e[ST_MAXE][ST_MAXE];     /* echelon copy */
    int piv[ST_MAXE];
    int len[ST_MAXE];              /* word length (symbols) of each basis vector */
} StSpan;
static int st_span_add(StSpan *B, const DcRat *x, int len, int *ovf) {
    DcRat r[ST_MAXE];
    memcpy(r, x, sizeof(DcRat) * (size_t)B->n);
    for (int i = 0; i < B->dim; i++) {
        int p = B->piv[i];
        if (dc_rat_is_zero(r[p])) continue;
        DcRat f = dc_rat_div(r[p], B->e[i][p], ovf);
        for (int c = 0; c < B->n; c++) r[c] = dc_rat_sub(r[c], dc_rat_mul(f, B->e[i][c], ovf), ovf);
    }
    int p = -1;
    for (int c = 0; c < B->n && p < 0; c++) if (!dc_rat_is_zero(r[c])) p = c;
    if (p < 0 || *ovf) return 0;
    memcpy(B->v[B->dim], x, sizeof(DcRat) * (size_t)B->n);
    memcpy(B->e[B->dim], r, sizeof(DcRat) * (size_t)B->n);
    B->piv[B->dim] = p; B->len[B->dim] = len; B->dim++;
    return 1;
}
static void st_span(const StMod *s, const StMach *M, StSpan *B, int *ovf) {
    int n = s->car[M->states].n, oc[ST_MAXE], no = st_obsclass(s, M, oc);
    memset(B, 0, sizeof *B); B->n = n;
    for (int y = 0; y < no; y++) {
        DcRat x[ST_MAXE];
        for (int t = 0; t < n; t++) x[t] = dc_rat(oc[t] == y, 1, ovf);
        st_span_add(B, x, 1, ovf);
    }
    for (int head = 0; head < B->dim && !*ovf; head++)      /* B->dim grows: BFS queue */
        for (int a = 0; a < M->nact; a++)
            for (int y = 0; y < no; y++) {
                DcRat x[ST_MAXE]; const StKer *K = &s->ker[M->ak[a]];
                for (int t = 0; t < n; t++) {
                    x[t] = dc_rat(0, 1, ovf);
                    if (oc[t] != y) continue;
                    for (int u = 0; u < n; u++) if (!dc_rat_is_zero(K->p[t][u])) x[t] = dc_rat_add(x[t], dc_rat_mul(K->p[t][u], B->v[head][u], ovf), ovf);
                }
                st_span_add(B, x, B->len[head] + 1, ovf);
            }
}
/* Trace classes: tc[x] = class index; returns the number of classes. */
static int st_trace_classes(const StSpan *B, int *tc) {
    int k = 0;
    for (int x = 0; x < B->n; x++) {
        tc[x] = -1;
        for (int y = 0; y < x && tc[x] < 0; y++) {
            int same = 1;
            for (int i = 0; i < B->dim && same; i++) if (dc_rat_cmp(B->v[i][x], B->v[i][y])) same = 0;
            if (same) tc[x] = tc[y];
        }
        if (tc[x] < 0) tc[x] = k++;
    }
    return k;
}

/* ---- S03/S04: behavioral (Kantorovich) pseudometric, exact ----
 * d(s,t) = 1 if the observations differ, else gamma * max_a W_d(K_a(s), K_a(t)),
 * where W_d is the optimal-transport (Kantorovich) cost.  W_d is solved exactly by
 * successive shortest paths on the bipartite transport network (Bellman-Ford over
 * rationals; costs lie in [0,1] so the residual graph keeps no negative cycle).
 * The metric is the least fixed point, reached exactly from d = obs-difference or
 * reported Unsupported when no exact fixed point appears within the round limit. */
#define ST_KANT_AUG (4 * ST_MAXE * ST_MAXE)
static int st_kant(int n, const DcRat *mu, const DcRat *nu, DcRat (*c)[ST_MAXE], DcRat *out, int *ovf) {
    static DcRat f[ST_MAXE][ST_MAXE];
    DcRat rs[ST_MAXE], rd[ST_MAXE], z = dc_rat(0, 1, ovf);
    for (int i = 0; i < n; i++) { rs[i] = mu[i]; rd[i] = nu[i]; for (int j = 0; j < n; j++) f[i][j] = z; }
    for (int it = 0;; it++) {
        int any = 0;
        for (int i = 0; i < n; i++) if (dc_rat_cmp(rs[i], z) > 0) any = 1;
        if (!any) break;
        if (it == ST_KANT_AUG || *ovf) return -1;
        DcRat dist[2 * ST_MAXE]; int reach[2 * ST_MAXE] = {0}, pre[2 * ST_MAXE];
        for (int i = 0; i < n; i++) if (dc_rat_cmp(rs[i], z) > 0) { reach[i] = 1; dist[i] = z; pre[i] = -1; }
        for (int round = 0; round < 2 * n + 1; round++) {
            int ch = 0;
            for (int i = 0; i < n; i++) if (reach[i])
                for (int j = 0; j < n; j++) {
                    DcRat nd = dc_rat_add(dist[i], c[i][j], ovf);
                    if (!reach[n + j] || dc_rat_cmp(nd, dist[n + j]) < 0) { reach[n + j] = 1; dist[n + j] = nd; pre[n + j] = i; ch = 1; }
                }
            for (int j = 0; j < n; j++) if (reach[n + j])
                for (int i = 0; i < n; i++) if (dc_rat_cmp(f[i][j], z) > 0) {
                    DcRat nd = dc_rat_sub(dist[n + j], c[i][j], ovf);
                    if (!reach[i] || dc_rat_cmp(nd, dist[i]) < 0) { reach[i] = 1; dist[i] = nd; pre[i] = n + j; ch = 1; }
                }
            if (!ch) break;
        }
        int js = -1;
        for (int j = 0; j < n; j++)
            if (reach[n + j] && dc_rat_cmp(rd[j], z) > 0 && (js < 0 || dc_rat_cmp(dist[n + j], dist[n + js]) < 0)) js = j;
        if (js < 0) return -1;
        DcRat b = rd[js]; int v = n + js;
        while (pre[v] >= 0) { int p = pre[v]; if (v < n) b = dc_rat_min(b, f[v][p - n]); v = p; }
        b = dc_rat_min(b, rs[v]);
        int src = v; v = n + js;
        while (pre[v] >= 0) {
            int p = pre[v];
            if (v >= n) f[p][v - n] = dc_rat_add(f[p][v - n], b, ovf); else f[v][p - n] = dc_rat_sub(f[v][p - n], b, ovf);
            v = p;
        }
        rs[src] = dc_rat_sub(rs[src], b, ovf); rd[js] = dc_rat_sub(rd[js], b, ovf);
    }
    *out = z;
    for (int i = 0; i < n; i++) for (int j = 0; j < n; j++)
        if (!dc_rat_is_zero(f[i][j])) *out = dc_rat_add(*out, dc_rat_mul(f[i][j], c[i][j], ovf), ovf);
    return *ovf ? -1 : 0;
}
#define ST_BEH_ROUNDS (2 * ST_MAXE + 8)
/* d is n x n; returns 0 at an exact fixed point, -1 on overflow, -2 on the round limit. */
static int st_behav(const StMod *s, const StMach *M, DcRat gamma, DcRat (*d)[ST_MAXE], int *ovf) {
    int n = s->car[M->states].n, oc[ST_MAXE]; static DcRat nd[ST_MAXE][ST_MAXE];
    st_obsclass(s, M, oc);
    for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) d[x][y] = dc_rat(oc[x] != oc[y], 1, ovf);
    for (int r = 0; r < ST_BEH_ROUNDS; r++) {
        int ch = 0;
        for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) {
            if (oc[x] != oc[y] || x == y) { nd[x][y] = d[x][y]; continue; }
            DcRat best = dc_rat(0, 1, ovf), w;
            for (int a = 0; a < M->nact; a++) {
                const StKer *K = &s->ker[M->ak[a]];
                if (st_kant(n, K->p[x], K->p[y], d, &w, ovf)) return -1;
                best = dc_rat_max(best, w);
            }
            nd[x][y] = dc_rat_mul(gamma, best, ovf);
            if (dc_rat_cmp(nd[x][y], d[x][y])) ch = 1;
        }
        if (*ovf) return -1;
        memcpy(d, nd, sizeof nd);
        if (!ch) return 0;
    }
    return -2;
}

static Sx *st_rsx(DcRat a);
/* Signed-minimum certificate (Table 1): the basis restricted to the pivot
 * columns is nonsingular (the echelon copy is triangular there).  The replay
 * recomputes that minor's determinant from the basis vectors themselves by
 * exact elimination, independently of the echelon copy. */
static DcRat st_minor_det(const StSpan *B, int *ovf) {
    static DcRat a[ST_MAXE][ST_MAXE];
    int k = B->dim;
    for (int i = 0; i < k; i++) for (int j = 0; j < k; j++) a[i][j] = B->v[i][B->piv[j]];
    DcRat det = dc_rat(1, 1, ovf);
    for (int c = 0; c < k; c++) {
        int p = -1;
        for (int r = c; r < k && p < 0; r++) if (!dc_rat_is_zero(a[r][c])) p = r;
        if (p < 0) return dc_rat(0, 1, ovf);
        if (p != c) { for (int j = 0; j < k; j++) { DcRat t = a[c][j]; a[c][j] = a[p][j]; a[p][j] = t; } det = dc_rat_sub(dc_rat(0, 1, ovf), det, ovf); }
        det = dc_rat_mul(det, a[c][c], ovf);
        for (int r = c + 1; r < k; r++) {
            if (dc_rat_is_zero(a[r][c])) continue;
            DcRat f = dc_rat_div(a[r][c], a[c][c], ovf);
            for (int j = c; j < k; j++) a[r][j] = dc_rat_sub(a[r][j], dc_rat_mul(f, a[c][j], ovf), ovf);
        }
    }
    return det;
}
static Sx *st_minor_sx(const StSpan *B, const StCar *C, int *ovf) {
    Sx *cols = dc_form("Columns", NULL);
    for (int j = 0; j < B->dim; j++) sx_push(cols, dc_sym(C->el[B->piv[j]]));
    DcRat det = st_minor_det(B, ovf);
    return dc_form("Minor", cols, dc_form("Determinant", st_rsx(det), NULL), NULL);
}

/* ---- S07: linear arrows and positive realization ----
 * A linear arrow L : Source -> Target is checked by exact intertwining
 * K_a L = L K'_a for every action label a, observation preservation
 * (L(s,z) != 0 implies obs z = obs s for every observation label) and, for
 * Kind Positive, nonnegative entries with every row summing to exactly 1. */
static int st_obs_same(const StMod *s, const StMach *A, int x, const StMach *B, int z, int j) {
    const StMap *ma = &s->map[A->om[j]];
    for (int k = 0; k < B->nobs; k++) if (!strcmp(B->ol[k], A->ol[j])) {
        const StMap *mb = &s->map[B->om[k]];
        return !strcmp(s->car[ma->to].el[ma->tab[x]], s->car[mb->to].el[mb->tab[z]]);
    }
    return 0;
}
static int st_check_lin(const StMod *s, const StLin *L, char *why, size_t ws, int *ovf, int inter) {
    const StMach *A = &s->mach[L->src], *B = &s->mach[L->tgt];
    int n = s->car[A->states].n, m = s->car[B->states].n;
    const StCar *CA = &s->car[A->states], *CB = &s->car[B->states];
    if (A->nobs != B->nobs || A->nact != B->nact) { snprintf(why, ws, "source and target differ in observation or action labels"); return 0; }
    for (int x = 0; x < n; x++) {
        DcRat sum = dc_rat(0, 1, ovf);
        for (int z = 0; z < m; z++) {
            if (dc_rat_is_zero(L->a[x][z])) continue;
            if (!strcmp(L->kind, "Positive") && L->a[x][z].n < 0) { snprintf(why, ws, "negative entry at (%s %s)", CA->el[x], CB->el[z]); return 0; }
            for (int j = 0; j < A->nobs; j++) if (!st_obs_same(s, A, x, B, z, j)) { snprintf(why, ws, "observation %s differs at (%s %s)", A->ol[j], CA->el[x], CB->el[z]); return 0; }
            sum = dc_rat_add(sum, L->a[x][z], ovf);
        }
        if (!strcmp(L->kind, "Positive") && dc_rat_cmp(sum, dc_rat(1, 1, ovf))) { snprintf(why, ws, "row %s does not sum to 1", CA->el[x]); return 0; }
    }
    for (int a = 0; a < A->nact; a++) {
        int b = -1;
        for (int k = 0; k < B->nact; k++) if (!strcmp(B->al[k], A->al[a])) b = k;
        if (b < 0) { snprintf(why, ws, "target has no action %s", A->al[a]); return 0; }
        if (!inter) continue;
        const StKer *KA = &s->ker[A->ak[a]], *KB = &s->ker[B->ak[b]];
        for (int x = 0; x < n; x++) for (int z = 0; z < m; z++) {
            DcRat l = dc_rat(0, 1, ovf), r = dc_rat(0, 1, ovf);
            for (int t = 0; t < n; t++) if (!dc_rat_is_zero(KA->p[x][t])) l = dc_rat_add(l, dc_rat_mul(KA->p[x][t], L->a[t][z], ovf), ovf);
            for (int t = 0; t < m; t++) if (!dc_rat_is_zero(L->a[x][t])) r = dc_rat_add(r, dc_rat_mul(L->a[x][t], KB->p[t][z], ovf), ovf);
            if (dc_rat_cmp(l, r)) { snprintf(why, ws, "intertwining fails for %s at (%s %s)", A->al[a], CA->el[x], CB->el[z]); return 0; }
        }
    }
    return *ovf ? 0 : 1;
}

static DcRat st_abs(DcRat a, int *ovf) { return a.n < 0 ? dc_rat_sub(dc_rat(0, 1, ovf), a, ovf) : a; }
static void st_grade(const StMod *s, const StLin *L, DcRat *lam, DcRat *rho, int *ovf) {
    const StMach *A = &s->mach[L->src], *B = &s->mach[L->tgt];
    int n = s->car[A->states].n, m = s->car[B->states].n;
    *lam = dc_rat(0, 1, ovf); *rho = dc_rat(0, 1, ovf);
    for (int x = 0; x < n; x++) {
        DcRat r = dc_rat(0, 1, ovf);
        for (int z = 0; z < m; z++) r = dc_rat_add(r, st_abs(L->a[x][z], ovf), ovf);
        *lam = dc_rat_max(*lam, r);
    }
    for (int a = 0; a < A->nact; a++) {
        int b = -1;
        for (int k = 0; k < B->nact; k++) if (!strcmp(B->al[k], A->al[a])) b = k;
        if (b < 0) continue;
        const StKer *KA = &s->ker[A->ak[a]], *KB = &s->ker[B->ak[b]];
        for (int x = 0; x < n; x++) {
            DcRat row = dc_rat(0, 1, ovf);
            for (int z = 0; z < m; z++) {
                DcRat l = dc_rat(0, 1, ovf), r = dc_rat(0, 1, ovf);
                for (int t = 0; t < n; t++) if (!dc_rat_is_zero(KA->p[x][t])) l = dc_rat_add(l, dc_rat_mul(KA->p[x][t], L->a[t][z], ovf), ovf);
                for (int t = 0; t < m; t++) if (!dc_rat_is_zero(L->a[x][t])) r = dc_rat_add(r, dc_rat_mul(L->a[x][t], KB->p[t][z], ovf), ovf);
                row = dc_rat_add(row, st_abs(dc_rat_sub(l, r, ovf), ovf), ovf);
            }
            *rho = dc_rat_max(*rho, row);
        }
    }
}

/* ---- V01/V02: encoding classes and their lumping refinement ---- */
static int st_encclass(const StMap *E, int n, int *blk) {
    int k = 0;
    for (int x = 0; x < n; x++) { blk[x] = -1; for (int y = 0; y < x && blk[x] < 0; y++) if (E->tab[y] == E->tab[x]) blk[x] = blk[y]; if (blk[x] < 0) blk[x] = k++; }
    return k;
}
static int st_refine(const StMod *s, const StMach *M, int *blk, int nb, int *rounds, int *ovf) {
    int n = s->car[M->states].n, nb2, b2[ST_MAXE]; *rounds = 0;
    for (;;) {
        nb2 = 0;
        for (int x = 0; x < n; x++) {
            b2[x] = -1;
            for (int y = 0; y < x && b2[x] < 0; y++) {
                if (blk[y] != blk[x]) continue;
                int same = 1;
                for (int a = 0; a < M->nact && same; a++)
                    for (int b = 0; b < nb && same; b++)
                        if (dc_rat_cmp(st_blockmass(&s->ker[M->ak[a]], n, blk, x, b, ovf), st_blockmass(&s->ker[M->ak[a]], n, blk, y, b, ovf))) same = 0;
                if (same) b2[x] = b2[y];
            }
            if (b2[x] < 0) b2[x] = nb2++;
        }
        (*rounds)++; memcpy(blk, b2, sizeof(int) * (size_t)n);
        if (nb2 == nb) return nb;
        nb = nb2;
    }
}
/* ---- V04: expected proposals of a keyed archive until a target genotype is proposed.
 * The archive only grows (one incumbent per key), so E(A) = (1 + sum_{A'} w E(A')) / (1 - w_self). */
static const StKer *g_hk; static int g_hn, g_ht, g_hkey[ST_MAXE], g_hnodes;
static int st_hit(int *arc, int nk, DcRat *out, int *ovf) {
    int k = 0; for (int b = 0; b < nk; b++) k += arc[b] >= 0;
    if (++g_hnodes > 200000) return -1;
    DcRat self = dc_rat(0, 1, ovf), acc = dc_rat(0, 1, ovf), inv = dc_rat(1, k, ovf);
    for (int b = 0; b < nk; b++) {
        int p = arc[b]; if (p < 0) continue;
        for (int c = 0; c < g_hn; c++) {
            if (dc_rat_is_zero(g_hk->p[p][c]) || c == g_ht) continue;
            DcRat w = dc_rat_mul(inv, g_hk->p[p][c], ovf);
            if (arc[g_hkey[c]] >= 0) { self = dc_rat_add(self, w, ovf); continue; }
            DcRat e; arc[g_hkey[c]] = c; int rc = st_hit(arc, nk, &e, ovf); arc[g_hkey[c]] = -1;
            if (rc) return rc;
            acc = dc_rat_add(acc, dc_rat_mul(w, e, ovf), ovf);
        }
    }
    DcRat one = dc_rat(1, 1, ovf);
    if (!dc_rat_cmp(self, one)) return -2;
    *out = dc_rat_div(dc_rat_add(one, acc, ovf), dc_rat_sub(one, self, ovf), ovf);
    return *ovf ? -1 : 0;
}

/* ---- request dispatch ---- */
static Sx *st_rsx(DcRat a) { return a.d == 1 ? dc_int((long)a.n) : dc_form("Rat", dc_int((long)a.n), dc_int((long)a.d), NULL); }
static Sx *st_blocks(const StCar *c, const int *blk, int nb) {
    Sx *part = dc_form("Partition", NULL);
    for (int b = 0; b < nb; b++) {
        Sx *bl = dc_form("Block", NULL);
        for (int x = 0; x < c->n; x++) if (blk[x] == b) sx_push(bl, dc_sym(c->el[x]));
        sx_push(part, bl);
    }
    return part;
}
static Sx *st_env(DcModule *m, DcVerdict v, const Sx *q, const char *subjk, const char *subjn, Sx *val, Sx *ev, const char *why) {
    DcScope sc = { "M4-Stochastic", -1, "", NULL };
    Sx *subj = dc_form("Subject", dc_form(subjk, dc_sym(subjn), NULL), NULL);
    Sx *res = dc_envelope_scoped(m, v, 1, dc_claim_of(q, "Literal"), subj, val, ev, why, &sc);
    /* same pattern as M3 sym_policy: name the policy that replayed the evidence */
    Sx *au = res ? sx_find(res, "Assurance", 1) : NULL, *p = au ? sx_find(au, "Policy", 1) : NULL;
    if (p && p->n == 2) { sx_free(p->items[1]); p->items[1] = dc_sym("M4-StochasticReplay"); }
    return res;
}
Sx *dc_req_stoch(DcRun *r, const Sx *q, const char *head, int slot) {
    DcModule *m = r->m; char err[256]; static StMod S; int ovf = 0; (void)slot;
    if (st_read(m->source, &S, err, sizeof err)) return dc_invalid(m, "stochastic module: %s", err);
    const char *a1 = st_name(q, 1);
    if (!strcmp(head, "MinimizeForQueries") || !strcmp(head, "TracePartition") || !strcmp(head, "MinimalLinear")) {
        int mi = st_machi(&S, a1); if (mi < 0) return dc_invalid(m, "%s: %s names no machine", head, a1 ? a1 : "?");
        const StMach *M = &S.mach[mi]; const StCar *C = &S.car[M->states]; int blk[ST_MAXE], nb, rounds;
        if (!strcmp(head, "MinimizeForQueries")) {
            nb = st_lump(&S, M, blk, &rounds, &ovf);
            if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
            Sx *val = dc_form("Value", dc_form("Bisimulation", st_blocks(C, blk, nb), dc_form("Classes", dc_int(nb), NULL), NULL), NULL);
            Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("StrongLumping"), NULL), dc_form("Rounds", dc_int(rounds), NULL), NULL), NULL);
            return st_env(m, VERDICT_HOLDS, q, "Machine", a1, val, ev, NULL);
        }
        static StSpan B; st_span(&S, M, &B, &ovf);
        if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
        Sx *tv = dc_form("TestVectors", NULL);
        for (int i = 0; i < B.dim; i++) { Sx *v = dc_form("Vector", dc_form("Length", dc_int(B.len[i]), NULL), NULL);
            for (int x = 0; x < C->n; x++) { sx_push(v, dc_form(C->el[x], st_rsx(B.v[i][x]), NULL)); }
            sx_push(tv, v); }
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("TestVectorBasis"), NULL), tv, NULL), NULL);
        if (!strcmp(head, "TracePartition")) {
            nb = st_trace_classes(&B, blk);
            Sx *val = dc_form("Value", dc_form("TraceClasses", st_blocks(C, blk, nb), dc_form("Classes", dc_int(nb), NULL), NULL), NULL);
            return st_env(m, VERDICT_HOLDS, q, "Machine", a1, val, ev, NULL);
        }
        Sx *val = dc_form("Value", dc_form("MinimalLinear", dc_form("Dimension", dc_int(B.dim), NULL), NULL), NULL);
        sx_push(ev->items[1], st_minor_sx(&B, C, &ovf));
        if (ovf) { sx_free(val); sx_free(ev); return dc_unsupported(m, "%s: rational overflow (int64)", head); }
        return st_env(m, VERDICT_HOLDS, q, "Machine", a1, val, ev, NULL);
    }
    if (!strcmp(head, "CheckBehavioral") || !strcmp(head, "MeasureBehavioral") || !strcmp(head, "CheckTrace")) {
        int pi = st_repi(&S, a1); if (pi < 0) return dc_invalid(m, "%s: %s names no representation", head, a1 ? a1 : "?");
        const StRepr *P = &S.rep[pi]; const StMach *M = &S.mach[P->mach]; const StCar *C = &S.car[M->states]; const StMap *E = &S.map[P->enc];
        if (E->to != M->states) return dc_invalid(m, "%s: representation %s encodes into %s, not into the machine states", head, a1, S.car[E->to].name);
        if (!strcmp(head, "CheckTrace")) {
            static StSpan B; st_span(&S, M, &B, &ovf);
            if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
            int tc[ST_MAXE], bad = -1; st_trace_classes(&B, tc);
            for (int x = 0; x < C->n && bad < 0; x++) if (tc[x] != tc[E->tab[x]]) bad = x;
            Sx *val = dc_form("Value", dc_form("TraceEquivalent", dc_sym(bad < 0 ? "True" : "False"), NULL), NULL);
            Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("TestVectorBasis"), NULL), dc_form("Dimension", dc_int(B.dim), NULL), NULL), NULL);
            return st_env(m, bad < 0 ? VERDICT_HOLDS : VERDICT_FAILS, q, "Representation", a1, val, ev, NULL);
        }
        DcRat g = dc_rat(1, 1, &ovf);
        const Sx *dsc = q->n >= 3 ? q->items[2] : NULL;
        if (dsc && (!sx_head_is(dsc, "Discount") || dsc->n != 2 || dc_sx_rat(dsc->items[1], &g) || g.n < 0 || dc_rat_cmp(g, dc_rat(1, 1, &ovf)) > 0))
            return dc_invalid(m, "%s: expected (Discount r) with 0 <= r <= 1", head);
        static DcRat d[ST_MAXE][ST_MAXE]; int rc = st_behav(&S, M, g, d, &ovf);
        if (rc == -1) return dc_unsupported(m, "%s: rational overflow (int64) or transport limit", head);
        if (rc == -2) return dc_unsupported(m, "%s: no exact fixed point within %d rounds", head, ST_BEH_ROUNDS);
        DcRat def = dc_rat(0, 1, &ovf); int wx = -1;
        for (int x = 0; x < C->n; x++) if (dc_rat_cmp(d[x][E->tab[x]], def) > 0) { def = d[x][E->tab[x]]; wx = x; }
        Sx *val = dc_form("Value", dc_form("BehavioralDefect", st_rsx(def), NULL), dc_form("Discount", st_rsx(g), NULL), NULL);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("KantorovichFixedPoint"), NULL), NULL), NULL);
        if (wx >= 0) {   /* 1-Lipschitz witness phi = d(x, .) separates enc x from x by the defect (oracle: phi(x)=1/2, phi(y)=0) */
            int y = E->tab[wx];
            sx_push(ev->items[1], dc_form("ModalTestWitness", dc_form("Pair", dc_sym(C->el[wx]), dc_sym(C->el[y]), NULL),
                dc_form("Phi", dc_form(C->el[y], st_rsx(d[wx][y]), NULL), dc_form(C->el[wx], st_rsx(d[wx][wx]), NULL), NULL), NULL));
        }
        if (!strcmp(head, "MeasureBehavioral")) return st_env(m, VERDICT_HOLDS, q, "Representation", a1, val, ev, NULL);
        return st_env(m, wx < 0 ? VERDICT_HOLDS : VERDICT_FAILS, q, "Representation", a1, val, ev, NULL);
    }
    if (!strcmp(head, "CheckLinearArrow")) {
        int li = st_lini(&S, a1); if (li < 0) return dc_invalid(m, "%s: %s names no linear arrow", head, a1 ? a1 : "?");
        char why[200] = ""; int ok = st_check_lin(&S, &S.lin[li], why, sizeof why, &ovf, 0); DcRat lam, rho;
        st_grade(&S, &S.lin[li], &lam, &rho, &ovf);
        if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
        Sx *val = dc_form("Value", dc_form("LinearArrow", dc_sym(S.lin[li].kind), dc_form("Valid", dc_sym(ok ? "True" : "False"), NULL),
            dc_form("Grade", dc_form("Lambda", st_rsx(lam), NULL), dc_form("Rho", st_rsx(rho), NULL), NULL), NULL), NULL);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("GradedIntertwining"), NULL),
            dc_form("Residual", dc_sym("max_a max_x sum_z |K_a L - L K'_a|"), NULL), NULL), NULL);
        if (!ok) sx_push(ev->items[1], dc_form("Failure", dc_sym(why), NULL));
        return st_env(m, ok ? VERDICT_HOLDS : VERDICT_FAILS, q, "LinearArrow", a1, val, ev, NULL);
    }
    if (!strcmp(head, "Then")) {   /* L03: graded composition of two CheckLinearArrow outputs */
        int li[2]; const char *dn[2];
        for (int k = 0; k < 2; k++) {
            const Sx *o = q->n == 3 ? q->items[1 + k] : NULL; const Sx *rq = NULL;
            dn[k] = sx_head_is(o, "Output") && o->n == 3 && sx_is_sym(o->items[2], "Value") ? st_name(o, 1) : NULL;
            for (size_t i = 2; dn[k] && i < m->source->n && !rq; i++) {
                const Sx *d = m->source->items[i];
                if (sx_head_is(d, "Derive") && d->n == 3 && st_name(d, 1) && !strcmp(st_name(d, 1), dn[k])) rq = d->items[2];
            }
            li[k] = sx_head_is(rq, "CheckLinearArrow") ? st_lini(&S, st_name(rq, 1)) : -1;
            if (li[k] < 0) return dc_invalid(m, "Then: expected (Output D Value) where D derives (CheckLinearArrow L)");
        }
        const StLin *A = &S.lin[li[0]], *Bk = &S.lin[li[1]];
        if (A->tgt != Bk->src) return dc_invalid(m, "Then: %s targets %s but %s starts at %s", A->name, S.mach[A->tgt].name, Bk->name, S.mach[Bk->src].name);
        if (S.nlin == ST_MAXD) return dc_unsupported(m, "Then: too many linear arrows");
        StLin *C = &S.lin[S.nlin]; memset(C, 0, sizeof *C);
        { char nm[2 * ST_NM + 2]; snprintf(nm, sizeof nm, "%s;%s", A->name, Bk->name); snprintf(C->name, ST_NM, "%.*s", (int)ST_NM - 1, nm); } C->src = A->src; C->tgt = Bk->tgt;
        snprintf(C->kind, ST_NM, "%s", !strcmp(A->kind, "Positive") && !strcmp(Bk->kind, "Positive") ? "Positive" : "Signed");
        int n = S.car[S.mach[A->src].states].n, mm = S.car[S.mach[A->tgt].states].n, p = S.car[S.mach[Bk->tgt].states].n;
        for (int x = 0; x < n; x++) for (int z = 0; z < p; z++) {
            C->a[x][z] = dc_rat(0, 1, &ovf);
            for (int t = 0; t < mm; t++) if (!dc_rat_is_zero(A->a[x][t])) C->a[x][z] = dc_rat_add(C->a[x][z], dc_rat_mul(A->a[x][t], Bk->a[t][z], &ovf), &ovf);
        }
        DcRat la, ra, lb, rb, lc, rc;
        st_grade(&S, A, &la, &ra, &ovf); st_grade(&S, Bk, &lb, &rb, &ovf); st_grade(&S, C, &lc, &rc, &ovf);
        /* composition rule: (lA lB, rA lB + lA rB) -- the residual of A is amplified by B's norm and vice versa */
        DcRat lam = dc_rat_mul(la, lb, &ovf), rho = dc_rat_add(dc_rat_mul(ra, lb, &ovf), dc_rat_mul(la, rb, &ovf), &ovf);
        if (ovf) return dc_unsupported(m, "Then: rational overflow (int64)");
        int sound = dc_rat_cmp(lc, lam) <= 0 && dc_rat_cmp(rc, rho) <= 0, attained = !dc_rat_cmp(rc, rho);
        Sx *val = dc_form("Value", dc_form("LinearArrow", dc_sym(C->kind), dc_form("Valid", dc_sym("True"), NULL),
            dc_form("Grade", dc_form("Lambda", st_rsx(lam), NULL), dc_form("Rho", st_rsx(rho), NULL), NULL),
            dc_form("Attained", dc_sym(attained ? "True" : "False"), NULL), NULL), NULL);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("GradedComposition"), NULL),
            dc_form("Rule", dc_sym("(lA*lB, rA*lB + lA*rB)"), NULL),
            dc_form("Factors", dc_form(A->name, st_rsx(la), st_rsx(ra), NULL), dc_form(Bk->name, st_rsx(lb), st_rsx(rb), NULL), NULL),
            dc_form("ComposedResidual", dc_form("Lambda", st_rsx(lc), NULL), dc_form("Rho", st_rsx(rc), NULL), NULL), NULL), NULL);
        if (!sound) return dc_unsupported(m, "Then: composed residual exceeds the composition bound (internal check)");
        return st_env(m, VERDICT_HOLDS, q, "LinearArrow", C->name, val, ev, NULL);
    }
    if (!strcmp(head, "CheckUpdates") || !strcmp(head, "Refine")) {   /* V01, V02 */
        int pi = st_repi(&S, a1); if (pi < 0) return dc_invalid(m, "%s: %s names no representation", head, a1 ? a1 : "?");
        const StRepr *P = &S.rep[pi]; const StMach *M = &S.mach[P->mach]; const StCar *C = &S.car[M->states]; const StMap *E = &S.map[P->enc];
        int n = C->n, blk[ST_MAXE], nb = st_encclass(E, n, blk), rounds;
        if (!strcmp(head, "Refine")) {
            for (size_t i = 2; i < q->n; i++) {
                const Sx *o = q->items[i];
                if (!(sx_head_is(o, "Preserve") && o->n == 2 && sx_is_sym(o->items[1], "Encoding")) && !(sx_head_is(o, "Until") && o->n == 2 && sx_is_sym(o->items[1], "Stable")))
                    return dc_invalid(m, "Refine: expected (Preserve Encoding) and (Until Stable)");
            }
            nb = st_refine(&S, M, blk, nb, &rounds, &ovf);
            if (ovf) return dc_unsupported(m, "Refine: rational overflow (int64)");
            Sx *val = dc_form("Value", dc_form("Refinement", st_blocks(C, blk, nb), dc_form("Classes", dc_int(nb), NULL), NULL), NULL);
            Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("StrongLumping"), NULL), dc_form("From", dc_sym("Encoding"), NULL), dc_form("Rounds", dc_int(rounds), NULL), NULL), NULL);
            return st_env(m, VERDICT_HOLDS, q, "Representation", a1, val, ev, NULL);
        }
        int wa = -1, wx = -1, wy = -1, wb = -1; DcRat mx = dc_rat(0, 1, &ovf), my = mx;
        for (int a = 0; a < M->nact && wa < 0; a++) for (int x = 0; x < n && wa < 0; x++) for (int y = x + 1; y < n && wa < 0; y++) {
            if (blk[x] != blk[y]) continue;
            for (int pass = 0; pass < 2 && wa < 0; pass++) for (int b = 0; b < nb && wa < 0; b++) {   /* prefer mass escaping to another class */
                if ((pass == 0) != (b != blk[x])) continue;
                DcRat u = st_blockmass(&S.ker[M->ak[a]], n, blk, x, b, &ovf), v = st_blockmass(&S.ker[M->ak[a]], n, blk, y, b, &ovf);
                if (dc_rat_cmp(u, v)) { wa = a; wx = x; wy = y; wb = b; mx = u; my = v; }
            }
        }
        if (ovf) return dc_unsupported(m, "CheckUpdates: rational overflow (int64)");
        Sx *val = dc_form("Value", dc_form("UpdatesStable", dc_sym(wa < 0 ? "True" : "False"), NULL), NULL);
        Sx *ev;
        if (wa < 0) ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("EncodingLumpable"), NULL), NULL), NULL);
        else {
            const char *lab = E->name; int rx = 0;
            for (int j = 0; j < M->nobs; j++) if (M->om[j] == P->enc) lab = M->ol[j];
            while (blk[rx] != wb) rx++;
            ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("UpdateWitness"), NULL),
                dc_form("Pair", dc_sym(C->el[wx]), dc_sym(C->el[wy]), NULL), dc_form("Action", dc_sym(M->al[wa]), NULL),
                dc_form("Class", dc_form(lab, dc_sym(S.car[E->to].el[E->tab[rx]]), NULL), NULL),
                dc_form("Masses", st_rsx(mx), st_rsx(my), NULL), NULL), NULL);
        }
        return st_env(m, wa < 0 ? VERDICT_HOLDS : VERDICT_FAILS, q, "Representation", a1, val, ev, NULL);
    }
    if (!strcmp(head, "ExpectedProposals")) {   /* V04 */
        const Sx *d = NULL, *src = m->source;
        for (size_t i = 2; i < src->n && !d; i++) if (sx_head_is(src->items[i], "Archive") && st_name(src->items[i], 1) && a1 && !strcmp(st_name(src->items[i], 1), a1)) d = src->items[i];
        if (!d) return dc_invalid(m, "ExpectedProposals: %s names no archive", a1 ? a1 : "?");
        int mi = st_machi(&S, st_name(st_field(d, "Machine"), 1));
        const Sx *pc = st_field(d, "ParentChoice"), *kf = st_field(d, "Key"), *ko = kf && kf->n == 2 ? kf->items[1] : NULL;
        const Sx *un = q->n == 3 ? q->items[2] : NULL, *hi = sx_head_is(un, "Until") && un->n == 2 ? un->items[1] : NULL;
        if (mi < 0 || !pc || !sx_is_sym(pc->n == 2 ? pc->items[1] : NULL, "Uniform") || !ko || !sx_head_is(hi, "Hits") || hi->n != 2)
            return dc_invalid(m, "ExpectedProposals: expected an archive with (Machine M) (Key K) (Start s) (ParentChoice Uniform) and (Until (Hits s))");
        const StMach *M = &S.mach[mi]; const StCar *C = &S.car[M->states]; int n = C->n, nk = -1, rounds;
        if (M->nact != 1) return dc_unsupported(m, "ExpectedProposals: archive machine must have exactly one action");
        if (sx_head_is(ko, "Output") && ko->n == 3 && sx_is_sym(ko->items[2], "Representation")) {
            const Sx *rq = NULL;
            for (size_t i = 2; i < src->n && !rq; i++) { const Sx *e = src->items[i];
                if (sx_head_is(e, "Derive") && e->n == 3 && st_name(e, 1) && st_name(ko, 1) && !strcmp(st_name(e, 1), st_name(ko, 1))) rq = e->items[2]; }
            int pi = sx_head_is(rq, "Refine") ? st_repi(&S, st_name(rq, 1)) : -1;
            if (pi < 0 || S.mach[S.rep[pi].mach].states != M->states) return dc_invalid(m, "ExpectedProposals: key must be (Output D Representation) with D a Refine over the archive states");
            nk = st_refine(&S, &S.mach[S.rep[pi].mach], g_hkey, st_encclass(&S.map[S.rep[pi].enc], n, g_hkey), &rounds, &ovf);
        } else if (ko->kind == SX_SYM && st_mapi(&S, ko->text) >= 0 && S.map[st_mapi(&S, ko->text)].from == M->states) nk = st_encclass(&S.map[st_mapi(&S, ko->text)], n, g_hkey);
        if (nk < 0) return dc_invalid(m, "ExpectedProposals: unknown key");
        int st0 = st_el(C, st_field(d, "Start") && st_field(d, "Start")->n == 2 ? st_field(d, "Start")->items[1] : NULL), tg = st_el(C, hi->items[1]);
        if (st0 < 0 || tg < 0) return dc_invalid(m, "ExpectedProposals: start and target must be states of %s", M->name);
        g_hk = &S.ker[M->ak[0]]; g_hn = n; g_ht = tg; g_hnodes = 0;
        int arc[ST_MAXE]; for (int b = 0; b < nk; b++) arc[b] = -1;
        arc[g_hkey[st0]] = st0; DcRat e = dc_rat(0, 1, &ovf); int rc = st0 == tg ? 0 : st_hit(arc, nk, &e, &ovf);
        if (rc == -2) return st_env(m, VERDICT_FAILS, q, "Archive", a1, dc_form("Value", dc_form("Reachable", dc_sym("False"), NULL), NULL), dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("ArchiveClosed"), NULL), NULL), NULL), NULL);
        if (rc || ovf) return dc_unsupported(m, "ExpectedProposals: rational overflow (int64) or archive state limit");
        Sx *val = dc_form("Value", dc_form("ExpectedProposals", st_rsx(e), NULL), dc_form("Until", dc_form("Hits", dc_sym(C->el[tg]), NULL), NULL), NULL);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("ArchiveHittingTime"), NULL), dc_form("Keys", dc_int(nk), NULL), dc_form("ArchiveStates", dc_int(g_hnodes), NULL), NULL), NULL);
        return st_env(m, VERDICT_HOLDS, q, "Archive", a1, val, ev, NULL);
    }
    if (!strcmp(head, "PositiveRealization")) {
        int mi = st_machi(&S, a1); if (mi < 0) return dc_invalid(m, "%s: %s names no machine", head, a1 ? a1 : "?");
        const Sx *cf = q->n >= 3 && sx_head_is(q->items[2], "Candidate") ? q->items[2] : NULL;
        int li = cf ? st_lini(&S, st_name(cf, 1)) : -1;
        if (q->n >= 3 && li < 0) return dc_invalid(m, "%s: expected (Candidate L) naming a linear arrow", head);
        if (li >= 0 && (S.lin[li].src != mi || strcmp(S.lin[li].kind, "Positive"))) return dc_invalid(m, "%s: candidate must be a Positive arrow from %s", head, a1);
        static StSpan B; int blk[ST_MAXE], rounds;
        st_span(&S, &S.mach[mi], &B, &ovf);
        int lumped = st_lump(&S, &S.mach[mi], blk, &rounds, &ovf), upper = lumped;   /* the lumped quotient is itself positive */
        if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
        char why[200] = ""; int cok = li >= 0 ? st_check_lin(&S, &S.lin[li], why, sizeof why, &ovf, 1) : 0;
        int cdim = li >= 0 ? S.car[S.mach[S.lin[li].tgt].states].n : 0;
        if (cok && cdim < upper) upper = cdim;
        Sx *val = dc_form("Value", dc_form("PositiveDimension", dc_form("Interval", dc_int(B.dim), dc_int(upper), NULL), NULL), NULL);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("SignedMinimumAndReplayedCandidate"), NULL),
            dc_form("SignedMinimum", dc_int(B.dim), NULL), dc_form("LumpedQuotient", dc_int(lumped), NULL), NULL), NULL);
        sx_push(ev->items[1], st_minor_sx(&B, &S.car[S.mach[mi].states], &ovf));
        if (li >= 0) sx_push(ev->items[1], dc_form("Candidate", dc_sym(S.lin[li].name), dc_sym(cok ? "Replayed" : "Rejected"), dc_form("States", dc_int(cdim), NULL), NULL));
        if (li >= 0 && !cok) sx_push(ev->items[1], dc_form("Failure", dc_sym(why), NULL));
        return st_env(m, VERDICT_HOLDS, q, "Machine", a1, val, ev, NULL);
    }
    return dc_unsupported(m, "request %s: stochastic head not implemented yet (M4)", head);
}
