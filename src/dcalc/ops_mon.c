/* Library Monitors (t-2026-11-27-mettadinc-monitors): the Monitor declaration, CheckMonitor and Detect.
 * Spec, doc03 (docs/e0/docs/03_four_worked_examples/mettadinc_worked_examples.txt):
 *  l.4529-4533 library Monitors: "a Monitor multiplies Alternative(c)(o) / Null(c)(o) over the observations o
 *    of a Stream, each read in the context c posted before it. Exact claims about a monitor are Checked;
 *    detections on data are Estimated."
 *  l.4544-4545 declaration Monitor: fields Context, Null, Alternative, Columns.
 *  l.4612-4620 CheckMonitor: result MonitorCheck, status Checked; the null expectation of the factor is at most
 *    one (exactly one under absolute continuity); Blind when the two laws agree in every context; exact
 *    chi-square per context.
 *  l.4631-4641 Detect: result Detection, status Estimated, arguments On, Level, Combine; Ville's inequality;
 *    "Union gives each of k monitors the threshold k/Level, Mixture thresholds the average of the e-values at
 *    1/Level"; the result names the first monitor and observation to reach its threshold, or reports that none
 *    did, with the stream digest, the protocol and the dependence assumptions.
 *  l.4645-4647 result types MonitorCheck (Valid, Blind, ChiSquare, Certificate) and Detection.
 * Release placement: Monitors is a s6.11 proposed addition; the modules say "(Use ... Monitors) ; PROPOSED",
 * so it is a beyond-release opt-in only (admit.c M4_LIBS, model.c m->monitors).
 * Executed fragment: Null and Alternative are law terms, or calls of a Map with (Parameters ..) and
 * (Body ($u) law) whose law, after substituting the arguments and the context element, evaluates in the Laws
 * fragment; a call of a Table map on a constant is replaced by its row.  The context is an enumerated local
 * carrier.  Anything else answers Unsupported with its reason (never InvalidInput): imported maps or carriers,
 * other map calls inside a law, contexts read from (Columns (context ..)), list-valued (each ..) observations,
 * Scheme ShiryaevRoberts / MeanTimeToFalseAlarm. */
#include "ops_run.h"
#include "records.h"
#include "estimates.h"
#include "laws.h"
#include "maprules.h"
#include "qrat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MN_MAXC 64
#define MN_MAXK 8
typedef struct { const DcModule *m; char why[480]; int unsup; } MonCtx;
typedef struct {
    const char *name; const Sx *decl; size_t nc;
    const Sx *ctx[MN_MAXC]; DcLaw N[MN_MAXC], A[MN_MAXC];
} MonDef;

static const Sx *mn_src(const DcModule *m) { return m->raw_source ? m->raw_source : m->source; }
static const Sx *mn_decl(const DcModule *m, const char *head, const char *nm) {
    const Sx *src = mn_src(m);
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (sx_head_is(d, head) && d->n >= 2 && d->items[1]->kind != SX_LIST && !strcmp(d->items[1]->text, nm)) return d;
    }
    return NULL;
}
static const Sx *mn_field(const Sx *d, const char *k) {
    for (size_t i = 1; d && d->kind == SX_LIST && i < d->n; i++)
        if (sx_head_is(d->items[i], k)) return d->items[i];
    return NULL;
}
static const Sx *mn_arg1(const Sx *d, const char *k) { const Sx *f = mn_field(d, k); return f && f->n == 2 ? f->items[1] : NULL; }
static void mn_why(MonCtx *c, int unsup, const char *fmt, const char *a, const char *b) {
    if (c->why[0]) return;
    snprintf(c->why, sizeof c->why, fmt, a ? a : "", b ? b : ""); c->unsup = unsup;
}
static Sx *mn_subst(const Sx *e, const char *var, const Sx *val) {
    if (e->kind == SX_SYM && !strcmp(e->text, var)) return sx_copy(val);
    if (e->kind != SX_LIST) return sx_copy(e);
    Sx *r = sx_list();
    for (size_t i = 0; i < e->n; i++) sx_push(r, mn_subst(e->items[i], var, val));
    return r;
}
/* Shared map rules (maprules.h) on a Table map read by a monitor law (review 1 of
 * t-2026-11-27-mettadinc-rebase-monitors).  In a Stochastic module with (Use .. Families) no other loader runs
 * dc_mr_put on such a Table (families.c passes it through, model.c does not tabulate maps in a Stochastic
 * profile), so Monitors admits it here, in model.c's Table order and texts: row shape, key in From, R3 codomain
 * (To an enumerated local carrier, or Rational01 on a literal rational), R2 duplicate key, R1 totality.
 * Without this, source order decided a duplicated row.  All are InvalidInput, as on model.c's loader. */
