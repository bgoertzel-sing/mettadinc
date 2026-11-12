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
            const Sx *ff = st_field(d, "From"), *tf = st_field(d, "To");
            if (ff && ff->n == 2 && ff->items[1]->kind == SX_LIST) continue;   /* R: product-domain laws are read by the decisions code */
            StMap *mp = &s->map[s->nmap]; memset(mp, 0, sizeof *mp); snprintf(mp->name, ST_NM, "%s", nm);
            mp->from = st_car(s, st_name(ff, 1)); mp->to = st_car(s, st_name(tf, 1));
            if (mp->from >= 0 && tf && tf->n == 2 && tf->items[1]->kind == SX_LIST) {
                /* structured image (R: rewards-new): a synthetic carrier of the distinct case values */
                const Sx *cs = st_field(d, "Cases"), *vals[ST_MAXE];
                if (!cs || s->ncar == ST_MAXD) return st_err(err, es, "structured map needs (Cases ...) and a free carrier slot:", nm);
                StCar *c = &s->car[s->ncar]; memset(c, 0, sizeof *c); snprintf(c->name, ST_NM, "%.*s#", (int)ST_NM - 2, nm);
                for (int k = 0; k < ST_MAXE; k++) mp->tab[k] = -1;
                for (size_t k = 1; k < cs->n; k++) {
                    const Sx *cc = cs->items[k];
                    int a = cc->kind == SX_LIST && cc->n == 2 ? st_el(&s->car[mp->from], cc->items[0]) : -1, j = 0;
                    if (a < 0 || mp->tab[a] >= 0) return st_err(err, es, "bad or duplicate case in map", nm);
                    while (j < c->n && !sx_equal(vals[j], cc->items[1])) j++;
                    if (j == c->n) { vals[j] = cc->items[1]; snprintf(c->el[j], ST_NM, "v%d", j); c->n++; }
                    mp->tab[a] = j;
                }
                for (int k = 0; k < s->car[mp->from].n; k++) if (mp->tab[k] < 0) return st_err(err, es, "map is not total:", nm);
                mp->to = s->ncar++; s->nmap++; continue;
            }
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
static DcRat g_kf[ST_MAXE][ST_MAXE];   /* U04: the optimal coupling of the last st_kant call */
static int st_kant(int n, const DcRat *mu, const DcRat *nu, DcRat (*c)[ST_MAXE], DcRat *out, int *ovf) {
    DcRat (*f)[ST_MAXE] = g_kf;
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

/* ---- R01-R06: decision models (Use Decisions) ---- */
static const Sx *st_decl(const Sx *src, const char *head, const char *nm) {
    for (size_t i = 2; nm && i < src->n; i++) { const Sx *d = src->items[i];
        if (sx_head_is(d, head) && st_name(d, 1) && !strcmp(st_name(d, 1), nm)) return d; }
    return NULL;
}
static int st_elval(const StCar *T, int j, DcRat *v, int *ovf) {
    char *e; long long k = strtoll(T->el[j], &e, 10);
    if (!T->el[j][0] || *e) return -1;
    *v = dc_rat(k, 1, ovf); return 0;
}
static int st_lawx(const Sx *e, const StCar *T, DcRat *out, int *ovf) {
    for (int j = 0; j < T->n; j++) out[j] = dc_rat(0, 1, ovf);
    if (sx_head_is(e, "Point") && e->n == 2) { int j = st_el(T, e->items[1]); if (j < 0) return -1; out[j] = dc_rat(1, 1, ovf); return 0; }
    if (sx_head_is(e, "Coin") && e->n == 2) {
        DcRat p; int j0 = -1, j1 = -1;
        for (int j = 0; j < T->n; j++) { if (!strcmp(T->el[j], "0")) j0 = j; if (!strcmp(T->el[j], "1")) j1 = j; }
        if (j0 < 0 || j1 < 0 || st_rat(e->items[1], &p) || p.n < 0 || dc_rat_cmp(p, dc_rat(1, 1, ovf)) > 0) return -1;
        out[j1] = p; out[j0] = dc_rat_sub(dc_rat(1, 1, ovf), p, ovf); return 0;
    }
    return -1;
}
static int st_measure(StMod *s, const Sx *src, const char *nm, int car, DcRat *mu, int *ovf) {
    const Sx *d = st_decl(src, "Measure", nm), *ms = d ? st_field(d, "Masses") : NULL;
    if (!ms || car < 0 || st_car(s, st_name(st_field(d, "On"), 1)) != car) return -1;
    const StCar *C = &s->car[car]; int got[ST_MAXE] = {0}; DcRat sum = dc_rat(0, 1, ovf);
    for (int x = 0; x < C->n; x++) mu[x] = dc_rat(0, 1, ovf);
    for (size_t k = 1; k < ms->n; k++) { const Sx *e = ms->items[k]; DcRat w;
        int x = e->kind == SX_LIST && e->n == 2 ? st_el(C, e->items[0]) : -1;
        if (x < 0 || got[x] || st_rat(e->items[1], &w) || w.n < 0) return -1;
        got[x] = 1; mu[x] = w; sum = dc_rat_add(sum, w, ovf); }
    return dc_rat_cmp(sum, dc_rat(1, 1, ovf)) ? -1 : 0;
}
typedef struct { int sc, ac, tc; DcRat law[ST_MAXE][ST_MAXE][ST_MAXE], er[ST_MAXE][ST_MAXE]; } StDM;
static int st_dm(StMod *s, const Sx *src, const char *nm, StDM *D, char *why, size_t ws, int *ovf) {
    const Sx *d = st_decl(src, "DecisionModel", nm);
    if (!d) { snprintf(why, ws, "%s names no decision model", nm ? nm : "?"); return -1; }
    D->sc = st_car(s, st_name(st_field(d, "States"), 1)); D->ac = st_car(s, st_name(st_field(d, "Actions"), 1)); D->tc = -1;
    const Sx *mp = st_decl(src, "Map", st_name(st_field(d, "RewardLaw"), 1));
    const Sx *ff = mp ? st_field(mp, "From") : NULL, *tf = mp ? st_field(mp, "To") : NULL;
    const Sx *pr = ff && ff->n == 2 ? ff->items[1] : NULL, *lw = tf && tf->n == 2 ? tf->items[1] : NULL;
    if (D->sc < 0 || D->ac < 0 || !sx_head_is(pr, "Product") || pr->n != 3 || st_car(s, st_name(pr, 1)) != D->sc || st_car(s, st_name(pr, 2)) != D->ac
        || !sx_head_is(lw, "Law") || lw->n != 2 || (D->tc = st_car(s, st_name(lw, 1))) < 0) {
        snprintf(why, ws, "decision model %s needs (States S) (Actions A) and a RewardLaw map (From (Product S A)) (To (Law T))", nm); return -1; }
    const StCar *SC = &s->car[D->sc], *AC = &s->car[D->ac], *TC = &s->car[D->tc];
    static int seen[ST_MAXE][ST_MAXE]; memset(seen, 0, sizeof seen);
    const Sx *bd = st_field(mp, "Body"), *cs = st_field(mp, "Cases");
    for (int x = 0; x < SC->n; x++) for (int a = 0; a < AC->n; a++)
        if (bd && bd->n == 3 && !st_lawx(bd->items[2], TC, D->law[x][a], ovf)) seen[x][a] = 1;
    for (size_t k = 1; cs && k < cs->n; k++) { const Sx *c = cs->items[k];
        const Sx *t = c->kind == SX_LIST && c->n == 2 ? c->items[0] : NULL;
        int x = sx_head_is(t, "Tuple") && t->n == 3 ? st_el(SC, t->items[1]) : -1, a = x >= 0 ? st_el(AC, t->items[2]) : -1;
        if (a < 0 || seen[x][a] || st_lawx(c->items[1], TC, D->law[x][a], ovf)) { snprintf(why, ws, "bad or duplicate case in the reward law of %s", nm); return -1; }
        seen[x][a] = 1; }
    for (int x = 0; x < SC->n; x++) for (int a = 0; a < AC->n; a++) {
        if (!seen[x][a]) { snprintf(why, ws, "reward law of %s is not total", nm); return -1; }
        D->er[x][a] = dc_rat(0, 1, ovf);
        for (int t = 0; t < TC->n; t++) { DcRat v; if (dc_rat_is_zero(D->law[x][a][t])) continue;
            if (st_elval(TC, t, &v, ovf)) { snprintf(why, ws, "reward outcomes of %s must be integers", nm); return -1; }
            D->er[x][a] = dc_rat_add(D->er[x][a], dc_rat_mul(D->law[x][a][t], v, ovf), ovf); }
    }
    return *ovf ? -1 : 0;
}
static void st_avg(const StMod *s, const StDM *D, const DcRat *mu, DcRat av[][ST_MAXE], int *ovf) {
    for (int a = 0; a < s->car[D->ac].n; a++) for (int t = 0; t < s->car[D->tc].n; t++) {
        av[a][t] = dc_rat(0, 1, ovf);
        for (int x = 0; x < s->car[D->sc].n; x++) av[a][t] = dc_rat_add(av[a][t], dc_rat_mul(mu[x], D->law[x][a][t], ovf), ovf);
    }
}
static Sx *st_avg_sx(const StMod *s, const StDM *D, DcRat av[][ST_MAXE], int *ovf) {
    const StCar *AC = &s->car[D->ac], *TC = &s->car[D->tc]; Sx *r = dc_form("Averaged", NULL);
    for (int a = 0; a < AC->n; a++) {
        Sx *lw = dc_form("Law", NULL); DcRat mean = dc_rat(0, 1, ovf), v;
        for (int t = 0; t < TC->n; t++) { sx_push(lw, dc_form(TC->el[t], st_rsx(av[a][t]), NULL));
            if (!st_elval(TC, t, &v, ovf)) mean = dc_rat_add(mean, dc_rat_mul(av[a][t], v, ovf), ovf); }
        sx_push(r, dc_form(AC->el[a], lw, dc_form("Mean", st_rsx(mean), NULL), NULL));
    }
    return r;
}

static const Sx *st_opt(const Sx *q, const char *h) {
    for (size_t i = 1; q && q->kind == SX_LIST && i < q->n; i++) if (sx_head_is(q->items[i], h) && q->items[i]->n == 2) return q->items[i];
    return NULL;
}

/* ---- O01-O04: bounded trace defect over fixed words or observation-based policies.
 * mu, nu are sub-probability vectors that agree on all reports so far; the defect is the
 * total positive part sum over leaves max(0, |mu_leaf| - |nu_leaf|), maximised over the
 * action choice at each node (policies) or along one fixed word. */
typedef struct { DcRat v, pe, qe; } StTv;
static int g_tvnodes; static unsigned long long g_tvlast; static char g_olab[ST_MAXE][ST_NM];
static StTv st_tvrec(const StMod *s, const StMach *M, const int *oc, int noc, const DcRat *mu, const DcRat *nu,
                     int k, const int *word, int depth, int last, Sx **tree, int *ovf) {
    int n = s->car[M->states].n; StTv r; r.v = r.pe = r.qe = dc_rat(0, 1, ovf);
    if (tree) *tree = NULL;
    if (++g_tvnodes > 200000) { *ovf = 1; return r; }
    if (k == 0) {
        DcRat a = dc_rat(0, 1, ovf), b = a;
        for (int x = 0; x < n; x++) { a = dc_rat_add(a, mu[x], ovf); b = dc_rat_add(b, nu[x], ovf); }
        if (dc_rat_cmp(a, b) > 0) { r.v = dc_rat_sub(a, b, ovf); r.pe = a; r.qe = b; if (last >= 0 && last < 64) g_tvlast |= 1ULL << last; }
        return r;
    }
    int a0 = word ? word[depth] : 0, a1 = word ? word[depth] + 1 : M->nact, best = -1; Sx *bt = NULL;
    unsigned long long save = g_tvlast, bmask = 0;
    for (int a = a0; a < a1; a++) {
        const StKer *K = &s->ker[M->ak[a]]; DcRat mu2[ST_MAXE], nu2[ST_MAXE];
        for (int y = 0; y < n; y++) mu2[y] = nu2[y] = dc_rat(0, 1, ovf);
        for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) if (!dc_rat_is_zero(K->p[x][y])) {
            if (!dc_rat_is_zero(mu[x])) mu2[y] = dc_rat_add(mu2[y], dc_rat_mul(mu[x], K->p[x][y], ovf), ovf);
            if (!dc_rat_is_zero(nu[x])) nu2[y] = dc_rat_add(nu2[y], dc_rat_mul(nu[x], K->p[x][y], ovf), ovf); }
        StTv acc; acc.v = acc.pe = acc.qe = dc_rat(0, 1, ovf); g_tvlast = 0;
        Sx *node = tree ? dc_form("Do", dc_sym(M->al[a]), NULL) : NULL;
        for (int c = 0; c < noc; c++) {
            DcRat m3[ST_MAXE], n3[ST_MAXE]; int any = 0;
            for (int y = 0; y < n; y++) { m3[y] = oc[y] == c ? mu2[y] : dc_rat(0, 1, ovf); n3[y] = oc[y] == c ? nu2[y] : dc_rat(0, 1, ovf);
                any |= !dc_rat_is_zero(m3[y]) || !dc_rat_is_zero(n3[y]); }
            if (!any) continue;
            Sx *sub = NULL;
            StTv t = st_tvrec(s, M, oc, noc, m3, n3, k - 1, word, depth + 1, c, node && k > 1 ? &sub : NULL, ovf);
            acc.v = dc_rat_add(acc.v, t.v, ovf); acc.pe = dc_rat_add(acc.pe, t.pe, ovf); acc.qe = dc_rat_add(acc.qe, t.qe, ovf);
            if (node && sub) sx_push(node, dc_form("On", dc_sym(g_olab[c]), sub, NULL));
        }
        if (best < 0 || dc_rat_cmp(acc.v, r.v) > 0) { r = acc; best = a; if (bt) sx_free(bt); bt = node; bmask = g_tvlast; }
        else if (node) sx_free(node);
    }
    g_tvlast = save | bmask;
    if (tree) *tree = bt; else if (bt) sx_free(bt);
    return r;
}

