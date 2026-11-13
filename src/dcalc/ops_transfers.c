#include "ops_internal.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* M6 (opt-in, beyond release only): transfers between method systems, spec section 10.2.
 * (MethodSystem S (States X) (Methods M) (Response r) (Observe o f)...) and
 * (Transfer T (Source A) (Target B) (StatePullback phi) (MethodPushforward iota)), phi : X_B -> X_A,
 * iota : M_A -> M_B, are read from m->source; Cases/Table maps are applied by structural key match.
 *   CheckTransfer T [(Metric RewardLawTV|ExpectedReward)]: defect = max over b in X_B, a in M_A of the
 *     distance between r_A(phi b, a) and r_B(b, iota a) (point laws: total variation 0/1; expected reward:
 *     |difference|), and every observer o declared on B must satisfy o_A(phi b) = o_B(b).
 *     Checked iff the defect is 0 and every observer is preserved, else Refuted with a witness.
 *   CheckValuePullback T: max_m r_B(b, m) = max_a r_A(phi b, a) for every b (not a transfer certificate).
 *   LibraryGap T: max over b of (max_m r_B(b, m) - max_a r_B(b, iota a)).
 *   ComposeTransfers (Output D Transfer)...: Poly composition of Checked CheckTransfer premises;
 *     phi = phi_1 o ... o phi_k, iota = iota_k o ... o iota_1, defect = sum of premise defects. */
typedef struct { const char *name; const Sx *d; int xs, ms; const char *resp; } TrSys;
typedef struct { const char *name; TrSys a, b; const char *phi, *iota; } TrT;