static int mn_table_rules(MonCtx *c, const Sx *mp, const char *f) {
    const Sx *tb = mn_field(mp, "Table"), *fr = mn_arg1(mp, "From"), *to = mn_arg1(mp, "To");
    const Sx *fc = fr && fr->kind == SX_SYM ? mn_decl(c->m, "Carrier", fr->text) : NULL, *en = fc ? mn_field(fc, "Enum") : NULL;
    const Sx *tc = to && to->kind == SX_SYM ? mn_decl(c->m, "Carrier", to->text) : NULL, *ten = tc ? mn_field(tc, "Enum") : NULL;
    int r01 = to && to->kind == SX_SYM && !strcmp(to->text, "Rational01");
    char w[320]; w[0] = 0;
    if (!en) {
        mn_why(c, 1, "Monitors: the table map %s reads from %s, which is not an enumerated local carrier; only such tables are executed",
               f, fr && fr->kind == SX_SYM ? fr->text : "?");
        return -1;
    }
    int n = (int)en->n - 1, *buf = malloc((n ? n : 1) * sizeof(int)); DcMrTab mr; dc_mr_init(&mr, n, buf);
    for (size_t j = 1; j < tb->n && !w[0]; j++) {
        const Sx *row = tb->items[j]; int a = -1, b = 0;
        if (row->kind != SX_LIST || row->n != 2) { snprintf(w, sizeof w, "Map %s: Table row %zu is not a pair", f, j - 1); break; }
        for (int k = 0; k < n; k++) if (sx_equal(en->items[k + 1], row->items[0])) { a = k; break; }
        if (ten) { b = -1; for (size_t k = 1; k < ten->n; k++) if (sx_equal(ten->items[k], row->items[1])) { b = 0; break; } }
        else if (r01) { DcRat q; if (!dc_sx_rat(row->items[1], &q) && (q.n < 0 || q.n > q.d)) b = -1; }
        int rc = dc_mr_put(&mr, a, b);
        if (rc == DC_MR_KEY) snprintf(w, sizeof w, "Map %s: Table row %zu key outside carrier %s", f, j - 1, fr->text);
        else if (rc == DC_MR_CODOMAIN) snprintf(w, sizeof w, "Map %s: Table row %zu value outside carrier %s", f, j - 1, to->text);
        else if (rc == DC_MR_DUP) snprintf(w, sizeof w, "Map %s: Table key at row %zu repeated", f, j - 1);
    }
    int miss = -1;
    if (!w[0] && dc_mr_total(&mr, &miss)) { char *s = sx_print(en->items[miss + 1]); snprintf(w, sizeof w, "Map %s: not total; no value for %s", f, s); free(s); }
    free(buf);
    if (w[0]) { mn_why(c, 0, "%s%s", w, ""); return -1; }
    return 0;
}
/* replace calls of Table maps on constants by their rows; any other map call: Unsupported */
static Sx *mn_tables(MonCtx *c, const Sx *e) {
    if (e->kind != SX_LIST) return sx_copy(e);
    if (e->n >= 1 && e->items[0]->kind == SX_SYM) {
        const char *f = e->items[0]->text;
        const Sx *mp = mn_decl(c->m, "Map", f);
        const Sx *tb = mp ? mn_field(mp, "Table") : NULL;
        if (tb && e->n == 2) {
            if (mn_table_rules(c, mp, f)) return NULL;
            Sx *a = mn_tables(c, e->items[1]);
            if (!a) return NULL;
            for (size_t k = 1; k < tb->n; k++) {
                const Sx *row = tb->items[k];
                if (row->kind == SX_LIST && row->n == 2 && sx_equal(row->items[0], a)) { sx_free(a); return mn_tables(c, row->items[1]); }
            }
            char *pa = sx_print(a);
            int var = a->kind == SX_LIST || (a->text && a->text[0] == '$');
            mn_why(c, var, var ? "Monitors: the table map %s is applied to %.160s, which is not a constant"
                              : "Monitors: the table map %s has no row for %.160s", f, pa);
            free(pa); sx_free(a); return NULL;
        }
        if (mp || dc_name_imported(mn_src(c->m), f)) {
            char *pe = sx_print(e);
            mn_why(c, 1, "Monitors: the map call %.200s inside a monitor law is not a table lookup on a constant%s; a map call inside a law term is outside the closed arithmetic of the Laws fragment",
                   pe, mp ? "" : " (the map is imported)");
            free(pe); return NULL;
        }
    }
    Sx *r = sx_list();
    for (size_t i = 0; i < e->n; i++) { Sx *x = mn_tables(c, e->items[i]); if (!x) { sx_free(r); return NULL; } sx_push(r, x); }
    return r;
}
static Sx *mn_leaf(const Sx *e, void *ctx, int *ok) {
    MonCtx *c = ctx; int ovf = 0;
    Sx *t = mn_tables(c, e);
    if (!t) { *ok = 0; return NULL; }
    *ok = 1;
    Sx *v = dc_law_arith(t, ok, &ovf);
    if (*ok != 1 && t->kind == SX_SYM) { *ok = 1; v = sx_copy(t); }   /* a symbol value, e.g. (Point adverse) */
    if (*ok != 1) { char *pt = sx_print(t); mn_why(c, 1, "Monitors: %.200s inside a monitor law is outside the closed arithmetic of the Laws fragment%s", pt, ovf ? " (overflow)" : ""); free(pt); }
    sx_free(t); return v;
}