/* ---- U01-U04: layered behavioral distances and exact fixed-point certificates ---- */
static int g_st_rep = 1;   /* 0: the envelope answers Unknown (no replayable evidence) */
static int st_bstep(const StMod *s, const StMach *M, const int *oc, DcRat gamma, DcRat (*d)[ST_MAXE], DcRat (*nd)[ST_MAXE], int *ch, int *ovf) {
    int n = s->car[M->states].n; *ch = 0;
    for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) {
        if (oc[x] != oc[y] || x == y) { nd[x][y] = d[x][y]; continue; }
        DcRat best = dc_rat(0, 1, ovf), w;
        for (int a = 0; a < M->nact; a++) {
            if (st_kant(n, s->ker[M->ak[a]].p[x], s->ker[M->ak[a]].p[y], d, &w, ovf)) return -1;
            best = dc_rat_max(best, w);
        }
        nd[x][y] = dc_rat_mul(gamma, best, ovf);
        if (dc_rat_cmp(nd[x][y], d[x][y])) *ch = 1;
    }
    return *ovf ? -1 : 0;
}
static DcRat st_defect(const StCar *C, const StMap *E, DcRat (*d)[ST_MAXE], int *wx, int *ovf) {
    DcRat def = dc_rat(0, 1, ovf); *wx = -1;
    for (int x = 0; x < C->n; x++) if (dc_rat_cmp(d[x][E->tab[x]], def) > 0) { def = d[x][E->tab[x]]; *wx = x; }
    return def;
}
/* ---- review 1 F2: replayable behavioral certificates (spec certificate table) ----
 * Layers D_0..D_K of st_behav's recurrence are kept.  Upper bound (Prefixpoint): the
 * fixed point D_K with one optimal coupling per pair and action.  Lower bound (Test): a
 * modal test of Definition 4.9, built bottom-up.  An observation test separates pairs in
 * different observation classes.  For a pair in one class at layer k, the
 * Kantorovich-Rubinstein dual of the optimal transport at D_(k-1) (potentials from the
 * residual graph of st_kant's flow) gives a 1-Lipschitz F; F is rebuilt on the two
 * supports as max_u min_v of clipped, shifted layer-(k-1) tests (lattice lemma), and
 * <a>_gamma applies it.  Every node value is computed exactly and checked as it is built. */
/* Kantorovich-Rubinstein dual of the optimal transport just computed by st_kant (flow in g_kf, cost w):
 * shortest-path potentials on the residual graph give F(z) = min_j (c(z,j) - pi_j), a c-transform, hence
 * 1-Lipschitz for the pseudometric c.  F is shifted to min 0 on U = supp(mu) u supp(nu) and accepted only
 * if F <= 1 and E_mu F - E_nu F = w exactly (weak duality makes that an optimality certificate). */
