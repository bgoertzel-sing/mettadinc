/* M2 graded requests on declared machines: Defects, MeasureNow/Updates/Behavioral,
 * CheckNow/Updates/Behavioral with (Within b), (Horizon (Steps h)), (Discount g).
 * Values are exact rationals; the behavioral distance is computed by both engines
 * (graded.h) and the result replays only when they agree and the certificates check. */
#include "graded.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { DcRat within; char wtxt[48]; int horizon; DcRat g; char gtxt[48]; } GOpts;
static const DcRat RZ = {0, 1}, R1 = {1, 1};

static Sx *rsym(DcRat r) { char b[48]; dc_rat_str(r, b, sizeof b); return dc_sym(b); }
static Sx *interval(DcRat r) { return dc_form("Defect", dc_form("Interval", rsym(r), rsym(r), NULL), NULL); }

static Sx *gopts(const DcModule *m, const Sx *q, const char *req, GOpts *o) {
    o->within = RZ; snprintf(o->wtxt, sizeof o->wtxt, "0"); o->horizon = -1; o->g = R1; o->gtxt[0] = 0;
    for (size_t i = 2; i < q->n; i++) {
        const Sx *f = q->items[i];
        if (sx_head_is(f, "Within") && f->n == 2 && !dc_sx_rat(f->items[1], &o->within) && o->within.n >= 0) {
            dc_rat_str(o->within, o->wtxt, sizeof o->wtxt); continue; }
        if (sx_head_is(f, "Horizon") && f->n == 2 && sx_head_is(f->items[1], "Steps") && f->items[1]->n == 2) {
            DcRat h; if (!dc_sx_rat(f->items[1]->items[1], &h) && h.d == 1 && h.n >= 0 && h.n <= 4096) { o->horizon = (int)h.n; continue; } }
        if (sx_head_is(f, "Discount") && f->n == 2 && !dc_sx_rat(f->items[1], &o->g) && o->g.n > 0 && dc_rat_cmp(o->g, R1) <= 0) {
            dc_rat_str(o->g, o->gtxt, sizeof o->gtxt); continue; }
        return dc_invalid(m, "%s: field %zu is not (Within b), (Horizon (Steps h)) or (Discount g) with valid values", req, i - 1);
    }
    return NULL;
}

/* A representation for a graded request; -1 with *out set otherwise. */
static int g_repr(const DcModule *m, const Sx *q, const char *req, Sx **out) {
    if (q->n < 2 || q->items[1]->kind != SX_SYM) { *out = dc_invalid(m, "%s: field Representation missing or not a name", req); return -1; }
    const char *nm = q->items[1]->text; int ri = dc_find_repr(m, nm);
    if (ri >= 0) {
        if (m->car[m->mach[m->rep[ri].machine].states].n > 256) { *out = dc_unsupported(m, "%s: more than 256 states is outside the M2 table engine", req); return -1; }
        return ri;
    }
    *out = dc_declared_unsupported(m, nm) ? dc_unsupported(m, "%s: Representation %s is outside the M2 fragment", req, nm)
                                          : dc_invalid(m, "%s: field Representation names no declared representation (%s)", req, nm);
    return -1;
}

/* Observer equality when some observation tolerance is not separated (Prop 4.5). */
static int tol_separated(const DcModule *m, int t) {
    size_t n = m->car[m->tol[t].on].n; int ovf = 0;
    for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++)
        if (i != j && dc_rat_is_zero(dc_tol_dist(m, t, (int)i, (int)j, &ovf))) return 0;
    return 1;
}
static const char *equality_of(const DcModule *m, const DcView *v) {
    for (size_t k = 0; k < v->nobs; k++) if (v->obs_tol[k] >= 0 && !tol_separated(m, v->obs_tol[k])) return "Observer";
    return "Literal";
}

/* |X/K_O|: classes of the zero set of the seed (an equivalence: d0 is a pseudometric).
 * A shortest separating word is at most n - |X/K_O| long (E03). */