/* the law of one monitor side (Null or Alternative) in context element cx */
static int mn_side(MonCtx *c, const Sx *e, const Sx *cx, DcLaw *out) {
    char why[320] = ""; int ovf = 0;
    Sx *t = NULL;
    if (e->kind == SX_LIST && e->n >= 1 && e->items[0]->kind == SX_SYM && !dc_law_head(e)) {
        const char *f = e->items[0]->text;
        const Sx *mp = mn_decl(c->m, "Map", f);
        if (!mp) {
            mn_why(c, dc_name_imported(mn_src(c->m), f), dc_name_imported(mn_src(c->m), f)
                   ? "Monitors: the monitor law calls %s, which is imported; imported maps are outside the Monitors fragment%s"
                   : "Monitors: the monitor law calls %s, which names no declared Map%s", f, "");
            return -1;
        }
        const Sx *pa = mn_field(mp, "Parameters"), *bd = mn_field(mp, "Body");
        size_t np = pa ? pa->n - 1 : 0;
        if (!bd || bd->n != 3 || bd->items[1]->kind != SX_LIST || bd->items[1]->n != 1 || bd->items[1]->items[0]->kind != SX_SYM) {
            mn_why(c, 1, "Monitors: map %s has no (Body ($u) law) form%s; only such maps are executed as monitor laws", f, "");
            return -1;
        }
        if (e->n - 1 != np) {
            char a[32], b[32]; snprintf(a, sizeof a, "%zu", e->n - 1); snprintf(b, sizeof b, "%zu", np);
            mn_why(c, 0, "Monitors: the monitor law applies its map to %s arguments; it declares %s parameters", a, b);
            return -1;
        }
        t = sx_copy(bd->items[2]);
        for (size_t k = 0; k < np; k++) {
            const Sx *pd = pa->items[k + 1];
            if (pd->kind != SX_LIST || pd->n != 2 || pd->items[0]->kind != SX_SYM) { sx_free(t); mn_why(c, 0, "Monitors: map %s: a parameter is not ($v Carrier)%s", f, ""); return -1; }
            Sx *u = mn_subst(t, pd->items[0]->text, e->items[k + 1]); sx_free(t); t = u;
        }
        Sx *u = mn_subst(t, bd->items[1]->items[0]->text, cx); sx_free(t); t = u;
    } else if (dc_law_head(e)) t = sx_copy(e);
    else { char *pe = sx_print(e); mn_why(c, 0, "Monitors: %.200s is neither a law nor a call of a map that returns a law%s", pe, ""); free(pe); return -1; }
    dc_law_init(out);
    int rc = dc_law_eval(t, mn_leaf, c, out, &ovf, why, sizeof why);
    sx_free(t);
    if (rc) { if (!c->why[0]) mn_why(c, 1, "Monitors: the monitor law does not evaluate in the Laws fragment: %.300s%s", why[0] ? why : (ovf ? "overflow" : "unknown"), ""); return -1; }
    DcQ s = dc_q(0, 1, &ovf);
    for (size_t i = 0; i < out->n; i++) { if (dc_mr_mass_entry(out->m[i]) != DC_MR_OK) { mn_why(c, 0, "Monitors: a monitor law has a negative mass%s%s", "", ""); return -1; } s = dc_q_add(s, out->m[i], &ovf); }
    if (ovf || dc_mr_mass_row(s) != DC_MR_OK) { mn_why(c, 0, "Monitors: a monitor law's masses do not sum to 1%s%s", "", ""); return -1; }
    return 0;
}
static void mn_def_free(MonDef *d) { for (size_t i = 0; i < d->nc; i++) { dc_law_free(&d->N[i]); dc_law_free(&d->A[i]); } d->nc = 0; }
/* resolve a Monitor declaration: its contexts and both laws in each; 0 ok, else c->why */
static int mn_resolve(MonCtx *c, const char *nm, MonDef *d) {
    memset(d, 0, sizeof *d); d->name = nm;
    d->decl = mn_decl(c->m, "Monitor", nm);
    if (!d->decl) { mn_why(c, 0, "Monitors: %s names no declared Monitor%s", nm, ""); return -1; }
    const Sx *cx = mn_arg1(d->decl, "Context"), *nu = mn_arg1(d->decl, "Null"), *al = mn_arg1(d->decl, "Alternative"), *co = mn_field(d->decl, "Columns");
    if (!cx || cx->kind == SX_LIST || !nu || !al || !co) { mn_why(c, 0, "Monitor %s needs the fields Context, Null, Alternative and Columns%s", nm, ""); return -1; }
    const Sx *car = mn_decl(c->m, "Carrier", cx->text), *en = car ? mn_field(car, "Enum") : NULL;
    if (!en) {
        int imp = dc_name_imported(mn_src(c->m), cx->text);
        mn_why(c, imp || car, imp ? "Monitor %s: the context carrier %s is imported; imported carriers are outside the Monitors fragment"
                              : car ? "Monitor %s: the context carrier %s is not an enumerated carrier; only (Enum ..) contexts are executed"
                                    : "Monitor %s: Context %s names no declared Carrier", nm, cx->text);
        return -1;
    }
    if (en->n - 1 > MN_MAXC) { mn_why(c, 1, "Monitor %s: the context carrier %s has more than 64 elements", nm, cx->text); return -1; }
    for (size_t k = 1; k < en->n; k++) {
        d->ctx[d->nc] = en->items[k];
        if (mn_side(c, nu, en->items[k], &d->N[d->nc])) { mn_def_free(d); return -1; }
        if (mn_side(c, al, en->items[k], &d->A[d->nc])) { dc_law_free(&d->N[d->nc]); mn_def_free(d); return -1; }
        d->nc++;
    }
    return 0;
}