static Sx *rsx(DcRat r) { return dc_form("Rat", dc_int((long)r.n), dc_int((long)r.d), NULL); }
static DcRat rq(long n, long d) { DcRat r; r.n = n; r.d = d; return r; }
static const Sx *kid(const Sx *x, const char *h) {
    for (size_t i = 1; x && x->kind == SX_LIST && i < x->n; i++) if (sx_head_is(x->items[i], h)) return x->items[i];
    return NULL;
}
static const char *arg1(const Sx *x, const char *h) { const Sx *k = kid(x, h); return k && k->n == 2 && k->items[1]->kind == SX_SYM ? k->items[1]->text : NULL; }
static const Sx *decl(const DcModule *m, const char *head, const char *name) {
    const Sx *s = m->source;
    for (size_t i = 2; s && name && i < s->n; i++) { const Sx *d = s->items[i]; if (sx_head_is(d, head) && d->n > 1 && sx_is_sym(d->items[1], name)) return d; }
    return NULL;
}
/* value of a Cases/Table map at arg, or NULL */
static const Sx *tr_apply(const DcModule *m, const char *map, const Sx *arg) {
    const Sx *d = decl(m, "Map", map);
    if (!d || d->n != 5 || !(sx_head_is(d->items[4], "Cases") || sx_head_is(d->items[4], "Table"))) return NULL;
    for (size_t i = 1; i < d->items[4]->n; i++) { const Sx *r = d->items[4]->items[i]; if (r->kind == SX_LIST && r->n == 2 && sx_equal(r->items[0], arg)) return r->items[1]; }
    return NULL;
}
static const Sx *tr_resp(const DcModule *m, const TrSys *s, const Sx *x, const Sx *a) {
    Sx *t = dc_form("Tuple", sx_copy(x), sx_copy(a), NULL); const Sx *v = tr_apply(m, s->resp, t); sx_free(t); return v;
}
static int in_car(const DcModule *m, int c, const Sx *v) { for (size_t i = 0; v && i < m->car[c].n; i++) if (sx_equal(m->car[c].elems[i], v)) return 1; return 0; }
#define TR_FAIL(rc, ...) do { snprintf(why, wn, __VA_ARGS__); return rc; } while (0)
static int tr_sys(const DcModule *m, const char *nm, TrSys *s, char *why, size_t wn) {
    memset(s, 0, sizeof *s); s->d = decl(m, "MethodSystem", nm);
    if (!s->d) TR_FAIL(-1, "%s names no declared MethodSystem", nm ? nm : "?");
    s->name = s->d->items[1]->text; s->resp = arg1(s->d, "Response");
    if ((s->xs = dc_find_carrier(m, arg1(s->d, "States") ? arg1(s->d, "States") : "")) < 0 || (s->ms = dc_find_carrier(m, arg1(s->d, "Methods") ? arg1(s->d, "Methods") : "")) < 0 || !s->resp || !decl(m, "Map", s->resp))
        TR_FAIL(-1, "MethodSystem %s: expected (States Carrier) (Methods Carrier) (Response Map) over declared names", s->name);
    for (size_t i = 0; i < m->car[s->xs].n; i++) for (size_t j = 0; j < m->car[s->ms].n; j++)
        if (!tr_resp(m, s, m->car[s->xs].elems[i], m->car[s->ms].elems[j])) TR_FAIL(-1, "MethodSystem %s: Response %s has no value at some (state, method)", s->name, s->resp);
    return 0;
}
static int tr_load(const DcModule *m, const Sx *tn, TrT *t, char *why, size_t wn) {
    memset(t, 0, sizeof *t);
    const Sx *d = tn && tn->kind == SX_SYM ? decl(m, "Transfer", tn->text) : NULL;
    if (!d) TR_FAIL(-1, "expected the name of a declared Transfer");
    t->name = d->items[1]->text; t->phi = arg1(d, "StatePullback"); t->iota = arg1(d, "MethodPushforward");
    int rc;
    if ((rc = tr_sys(m, arg1(d, "Source"), &t->a, why, wn)) || (rc = tr_sys(m, arg1(d, "Target"), &t->b, why, wn))) return rc;
    for (size_t i = 0; i < m->car[t->b.xs].n; i++) if (!in_car(m, t->a.xs, tr_apply(m, t->phi, m->car[t->b.xs].elems[i])))
        TR_FAIL(-1, "Transfer %s: StatePullback %s must map every state of %s to a state of %s", t->name, t->phi ? t->phi : "?", t->b.name, t->a.name);
    for (size_t i = 0; i < m->car[t->a.ms].n; i++) if (!in_car(m, t->b.ms, tr_apply(m, t->iota, m->car[t->a.ms].elems[i])))
        TR_FAIL(-1, "Transfer %s: MethodPushforward %s must map every method of %s to a method of %s", t->name, t->iota ? t->iota : "?", t->a.name, t->b.name);
    return 0;
}
/* 0 = RewardLawTV, 1 = ExpectedReward, -1 invalid shape, -2 unsupported metric */
static int tr_metric(const Sx *q, size_t from) {
    int met = 0;
    for (size_t i = from; i < q->n; i++) {
        const Sx *o = q->items[i];
        if (!sx_head_is(o, "Metric") || o->n != 2 || o->items[1]->kind != SX_SYM) return -1;
        if (!strcmp(o->items[1]->text, "RewardLawTV")) met = 0; else if (!strcmp(o->items[1]->text, "ExpectedReward")) met = 1; else return -2;
    }
    return met;
}
static int tr_dist(int met, const Sx *u, const Sx *v, DcRat *d, int *ovf) {
    DcRat p, q;
    if (met == 0) { *d = rq(!sx_equal(u, v), 1); if (!sx_equal(u, v) && !dc_sx_rat(u, &p) && !dc_sx_rat(v, &q) && !dc_rat_cmp(p, q)) *d = rq(0, 1); return 0; }
    if (dc_sx_rat(u, &p) || dc_sx_rat(v, &q)) return 1;
    *d = dc_rat_abs(dc_rat_sub(p, q, ovf)); return 0;
}
static const char *METN[2] = { "RewardLawTV", "ExpectedReward" };
#define TR_LOAD(op) \
    int rc = tr_load(m, q->n >= 2 ? q->items[1] : NULL, &t, why, sizeof why); \
    if (rc == -2) return dc_unsupported(m, "%s: %s", op, why); \
    if (rc) return dc_invalid(m, "%s: %s", op, why);
static Sx *tr_subj(const TrT *t) { return dc_form("Subject", dc_form("Transfer", dc_sym(t->name), NULL), dc_form("Source", dc_sym(t->a.name), NULL), dc_form("Target", dc_sym(t->b.name), NULL), NULL); }