static size_t zero_classes(const DcView *v, const DcRat *d0) {
    size_t n = v->n, c = 0;
    for (size_t x = 0; x < n; x++) { int seen = 0; for (size_t y = 0; y < x && !seen; y++) if (dc_rat_is_zero(d0[y * n + x])) seen = 1; if (!seen) c++; }
    return c;
}
/* WordWitness for pair (x,y): a shortest word to the pair attaining g^k d0 (horizon-bounded). */
static Sx *word_witness(const DcModule *m, const DcView *v, const int *enc, int codecar, const DcRat *d0, DcRat g, int horizon, int x, int y) {
    size_t n = v->n, N = n * n; int ovf = 0;
    int *dist = malloc(N * sizeof *dist), *par = malloc(N * sizeof *par), *pact = malloc(N * sizeof *pact), *qu = malloc(N * sizeof *qu);
    for (size_t i = 0; i < N; i++) dist[i] = -1;
    size_t h = 0, t = 0, s = (size_t)x * n + y; dist[s] = 0; par[s] = -1; qu[t++] = (int)s;
    int bestp = (int)s; DcRat best = d0[s];
    while (h < t) {
        int p = qu[h++]; DcRat gk = R1;
        for (int k = 0; k < dist[p]; k++) gk = dc_rat_mul(gk, g, &ovf);
        DcRat val = dc_rat_mul(gk, d0[p], &ovf);
        if (dc_rat_cmp(val, best) > 0) { best = val; bestp = p; }
        if (horizon >= 0 && dist[p] >= horizon) continue;
        size_t a0 = (size_t)p / n, b0 = (size_t)p % n;
        for (size_t a = 0; a < v->nact; a++) {
            size_t q = (size_t)v->act[a][a0] * n + v->act[a][b0];
            if (dist[q] < 0) { dist[q] = dist[p] + 1; par[q] = p; pact[q] = (int)a; qu[t++] = (int)q; }
        }
    }
    int len = dist[bestp], *word = malloc((len > 0 ? len : 1) * sizeof *word);
    for (int p = bestp, k = len - 1; par[p] >= 0; p = par[p], k--) word[k] = pact[p];
    size_t px = (size_t)bestp / n, py = (size_t)bestp % n; int qk = 0; DcRat qd = RZ;
    for (size_t k = 0; k < v->nobs; k++) {
        int a = v->obs[k][px], b = v->obs[k][py];
        DcRat d = v->obs_tol[k] >= 0 ? dc_tol_dist(m, v->obs_tol[k], a, b, &ovf) : (a == b ? RZ : R1);
        if (dc_rat_cmp(d, qd) > 0) { qd = d; qk = (int)k; }
    }
    const DcCarrier *S = &m->car[v->states], *O = &m->car[v->obs_car[qk]];
    Sx *w = dc_form("Word", NULL);
    for (int k = 0; k < len; k++) sx_push(w, dc_form("Do", dc_sym(v->act_label[word[k]]), NULL));
    Sx *r = dc_form("WordWitness", dc_form("Pair", sx_copy(S->elems[x]), sx_copy(S->elems[y]), NULL),
                    dc_form("Codes", sx_copy(m->car[codecar].elems[enc[x]]), sx_copy(m->car[codecar].elems[enc[y]]), NULL),
                    w, dc_form("Query", dc_sym(v->obs_label[qk]), NULL),
                    dc_form("Left", sx_copy(O->elems[v->obs[qk][px]]), NULL), dc_form("Right", sx_copy(O->elems[v->obs[qk][py]]), NULL),
                    dc_form("LengthBound", dc_int((long)(n - zero_classes(v, d0))), NULL), NULL);
    free(dist); free(par); free(pact); free(qu); free(word);
    return r;
}

/* Prefixpoint upper certificate: kernel entries D(x,y) > 0 for x < y. */
static Sx *prefixpoint(const DcModule *m, const DcView *v, const DcRat *D, DcRat g, int horizon) {
    const DcCarrier *S = &m->car[v->states]; Sx *k = dc_form("Kernel", NULL);
    for (size_t x = 0; x < v->n; x++) for (size_t y = x + 1; y < v->n; y++)
        if (!dc_rat_is_zero(D[x * v->n + y])) sx_push(k, dc_form("Entry", sx_copy(S->elems[x]), sx_copy(S->elems[y]), rsym(D[x * v->n + y]), NULL));
    return dc_form("Certificate", dc_form("Kind", dc_sym(horizon >= 0 ? "LayeredPrefixpoint" : "Prefixpoint"), NULL),
                   dc_form("Discount", rsym(g), NULL),
                   horizon >= 0 ? dc_form("Horizon", dc_form("Steps", dc_int(horizon), NULL), NULL) : dc_form("Horizon", dc_sym("Unbounded"), NULL),
                   k, NULL);
}