/* mass of law L at value v (0 when v is outside the support) */
static DcQ mn_mass(const DcLaw *L, const Sx *v) {
    int ovf = 0;
    for (size_t i = 0; i < L->n; i++) if (sx_equal(L->val[i], v)) return L->m[i];
    return dc_q(0, 1, &ovf);
}
static Sx *mn_qsx(DcQ a) {
    if (!dc_q_is_big(a)) return a.d == 1 ? dc_int((long)a.n) : dc_form("Rat", dc_int((long)a.n), dc_int((long)a.d), NULL);
    char buf[4096]; const char *t = dc_q_str(a, buf, sizeof buf), *sl = strchr(t, '/');
    if (!sl) return sx_sym(t);
    char num[4096]; snprintf(num, sizeof num, "%.*s", (int)(sl - t), t);
    return dc_form("Rat", sx_sym(num), sx_sym(sl + 1), NULL);
}
static Sx *mn_fail(const DcModule *m, MonCtx *c) {
    return c->unsup ? dc_unsupported(m, "%s", c->why) : dc_invalid(m, "%s", c->why);
}
/* CheckMonitor M: for every context c, NullMean(c) = sum over supp Null(c) of Alt(c)(o) (<= 1; = 1 iff
 * Alt(c) is absolutely continuous w.r.t. Null(c)), chi-square(c) = sum Alt(c)(o)^2/Null(c)(o) - 1
 * (Infinite when not absolutely continuous), Blind iff Null(c) = Alt(c) in every c.  Checked (exact). */