static int st_kdual(int n, const DcRat *mu, const DcRat *nu, DcRat (*c)[ST_MAXE], DcRat w, DcRat *F, int *U, int *mo, int *ovf) {
    static DcRat fl[ST_MAXE][ST_MAXE]; memcpy(fl, g_kf, sizeof fl);
    DcRat z0 = dc_rat(0, 1, ovf), one = dc_rat(1, 1, ovf), pi[2 * ST_MAXE], lo = z0, em = z0; int in[2 * ST_MAXE], m = 0, ch = 1;
    for (int i = 0; i < n; i++) { in[i] = dc_rat_cmp(mu[i], z0) > 0; in[n + i] = dc_rat_cmp(nu[i], z0) > 0; pi[i] = pi[n + i] = z0; }
    for (int round = 0; round < 2 * n + 2 && ch; round++) { ch = 0;
        for (int i = 0; i < n; i++) if (in[i]) for (int j = 0; j < n; j++) if (in[n + j]) {
            DcRat q = dc_rat_add(pi[i], c[i][j], ovf); if (dc_rat_cmp(q, pi[n + j]) < 0) { pi[n + j] = q; ch = 1; }
            if (dc_rat_cmp(fl[i][j], z0) > 0) { q = dc_rat_sub(pi[n + j], c[i][j], ovf); if (dc_rat_cmp(q, pi[i]) < 0) { pi[i] = q; ch = 1; } } } }
    if (ch || *ovf) return -1;
    for (int z = 0; z < n; z++) if (in[z] || in[n + z]) {
        int f1 = 1; for (int j = 0; j < n; j++) if (in[n + j]) { DcRat q = dc_rat_sub(c[z][j], pi[n + j], ovf); if (f1 || dc_rat_cmp(q, F[z]) < 0) F[z] = q; f1 = 0; }
        if (!m || dc_rat_cmp(F[z], lo) < 0) lo = F[z];
        U[m++] = z; }
    for (int i = 0; i < m; i++) { F[U[i]] = dc_rat_sub(F[U[i]], lo, ovf); if (dc_rat_cmp(F[U[i]], one) > 0) return -1;
        em = dc_rat_add(em, dc_rat_mul(dc_rat_sub(mu[U[i]], nu[U[i]], ovf), F[U[i]], ovf), ovf); }
    *mo = m;
    return (*ovf || dc_rat_cmp(em, w)) ? -1 : 0;
}
enum { MT_OBS, MT_NOT, MT_MIN, MT_MAX, MT_SUB, MT_NEXT };
typedef struct { int op, a, b, act, obs, oval; DcRat r; } StMtN;
typedef struct {
    const StMod *s; const StMach *M; DcRat g; int n, K, nn, cap, base; int *ovf;
    const int *oc; DcRat (*L)[ST_MAXE][ST_MAXE]; int *memo; StMtN *nd; DcRat *v;
    int ncst; DcRat cr[256]; int cn[256];
} StMt;
#define MTV(t, k, z) ((t)->v[(size_t)(k) * (t)->n + (z)])
static int mt_new(StMt *t, int op, int a, int b, DcRat r, int act, int obs, int oval) {
    if (t->nn >= t->cap || a >= t->nn || b >= t->nn) return -1;
    if (op != MT_OBS && (a < 0 || ((op == MT_MIN || op == MT_MAX) && b < 0))) return -1;
    int k = t->nn, n = t->n, *ovf = t->ovf; StMtN *x = &t->nd[k];
    x->op = op; x->a = a; x->b = b; x->r = r; x->act = act; x->obs = obs; x->oval = oval;
    DcRat one = dc_rat(1, 1, ovf), z0 = dc_rat(0, 1, ovf);
    for (int z = 0; z < n; z++) {
        DcRat w = z0;
        switch (op) {
        case MT_OBS: w = dc_rat(t->s->map[t->M->om[obs]].tab[z] == oval, 1, ovf); break;
        case MT_NOT: w = dc_rat_sub(one, MTV(t, a, z), ovf); break;
        case MT_MIN: w = dc_rat_min(MTV(t, a, z), MTV(t, b, z)); break;
        case MT_MAX: w = dc_rat_max(MTV(t, a, z), MTV(t, b, z)); break;
        case MT_SUB: w = dc_rat_max(z0, dc_rat_sub(MTV(t, a, z), r, ovf)); break;
        case MT_NEXT: { const StKer *K = &t->s->ker[t->M->ak[act]];
            for (int y = 0; y < n; y++) if (!dc_rat_is_zero(K->p[z][y])) w = dc_rat_add(w, dc_rat_mul(K->p[z][y], MTV(t, a, y), ovf), ovf);
            w = dc_rat_mul(t->g, w, ovf); break; }
        }
        MTV(t, k, z) = w;
    }
    t->nn++; return *ovf ? -1 : k;
}
static int mt_const(StMt *t, DcRat r) {   /* constants inside the grammar: 0 = max(0, phi - 1), 1 = 1 - 0, r = max(0, 1 - (1 - r)) */
    for (int i = 0; i < t->ncst; i++) if (!dc_rat_cmp(t->cr[i], r)) return t->cn[i];
    int *ovf = t->ovf, c; DcRat one = dc_rat(1, 1, ovf), z0 = dc_rat(0, 1, ovf);
    if (dc_rat_is_zero(r)) {
        if (t->base < 0 && (t->base = mt_new(t, MT_OBS, -1, -1, z0, 0, 0, t->s->map[t->M->om[0]].tab[0])) < 0) return -1;
        c = mt_new(t, MT_SUB, t->base, -1, one, 0, 0, 0);
    } else if (!dc_rat_cmp(r, one)) c = mt_new(t, MT_NOT, mt_const(t, z0), -1, z0, 0, 0, 0);
    else c = mt_new(t, MT_SUB, mt_const(t, one), -1, dc_rat_sub(one, r, ovf), 0, 0, 0);
    if (c >= 0 && t->ncst < 256) { t->cr[t->ncst] = r; t->cn[t->ncst++] = c; }
    return c;
}
static int mt_shift(StMt *t, int a, DcRat c) {   /* min(1, a + c) for c > 0, max(0, a + c) for c < 0 */
    int *ovf = t->ovf; DcRat z0 = dc_rat(0, 1, ovf);
    if (a < 0 || dc_rat_is_zero(c)) return a;
    if (dc_rat_cmp(c, z0) < 0) return mt_new(t, MT_SUB, a, -1, dc_rat_sub(z0, c, ovf), 0, 0, 0);
    int na = mt_new(t, MT_NOT, a, -1, z0, 0, 0, 0);
    return mt_new(t, MT_NOT, mt_new(t, MT_SUB, na, -1, c, 0, 0, 0), -1, z0, 0, 0, 0);
}
static int mt_clip(StMt *t, int a, DcRat lo, DcRat hi) {
    DcRat z0 = dc_rat(0, 1, t->ovf); int h = mt_const(t, hi), l = mt_const(t, lo);
    return mt_new(t, MT_MAX, l, mt_new(t, MT_MIN, h, a, z0, 0, 0, 0), z0, 0, 0, 0);
}
static int mt_test(StMt *t, int k, int u, int v);
static int mt_lift(StMt *t, int k, const int *U, int m, const DcRat *F) {   /* a test equal to F on U from layer-k tests */
    int outer = -1, *ovf = t->ovf; DcRat z0 = dc_rat(0, 1, ovf);
    for (int i = 0; i < m; i++) {
        int inner = -1;
        for (int j = 0; j < m; j++) {
            int u = U[i], w = U[j], h, c = dc_rat_cmp(F[u], F[w]);
            if (c == 0) h = mt_const(t, F[u]);
            else {
                int up = c > 0, tt = up ? mt_test(t, k, u, w) : mt_test(t, k, w, u), at = up ? w : u;
                if (tt < 0) return -1;
                DcRat lo = up ? F[w] : F[u], hi = up ? F[u] : F[w];
                h = mt_clip(t, mt_shift(t, tt, dc_rat_sub(lo, MTV(t, tt, at), ovf)), lo, hi);
            }
            if (h < 0) return -1;
            inner = inner < 0 ? h : mt_new(t, MT_MIN, inner, h, z0, 0, 0, 0);
            if (inner < 0) return -1;
        }
        outer = outer < 0 ? inner : mt_new(t, MT_MAX, outer, inner, z0, 0, 0, 0);
        if (outer < 0) return -1;
    }
    for (int i = 0; i < m; i++) if (dc_rat_cmp(MTV(t, outer, U[i]), F[U[i]])) return -1;
    return outer;
}
static int mt_test(StMt *t, int k, int u, int v) {   /* a test with value(u) - value(v) = D_k(u, v) */
    int n = t->n, *mm = &t->memo[((size_t)k * n + u) * n + v], *ovf = t->ovf;
    if (*mm != -2) return *mm;
    DcRat z0 = dc_rat(0, 1, ovf), want = t->L[k][u][v]; int r = -1;
    if (t->oc[u] != t->oc[v]) {
        for (int j = 0; j < t->M->nobs && r < 0; j++) { const StMap *O = &t->s->map[t->M->om[j]];
            if (O->tab[u] != O->tab[v]) r = mt_new(t, MT_OBS, -1, -1, z0, 0, j, O->tab[u]); }
    } else if (dc_rat_is_zero(want)) r = mt_const(t, z0);
    else if (k > 0) {
        DcRat (*c)[ST_MAXE] = t->L[k - 1];
        for (int a = 0; a < t->M->nact && r < 0; a++) {
            const StKer *K = &t->s->ker[t->M->ak[a]]; DcRat w;
            if (st_kant(n, K->p[u], K->p[v], c, &w, ovf)) return *mm = -1;
            if (dc_rat_cmp(dc_rat_mul(t->g, w, ovf), want)) continue;
            DcRat F[ST_MAXE]; int U[ST_MAXE], m = 0;
            if (st_kdual(n, K->p[u], K->p[v], c, w, F, U, &m, ovf)) continue;
            int f = mt_lift(t, k - 1, U, m, F); if (f < 0) continue;
            int nx = mt_new(t, MT_NEXT, f, -1, z0, a, 0, 0);
            if (nx >= 0 && !dc_rat_cmp(dc_rat_sub(MTV(t, nx, u), MTV(t, nx, v), ovf), want)) r = nx;
        }
    }
    if (r >= 0 && dc_rat_cmp(dc_rat_sub(MTV(t, r, u), MTV(t, r, v), ovf), want)) r = -1;
    return *mm = r;
}

