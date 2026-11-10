/* M2 graded requests on declared machines: Defects, MeasureNow/Updates/Behavioral,
 * CheckNow/Updates/Behavioral with (Within b), (Horizon (Steps h)), (Discount g).
 * Values are exact rationals; the behavioral distance is computed by both engines
 * (graded.h) and the result replays only when they agree and the certificates check. */
#include "graded.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { DcRat within; char wtxt[48]; int horizon; DcRat g; char gtxt[48]; char ptxt[24]; } GOpts;
static const DcRat RZ = {0, 1}, R1 = {1, 1};

static Sx *rsym(DcRat r) { char b[48]; dc_rat_str(r, b, sizeof b); return dc_sym(b); }
static Sx *interval(DcRat r) { return dc_form("Defect", dc_form("Interval", rsym(r), rsym(r), NULL), NULL); }

static Sx *gopts(const DcModule *m, const Sx *q, const char *req, GOpts *o) {
    o->within = RZ; snprintf(o->wtxt, sizeof o->wtxt, "0"); o->horizon = -1; o->g = R1; o->gtxt[0] = 0; o->ptxt[0] = 0;
    for (size_t i = 2; i < q->n; i++) {
        const Sx *f = q->items[i];
        if (sx_head_is(f, "Within") && f->n == 2 && !dc_sx_rat(f->items[1], &o->within) && o->within.n >= 0) {
            dc_rat_str(o->within, o->wtxt, sizeof o->wtxt); continue; }
        if (sx_head_is(f, "Horizon") && f->n == 2 && sx_head_is(f->items[1], "Steps") && f->items[1]->n == 2) {
            DcRat h; if (!dc_sx_rat(f->items[1]->items[1], &h) && h.d == 1 && h.n >= 0 && h.n <= 4096) { o->horizon = (int)h.n; continue; } }
        if (sx_head_is(f, "Discount") && f->n == 2 && !dc_sx_rat(f->items[1], &o->g) && o->g.n > 0 && dc_rat_cmp(o->g, R1) <= 0) {
            dc_rat_str(o->g, o->gtxt, sizeof o->gtxt); continue; }
        if (sx_head_is(f, "Policies") && f->n == 2 && (sx_is_sym(f->items[1], "Words") || sx_is_sym(f->items[1], "ObservationBased")) && !o->ptxt[0]) {
            snprintf(o->ptxt, sizeof o->ptxt, "%s", f->items[1]->text); continue; }
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
    /* enc == NULL: a machine-level witness (BehavioralTolerance), no Codes field. */
    Sx *r = dc_form("WordWitness", dc_form("Pair", sx_copy(S->elems[x]), sx_copy(S->elems[y]), NULL), NULL);
    if (enc) sx_push(r, dc_form("Codes", sx_copy(m->car[codecar].elems[enc[x]]), sx_copy(m->car[codecar].elems[enc[y]]), NULL));
    sx_push(r, w); sx_push(r, dc_form("Query", dc_sym(v->obs_label[qk]), NULL));
    sx_push(r, dc_form("Left", sx_copy(O->elems[v->obs[qk][px]]), NULL)); sx_push(r, dc_form("Right", sx_copy(O->elems[v->obs[qk][py]]), NULL));
    sx_push(r, dc_form("LengthBound", dc_int((long)(n - zero_classes(v, d0))), NULL));
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
typedef enum { GK_NOW = 0, GK_UPD, GK_BEH, GK_TRACE } GKind;
static const char *GKN[4] = {"Current", "Update", "Behavioral", "Trace"};
typedef struct { DcRat d; int x, y, a; int x2, y2, mp; } GRes;   /* mp >= 0: a Merge witness (x,y) vs (x2,y2) */
typedef struct { const DcModule *m; int ri; DcView v; size_t n; DcRat *d0, *dq, *bref, *bbfs; int agree; } GCtx;

int dc_repr_graded(const DcModule *m, int ri) {
    const DcRepr *R = &m->rep[ri];
    return m->mach[R->machine].graded_obs || m->mach[R->machine].nmerge || (R->tol >= 0 && m->tol[R->tol].kind != DC_TOL_TRIVIAL);
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

/* Merge congruence (P10): for a Merge port m and pairs a~a', b~b',
 * defect = max (dq(m(a,b), m(a',b')) - max(dq(a,a'), dq(b,b')))+. */
static GRes merge_defect(GCtx *c) {
    GRes r = {RZ, -1, -1, -1, -1, -1, -1};
    const DcMachine *mc = &c->m->mach[c->m->rep[c->ri].machine]; size_t n = c->n; int ovf = 0;
    for (size_t p = 0; p < mc->nmerge; p++) {
        const int *t = c->m->map[mc->merge[p].map].table;
        for (size_t a = 0; a < n; a++) for (size_t b = 0; b < n; b++)
            for (size_t a2 = 0; a2 < n; a2++) for (size_t b2 = 0; b2 < n; b2++) {
                DcRat pre = dc_rat_max(c->dq[a * n + a2], c->dq[b * n + b2]);
                DcRat e = dc_rat_sub(c->dq[(size_t)t[a * n + b] * n + t[a2 * n + b2]], pre, &ovf);
                if (dc_rat_cmp(e, r.d) > 0) { r.d = e; r.x = (int)a; r.y = (int)b; r.x2 = (int)a2; r.y2 = (int)b2; r.mp = (int)p; }
            }
    }
    return r;
}

static GRes g_measure(GCtx *c, GKind k) {
    GRes r = {RZ, -1, -1, -1, -1, -1, -1};
    if (k == GK_NOW) r.d = dc_g_excess(c->n, c->d0, c->dq, &r.x, &r.y);
    else if (k == GK_UPD) {
        r.d = dc_g_update_defect(&c->v, c->dq, &r.x, &r.y, &r.a);
        GRes mr = merge_defect(c);
        if (dc_rat_cmp(mr.d, r.d) > 0) r = mr;
    }
    else if (k == GK_TRACE) {
        /* Def 4.4(4), deterministic, discrete value tolerances: the largest undiscounted
         * horizon-h behavioral distance between two states with the same code. */
        const int *enc = c->m->map[c->m->rep[c->ri].encode].table; size_t n = c->n;
        for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++)
            if (enc[x] == enc[y] && dc_rat_cmp(c->bbfs[x * n + y], r.d) > 0) { r.d = c->bbfs[x * n + y]; r.x = (int)x; r.y = (int)y; }
    }
    else r.d = dc_g_excess(c->n, c->bbfs, c->dq, &r.x, &r.y);
    return r;
}

/* Pushes the lower (witness) and upper (certificate) evidence of one defect into dst. */
static void g_evidence(GCtx *c, GKind k, GRes r, const GOpts *o, Sx *dst, int *rep) {
    const DcModule *m = c->m; const DcRepr *R = &m->rep[c->ri];
    const int *enc = m->map[R->encode].table; int cc = m->map[R->encode].to;
    const DcCarrier *S = &m->car[c->v.states], *C = &m->car[cc];
    *rep = 1;
    if (k == GK_BEH || k == GK_TRACE) {
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
    if (r.mp >= 0) {
        const DcPort *mp = &m->mach[R->machine].merge[r.mp]; const int *t = m->map[mp->map].table; size_t n = c->n;
        int u = t[(size_t)r.x * n + r.y], w = t[(size_t)r.x2 * n + r.y2];
        sx_push(dst, dc_form("Witness", dc_form("MergeWitness", dc_form("Merge", dc_sym(mp->label), NULL),
            dc_form("Left", sx_copy(S->elems[r.x]), sx_copy(S->elems[r.y]), NULL),
            dc_form("Right", sx_copy(S->elems[r.x2]), sx_copy(S->elems[r.y2]), NULL),
            dc_form("Results", sx_copy(S->elems[u]), sx_copy(S->elems[w]), NULL),
            dc_form("Codes", sx_copy(C->elems[enc[u]]), sx_copy(C->elems[enc[w]]), NULL), NULL), NULL));
        return;
    }
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
    GKind k = strstr(h, "Now") ? GK_NOW : strstr(h, "Updates") ? GK_UPD : strstr(h, "Trace") ? GK_TRACE : GK_BEH;
    for (size_t i = 2; i < q->n; i++) {
        if (sx_head_is(q->items[i], "Policies") && k != GK_TRACE) return dc_invalid(m, "%s: (Policies P) applies to trace claims only", h);
        if (k == GK_TRACE && sx_head_is(q->items[i], "Discount")) return dc_invalid(m, "%s: a trace claim takes no Discount (trace laws are undiscounted)", h);
        if (sx_head_is(q->items[i], "Within") && !is_check) return dc_invalid(m, "%s: (Within b) belongs to a check, not a measurement", h);
        if (!sx_head_is(q->items[i], "Within") && k != GK_BEH && k != GK_TRACE && !is_def) return dc_invalid(m, "%s: Horizon and Discount apply to behavioral claims only", h);
    }
    if (m->mach[m->rep[ri].machine].nmerge && (is_def || k == GK_BEH || k == GK_TRACE))
        return dc_unsupported(m, "%s: behavioral claims on a machine with Merge ports are outside the M2 fragment", h);
    if (m->mach[m->rep[ri].machine].nmerge && m->car[m->mach[m->rep[ri].machine].states].n > 32)
        return dc_unsupported(m, "%s: merge congruence over more than 32 states is outside the M2 table engine", h);
    GCtx c;
    if (gctx_init(&c, m, ri, &o)) { gctx_free(&c); return dc_unsupported(m, "%s: a rational left the 64-bit exact range", h); }
    if (k == GK_TRACE)
        for (size_t i = 0; i < c.n * c.n; i++)
            if (!dc_rat_is_zero(c.d0[i]) && dc_rat_cmp(c.d0[i], R1)) {
                gctx_free(&c);
                return dc_unsupported(m, "%s: a trace defect under graded value tolerances is outside the M2 fragment (Def 4.4 gives the deterministic formula for discrete value tolerances)", h);
            }
    const char *eq = equality_of(m, &c.v);
    DcScope sc = {"M2-GradedDeterministic", o.horizon, ""}; snprintf(sc.discount, sizeof sc.discount, "%s", o.gtxt);
    sc.policy = k == GK_TRACE ? (o.ptxt[0] ? o.ptxt : "Words") : NULL;
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

/* ---- part 3: InduceExact on a graded representation (H02; invariant 4, Prop 4.5) ----
 * Obligations in order: Current (dnow = 0), Update (dupd = 0), then literal
 * congruence of the code fibers on code values, whatever the code tolerance.
 * Under a non-separated observation tolerance the decoders land in the
 * zero-distance quotient Y/~0 only, and the result says so (Equality Observer). */
Sx *dc_req_induce_graded(DcRun *run, const Sx *q, int slot) {
    DcModule *m = run->m; Sx *e = NULL; int ri = g_repr(m, q, "InduceExact", &e);
    if (ri < 0) return e;
    if (q->n != 2) return dc_invalid(m, "InduceExact: field 2 is unexpected; InduceExact takes one Representation");
    const DcRepr *R = &m->rep[ri];
    if (m->mach[R->machine].nmerge) return dc_unsupported(m, "InduceExact: a machine with Merge ports is outside the M2 fragment");
    GOpts o; memset(&o, 0, sizeof o); o.within = RZ; o.horizon = -1; o.g = R1;
    GCtx c;
    if (gctx_init(&c, m, ri, &o)) { gctx_free(&c); return dc_unsupported(m, "InduceExact: a rational left the 64-bit exact range"); }
    const char *eq = equality_of(m, &c.v);
    DcScope sc = {"M2-GradedDeterministic", -1, ""};
    Sx *subj = dc_form("Subject", dc_form("Representation", dc_sym(R->name), NULL), dc_form("Machine", dc_sym(m->mach[R->machine].name), NULL), NULL);
    const int *enc = m->map[R->encode].table; int cc = m->map[R->encode].to;
    const DcCarrier *S = &m->car[c.v.states], *C = &m->car[cc]; size_t n = c.n;
    GRes now = g_measure(&c, GK_NOW), upd = g_measure(&c, GK_UPD);
    int cx = -1, cy = -1, ca = -1;
    for (size_t x = 0; x < n && cx < 0; x++) for (size_t y = x + 1; y < n && cx < 0; y++) {
        if (enc[x] != enc[y]) continue;
        for (size_t a = 0; a < c.v.nact; a++) if (enc[c.v.act[a][x]] != enc[c.v.act[a][y]]) { cx = (int)x; cy = (int)y; ca = (int)a; break; }
    }
    const char *fail = !dc_rat_is_zero(now.d) ? "Current" : !dc_rat_is_zero(upd.d) ? "Update" : cx >= 0 ? "Congruence" : NULL;
    Sx *res;
    if (fail) {
        Sx *ev = dc_form("Evidence", dc_form("Obligation", dc_sym(fail), NULL), NULL); int rep = 1;
        if (!strcmp(fail, "Current")) g_evidence(&c, GK_NOW, now, &o, ev, &rep);
        else if (!strcmp(fail, "Update")) g_evidence(&c, GK_UPD, upd, &o, ev, &rep);
        else {
            int tx = c.v.act[ca][cx], ty = c.v.act[ca][cy];
            sx_push(ev, dc_form("Witness", dc_form("CongruenceWitness",
                dc_form("Pair", sx_copy(S->elems[cx]), sx_copy(S->elems[cy]), NULL), dc_form("Do", dc_sym(c.v.act_label[ca]), NULL),
                dc_form("Code", sx_copy(C->elems[enc[cx]]), NULL),
                dc_form("Successors", sx_copy(C->elems[enc[tx]]), sx_copy(C->elems[enc[ty]]), NULL), NULL), NULL));
        }
        res = dc_envelope_scoped(m, VERDICT_FAILS, rep, dc_claim_of(q, eq), subj,
            dc_form("Value", dc_form("Refutation", dc_form("Obligation", dc_sym(fail), NULL), NULL), NULL), ev, NULL, &sc);
        gctx_free(&c); return res;
    }
    Sx *fib = dc_form("Fibers", NULL); long nb = 0;
    for (size_t k = 0; k < C->n; k++) {
        Sx *b = NULL;
        for (size_t s = 0; s < n; s++) if (enc[s] == (int)k) { if (!b) b = dc_form("Fiber", sx_copy(C->elems[k]), NULL); sx_push(b, sx_copy(S->elems[s])); }
        if (b) { sx_push(fib, b); nb++; }
    }
    char id[160]; snprintf(id, sizeof id, "%s", slot >= 0 ? m->der[slot].name : "?");
    Sx *val = dc_form("ExactAbstraction", dc_form("Defect", dc_form("Interval", dc_int(0), dc_int(0), NULL), NULL),
        dc_form("Machine", dc_form("Output", dc_sym(id), dc_sym("Machine"), NULL), NULL), dc_form("States", dc_int(nb), NULL),
        dc_form("Encode", dc_sym(m->map[R->encode].name), NULL), dc_form("Equality", dc_sym(eq), NULL),
        dc_form("Decoders", dc_sym(strcmp(eq, "Observer") ? "Literal" : "ZeroDistanceQuotient"), NULL), NULL);
    Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("Prefixpoint"), NULL),
        dc_form("Checks", dc_sym("Current"), dc_sym("Update"), dc_sym("Congruence"), NULL), fib, NULL), NULL);
    res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, dc_claim_of(q, eq), subj, dc_form("Value", val, NULL), ev, NULL, &sc);
    gctx_free(&c); return res;
}