static Sx *mn_check(DcRun *r, const Sx *q) {
    DcModule *m = r->m; MonCtx c = { m, "", 0 };
    if (q->n != 2 || q->items[1]->kind == SX_LIST) return dc_invalid(m, "CheckMonitor: expected (CheckMonitor MonitorName)");
    MonDef d;
    if (mn_resolve(&c, q->items[1]->text, &d)) return mn_fail(m, &c);
    int ovf = 0, blind = 1, allac = 1;
    Sx *chi = dc_form("Table", NULL), *nm = dc_form("Table", NULL);
    for (size_t i = 0; i < d.nc; i++) {
        DcQ s = dc_q(0, 1, &ovf), x2 = dc_q(0, 1, &ovf);
        for (size_t j = 0; j < d.N[i].n; j++) {
            DcQ a = mn_mass(&d.A[i], d.N[i].val[j]);
            s = dc_q_add(s, a, &ovf);
            x2 = dc_q_add(x2, dc_q_div(dc_q_mul(a, a, &ovf), d.N[i].m[j], &ovf), &ovf);
        }
        int ac = !dc_q_cmp(s, dc_q(1, 1, &ovf));
        if (!ac) allac = 0;
        x2 = dc_q_sub(x2, dc_q(1, 1, &ovf), &ovf);
        if (d.N[i].n != d.A[i].n) blind = 0;
        for (size_t j = 0; blind && j < d.N[i].n; j++) if (dc_q_cmp(mn_mass(&d.A[i], d.N[i].val[j]), d.N[i].m[j])) blind = 0;
        sx_push(chi, dc_form("Row", sx_copy(d.ctx[i]), ac ? mn_qsx(x2) : dc_sym("Infinite"), NULL));
        sx_push(nm, dc_form("Row", sx_copy(d.ctx[i]), mn_qsx(s), NULL));
    }
    if (ovf) { sx_free(chi); sx_free(nm); mn_def_free(&d); return dc_unsupported(m, "CheckMonitor %s: exact arithmetic overflow", d.name); }
    Sx *val = dc_form("Value", dc_form("MonitorCheck",
        dc_form("Valid", dc_sym("True"), NULL), dc_form("Blind", dc_sym(blind ? "True" : "False"), NULL),
        dc_form("ChiSquare", chi, NULL),
        dc_form("Certificate", dc_form("NullMean", nm, NULL), dc_form("AbsolutelyContinuous", dc_sym(allac ? "True" : "False"), NULL),
                dc_form("Contexts", dc_int((long)d.nc), NULL),
                dc_form("Rule", sx_str("the null expectation of each factor is the mass of Alternative(c) on the support of Null(c), at most 1; the product is a nonnegative supermartingale under the null for every policy that fixes the context before the observation"), NULL), NULL), NULL), NULL);
    Sx *ev = dc_form("Evidence", dc_form("Monitor", dc_sym(d.name), NULL), NULL);
    mn_def_free(&d);
    DcScope sc = { "Monitors", -1, "1", NULL };
    return dc_envelope_scoped(m, VERDICT_HOLDS, 1, dc_form("Claim", sx_copy(q), NULL),
                              dc_form("Subject", dc_form("Monitor", dc_sym(q->items[1]->text), NULL), NULL), val, ev, NULL, &sc);
}