/* Driver: layers D_0..D_K of the behavioral recurrence (D_K the exact fixed point), then a
 * modal test at layer K for the pair (u, v), serialized as a graph with shared subformulas. */
static Sx *st_modal_witness(const StMod *s, const StMach *M, DcRat g, int u, int v, int *ovf) {
    int n = s->car[M->states].n, oc[ST_MAXE], KM = ST_BEH_ROUNDS + 2, K = 0, ok = 0, cap = 4096;
    st_obsclass(s, M, oc);
    DcRat (*L)[ST_MAXE][ST_MAXE] = malloc(sizeof(*L) * (size_t)KM);
    int *memo = NULL; StMtN *nd = malloc(sizeof(StMtN) * (size_t)cap); DcRat *val = malloc(sizeof(DcRat) * (size_t)cap * (size_t)n);
    char *keep = calloc((size_t)cap, 1); int *ren = malloc(sizeof(int) * (size_t)cap);
    Sx *res = NULL;
    if (!L || !nd || !val || !keep || !ren) goto out;
    for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) L[0][x][y] = dc_rat(oc[x] != oc[y], 1, ovf);
    for (;;) { int ch = 0;
        if (K + 1 >= KM || st_bstep(s, M, oc, g, L[K], L[K + 1], &ch, ovf)) goto out;
        if (!ch) { ok = 1; break; }
        K++; }
    memo = malloc(sizeof(int) * (size_t)(K + 1) * (size_t)n * (size_t)n); if (!memo) goto out;
    for (size_t i = 0; i < (size_t)(K + 1) * n * n; i++) memo[i] = -2;
    StMt t; memset(&t, 0, sizeof t);
    t.s = s; t.M = M; t.g = g; t.n = n; t.K = K; t.cap = cap; t.base = -1; t.ovf = ovf; t.oc = oc; t.L = L; t.memo = memo; t.nd = nd; t.v = val;
    int root = ok ? mt_test(&t, K, u, v) : -1;
    if (root < 0 || *ovf) goto out;
    keep[root] = 1;
    for (int k = root; k >= 0; k--) if (keep[k]) { if (nd[k].a >= 0 && nd[k].op != MT_OBS) keep[nd[k].a] = 1; if (nd[k].op == MT_MIN || nd[k].op == MT_MAX) keep[nd[k].b] = 1; }
    int id = 0; for (int k = 0; k <= root; k++) ren[k] = keep[k] ? id++ : -1;
    Sx *fm = dc_form("Formula", dc_form("Root", dc_int(ren[root]), NULL), NULL);
    for (int k = 0; k <= root; k++) if (keep[k]) {
        StMtN *x = &nd[k]; Sx *e = NULL;
        switch (x->op) {
        case MT_OBS: { const StMap *O = &s->map[M->om[x->obs]];
            e = dc_form("Indicator", dc_sym(M->ol[x->obs]), dc_sym(s->car[O->to].el[x->oval]), NULL); break; }
        case MT_NOT: e = dc_form("Not", dc_int(ren[x->a]), NULL); break;
        case MT_MIN: e = dc_form("Min", dc_int(ren[x->a]), dc_int(ren[x->b]), NULL); break;
        case MT_MAX: e = dc_form("Max", dc_int(ren[x->a]), dc_int(ren[x->b]), NULL); break;
        case MT_SUB: e = dc_form("Sub", dc_int(ren[x->a]), st_rsx(x->r), NULL); break;
        case MT_NEXT: e = dc_form("Next", dc_sym(M->al[x->act]), dc_int(ren[x->a]), st_rsx(g), NULL); break;
        }
        sx_push(fm, dc_form("Node", dc_int(ren[k]), e, NULL));
    }
    const StCar *C = &s->car[M->states];
    res = dc_form("ModalTestWitness", dc_form("Pair", dc_sym(C->el[u]), dc_sym(C->el[v]), NULL), fm,
        dc_form("Left", st_rsx(MTV(&t, root, u)), NULL), dc_form("Right", st_rsx(MTV(&t, root, v)), NULL), dc_form("Layers", dc_int(K), NULL), NULL);
out:
    free(L); free(memo); free(nd); free(val); free(keep); free(ren);
    return res;
}


/* review 1 F2: Prefixpoint upper certificate (spec certificate table): the kernel D (every nonzero
 * entry, ordered pairs) and, for every pair x < y in one observation class with D(x,y) > 0 and every
 * action, one coupling theta of the two successor laws optimal for cost D.  Replay checks the
 * marginals of theta and D >= max(d0, gamma * E_theta D).  Built and self-checked here. */
static Sx *st_prefix_cert(const StMod *s, const StMach *M, DcRat g, DcRat (*d)[ST_MAXE], const char *kind, int *ovf) {
    int n = s->car[M->states].n, oc[ST_MAXE]; const StCar *C = &s->car[M->states];
    st_obsclass(s, M, oc);
    Sx *D = dc_form("Kernel", NULL), *cp = dc_form("Couplings", NULL);
    for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) if (!dc_rat_is_zero(d[x][y]))
        sx_push(D, dc_form("Entry", dc_sym(C->el[x]), dc_sym(C->el[y]), st_rsx(d[x][y]), NULL));
    for (int x = 0; x < n; x++) for (int y = x + 1; y < n; y++) {
        if (oc[x] != oc[y]) continue;   /* D(x,y) = 0 needs its zero-cost coupling too */
        for (int a = 0; a < M->nact; a++) {
            const StKer *K = &s->ker[M->ak[a]]; DcRat w;
            if (st_kant(n, K->p[x], K->p[y], d, &w, ovf)) { sx_free(D); sx_free(cp); return NULL; }
            if (dc_rat_cmp(dc_rat_mul(g, w, ovf), d[x][y]) > 0) { sx_free(D); sx_free(cp); return NULL; }   /* not a prefixpoint */
            Sx *c = dc_form("Coupling", dc_sym(C->el[x]), dc_sym(C->el[y]), dc_sym(M->al[a]), NULL);
            for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (!dc_rat_is_zero(g_kf[i][j]))
                sx_push(c, dc_form("Mass", dc_sym(C->el[i]), dc_sym(C->el[j]), st_rsx(g_kf[i][j]), NULL));
            sx_push(cp, c);
        }
    }
    return dc_form("Certificate", dc_form("Kind", dc_sym(kind), NULL), dc_form("Discount", st_rsx(g), NULL), D, cp, NULL);
}