/* ---- part 2: contexts, measurements, evidence, the request ---- */
typedef enum { GK_NOW = 0, GK_UPD, GK_BEH } GKind;
static const char *GKN[3] = {"Current", "Update", "Behavioral"};
typedef struct { DcRat d; int x, y, a; } GRes;
typedef struct { const DcModule *m; int ri; DcView v; size_t n; DcRat *d0, *dq, *bref, *bbfs; int agree; } GCtx;

int dc_repr_graded(const DcModule *m, int ri) {
    const DcRepr *R = &m->rep[ri];
    return m->mach[R->machine].graded_obs || (R->tol >= 0 && m->tol[R->tol].kind != DC_TOL_TRIVIAL);
}

/* Unbounded Prefixpoint: D >= d0 and D >= g * D o (Ta x Ta) everywhere. */
static int prefix_ok(const DcView *v, const DcRat *d0, const DcRat *D, DcRat g) {
    size_t n = v->n; int ovf = 0;
    for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++) {
        if (dc_rat_cmp(D[x * n + y], d0[x * n + y]) < 0) return 0;
        for (size_t a = 0; a < v->nact; a++)
            if (dc_rat_cmp(D[x * n + y], dc_rat_mul(g, D[(size_t)v->act[a][x] * n + v->act[a][y]], &ovf)) < 0) return 0;
    }
    return !ovf;
}

static void gctx_free(GCtx *c) { free(c->d0); free(c->dq); free(c->bref); free(c->bbfs); dc_view_free(&c->v); }
static int gctx_init(GCtx *c, const DcModule *m, int ri, const GOpts *o) {
    memset(c, 0, sizeof *c); c->m = m; c->ri = ri;
    dc_view_of_machine(m, m->rep[ri].machine, &c->v); c->n = c->v.n;
    size_t N = c->n ? c->n * c->n : 1;
    c->d0 = calloc(N, sizeof(DcRat)); c->dq = calloc(N, sizeof(DcRat)); c->bref = calloc(N, sizeof(DcRat)); c->bbfs = calloc(N, sizeof(DcRat));
    if (!c->d0 || !c->dq || !c->bref || !c->bbfs) return -1;
    int bad = dc_g_seed(m, &c->v, c->d0) | dc_g_codes(m, ri, c->dq)
            | dc_g_beh_ref(&c->v, c->d0, o->g, o->horizon, c->bref) | dc_g_beh_bfs(&c->v, c->d0, o->g, o->horizon, c->bbfs);
    if (bad) return -1;
    c->agree = 1;
    for (size_t i = 0; i < c->n * c->n; i++) if (dc_rat_cmp(c->bref[i], c->bbfs[i])) c->agree = 0;
    return 0;
}

static GRes g_measure(GCtx *c, GKind k) {
    GRes r = {RZ, -1, -1, -1};
    if (k == GK_NOW) r.d = dc_g_excess(c->n, c->d0, c->dq, &r.x, &r.y);
    else if (k == GK_UPD) r.d = dc_g_update_defect(&c->v, c->dq, &r.x, &r.y, &r.a);
    else r.d = dc_g_excess(c->n, c->bbfs, c->dq, &r.x, &r.y);
    return r;
}

/* Pushes the lower (witness) and upper (certificate) evidence of one defect into dst. */
static void g_evidence(GCtx *c, GKind k, GRes r, const GOpts *o, Sx *dst, int *rep) {
    const DcModule *m = c->m; const DcRepr *R = &m->rep[c->ri];
    const int *enc = m->map[R->encode].table; int cc = m->map[R->encode].to;
    const DcCarrier *S = &m->car[c->v.states], *C = &m->car[cc];
    *rep = 1;
    if (k == GK_BEH) {
        *rep = c->agree && (o->horizon >= 0 || prefix_ok(&c->v, c->d0, c->bbfs, o->g));
        if (!dc_rat_is_zero(r.d)) sx_push(dst, dc_form("Witness", word_witness(m, &c->v, enc, cc, c->d0, o->g, o->horizon, r.x, r.y), NULL));
        sx_push(dst, prefixpoint(m, &c->v, c->bbfs, o->g, o->horizon));
        return;
    }
    if (dc_rat_is_zero(r.d)) {
        sx_push(dst, dc_form("Certificate", dc_form("Kind", dc_sym("Prefixpoint"), NULL), dc_form("Checks", dc_sym(GKN[k]), NULL), NULL));
        return;
    }
    if (k == GK_NOW) { sx_push(dst, dc_form("Witness", word_witness(m, &c->v, enc, cc, c->d0, R1, 0, r.x, r.y), NULL)); return; }
    int tx = c->v.act[r.a][r.x], ty = c->v.act[r.a][r.y];
    sx_push(dst, dc_form("Witness", dc_form("UpdateWitness",
        dc_form("Pair", sx_copy(S->elems[r.x]), sx_copy(S->elems[r.y]), NULL),
        dc_form("Do", dc_sym(c->v.act_label[r.a]), NULL),
        dc_form("Codes", sx_copy(C->elems[enc[r.x]]), sx_copy(C->elems[enc[r.y]]), NULL),
        dc_form("Successors", sx_copy(C->elems[enc[tx]]), sx_copy(C->elems[enc[ty]]), NULL), NULL), NULL));
}