/* ---- BehavioralTolerance (Def 4.1, Thm 4.2, Prop 4.10) ----
 * The kernel alpha = 1 - d_beh of a deterministic machine at discount g and horizon h,
 * enclosed by a two-sided certificate: a word test from below for every pair at positive
 * distance, and a (layered) prefixpoint from above.  The engine is exact, so Precision is
 * met with an exact kernel. */
Sx *dc_req_beh_tol(DcRun *run, const Sx *q) {
    DcModule *m = run->m; const char *h = "BehavioralTolerance";
    if (q->n < 2 || q->items[1]->kind != SX_SYM) return dc_invalid(m, "%s: field machine missing or not a name", h);
    const char *nm = q->items[1]->text; int mi = dc_find_machine(m, nm);
    if (mi < 0) return dc_declared_unsupported(m, nm) ? dc_unsupported(m, "%s: Machine %s is outside the M2 fragment", h, nm)
                                                      : dc_invalid(m, "%s: field machine names no declared machine (%s)", h, nm);
    int horizon = -1, sh = 0, sg = 0, sp = 0; DcRat g = R1, prec = RZ; char gtxt[48] = "";
    for (size_t i = 2; i < q->n; i++) {
        const Sx *f = q->items[i];
        if (sx_head_is(f, "Horizon") && f->n == 2 && !sh) {
            if (sx_is_sym(f->items[1], "AllFiniteWords")) { sh = 1; continue; }
            if (sx_head_is(f->items[1], "Steps") && f->items[1]->n == 2) {
                DcRat t; if (!dc_sx_rat(f->items[1]->items[1], &t) && t.d == 1 && t.n >= 0 && t.n <= 4096) { horizon = (int)t.n; sh = 1; continue; } } }
        if (sx_head_is(f, "Discount") && f->n == 2 && !sg && !dc_sx_rat(f->items[1], &g) && g.n > 0 && dc_rat_cmp(g, R1) <= 0) {
            dc_rat_str(g, gtxt, sizeof gtxt); sg = 1; continue; }
        if (sx_head_is(f, "Precision") && f->n == 2 && !sp && !dc_sx_rat(f->items[1], &prec) && prec.n >= 0 && dc_rat_cmp(prec, R1) <= 0) { sp = 1; continue; }
        if (sx_head_is(f, "Budget")) return dc_unsupported(m, "%s: a Budget is outside the M2 table engine (it computes exactly)", h);
        return dc_invalid(m, "%s: field %zu is not (Discount g), (Horizon (Steps h)|AllFiniteWords) or (Precision p) with valid values", h, i - 1);
    }
    if (m->mach[mi].nmerge) return dc_unsupported(m, "%s: a machine with Merge ports is outside the M2 fragment", h);
    DcView v; dc_view_of_machine(m, mi, &v); size_t n = v.n, N = n ? n * n : 1;
    if (n > 256) { dc_view_free(&v); return dc_unsupported(m, "%s: more than 256 states is outside the M2 table engine", h); }
    DcRat *d0 = calloc(N, sizeof *d0), *br = calloc(N, sizeof *br), *bb = calloc(N, sizeof *bb); int ovf = 0;
    if (dc_g_seed(m, &v, d0) | dc_g_beh_ref(&v, d0, g, horizon, br) | dc_g_beh_bfs(&v, d0, g, horizon, bb)) {
        free(d0); free(br); free(bb); dc_view_free(&v); return dc_unsupported(m, "%s: a rational left the 64-bit exact range", h); }
    int rep = 1;
    for (size_t i = 0; i < n * n; i++) if (dc_rat_cmp(br[i], bb[i])) rep = 0;
    if (horizon < 0 && !prefix_ok(&v, d0, bb, g)) rep = 0;
    const DcCarrier *S = &m->car[v.states];
    Sx *ent = dc_form("Entries", NULL), *ev = dc_form("Evidence", NULL);
    for (size_t x = 0; x < n; x++) for (size_t y = 0; y < n; y++)
        sx_push(ent, dc_form("Entry", sx_copy(S->elems[x]), sx_copy(S->elems[y]), rsym(dc_rat_sub(R1, bb[x * n + y], &ovf)), NULL));
    size_t nw = 0;
    for (size_t x = 0; x < n; x++) for (size_t y = x + 1; y < n; y++)
        if (!dc_rat_is_zero(bb[x * n + y])) { sx_push(ev, dc_form("Witness", word_witness(m, &v, NULL, -1, d0, g, horizon, (int)x, (int)y), NULL)); nw++; }
    sx_push(ev, prefixpoint(m, &v, bb, g, horizon));
    const char *eq = equality_of(m, &v);
    Sx *val = dc_form("Value", dc_form("ToleranceResult",
        dc_form("Tolerance", dc_form("Kernel", dc_form("On", dc_sym(S->name), NULL), ent, NULL), NULL),
        dc_form("Certificate", dc_form("Kind", dc_sym("TwoSided"), NULL),
                dc_form("Lower", dc_form("WordTests", dc_int((long)nw), NULL), NULL),
                dc_form("Upper", dc_sym(horizon >= 0 ? "LayeredPrefixpoint" : "Prefixpoint"), NULL), NULL), NULL), NULL);
    DcScope sc = {"M2-GradedDeterministic", horizon, ""}; snprintf(sc.discount, sizeof sc.discount, "%s", gtxt); sc.policy = NULL;
    Sx *subj = dc_form("Subject", dc_form("Machine", dc_sym(m->mach[mi].name), NULL), NULL);
    Sx *res = dc_envelope_scoped(m, ovf ? VERDICT_HOLDS : VERDICT_HOLDS, rep && !ovf, dc_claim_of(q, eq), subj, val, ev, NULL, &sc);
    free(d0); free(br); free(bb); dc_view_free(&v); return res;
}