/* a stream cell as a law value: an integer literal, else a symbol */
static Sx *mn_cell(const char *t) {
    char *e = NULL; long v = strtol(t, &e, 10);
    if (t[0] && e && !*e) return dc_int(v);
    return sx_sym(t);
}
/* Detect M1 .. Mk (On S) (Level L) [(Combine Union|Mixture)] [(Scheme Ville)].  Ville e-processes from the
 * first observation; Union: monitor j fires when E_j >= k/Level; Mixture: fires when (sum E_j)/k >= 1/Level.
 * Estimated (statistical ground): the claim is about the data source, never about the model. */
static Sx *mn_detect(DcRun *r, const Sx *q) {
    DcModule *m = r->m; MonCtx c = { m, "", 0 };
    size_t k = 0; const char *mon[MN_MAXK];
    for (size_t i = 1; i < q->n && q->items[i]->kind != SX_LIST; i++) {
        if (k == MN_MAXK) return dc_unsupported(m, "Detect: more than %d monitors", MN_MAXK);
        mon[k++] = q->items[i]->text;
    }
    if (!k) return dc_invalid(m, "Detect: expected (Detect Monitor.. (On Stream) (Level p))");
    const Sx *on = mn_arg1(q, "On"), *lv = mn_arg1(q, "Level"), *cb = mn_arg1(q, "Combine"), *sc = mn_arg1(q, "Scheme");
    if (sc && (sc->kind == SX_LIST || strcmp(sc->text, "Ville")))
        return dc_unsupported(m, "Detect: Scheme %s is outside the executed Monitors fragment (doc03 s6.11 Detect: Ville's inequality, e-processes from the first observation)", sc->kind == SX_LIST ? "(..)" : sc->text);
    if (mn_field(q, "MeanTimeToFalseAlarm"))
        return dc_unsupported(m, "Detect: MeanTimeToFalseAlarm belongs to Scheme ShiryaevRoberts, outside the executed Monitors fragment");
    if (!on || on->kind == SX_LIST) return dc_invalid(m, "Detect: field On must name a Stream");
    if (!lv) return dc_invalid(m, "Detect: (Level p) is required with Scheme Ville");
    DcRat lr; if (dc_sx_rat(lv, &lr) || lr.n <= 0 || lr.n >= lr.d) return dc_invalid(m, "Detect: Level must be a rational in (0,1)");
    int mix = 0;
    if (cb) { if (cb->kind == SX_LIST || (strcmp(cb->text, "Union") && strcmp(cb->text, "Mixture"))) return dc_invalid(m, "Detect: Combine must be Union or Mixture"); mix = !strcmp(cb->text, "Mixture"); }
    /* resolve every monitor (laws first: an Unsupported law answers before any data is read) */
    MonDef *D = calloc(k, sizeof *D);
    if (!D) return dc_unsupported(m, "Detect: out of memory");
    size_t nd = 0; Sx *res = NULL;
    int colk[MN_MAXK][4]; size_t ncol[MN_MAXK];
    for (; nd < k; nd++) if (mn_resolve(&c, mon[nd], &D[nd])) { res = mn_fail(m, &c); goto out; }
    const Sx *sd = mn_decl(m, "Stream", on->text);
    if (!sd) { res = dc_invalid(m, "Detect: On %s names no declared Stream", on->text); goto out; }
    const Sx *srcf = mn_arg1(sd, "Source"), *dgf = mn_arg1(sd, "Digest");
    if (!srcf || !dgf || srcf->kind == SX_LIST || dgf->kind == SX_LIST) { res = dc_invalid(m, "Detect: Stream %s needs (Source path) and (Digest sha256:..)", on->text); goto out; }
    const char *src = srcf->text, *dig = dgf->text;
    char path[1100];
    if (src[0] == '/' || !m->basedir[0]) snprintf(path, sizeof path, "%s", src); else snprintf(path, sizeof path, "%s/%s", m->basedir, src);
    DcStream s; char err[256];
    if (dc_stream_load(path, dig, &s, err, sizeof err)) {
        res = strstr(err, "not a number or short string")
            ? dc_unsupported(m, "Detect: Stream %s: %s; list-valued cells are outside the executed Monitors fragment", on->text, err)
            : dc_invalid(m, "Detect: Stream %s: %s", on->text, err);
        goto out;
    }
    for (size_t j = 0; j < k; j++) {
        const Sx *co = mn_field(D[j].decl, "Columns"); ncol[j] = 0;
        for (size_t i = 1; i < co->n; i++) {
            const Sx *f = co->items[i];
            if (!sx_head_is(f, "observation") || D[j].nc != 1) {
                res = dc_unsupported(m, "Monitor %s: Columns %s is outside the executed Monitors fragment (one context, scalar observation columns)", D[j].name,
                                     sx_head_is(f, "context") || D[j].nc != 1 ? "with a context read from the stream" : "with a list-valued (each ..) observation");
                dc_stream_free(&s); goto out;
            }
            for (size_t t = 1; t < f->n; t++) {
                if (f->items[t]->kind == SX_LIST || ncol[j] == 4) { res = dc_unsupported(m, "Monitor %s: an observation column is not a plain column name", D[j].name); dc_stream_free(&s); goto out; }
                int ci = dc_stream_col(&s, f->items[t]->text);
                if (ci < 0) { res = dc_invalid(m, "Detect: Stream %s has no column %s (Monitor %s)", on->text, f->items[t]->text, D[j].name); dc_stream_free(&s); goto out; }
                colk[j][ncol[j]++] = ci;
            }
        }
        if (!ncol[j]) { res = dc_invalid(m, "Monitor %s: Columns names no observation column", D[j].name); dc_stream_free(&s); goto out; }
    }
    {
        int ovf = 0;
        DcQ L = dc_q_from_rat(lr), one = dc_q(1, 1, &ovf), kk = dc_q((int64_t)k, 1, &ovf);
        DcQ thr = mix ? dc_q_div(one, L, &ovf) : dc_q_div(kk, L, &ovf);
        DcQ E[MN_MAXK], best = dc_q(0, 1, &ovf); size_t bestat = 0, fired_at = 0; int fired = -1;
        for (size_t j = 0; j < k; j++) E[j] = one;
        DcQ stat = one;
        for (size_t row = 0; row < s.nrows && fired < 0; row++) {
            for (size_t j = 0; j < k; j++) {
                Sx *o;
                if (ncol[j] == 1) o = mn_cell(s.cell[row * s.ncol + colk[j][0]]);
                else { o = dc_form("Tuple", NULL); for (size_t t = 0; t < ncol[j]; t++) sx_push(o, mn_cell(s.cell[row * s.ncol + colk[j][t]])); }
                DcQ n0 = mn_mass(&D[j].N[0], o), a1 = mn_mass(&D[j].A[0], o);
                sx_free(o);
                if (dc_q_sign(n0) == 0) { res = dc_unsupported(m, "Detect: row %zu of Stream %s is outside the support of the null law of Monitor %s; an e-value outside the null support is not executed", row + 1, on->text, D[j].name); break; }
                E[j] = dc_q_mul(E[j], dc_q_div(a1, n0, &ovf), &ovf);
            }
            if (res) break;
            if (mix) { stat = dc_q(0, 1, &ovf); for (size_t j = 0; j < k; j++) stat = dc_q_add(stat, E[j], &ovf); stat = dc_q_div(stat, kk, &ovf); if (dc_q_cmp(stat, best) > 0) { best = stat; bestat = row + 1; } if (dc_q_cmp(stat, thr) >= 0) { fired = 0; fired_at = row + 1; } }
            else for (size_t j = 0; j < k; j++) { if (dc_q_cmp(E[j], best) > 0) { best = E[j]; bestat = row + 1; } if (fired < 0 && dc_q_cmp(E[j], thr) >= 0) { fired = (int)j; fired_at = row + 1; stat = E[j]; } }
        }
        size_t rows = s.nrows; dc_stream_free(&s);
        if (res) goto out;
        if (ovf) { res = dc_unsupported(m, "Detect: exact arithmetic overflow"); goto out; }
        Sx *det = dc_form("Detection", NULL);
        if (fired >= 0) {
            sx_push(det, dc_form("Fired", mix ? dc_sym("Mixture") : dc_sym(D[fired].name), NULL));
            sx_push(det, dc_form("Step", dc_int((long)fired_at), NULL));
            sx_push(det, dc_form("Observations", dc_int((long)fired_at), NULL));
            sx_push(det, dc_form("EValue", mn_qsx(stat), NULL));
        } else {
            sx_push(det, dc_form("Fired", dc_sym("None"), NULL));
            sx_push(det, dc_form("Step", dc_sym("None"), NULL));
            sx_push(det, dc_form("Observations", dc_int((long)rows), NULL));
            sx_push(det, dc_form("EValue", mn_qsx(mix ? stat : E[0]), NULL));
            sx_push(det, dc_form("Largest", mn_qsx(best), NULL));
            sx_push(det, dc_form("LargestAt", dc_int((long)bestat), NULL));
        }
        sx_push(det, dc_form("Threshold", mn_qsx(thr), NULL));
        sx_push(det, dc_form("Scheme", dc_sym("Ville"), NULL));
        sx_push(det, dc_form("Procedure", dc_form("LikelihoodRatioEProcess", dc_form("Combine", dc_sym(mix ? "Mixture" : "Union"), NULL), dc_form("Level", sx_copy(lv), NULL), NULL), NULL));
        sx_push(det, dc_form("Assumptions", sx_str("under the null, each observation follows the monitor's null law given the context posted before it"), NULL));
        Sx *val = dc_form("Value", det, NULL);
        Sx *ev = dc_form("Evidence", dc_form("Stream", dc_sym(on->text), sx_str(dig), NULL), dc_form("Rows", dc_int((long)rows), NULL),
                         dc_form("Combine", dc_sym(mix ? "Mixture" : "Union"), NULL), dc_form("Level", sx_copy(lv), NULL), NULL);
        DcScope scp = { "Monitors", -1, "1", NULL };
        res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, dc_form("Claim", sx_copy(q), NULL),
                                 dc_form("Subject", dc_form("Stream", dc_sym(on->text), NULL), NULL), val, ev, NULL, &scp);
        Sx *st = sx_find(res, "Status", 1);
        if (st && st->n == 2) { sx_free(st->items[1]); st->items[1] = dc_sym(dc_status_name(dc_assure_grounded(VERDICT_HOLDS, GROUND_STATISTICAL, 0))); }
        for (size_t i = 1; i < res->n; i++)
            if (sx_head_is(res->items[i], "Assurance")) {
                sx_free(res->items[i]);
                res->items[i] = dc_form("Assurance", dc_form("Policy", dc_sym("Monitors"), NULL), dc_form("Replayed", dc_sym("False"), NULL),
                                        dc_form("Ground", dc_sym(dc_ground_name(GROUND_STATISTICAL)), NULL), NULL);
            }
    }
out:
    for (size_t j = 0; j < nd; j++) mn_def_free(&D[j]);
    free(D);
    return res;
}

Sx *dc_req_monitors(DcRun *r, const Sx *q, const char *head) {
    return !strcmp(head, "CheckMonitor") ? mn_check(r, q) : mn_detect(r, q);
}