/* review 1 F2: DualPostfixpoint lower certificate (spec certificate table): the kernel D and, for every
 * same-class pair x < y with D(x,y) > 0 (D above d0), an action attaining D(x,y) = gamma * W_D and
 * Kantorovich dual potentials f (on the support of the x successor law) and g (on the y support) with
 * f(u) - g(v) <= D(u,v) and E f - E g = W_D.  Built from st_kdual and self-checked here. */
static Sx *st_dual_cert(const StMod *s, const StMach *M, DcRat g, DcRat (*d)[ST_MAXE], int iters, int *ovf) {
    int n = s->car[M->states].n, oc[ST_MAXE]; const StCar *C = &s->car[M->states];
    st_obsclass(s, M, oc);
    Sx *D = dc_form("Kernel", NULL), *du = dc_form("Duals", NULL);
    for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) if (!dc_rat_is_zero(d[x][y]))
        sx_push(D, dc_form("Entry", dc_sym(C->el[x]), dc_sym(C->el[y]), st_rsx(d[x][y]), NULL));
    for (int x = 0; x < n; x++) for (int y = x + 1; y < n; y++) {
        if (oc[x] != oc[y] || dc_rat_is_zero(d[x][y])) continue;
        Sx *got = NULL;
        for (int a = 0; a < M->nact && !got; a++) {
            const StKer *K = &s->ker[M->ak[a]]; DcRat w, F[ST_MAXE]; int U[ST_MAXE], m = 0, ok = 1;
            if (st_kant(n, K->p[x], K->p[y], d, &w, ovf)) goto fail;
            if (dc_rat_cmp(dc_rat_mul(g, w, ovf), d[x][y])) continue;
            if (st_kdual(n, K->p[x], K->p[y], d, w, F, U, &m, ovf)) continue;
            for (int i = 0; i < m && ok; i++) for (int j = 0; j < m && ok; j++)
                if (dc_rat_cmp(dc_rat_sub(F[U[i]], F[U[j]], ovf), d[U[i]][U[j]]) > 0) ok = 0;
            if (!ok) continue;
            Sx *f = dc_form("F", NULL), *gg = dc_form("G", NULL);
            for (int i = 0; i < m; i++) {
                if (!dc_rat_is_zero(K->p[x][U[i]])) sx_push(f, dc_form("Pot", dc_sym(C->el[U[i]]), st_rsx(F[U[i]]), NULL));
                if (!dc_rat_is_zero(K->p[y][U[i]])) sx_push(gg, dc_form("Pot", dc_sym(C->el[U[i]]), st_rsx(F[U[i]]), NULL));
            }
            got = dc_form("Dual", dc_sym(C->el[x]), dc_sym(C->el[y]), dc_sym(M->al[a]), f, gg, NULL);
        }
        if (!got) goto fail;
        sx_push(du, got);
    }
    if (*ovf) goto fail;
    return dc_form("Certificate", dc_form("Kind", dc_sym("DualPostfixpoint"), NULL), dc_form("Discount", st_rsx(g), NULL), D, du,
                   dc_form("PolicyIterations", dc_int(iters), NULL), NULL);
fail:
    sx_free(D); sx_free(du); return NULL;
}

/* Candidate d* solves d = gamma * (coupling at d) d exactly for the couplings optimal at the
 * current d (policy iteration); it is accepted only if one exact Bellman step (st_kant, whose
 * optimum is the dual post-fixpoint check) maps d* to itself and 0 <= d* <= 1.
 * Returns 0 accepted (d holds d*), 1 not found, -1 overflow. */