Sx *dc_req_graded(DcRun *run, const Sx *q, const char *h) {
    DcModule *m = run->m; Sx *e = NULL; int ri = g_repr(m, q, h, &e);
    if (ri < 0) return e;
    GOpts o; if ((e = gopts(m, q, h, &o))) return e;
    int is_def = !strcmp(h, "Defects"), is_check = !strncmp(h, "Check", 5);
    GKind k = strstr(h, "Now") ? GK_NOW : strstr(h, "Updates") ? GK_UPD : GK_BEH;
    for (size_t i = 2; i < q->n; i++) {
        if (sx_head_is(q->items[i], "Within") && !is_check) return dc_invalid(m, "%s: (Within b) belongs to a check, not a measurement", h);
        if (!sx_head_is(q->items[i], "Within") && k != GK_BEH && !is_def) return dc_invalid(m, "%s: Horizon and Discount apply to behavioral claims only", h);
    }
    GCtx c;
    if (gctx_init(&c, m, ri, &o)) { gctx_free(&c); return dc_unsupported(m, "%s: a rational left the 64-bit exact range", h); }
    const char *eq = equality_of(m, &c.v);
    DcScope sc = {"M2-GradedDeterministic", o.horizon, ""}; snprintf(sc.discount, sizeof sc.discount, "%s", o.gtxt);
    Sx *subj = dc_form("Subject", dc_form("Representation", dc_sym(m->rep[ri].name), NULL),
                       dc_form("Machine", dc_sym(m->mach[m->rep[ri].machine].name), NULL), NULL);
    Sx *ev = dc_form("Evidence", NULL), *val; int rep = 1; DcVerdict vd = VERDICT_HOLDS;
    if (is_def) {
        Sx *d = dc_form("Defects", NULL);
        for (int kk = 0; kk < 3; kk++) {
            GRes r = g_measure(&c, (GKind)kk); int rp; Sx *part = dc_form("Part", dc_sym(GKN[kk]), NULL);
            g_evidence(&c, (GKind)kk, r, &o, part, &rp); rep &= rp; sx_push(ev, part);
            sx_push(d, dc_form(GKN[kk], dc_form("Interval", rsym(r.d), rsym(r.d), NULL), NULL));
        }
        sx_push(d, dc_form("Equality", dc_sym(eq), NULL)); val = dc_form("Value", d, NULL);
    } else {
        GRes r = g_measure(&c, k); g_evidence(&c, k, r, &o, ev, &rep);
        if (is_check) {
            vd = dc_rat_cmp(r.d, o.within) <= 0 ? VERDICT_HOLDS : VERDICT_FAILS;
            val = dc_form("Value", dc_form("DefectCheck", interval(r.d), dc_form("Bound", dc_sym(o.wtxt), NULL),
                          dc_form("Kind", dc_sym(GKN[k]), NULL), dc_form("Equality", dc_sym(eq), NULL), NULL), NULL);
        } else
            val = dc_form("Value", dc_form("DefectMeasurement", interval(r.d), dc_form("Kind", dc_sym(GKN[k]), NULL),
                          dc_form("Equality", dc_sym(eq), NULL), NULL), NULL);
    }
    Sx *res = dc_envelope_scoped(m, vd, rep, dc_claim_of(q, eq), subj, val, ev, NULL, &sc);
    gctx_free(&c); return res;
}