static Sx *tr_check(DcRun *r, const Sx *q) {
    DcModule *m = r->m; TrT t; char why[300]; int ovf = 0;
    if (q->n < 2) return dc_invalid(m, "CheckTransfer: expected (CheckTransfer T (Metric M)?)");
    int met = tr_metric(q, 2);
    if (met == -1) return dc_invalid(m, "CheckTransfer: options must be (Metric Name)");
    if (met == -2) return dc_unsupported(m, "CheckTransfer: only the RewardLawTV and ExpectedReward metrics are evaluated");
    TR_LOAD("CheckTransfer")
    const DcCarrier *XB = &m->car[t.b.xs], *MA = &m->car[t.a.ms];
    /* observers declared on the target must be preserved */
    for (size_t k = 2; k < t.b.d->n; k++) {
        const Sx *o = t.b.d->items[k], *oa = NULL;
        if (!sx_head_is(o, "Observe")) continue;
        if (o->n != 3 || o->items[1]->kind != SX_SYM || o->items[2]->kind != SX_SYM) return dc_invalid(m, "CheckTransfer: MethodSystem %s: expected (Observe name Map)", t.b.name);
        for (size_t j = 2; j < t.a.d->n && !oa; j++) if (sx_head_is(t.a.d->items[j], "Observe") && t.a.d->items[j]->n == 3 && sx_equal(t.a.d->items[j]->items[1], o->items[1])) oa = t.a.d->items[j];
        if (!oa) return dc_invalid(m, "CheckTransfer: observer %s of %s is not declared on %s", o->items[1]->text, t.b.name, t.a.name);
        for (size_t i = 0; i < XB->n; i++) {
            const Sx *b = XB->elems[i], *pb = tr_apply(m, t.phi, b), *vb = tr_apply(m, o->items[2]->text, b), *va = tr_apply(m, oa->items[2]->text, pb);
            if (!va || !vb) return dc_invalid(m, "CheckTransfer: observer %s has no value at some state", o->items[1]->text);
            if (!sx_equal(va, vb)) {
                Sx *ev = dc_form("Evidence", dc_form("Witness", dc_form("Observer", sx_copy(o->items[1]), NULL), dc_form("State", sx_copy(b), NULL),
                                 dc_form("Pulled", sx_copy(pb), NULL), dc_form("Source", sx_copy(va), NULL), dc_form("Target", sx_copy(vb), NULL), NULL), NULL);
                return dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), tr_subj(&t), NULL, ev, NULL);
            }
        }
    }
    DcRat worst = rq(0, 1); size_t wi = 0, wj = 0;
    for (size_t i = 0; i < XB->n; i++) for (size_t j = 0; j < MA->n; j++) {
        const Sx *b = XB->elems[i], *a = MA->elems[j], *pb = tr_apply(m, t.phi, b), *ia = tr_apply(m, t.iota, a); DcRat d;
        if (tr_dist(met, tr_resp(m, &t.a, pb, a), tr_resp(m, &t.b, b, ia), &d, &ovf)) return dc_unsupported(m, "CheckTransfer %s: ExpectedReward needs rational responses", t.name);
        if (dc_rat_cmp(d, worst) > 0) { worst = d; wi = i; wj = j; }
    }
    if (ovf) return dc_unsupported(m, "CheckTransfer %s: rational overflow", t.name);
    Sx *val = dc_form("Value", dc_form("Defect", rsx(worst), NULL), dc_form("Metric", dc_sym(METN[met]), NULL), NULL);
    if (!worst.n)
        return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), tr_subj(&t), val,
                           dc_form("Evidence", dc_form("Pairs", dc_int((long)(XB->n * MA->n)), NULL), NULL), NULL);
    const Sx *b = XB->elems[wi], *a = MA->elems[wj], *pb = tr_apply(m, t.phi, b), *ia = tr_apply(m, t.iota, a);
    Sx *ev = dc_form("Evidence", dc_form("Witness", dc_form("State", sx_copy(b), NULL), dc_form("Method", sx_copy(a), NULL),
                     dc_form("Source", sx_copy(tr_resp(m, &t.a, pb, a)), NULL), dc_form("Target", sx_copy(tr_resp(m, &t.b, b, ia)), NULL),
                     dc_form("Defect", rsx(worst), NULL), NULL), NULL);
    sx_free(val);
    return dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), tr_subj(&t), NULL, ev, NULL);
}
/* max over methods of a rational response; rc 1 if not rational */
static int tr_max(const DcModule *m, const TrSys *s, const Sx *x, const TrT *via, DcRat *out) {
    const DcCarrier *M = &m->car[via ? via->a.ms : s->ms]; int first = 1;
    for (size_t j = 0; j < M->n; j++) {
        const Sx *a = via ? tr_apply(m, via->iota, M->elems[j]) : M->elems[j]; DcRat v;
        if (dc_sx_rat(tr_resp(m, s, x, a), &v)) return 1;
        if (first || dc_rat_cmp(v, *out) > 0) *out = v;
        first = 0;
    }
    return 0;
}
static Sx *tr_vpb(DcRun *r, const Sx *q) {
    DcModule *m = r->m; TrT t; char why[300];
    if (q->n != 2) return dc_invalid(m, "CheckValuePullback: expected (CheckValuePullback T)");
    TR_LOAD("CheckValuePullback")
    const DcCarrier *XB = &m->car[t.b.xs];
    for (size_t i = 0; i < XB->n; i++) {
        const Sx *b = XB->elems[i]; DcRat vb, va;
        if (tr_max(m, &t.b, b, NULL, &vb) || tr_max(m, &t.a, tr_apply(m, t.phi, b), NULL, &va)) return dc_unsupported(m, "CheckValuePullback %s: needs rational responses", t.name);
        if (dc_rat_cmp(va, vb))
            return dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), tr_subj(&t), NULL,
                               dc_form("Evidence", dc_form("Witness", dc_form("State", sx_copy(b), NULL), dc_form("SourceValue", rsx(va), NULL), dc_form("TargetValue", rsx(vb), NULL), NULL), NULL), NULL);
    }
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), tr_subj(&t), NULL,
                       dc_form("Evidence", dc_form("OptimalValues", dc_form("States", dc_int((long)XB->n), NULL), NULL), dc_form("Note", dc_sym("NotATransferCertificate"), NULL), NULL), NULL);
}
static Sx *tr_gap(DcRun *r, const Sx *q) {
    DcModule *m = r->m; TrT t; char why[300]; int ovf = 0;
    if (q->n != 2) return dc_invalid(m, "LibraryGap: expected (LibraryGap T)");
    TR_LOAD("LibraryGap")
    const DcCarrier *XB = &m->car[t.b.xs]; DcRat gap = rq(0, 1); size_t wi = 0;
    for (size_t i = 0; i < XB->n; i++) {
        DcRat all, lib;
        if (tr_max(m, &t.b, XB->elems[i], NULL, &all) || tr_max(m, &t.b, XB->elems[i], &t, &lib)) return dc_unsupported(m, "LibraryGap %s: needs rational responses", t.name);
        DcRat g = dc_rat_sub(all, lib, &ovf);
        if (i == 0 || dc_rat_cmp(g, gap) > 0) { gap = g; wi = i; }
    }
    if (ovf) return dc_unsupported(m, "LibraryGap %s: rational overflow", t.name);
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), tr_subj(&t), dc_form("Value", rsx(gap), NULL),
                       dc_form("Evidence", dc_form("WorstState", sx_copy(XB->elems[wi]), NULL), NULL), NULL);
}
static Sx *tr_compose(DcRun *r, const Sx *q) {
    DcModule *m = r->m; char why[300]; TrT t[8]; int k = 0, met = -1, ovf = 0; DcRat sum = rq(0, 1);
    if (q->n < 3 || q->n > 9) return dc_invalid(m, "ComposeTransfers: expected 2 to 8 (Output Derive Transfer) premises");
    for (size_t i = 1; i < q->n; i++, k++) {
        const Sx *x = q->items[i];
        if (!sx_head_is(x, "Output") || x->n != 3 || x->items[1]->kind != SX_SYM || !sx_is_sym(x->items[2], "Transfer")) return dc_invalid(m, "ComposeTransfers: premise %zu is not (Output Derive Transfer)", i);
        int d = dc_find_derive(m, x->items[1]->text);
        if (d < 0) return dc_invalid(m, "ComposeTransfers: %s names no declared Derive", x->items[1]->text);
        const Sx *res = dc_run_derive(r, d);
        if (!res) return dc_invalid(m, "ComposeTransfers: Derive %s: cyclic reference", x->items[1]->text);
        DcStatus st = dc_result_status(res);
        if (st == DC_UNSUPPORTED) return dc_unsupported(m, "ComposeTransfers: premise Derive %s is Unsupported", x->items[1]->text);
        const Sx *cl = kid(res, "Claim"), *rqq = cl && cl->n >= 2 ? cl->items[1] : NULL;
        if (!rqq || !sx_head_is(rqq, "CheckTransfer")) return dc_invalid(m, "ComposeTransfers: premise %s is not a CheckTransfer", x->items[1]->text);
        if (st != DC_CHECKED) return dc_invalid(m, "ComposeTransfers: premise %s is %s, not Checked (a value-pullback or refuted transfer is not accepted)", x->items[1]->text, dc_status_name(st));
        int pm = tr_metric(rqq, 2); DcRat dv;
        if (met >= 0 && pm != met) return dc_unsupported(m, "ComposeTransfers: premises use different metrics");
        met = pm;
        const Sx *df = kid(kid(res, "Value"), "Defect");
        if (!df || df->n != 2 || dc_sx_rat(df->items[1], &dv)) return dc_invalid(m, "ComposeTransfers: premise %s carries no (Value (Defect d))", x->items[1]->text);
        sum = dc_rat_add(sum, dv, &ovf);
        int rc = tr_load(m, rqq->items[1], &t[k], why, sizeof why);
        if (rc) return dc_invalid(m, "ComposeTransfers: %s", why);
        if (k && strcmp(t[k - 1].b.name, t[k].a.name)) return dc_invalid(m, "ComposeTransfers: %s ends at %s but %s starts at %s", t[k - 1].name, t[k - 1].b.name, t[k].name, t[k].a.name);
    }
    if (ovf) return dc_unsupported(m, "ComposeTransfers: rational overflow");
    const DcCarrier *XC = &m->car[t[k - 1].b.xs], *MA = &m->car[t[0].a.ms];
    Sx *pe = dc_form("Entries", NULL), *ie = dc_form("Entries", NULL), *path = dc_form("Path", NULL);
    int idx = 1, idm = 1;
    for (size_t i = 0; i < XC->n; i++) {
        const Sx *x = XC->elems[i];
        for (int s = k - 1; s >= 0; s--) x = tr_apply(m, t[s].phi, x);
        sx_push(pe, dc_form("Map", sx_copy(XC->elems[i]), sx_copy(x), NULL)); if (!sx_equal(x, XC->elems[i])) idx = 0;
    }
    for (size_t i = 0; i < MA->n; i++) {
        const Sx *a = MA->elems[i];
        for (int s = 0; s < k; s++) a = tr_apply(m, t[s].iota, a);
        sx_push(ie, dc_form("Map", sx_copy(MA->elems[i]), sx_copy(a), NULL)); if (!sx_equal(a, MA->elems[i])) idm = 0;
    }
    for (int s = 0; s < k; s++) sx_push(path, dc_sym(t[s].name));
    Sx *val = dc_form("Value", dc_form("Transfer", dc_form("Source", dc_sym(t[0].a.name), NULL), dc_form("Target", dc_sym(t[k - 1].b.name), NULL),
                      dc_form("StatePullback", pe, dc_form("Identity", dc_sym(idx ? "True" : "False"), NULL), NULL),
                      dc_form("MethodPushforward", ie, dc_form("Identity", dc_sym(idm ? "True" : "False"), NULL), NULL),
                      dc_form("Defect", rsx(sum), NULL), dc_form("Metric", dc_sym(METN[met < 0 ? 0 : met]), NULL), NULL), NULL);
    Sx *subj = dc_form("Subject", dc_form("Composite", NULL), NULL);
    for (int s = 0; s < k; s++) sx_push(subj->items[1], dc_sym(t[s].name));
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), subj, val, dc_form("Evidence", dc_form("Composition", dc_form("Rule", dc_sym("PolyComposition"), NULL), path, NULL), NULL), NULL);
}
Sx *dc_req_transfers(DcRun *r, const Sx *q, const char *h) {
    if (!strcmp(h, "CheckTransfer")) return tr_check(r, q);
    if (!strcmp(h, "CheckValuePullback")) return tr_vpb(r, q);
    if (!strcmp(h, "LibraryGap")) return tr_gap(r, q);
    if (!strcmp(h, "ComposeTransfers")) return tr_compose(r, q);
    return dc_unsupported(r->m, "%s is not evaluated yet in the M6 Transfers subset", h);
}