#define ST_FPK 80
static int st_fixpoint(const StMod *s, const StMach *M, const int *oc, DcRat gamma, DcRat (*d)[ST_MAXE], int *iters, int *ovf) {
    int n = s->car[M->states].n, id[ST_MAXE][ST_MAXE], k = 0, px[ST_FPK], py[ST_FPK], ch;
    static DcRat A[ST_FPK][ST_FPK + 1], T[ST_MAXE][ST_MAXE], bp[ST_MAXE][ST_MAXE];
    for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) id[x][y] = -1;
    for (int x = 0; x < n; x++) for (int y = x + 1; y < n; y++) if (oc[x] == oc[y]) {
        if (k == ST_FPK) return 1;
        px[k] = x; py[k] = y; id[x][y] = id[y][x] = k++; }
    DcRat z = dc_rat(0, 1, ovf), one = dc_rat(1, 1, ovf);
    for (int it = 0; it < 30; it++) {
        *iters = it + 1;
        for (int i = 0; i < k; i++) {
            int x = px[i], y = py[i], ba = -1; DcRat best = z, w;
            for (int a = 0; a < M->nact; a++) {
                if (st_kant(n, s->ker[M->ak[a]].p[x], s->ker[M->ak[a]].p[y], d, &w, ovf)) return -1;
                if (ba < 0 || dc_rat_cmp(w, best) > 0) { best = w; ba = a; memcpy(bp, g_kf, sizeof bp); }
            }
            for (int j = 0; j <= k; j++) A[i][j] = z;
            A[i][i] = one;
            for (int u = 0; u < n; u++) for (int v = 0; v < n; v++) if (!dc_rat_is_zero(bp[u][v])) {
                DcRat c = dc_rat_mul(gamma, bp[u][v], ovf);
                if (id[u][v] >= 0) A[i][id[u][v]] = dc_rat_sub(A[i][id[u][v]], c, ovf);
                else if (oc[u] != oc[v]) A[i][k] = dc_rat_add(A[i][k], c, ovf);
            }
        }
        for (int c = 0; c < k; c++) {
            int p = -1;
            for (int r = c; r < k && p < 0; r++) if (!dc_rat_is_zero(A[r][c])) p = r;
            if (p < 0) return 1;
            if (p != c) for (int j = 0; j <= k; j++) { DcRat t = A[c][j]; A[c][j] = A[p][j]; A[p][j] = t; }
            for (int r = 0; r < k; r++) if (r != c && !dc_rat_is_zero(A[r][c])) {
                DcRat f = dc_rat_div(A[r][c], A[c][c], ovf);
                for (int j = c; j <= k; j++) A[r][j] = dc_rat_sub(A[r][j], dc_rat_mul(f, A[c][j], ovf), ovf);
            }
            if (*ovf) return -1;
        }
        for (int i = 0; i < k; i++) {
            DcRat v = dc_rat_div(A[i][k], A[i][i], ovf);
            if (dc_rat_cmp(v, z) < 0 || dc_rat_cmp(v, one) > 0) return 1;
            d[px[i]][py[i]] = d[py[i]][px[i]] = v;
        }
        if (st_bstep(s, M, oc, gamma, d, T, &ch, ovf)) return -1;
        if (!ch) return 0;
    }
    return 1;
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
    /* review 1 F1 (invariant 16): the scope is read from the request, as ops_graded.c does */
    DcScope sc = { "M4-Stochastic", -1, "", NULL };
    const Sx *hz = st_opt(q, "Horizon"), *dsc = st_opt(q, "Discount"), *po = st_opt(q, "Policies");
    if (hz && hz->items[1]->kind == SX_LIST && sx_head_is(hz->items[1], "Steps") && hz->items[1]->n == 2) {
        DcRat h; if (!dc_sx_rat(hz->items[1]->items[1], &h) && h.d == 1 && h.n >= 0 && h.n <= 4096) sc.horizon = (int)h.n; }
    if (dsc) { DcRat g; if (!dc_sx_rat(dsc->items[1], &g)) dc_rat_str(g, sc.discount, sizeof sc.discount); }
    if (po && po->items[1]->kind == SX_SYM) sc.policy = po->items[1]->text;
    else if (q && (sx_head_is(q, "MeasureTrace") || sx_head_is(q, "CheckTrace"))) sc.policy = "Words";
    Sx *subj = dc_form("Subject", dc_form(subjk, dc_sym(subjn), NULL), NULL);
    Sx *res = dc_envelope_scoped(m, v, g_st_rep, dc_claim_of(q, "Literal"), subj, val, ev, why, &sc);
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
    if (!strcmp(head, "MeasureTrace") || (!strcmp(head, "CheckTrace") && st_opt(q, "Horizon"))) {   /* O01-O04 handler */
        int pi = st_repi(&S, a1); if (pi < 0) return dc_invalid(m, "%s: %s names no representation", head, a1 ? a1 : "?");
        const StRepr *P = &S.rep[pi]; const StMach *M = &S.mach[P->mach]; const StCar *C = &S.car[M->states]; const StMap *E = &S.map[P->enc];
        if (E->to != M->states) return dc_invalid(m, "%s: representation %s encodes into %s, not into the machine states", head, a1, S.car[E->to].name);
        const Sx *hz = st_opt(q, "Horizon"), *po = st_opt(q, "Policies"), *wi = st_opt(q, "Within"), *sp = hz ? hz->items[1] : NULL;
        DcRat hv, bound = dc_rat(0, 1, &ovf);
        if (!sx_head_is(sp, "Steps") || sp->n != 2 || st_rat(sp->items[1], &hv) || hv.d != 1 || hv.n < 0 || hv.n > 12)
            return dc_invalid(m, "%s: expected (Horizon (Steps h)) with 0 <= h <= 12", head);
        int pol = po != NULL, chk = !strcmp(head, "CheckTrace");
        if (po && !sx_is_sym(po->items[1], "ObservationBased")) return dc_invalid(m, "%s: (Policies P) supports ObservationBased only", head);
        if (chk != (wi != NULL) || (wi && (st_rat(wi->items[1], &bound) || bound.n < 0)))
            return dc_invalid(m, "%s: %s", head, chk ? "expected (Within b) with b >= 0" : "takes no (Within b)");
        for (size_t i = 2; i < q->n; i++)
            if (!sx_head_is(q->items[i], "Horizon") && !sx_head_is(q->items[i], "Policies") && !sx_head_is(q->items[i], "Within")) return dc_invalid(m, "%s: unexpected option", head);
        int n = C->n, h = (int)hv.n, oc[ST_MAXE], noc = 0, rep[ST_MAXE];
        for (int x = 0; x < n; x++) { oc[x] = -1;
            for (int y = 0; y < x && oc[x] < 0; y++) { int same = 1;
                for (int j = 0; j < M->nobs; j++) if (S.map[M->om[j]].tab[x] != S.map[M->om[j]].tab[y]) same = 0;
                if (same) oc[x] = oc[y]; }
            if (oc[x] < 0) { rep[noc] = x; oc[x] = noc++; } }
        for (int c = 0; c < noc; c++) {
            if (M->nobs == 1) snprintf(g_olab[c], ST_NM, "%s", S.car[S.map[M->om[0]].to].el[S.map[M->om[0]].tab[rep[c]]]);
            else snprintf(g_olab[c], ST_NM, "c%d", c); }
        long nw = 1;
        for (int i = 0; i < h && !pol; i++) { nw *= M->nact; if (nw > 100000) return dc_unsupported(m, "%s: more than 100000 words of length %d", head, h); }
        StTv best; best.v = best.pe = best.qe = dc_rat(0, 1, &ovf); int bx = -1, bw[16] = {0}; Sx *btree = NULL; unsigned long long bmask = 0;
        for (int x = 0; x < n; x++) {
            int y = E->tab[x]; if (y == x) continue;
            DcRat mu[ST_MAXE], nu[ST_MAXE];
            for (int z = 0; z < n; z++) { mu[z] = dc_rat(z == y, 1, &ovf); nu[z] = dc_rat(z == x, 1, &ovf); }   /* left = encoded image */
            if (oc[x] != oc[y]) {   /* separated by the initial report */
                if (bx < 0 || dc_rat_cmp(dc_rat(1, 1, &ovf), best.v) > 0) { best.v = best.pe = dc_rat(1, 1, &ovf); best.qe = dc_rat(0, 1, &ovf);
                    bx = x; memset(bw, 0, sizeof bw); if (btree) sx_free(btree); btree = NULL; bmask = 1ULL << oc[y]; }
                continue;
            }
            int w[16] = {0};
            for (long k = 0; k < (pol ? 1 : nw); k++) {
                long t = k; for (int i = 0; i < h; i++) { w[i] = (int)(t % M->nact); t /= M->nact; }
                Sx *tr = NULL; g_tvlast = 0; g_tvnodes = 0;
                StTv r = st_tvrec(&S, M, oc, noc, mu, nu, h, pol ? NULL : w, 0, oc[x], pol ? &tr : NULL, &ovf);
                if (ovf) { if (tr) sx_free(tr); if (btree) sx_free(btree); return dc_unsupported(m, "%s: rational overflow (int64) or search limit", head); }
                if (bx < 0 || dc_rat_cmp(r.v, best.v) > 0) { best = r; bx = x; memcpy(bw, w, sizeof bw); if (btree) sx_free(btree); btree = tr; bmask = g_tvlast; }
                else if (tr) sx_free(tr);
            }
        }
        int holds = !chk || dc_rat_cmp(best.v, bound) <= 0;
        Sx *val = chk ? dc_form("Value", dc_form("WithinBound", dc_sym(holds ? "True" : "False"), NULL), dc_form("TraceDefect", st_rsx(best.v), NULL), NULL)
                      : dc_form("Value", dc_form("TraceDefect", st_rsx(best.v), NULL), NULL);
        sx_push(val, dc_form("Horizon", dc_form("Steps", dc_int(h), NULL), NULL));
        sx_push(val, dc_form("Policies", dc_sym(pol ? "ObservationBased" : "FixedWords"), NULL));
        Sx *cert = dc_form("Certificate", dc_form("Kind", dc_sym(pol ? "PolicyTreeSearch" : "ExhaustiveWords"), NULL), NULL);
        if (bx >= 0 && !dc_rat_is_zero(best.v)) {
            Sx *lr = dc_form("LastReport", NULL);
            for (int c = 0; c < noc && c < 64; c++) if (bmask >> c & 1) sx_push(lr, dc_sym(g_olab[c]));
            Sx *pair = dc_form("Pair", dc_sym(C->el[E->tab[bx]]), dc_sym(C->el[bx]), NULL), *wit;
            Sx *probs = dc_form("Probabilities", st_rsx(best.pe), st_rsx(best.qe), NULL), *evt = dc_form("Event", lr, NULL);
            if (pol) { wit = dc_form("PolicyTreeWitness", pair, btree ? btree : dc_form("Stop", NULL), evt, probs, NULL); btree = NULL; }
            else { Sx *wd = dc_form("Word", NULL); for (int i = 0; i < h; i++) sx_push(wd, dc_sym(M->al[bw[i]]));
                wit = dc_form("TraceEventWitness", pair, wd, evt, probs, NULL); }
            sx_push(cert, wit);
        }
        if (btree) sx_free(btree);
        if (ovf) { sx_free(val); sx_free(cert); return dc_unsupported(m, "%s: rational overflow (int64)", head); }
        return st_env(m, holds ? VERDICT_HOLDS : VERDICT_FAILS, q, "Representation", a1, val, dc_form("Evidence", cert, NULL), NULL);
    }
    if ((!strcmp(head, "MeasureBehavioral") || !strcmp(head, "CheckBehavioral")) && st_repi(&S, a1) >= 0) {   /* U01-U04 handler */
        const StRepr *P = &S.rep[st_repi(&S, a1)]; const StMach *M = &S.mach[P->mach]; const StCar *C = &S.car[M->states]; const StMap *E = &S.map[P->enc];
        const Sx *hz = st_opt(q, "Horizon"), *wi = st_opt(q, "Within"), *dsc = st_opt(q, "Discount");
        int handle = E->to == M->states, chk = !strcmp(head, "CheckBehavioral"), h = -1;
        for (size_t i = 2; i < q->n; i++) if (!sx_head_is(q->items[i], "Horizon") && !sx_head_is(q->items[i], "Within") && !sx_head_is(q->items[i], "Discount")) handle = 0;
        DcRat g = dc_rat(1, 1, &ovf), b = dc_rat(0, 1, &ovf);
        if (handle && dsc && (dc_sx_rat(dsc->items[1], &g) || g.n < 0 || dc_rat_cmp(g, dc_rat(1, 1, &ovf)) > 0)) handle = 0;   /* the S04 path answers InvalidInput */
        if (handle && hz) { const Sx *sp = hz->items[1]; DcRat hv;
            if (!sx_head_is(sp, "Steps") || sp->n != 2 || st_rat(sp->items[1], &hv) || hv.d != 1 || hv.n < 0 || hv.n > 40)
                return dc_invalid(m, "%s: expected (Horizon (Steps h)) with 0 <= h <= 40", head);
            h = (int)hv.n; }
        if (handle && wi && (!chk || st_rat(wi->items[1], &b) || b.n < 0)) return dc_invalid(m, "%s: (Within b) needs CheckBehavioral and b >= 0", head);
        if (handle && !hz && !wi) { static DcRat d0[ST_MAXE][ST_MAXE]; int o2 = 0; if (!st_behav(&S, M, g, d0, &o2)) handle = 0; }   /* S03/S04 path */
        if (handle) {
            int n = C->n, oc[ST_MAXE], wx = -1, ch = 1, layers = 0, lim = hz ? h : (wi ? 40 : 20);
            static DcRat d[ST_MAXE][ST_MAXE], nd[ST_MAXE][ST_MAXE];
            for (int x = 0; x < n; x++) { oc[x] = -1;
                for (int y = 0; y < x && oc[x] < 0; y++) { int same = 1;
                    for (int j = 0; j < M->nobs; j++) if (S.map[M->om[j]].tab[x] != S.map[M->om[j]].tab[y]) same = 0;
                    if (same) oc[x] = oc[y]; }
                if (oc[x] < 0) oc[x] = x; }
            for (int x = 0; x < n; x++) for (int y = 0; y < n; y++) d[x][y] = dc_rat(oc[x] != oc[y], 1, &ovf);
            DcRat def = st_defect(C, E, d, &wx, &ovf);
            while (layers < lim && ch && !(wi && dc_rat_cmp(def, b) > 0)) {
                if (st_bstep(&S, M, oc, g, d, nd, &ch, &ovf)) return dc_unsupported(m, "%s: rational overflow (int64) or transport limit", head);
                memcpy(d, nd, sizeof d); layers++; def = st_defect(C, E, d, &wx, &ovf);
            }
            if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
            Sx *pair = wx >= 0 ? dc_form("Pair", dc_sym(C->el[wx]), dc_sym(C->el[E->tab[wx]]), NULL) : NULL;
            if (hz) {
                Sx *val = dc_form("Value", dc_form("BehavioralDefect", st_rsx(def), NULL), dc_form("Horizon", dc_form("Steps", dc_int(h), NULL), NULL), dc_form("Discount", st_rsx(g), NULL), NULL);
                Sx *cert = dc_form("Certificate", dc_form("Kind", dc_sym("LayeredPrefixpoint"), NULL), dc_form("Layers", dc_int(layers), NULL), NULL);
                if (pair) sx_push(cert, dc_form("DepthTest", pair, dc_form("Depth", dc_int(layers), NULL), dc_form("Separation", st_rsx(def), NULL), NULL));
                return st_env(m, VERDICT_HOLDS, q, "Representation", a1, val, dc_form("Evidence", cert, NULL), NULL);
            }
            if (wi && (dc_rat_cmp(def, b) > 0 || !ch)) {
                int bad = dc_rat_cmp(def, b) > 0;
                Sx *val = dc_form("Value", dc_form("WithinBound", dc_sym(bad ? "False" : "True"), NULL), dc_form("BehavioralDefect", st_rsx(def), NULL), NULL);
                Sx *cert = dc_form("Certificate", dc_form("Kind", dc_sym(bad ? "DepthTestWitness" : "ExactFixpoint"), NULL), NULL);
                if (bad && pair) { sx_push(cert, dc_form("DepthTest", pair, dc_form("Depth", dc_int(layers), NULL), dc_form("Separation", st_rsx(def), NULL), NULL)); pair = NULL; }
                if (pair) sx_free(pair);
                return st_env(m, bad ? VERDICT_FAILS : VERDICT_HOLDS, q, "Representation", a1, val, dc_form("Evidence", cert, NULL), NULL);
            }
            if (pair) sx_free(pair);
            DcRat lo = def; int it = 0, frc = 1;
            if (dc_rat_cmp(g, dc_rat(1, 1, &ovf)) < 0) frc = st_fixpoint(&S, M, oc, g, d, &it, &ovf);
            if (frc < 0 || ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
            if (frc == 0) {
                DcRat dv = st_defect(C, E, d, &wx, &ovf); int holds = !wi || dc_rat_cmp(dv, b) <= 0;
                Sx *val = dc_form("Value", dc_form("BehavioralDefect", st_rsx(dv), NULL), dc_form("Discount", st_rsx(g), NULL), NULL);
                if (wi) sx_push(val, dc_form("WithinBound", dc_sym(holds ? "True" : "False"), NULL));
                /* review 1 F2 (invariant 18): upper Prefixpoint and lower DualPostfixpoint, both carrying their data */
                Sx *up = st_prefix_cert(&S, M, g, d, "Prefixpoint", &ovf), *lo2 = up ? st_dual_cert(&S, M, g, d, it, &ovf) : NULL;
                if (!up || !lo2 || ovf) { if (up) sx_free(up); return dc_unsupported(m, "%s: no replayable prefixpoint/dual certificate pair", head); }
                Sx *ev = dc_form("Evidence", up, lo2, NULL);
                return st_env(m, holds ? VERDICT_HOLDS : VERDICT_FAILS, q, "Representation", a1, val, ev, NULL);
            }
            Sx *val = dc_form("Value", dc_form("BehavioralInterval", dc_form("Lower", st_rsx(lo), NULL), dc_form("Upper", dc_int(1), NULL), NULL),
                dc_form("Layers", dc_int(layers), NULL), dc_form("Discount", st_rsx(g), NULL), dc_form("Precision", dc_int(0), NULL), NULL);
            Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("LayeredPrefixpoint"), NULL), dc_form("Closed", dc_sym("False"), NULL), NULL), NULL);
            g_st_rep = 0; Sx *res = st_env(m, VERDICT_HOLDS, q, "Representation", a1, val, ev, "supremum not attained by any finite layer; interval does not close at Precision 0"); g_st_rep = 1;
            return res;
        }
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
        /* review 1 F2 (invariant 18): an upper certificate (Prefixpoint: D with couplings) and, when the
         * defect is positive, a lower certificate (Test: a Definition 4.9 modal test) that meet at the value */
        Sx *up = st_prefix_cert(&S, M, g, d, "Prefixpoint", &ovf);
        if (!up || ovf) return dc_unsupported(m, "%s: no prefixpoint certificate could be built", head);
        Sx *ev = dc_form("Evidence", up, NULL);
        if (wx >= 0) {
            int y = E->tab[wx];
            Sx *mw = st_modal_witness(&S, M, g, wx, y, &ovf);   /* a Definition 4.9 test, replayable */
            if (!mw || ovf) return dc_unsupported(m, "%s: no modal test witness could be built", head);
            sx_push(ev, dc_form("Certificate", dc_form("Kind", dc_sym("Test"), NULL), mw, NULL));
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
        /* review 1 F4 (registry Output rule, as ops_kernels.c / ops_refine.c): Output projects only from Checked results.
         * An input arrow that fails its own check (neg 12: a Positive arrow whose rows do not sum to 1) makes Then InvalidInput. */
        { char wa[200] = "", wb[200] = "";
          if (!st_check_lin(&S, A, wa, sizeof wa, &ovf, 0)) return dc_invalid(m, "Then: Output projects only from Checked results (Derive %s is Refuted: %s)", dn[0], wa);
          if (!st_check_lin(&S, Bk, wb, sizeof wb, &ovf, 0)) return dc_invalid(m, "Then: Output projects only from Checked results (Derive %s is Refuted: %s)", dn[1], wb); }
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
    /* ---- R01-R06 handlers (Use Decisions) ---- */
    if (!strcmp(head, "CheckEqual") || !strcmp(head, "AverageModel")) {   /* R01, R02 */
        int one = !strcmp(head, "AverageModel"), ns = one ? 1 : 2;
        const Sx *sides[2] = { one ? q : (q->n == 3 ? q->items[1] : NULL), !one && q->n == 3 ? q->items[2] : NULL };
        static StDM DD[2]; static DcRat AV[2][ST_MAXE][ST_MAXE]; DcRat mu[ST_MAXE]; char why[200] = "";
        for (int k = 0; k < ns; k++) {
            const Sx *e = sides[k], *u = st_opt(e, "Under");
            if (!sx_head_is(e, "AverageModel") || e->n != 3) return dc_invalid(m, "%s: expected (AverageModel D (Under P))", head);
            if (st_dm(&S, m->source, st_name(e, 1), &DD[k], why, sizeof why, &ovf)) return ovf ? dc_unsupported(m, "%s: rational overflow (int64)", head) : dc_invalid(m, "%s: %s", head, why);
            if (!u || st_measure(&S, m->source, st_name(u, 1), DD[k].sc, mu, &ovf)) return dc_invalid(m, "%s: (Under P) must name a probability Measure on the states of %s", head, st_name(e, 1));
            st_avg(&S, &DD[k], mu, AV[k], &ovf);
        }
        if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
        if (one) {
            Sx *val = dc_form("Value", st_avg_sx(&S, &DD[0], AV[0], &ovf), NULL);
            Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("PriorAverage"), NULL), dc_form("Prior", dc_sym(st_name(st_opt(q, "Under"), 1)), NULL), NULL), NULL);
            return st_env(m, VERDICT_HOLDS, q, "DecisionModel", st_name(q, 1), val, ev, NULL);
        }
        int eq = DD[0].ac == DD[1].ac && DD[0].tc == DD[1].tc, wa = -1;
        for (int a = 0; eq && a < S.car[DD[0].ac].n; a++) for (int t = 0; t < S.car[DD[0].tc].n; t++) if (dc_rat_cmp(AV[0][a][t], AV[1][a][t])) { eq = 0; wa = a; break; }
        Sx *val = dc_form("Value", dc_form("Equal", dc_sym(eq ? "True" : "False"), NULL), st_avg_sx(&S, &DD[0], AV[0], &ovf), st_avg_sx(&S, &DD[1], AV[1], &ovf), NULL);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym(eq ? "ExactLawEquality" : "LawDifference"), NULL), NULL), NULL);
        if (wa >= 0) sx_push(ev->items[1], dc_form("Action", dc_sym(S.car[DD[0].ac].el[wa]), NULL));
        return st_env(m, eq ? VERDICT_HOLDS : VERDICT_FAILS, q, "DecisionModel", st_name(sides[0], 1), val, ev, NULL);
    }
    if (!strcmp(head, "InduceExact")) {   /* R03 */
        int pi = st_repi(&S, a1); if (pi < 0) return dc_invalid(m, "%s: %s names no representation", head, a1 ? a1 : "?");
        const StRepr *P = &S.rep[pi]; const StMach *M = &S.mach[P->mach]; const StCar *C = &S.car[M->states];
        int n = C->n, blk[ST_MAXE], nb = st_encclass(&S.map[P->enc], n, blk), wx = -1, wy = -1, wj = -1, rounds;
        for (int j = 0; j < M->nobs && wj < 0; j++) for (int x = 0; x < n && wj < 0; x++) for (int y = x + 1; y < n && wj < 0; y++)
            if (blk[x] == blk[y] && S.map[M->om[j]].tab[x] != S.map[M->om[j]].tab[y]) { wx = x; wy = y; wj = j; }
        int b2[ST_MAXE]; memcpy(b2, blk, sizeof b2); int nb2 = wj < 0 ? st_refine(&S, M, b2, nb, &rounds, &ovf) : nb;
        if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
        int ok = wj < 0 && nb2 == nb;
        Sx *val = dc_form("Value", dc_form("Exact", dc_sym(ok ? "True" : "False"), NULL), NULL), *ev;
        if (wj >= 0) ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("ObservationWitness"), NULL),
            dc_form("Pair", dc_sym(C->el[wx]), dc_sym(C->el[wy]), NULL), dc_form("Observation", dc_sym(M->ol[wj]), NULL), NULL), NULL);
        else ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym(ok ? "EncodingLumpable" : "LumpingSplit"), NULL), dc_form("Classes", dc_int(nb), dc_int(nb2), NULL), NULL), NULL);
        return st_env(m, ok ? VERDICT_HOLDS : VERDICT_FAILS, q, "Representation", a1, val, ev, NULL);
    }
    if (!strcmp(head, "OptimizePolicy") || !strcmp(head, "EvaluatePolicy")) {   /* R04, R05, R06 */
        static StDM D; DcRat mu[ST_MAXE]; char why[200] = ""; const Sx *u = st_opt(q, "Under");
        if (st_dm(&S, m->source, a1, &D, why, sizeof why, &ovf)) return ovf ? dc_unsupported(m, "%s: rational overflow (int64)", head) : dc_invalid(m, "%s: %s", head, why);
        if (!u || st_measure(&S, m->source, st_name(u, 1), D.sc, mu, &ovf)) return dc_invalid(m, "%s: (Under P) must name a probability Measure on the states of %s", head, a1);
        const StCar *SC = &S.car[D.sc], *AC = &S.car[D.ac]; int n = SC->n;
        DcRat base = dc_rat(0, 1, &ovf); int ba = 0;   /* uninformed optimum */
        for (int a = 0; a < AC->n; a++) { DcRat v = dc_rat(0, 1, &ovf);
            for (int x = 0; x < n; x++) v = dc_rat_add(v, dc_rat_mul(mu[x], D.er[x][a], &ovf), &ovf);
            if (a == 0 || dc_rat_cmp(v, base) > 0) { base = v; ba = a; } }
        (void)ba;
        if (!strcmp(head, "OptimizePolicy")) {
            int blk[ST_MAXE], nb = n; const Sx *th = st_opt(q, "Through");
            for (int x = 0; x < n; x++) blk[x] = x;
            if (th) { int pi = st_repi(&S, st_name(th, 1));
                if (pi < 0 || S.mach[S.rep[pi].mach].states != D.sc) return dc_invalid(m, "%s: (Through R) must name a representation over the states of %s", head, a1);
                nb = st_encclass(&S.map[S.rep[pi].enc], n, blk); }
            DcRat tot = dc_rat(0, 1, &ovf); int pol[ST_MAXE];
            for (int b = 0; b < nb; b++) { DcRat best = dc_rat(0, 1, &ovf); pol[b] = -1;
                for (int a = 0; a < AC->n; a++) { DcRat v = dc_rat(0, 1, &ovf);
                    for (int x = 0; x < n; x++) if (blk[x] == b) v = dc_rat_add(v, dc_rat_mul(mu[x], D.er[x][a], &ovf), &ovf);
                    if (pol[b] < 0 || dc_rat_cmp(v, best) > 0) { best = v; pol[b] = a; } }
                tot = dc_rat_add(tot, best, &ovf); }
            if (ovf) return dc_unsupported(m, "%s: rational overflow (int64)", head);
            Sx *pl = dc_form("Policy", NULL);
            for (int x = 0; x < n; x++) sx_push(pl, dc_form(SC->el[x], dc_sym(AC->el[pol[blk[x]]]), NULL));
            Sx *val = dc_form("Value", dc_form("Optimum", st_rsx(tot), NULL), pl, NULL);
            Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("ExhaustiveClassPolicy"), NULL), dc_form("Classes", dc_int(nb), NULL), NULL), NULL);
            return st_env(m, VERDICT_HOLDS, q, "DecisionModel", a1, val, ev, NULL);
        }
        const Sx *wf = st_opt(q, "With"), *om = wf ? st_decl(m->source, "ObservationMethod", st_name(wf, 1)) : NULL;
        int ki = om ? st_keri(&S, st_name(st_field(om, "Channel"), 1)) : -1; DcRat cost;
        const Sx *cf = om ? st_field(om, "Cost") : NULL;
        if (ki < 0 || S.ker[ki].from != D.sc || !cf || cf->n != 2 || st_rat(cf->items[1], &cost) || cost.n < 0)
            return dc_invalid(m, "%s: (With O) must name an ObservationMethod with (Channel K) on the states of %s and (Cost c >= 0)", head, a1);
        const StKer *K = &S.ker[ki]; const StCar *RC = &S.car[K->to]; DcRat gross = dc_rat(0, 1, &ovf); Sx *pl = dc_form("Policy", NULL);
        for (int r = 0; r < RC->n; r++) { DcRat best = dc_rat(0, 1, &ovf); int bp = -1;
            for (int a = 0; a < AC->n; a++) { DcRat v = dc_rat(0, 1, &ovf);
                for (int x = 0; x < n; x++) v = dc_rat_add(v, dc_rat_mul(dc_rat_mul(mu[x], K->p[x][r], &ovf), D.er[x][a], &ovf), &ovf);
                if (bp < 0 || dc_rat_cmp(v, best) > 0) { best = v; bp = a; } }
            gross = dc_rat_add(gross, best, &ovf); sx_push(pl, dc_form(RC->el[r], dc_sym(AC->el[bp]), NULL)); }
        DcRat net = dc_rat_sub(gross, cost, &ovf), gain = dc_rat_sub(net, base, &ovf);
        if (ovf) { sx_free(pl); return dc_unsupported(m, "%s: rational overflow (int64)", head); }
        Sx *val = dc_form("Value", dc_form("NetValue", st_rsx(net), NULL), dc_form("Gross", st_rsx(gross), NULL), dc_form("Cost", st_rsx(cost), NULL),
            dc_form("GainOverUninformed", st_rsx(gain), NULL), pl, NULL);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("BayesOptimalReadingPolicy"), NULL), dc_form("Uninformed", st_rsx(base), NULL), NULL), NULL);
        return st_env(m, VERDICT_HOLDS, q, "DecisionModel", a1, val, ev, NULL);
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
