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
/* ---- CheckTransferHive (spec 10.4): (TransferHive H (Member S)... (Edge T)... (Cycle S1 ... Sk)... (Gauge S Symmetry)...).
 * Checked iff every edge transfer is exact (RewardLawTV defect 0), every declared Symmetry is a bijective symmetry of
 * its member's response, the gauge groups (closure of the declared symmetries) are intertwined by every edge, and the
 * holonomy around every declared cycle (composite pullback and pushforward at the first member) lies in that
 * member's gauge group.  Without a declared gauge the group is trivial, so a non-identity holonomy is a witness. */
#define TH_MAXM 8
#define TH_MAXE 16
#define TH_MAXG 32
#define TH_MAXV 64
typedef struct { int s[TH_MAXV], a[TH_MAXV]; } Perm;
typedef struct { TrSys sys; int ns, na, ng; Perm g[TH_MAXG]; } ThMem;
typedef struct { TrT t; int src, tgt, phi[TH_MAXV], iota[TH_MAXV]; } ThEdge;
static ThMem th_m[TH_MAXM]; static ThEdge th_e[TH_MAXE]; static Perm th_gen[TH_MAXM][TH_MAXG];
static int th_idx(const DcModule *m, int c, const Sx *v) { for (size_t i = 0; v && i < m->car[c].n; i++) if (sx_equal(m->car[c].elems[i], v)) return (int)i; return -1; }
static int th_tab(const DcModule *m, const char *map, int c1, int c2, int *out) {
    for (size_t i = 0; i < m->car[c1].n; i++) if ((out[i] = th_idx(m, c2, tr_apply(m, map, m->car[c1].elems[i]))) < 0) return -1;
    return 0;
}
static int th_eq(const Perm *p, const Perm *q, int ns, int na) { return !memcmp(p->s, q->s, (size_t)ns * sizeof(int)) && !memcmp(p->a, q->a, (size_t)na * sizeof(int)); }
static int th_find(const ThMem *M, const Perm *p) { for (int i = 0; i < M->ng; i++) if (th_eq(&M->g[i], p, M->ns, M->na)) return i; return -1; }
static int th_mi(int nm, const char *n) { for (int i = 0; n && i < nm; i++) if (!strcmp(th_m[i].sys.name, n)) return i; return -1; }
static Sx *th_ent(const DcModule *m, int c, const int *f) {
    Sx *e = dc_form("Entries", NULL);
    for (size_t i = 0; i < m->car[c].n; i++) sx_push(e, dc_form("Map", sx_copy(m->car[c].elems[i]), sx_copy(m->car[c].elems[f[i]]), NULL));
    return e;
}
static int th_inter(const ThEdge *E, const ThMem *A, const ThMem *B, const Perm *ga, const Perm *gb) {
    for (int b = 0; b < B->ns; b++) if (E->phi[gb->s[b]] != ga->s[E->phi[b]]) return 0;
    for (int a = 0; a < A->na; a++) if (E->iota[ga->a[a]] != gb->a[E->iota[a]]) return 0;
    return 1;
}
static Sx *th_subj(const char *hn) { return dc_form("Subject", dc_form("TransferHive", dc_sym(hn), NULL), NULL); }
static Sx *th_fail(DcModule *m, const Sx *q, const char *hn, Sx *wit) {
    return dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), th_subj(hn), NULL, dc_form("Evidence", wit, NULL), NULL);
}
static Sx *tr_hive(DcRun *r, const Sx *q) {
    DcModule *m = r->m; char why[300]; int nm = 0, ne = 0, ovf = 0, ngen[TH_MAXM] = {0};
    if (q->n != 2 || q->items[1]->kind != SX_SYM) return dc_invalid(m, "CheckTransferHive: expected (CheckTransferHive Name)");
    const Sx *d = decl(m, "TransferHive", q->items[1]->text);
    if (!d) return dc_invalid(m, "CheckTransferHive: %s names no declared TransferHive", q->items[1]->text);
    const char *hn = d->items[1]->text;
    for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Member")) {
        const Sx *x = d->items[i];
        if (x->n != 2 || x->items[1]->kind != SX_SYM) return dc_invalid(m, "CheckTransferHive %s: expected (Member MethodSystem)", hn);
        if (nm >= TH_MAXM) return dc_unsupported(m, "CheckTransferHive %s: more than %d members", hn, TH_MAXM);
        ThMem *M = &th_m[nm];
        if (tr_sys(m, x->items[1]->text, &M->sys, why, sizeof why)) return dc_invalid(m, "CheckTransferHive %s: %s", hn, why);
        if (th_mi(nm, M->sys.name) >= 0) return dc_invalid(m, "CheckTransferHive %s: Member %s declared twice", hn, M->sys.name);
        M->ns = (int)m->car[M->sys.xs].n; M->na = (int)m->car[M->sys.ms].n;
        if (M->ns > TH_MAXV || M->na > TH_MAXV) return dc_unsupported(m, "CheckTransferHive %s: carriers above %d values", hn, TH_MAXV);
        M->ng = 1; for (int s = 0; s < M->ns; s++) M->g[0].s[s] = s; for (int a = 0; a < M->na; a++) M->g[0].a[a] = a;
        nm++;
    }
    if (nm < 2) return dc_invalid(m, "CheckTransferHive %s: needs at least two Members", hn);
    for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Gauge")) {
        const Sx *x = d->items[i]; int mi;
        if (x->n != 3 || x->items[1]->kind != SX_SYM || x->items[2]->kind != SX_SYM || (mi = th_mi(nm, x->items[1]->text)) < 0)
            return dc_invalid(m, "CheckTransferHive %s: expected (Gauge Member Symmetry) on a declared member", hn);
        ThMem *M = &th_m[mi]; const Sx *sy = decl(m, "Symmetry", x->items[2]->text);
        if (!sy || !arg1(sy, "Of") || strcmp(arg1(sy, "Of"), M->sys.name)) return dc_invalid(m, "CheckTransferHive %s: Symmetry %s is not declared Of %s", hn, x->items[2]->text, M->sys.name);
        if (ngen[mi] >= TH_MAXG) return dc_unsupported(m, "CheckTransferHive %s: too many gauge generators", hn);
        Perm *p = &th_gen[mi][ngen[mi]]; int seen[TH_MAXV];
        if (th_tab(m, arg1(sy, "States"), M->sys.xs, M->sys.xs, p->s) || th_tab(m, arg1(sy, "Methods"), M->sys.ms, M->sys.ms, p->a))
            return dc_invalid(m, "CheckTransferHive %s: Symmetry %s: (States map) and (Methods map) must be total on the carriers of %s", hn, x->items[2]->text, M->sys.name);
        memset(seen, 0, sizeof seen); for (int s = 0; s < M->ns; s++) seen[p->s[s]]++;
        for (int s = 0; s < M->ns; s++) if (seen[s] != 1) return dc_invalid(m, "CheckTransferHive %s: Symmetry %s: States map is not a bijection", hn, x->items[2]->text);
        memset(seen, 0, sizeof seen); for (int a = 0; a < M->na; a++) seen[p->a[a]]++;
        for (int a = 0; a < M->na; a++) if (seen[a] != 1) return dc_invalid(m, "CheckTransferHive %s: Symmetry %s: Methods map is not a bijection", hn, x->items[2]->text);
        const DcCarrier *X = &m->car[M->sys.xs], *A = &m->car[M->sys.ms];
        for (int s = 0; s < M->ns; s++) for (int a = 0; a < M->na; a++)
            if (!sx_equal(tr_resp(m, &M->sys, X->elems[p->s[s]], A->elems[p->a[a]]), tr_resp(m, &M->sys, X->elems[s], A->elems[a])))
                return th_fail(m, q, hn, dc_form("Witness", dc_form("NotASymmetry", dc_sym(x->items[2]->text), NULL), dc_form("State", sx_copy(X->elems[s]), NULL), dc_form("Method", sx_copy(A->elems[a]), NULL), NULL));
        ngen[mi]++;
    }
    for (int i = 0; i < nm; i++) {   /* gauge group = closure of the generators */
        ThMem *M = &th_m[i];
        for (int g = 0; g < M->ng; g++) for (int j = 0; j < ngen[i]; j++) {
            Perm p; const Perm *G = &th_gen[i][j];
            for (int s = 0; s < M->ns; s++) p.s[s] = G->s[M->g[g].s[s]];
            for (int a = 0; a < M->na; a++) p.a[a] = G->a[M->g[g].a[a]];
            if (th_find(M, &p) < 0) { if (M->ng >= TH_MAXG) return dc_unsupported(m, "CheckTransferHive %s: gauge group of %s above %d elements", hn, M->sys.name, TH_MAXG); M->g[M->ng++] = p; }
        }
    }
    for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Edge")) {
        const Sx *x = d->items[i];
        if (x->n != 2) return dc_invalid(m, "CheckTransferHive %s: expected (Edge Transfer)", hn);
        if (ne >= TH_MAXE) return dc_unsupported(m, "CheckTransferHive %s: more than %d edges", hn, TH_MAXE);
        ThEdge *E = &th_e[ne];
        if (tr_load(m, x->items[1], &E->t, why, sizeof why)) return dc_invalid(m, "CheckTransferHive %s: %s", hn, why);
        if ((E->src = th_mi(nm, E->t.a.name)) < 0 || (E->tgt = th_mi(nm, E->t.b.name)) < 0) return dc_invalid(m, "CheckTransferHive %s: Edge %s joins a non-member", hn, E->t.name);
        if (th_tab(m, E->t.phi, E->t.b.xs, E->t.a.xs, E->phi) || th_tab(m, E->t.iota, E->t.a.ms, E->t.b.ms, E->iota)) return dc_invalid(m, "CheckTransferHive %s: Edge %s maps are not total", hn, E->t.name);
        const DcCarrier *XB = &m->car[E->t.b.xs], *MA = &m->car[E->t.a.ms];
        for (size_t b = 0; b < XB->n; b++) for (size_t a = 0; a < MA->n; a++) {
            DcRat dd; tr_dist(0, tr_resp(m, &E->t.a, m->car[E->t.a.xs].elems[E->phi[b]], MA->elems[a]), tr_resp(m, &E->t.b, XB->elems[b], m->car[E->t.b.ms].elems[E->iota[a]]), &dd, &ovf);
            if (dd.n) return th_fail(m, q, hn, dc_form("Witness", dc_form("InexactEdge", dc_sym(E->t.name), NULL), dc_form("State", sx_copy(XB->elems[b]), NULL), dc_form("Method", sx_copy(MA->elems[a]), NULL), NULL));
        }
        ne++;
    }
    for (int e = 0; e < ne; e++) {   /* intertwining: every gauge element on either end has a partner on the other */
        const ThEdge *E = &th_e[e]; const ThMem *A = &th_m[E->src], *B = &th_m[E->tgt];
        for (int side = 0; side < 2; side++) {
            const ThMem *P = side ? A : B, *O = side ? B : A;
            for (int i = 0; i < P->ng; i++) {
                int ok = 0;
                for (int j = 0; j < O->ng && !ok; j++) ok = side ? th_inter(E, A, B, &P->g[i], &O->g[j]) : th_inter(E, A, B, &O->g[j], &P->g[i]);
                if (!ok) return th_fail(m, q, hn, dc_form("Witness", dc_form("NotIntertwined", dc_sym(E->t.name), NULL), dc_form("Member", dc_sym(P->sys.name), NULL),
                                                       dc_form("States", th_ent(m, P->sys.xs, P->g[i].s), NULL), dc_form("Methods", th_ent(m, P->sys.ms, P->g[i].a), NULL), NULL));
            }
        }
    }
    Sx *hols = dc_form("Value", NULL); int ncyc = 0;
    for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Cycle")) {
        const Sx *x = d->items[i]; int k = (int)x->n - 1, cyc[TH_MAXM * 4], eix[TH_MAXM * 4];
        if (k < 2 || k > TH_MAXM * 4) { sx_free(hols); return dc_invalid(m, "CheckTransferHive %s: a Cycle needs 2 or more members", hn); }
        for (int j = 0; j < k; j++) if (x->items[j + 1]->kind != SX_SYM || (cyc[j] = th_mi(nm, x->items[j + 1]->text)) < 0) { sx_free(hols); return dc_invalid(m, "CheckTransferHive %s: Cycle entry %d is not a member", hn, j + 1); }
        for (int j = 0; j < k; j++) {
            eix[j] = -1;
            for (int e = 0; e < ne && eix[j] < 0; e++) if (th_e[e].src == cyc[j] && th_e[e].tgt == cyc[(j + 1) % k]) eix[j] = e;
            if (eix[j] < 0) { sx_free(hols); return dc_invalid(m, "CheckTransferHive %s: no Edge from %s to %s on the Cycle", hn, th_m[cyc[j]].sys.name, th_m[cyc[(j + 1) % k]].sys.name); }
        }
        const ThMem *U = &th_m[cyc[0]]; Perm h;
        for (int s = 0; s < U->ns; s++) { int y = s; for (int j = k - 1; j >= 0; j--) y = th_e[eix[j]].phi[y]; h.s[s] = y; }
        for (int a = 0; a < U->na; a++) { int y = a; for (int j = 0; j < k; j++) y = th_e[eix[j]].iota[y]; h.a[a] = y; }
        Sx *ho = dc_form("Holonomy", sx_copy(x), dc_form("States", th_ent(m, U->sys.xs, h.s), NULL), dc_form("Methods", th_ent(m, U->sys.ms, h.a), NULL), NULL);
        /* spec Def 10.2: the holonomy (phi, iota) lies in the gauge when (phi, iota^-1) is in G */
        Perm hg; int bij = 1, hit[TH_MAXV] = {0};
        for (int s = 0; s < U->ns; s++) hg.s[s] = h.s[s];
        for (int a = 0; a < U->na; a++) { if (hit[h.a[a]]++) bij = 0; hg.a[h.a[a]] = a; }
        if (!bij || th_find(U, &hg) < 0) { sx_free(hols); return th_fail(m, q, hn, dc_form("Witness", ho, dc_form("OutsideGauge", dc_sym(U->sys.name), dc_form("Order", dc_int(U->ng), NULL), NULL), NULL)); }
        sx_push(hols, ho); ncyc++;
    }
    Sx *ord = dc_form("GaugeOrders", NULL);
    for (int i = 0; i < nm; i++) sx_push(ord, dc_form(th_m[i].sys.name, dc_int(th_m[i].ng), NULL));
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), th_subj(hn), hols,
                       dc_form("Evidence", dc_form("ExactEdges", dc_int(ne), NULL), dc_form("Intertwined", dc_sym("True"), NULL), dc_form("Cycles", dc_int(ncyc), NULL), ord, NULL), NULL);
}
/* ---- KernelOf (spec 10.4, derived kernel hive of a transfer hive), crisp case.
 * Nodes are (member, state).  Member tolerance alpha(x, x') = 1 - max_m |r(x, m) - r(x', m)|; an Edge T (A -> B)
 * gives the correspondence c(x, y) = 1 - max_m |r_A(x, m) - r_B(y, iota m)|.  With (Saturate Gauge) the member
 * tolerance is alpha^G(x, x') = max over the gauge group g of 1 - max_m |r(x, m) - r(x', g m)|, and the cross block is
 * the crisp composite alpha_A o c o alpha_B.  Degrees other than 0/1 answer Unsupported (-2). */
static int kd(const DcModule *m, const TrSys *A, int x, const TrSys *B, int y, const int *f, int *out) {
    const DcCarrier *MA = &m->car[A->ms], *MB = &m->car[B->ms]; DcRat worst = rq(0, 1); int ovf = 0;
    for (size_t a = 0; a < MA->n; a++) {
        DcRat p, q;
        if (dc_sx_rat(tr_resp(m, A, m->car[A->xs].elems[x], MA->elems[a]), &p) || dc_sx_rat(tr_resp(m, B, m->car[B->xs].elems[y], MB->elems[f ? f[a] : (int)a]), &q)) return -2;
        DcRat dd = dc_rat_abs(dc_rat_sub(p, q, &ovf));
        if (dc_rat_cmp(dd, worst) > 0) worst = dd;
    }
    if (ovf) return -2;
    if (dc_rat_cmp(worst, rq(1, 1)) >= 0) { *out = 0; return 0; }
    if (!worst.n) { *out = 1; return 0; }
    return -3;
}
int dc_kernel_of(const DcModule *m, const Sx *req, const char **names, int *cars, int *nvs, int *nmo, signed char H[64][64], char *why, size_t wn) {
    static unsigned char al[TH_MAXM][TH_MAXV][TH_MAXV], cc[TH_MAXV][TH_MAXV];
    int nm = 0, sat = 0, base[TH_MAXM], nn = 0, ngen[TH_MAXM] = {0}, rc, v, iot[TH_MAXV];
    if (!sx_head_is(req, "KernelOf") || req->n < 2 || req->items[1]->kind != SX_SYM) TR_FAIL(-1, "expected (KernelOf TransferHive (Saturate Gauge)?)");
    for (size_t i = 2; i < req->n; i++) {
        const Sx *o = req->items[i];
        if (sx_head_is(o, "Saturate") && o->n == 2 && sx_is_sym(o->items[1], "Gauge")) sat = 1;
        else TR_FAIL(-2, "KernelOf: only the (Saturate Gauge) option is evaluated");
    }
    const Sx *d = decl(m, "TransferHive", req->items[1]->text);
    if (!d) TR_FAIL(-1, "KernelOf: %s names no declared TransferHive", req->items[1]->text);
    const char *hn = d->items[1]->text;
    for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Member")) {
        const Sx *x = d->items[i];
        if (x->n != 2 || x->items[1]->kind != SX_SYM) TR_FAIL(-1, "KernelOf %s: expected (Member MethodSystem)", hn);
        if (nm >= TH_MAXM) TR_FAIL(-2, "KernelOf %s: more than %d members", hn, TH_MAXM);
        ThMem *M = &th_m[nm];
        if ((rc = tr_sys(m, x->items[1]->text, &M->sys, why, wn))) return rc;
        if (th_mi(nm, M->sys.name) >= 0) TR_FAIL(-1, "KernelOf %s: Member %s declared twice", hn, M->sys.name);
        M->ns = (int)m->car[M->sys.xs].n; M->na = (int)m->car[M->sys.ms].n;
        if (M->na > TH_MAXV || nn + M->ns > 64) TR_FAIL(-2, "KernelOf %s: more than 64 nodes", hn);
        M->ng = 1; for (int s = 0; s < M->ns; s++) M->g[0].s[s] = s; for (int a = 0; a < M->na; a++) M->g[0].a[a] = a;
        base[nm] = nn; nn += M->ns; names[nm] = M->sys.name; cars[nm] = M->sys.xs; nvs[nm] = M->ns; nm++;
    }
    if (nm < 2) TR_FAIL(-1, "KernelOf %s: needs at least two Members", hn);
    if (sat) {
        for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Gauge")) {
            const Sx *x = d->items[i]; int mi, seen[TH_MAXV];
            if (x->n != 3 || x->items[1]->kind != SX_SYM || x->items[2]->kind != SX_SYM || (mi = th_mi(nm, x->items[1]->text)) < 0) TR_FAIL(-1, "KernelOf %s: expected (Gauge Member Symmetry)", hn);
            ThMem *M = &th_m[mi]; const Sx *sy = decl(m, "Symmetry", x->items[2]->text);
            if (!sy || !arg1(sy, "Of") || strcmp(arg1(sy, "Of"), M->sys.name)) TR_FAIL(-1, "KernelOf %s: Symmetry %s is not declared Of %s", hn, x->items[2]->text, M->sys.name);
            if (ngen[mi] >= TH_MAXG) TR_FAIL(-2, "KernelOf %s: too many gauge generators", hn);
            Perm *p = &th_gen[mi][ngen[mi]];
            if (th_tab(m, arg1(sy, "States"), M->sys.xs, M->sys.xs, p->s) || th_tab(m, arg1(sy, "Methods"), M->sys.ms, M->sys.ms, p->a)) TR_FAIL(-1, "KernelOf %s: Symmetry %s maps are not total", hn, x->items[2]->text);
            memset(seen, 0, sizeof seen); for (int a = 0; a < M->na; a++) seen[p->a[a]]++;
            for (int a = 0; a < M->na; a++) if (seen[a] != 1) TR_FAIL(-1, "KernelOf %s: Symmetry %s: Methods map is not a bijection", hn, x->items[2]->text);
            const DcCarrier *X = &m->car[M->sys.xs], *A = &m->car[M->sys.ms];
            for (int s = 0; s < M->ns; s++) for (int a = 0; a < M->na; a++)
                if (!sx_equal(tr_resp(m, &M->sys, X->elems[p->s[s]], A->elems[p->a[a]]), tr_resp(m, &M->sys, X->elems[s], A->elems[a])))
                    TR_FAIL(-1, "KernelOf %s: Symmetry %s does not preserve the response of %s", hn, x->items[2]->text, M->sys.name);
            ngen[mi]++;
        }
        for (int i = 0; i < nm; i++) {
            ThMem *M = &th_m[i];
            for (int g = 0; g < M->ng; g++) for (int j = 0; j < ngen[i]; j++) {
                Perm p; const Perm *G = &th_gen[i][j];
                for (int s = 0; s < M->ns; s++) p.s[s] = G->s[M->g[g].s[s]];
                for (int a = 0; a < M->na; a++) p.a[a] = G->a[M->g[g].a[a]];
                if (th_find(M, &p) < 0) { if (M->ng >= TH_MAXG) TR_FAIL(-2, "KernelOf %s: gauge group above %d elements", hn, TH_MAXG); M->g[M->ng++] = p; }
            }
        }
    }
    for (int a = 0; a < 64; a++) for (int b = 0; b < 64; b++) H[a][b] = -1;
    for (int i = 0; i < nm; i++) {
        ThMem *M = &th_m[i];
        for (int x = 0; x < M->ns; x++) for (int y = 0; y < M->ns; y++) {
            int best = 0;
            for (int g = 0; g < (sat ? M->ng : 1); g++) {
                rc = kd(m, &M->sys, x, &M->sys, y, M->g[g].a, &v);
                if (rc == -2) TR_FAIL(-2, "KernelOf %s: member tolerances need rational responses", hn);
                if (rc == -3) TR_FAIL(-2, "KernelOf %s: graded member tolerance (crisp 0/1 degrees only)", hn);
                best |= v;
            }
            al[i][x][y] = (unsigned char)best; H[base[i] + x][base[i] + y] = (signed char)best;
        }
    }
    for (size_t k = 2; k < d->n; k++) if (sx_head_is(d->items[k], "Edge")) {
        const Sx *x = d->items[k]; TrT t; int i, j;
        if (x->n != 2) TR_FAIL(-1, "KernelOf %s: expected (Edge Transfer)", hn);
        if ((rc = tr_load(m, x->items[1], &t, why, wn))) return rc;
        if ((i = th_mi(nm, t.a.name)) < 0 || (j = th_mi(nm, t.b.name)) < 0 || i == j) TR_FAIL(-1, "KernelOf %s: Edge %s must join two distinct members", hn, t.name);
        if (th_tab(m, t.iota, t.a.ms, t.b.ms, iot)) TR_FAIL(-1, "KernelOf %s: Edge %s pushforward is not total", hn, t.name);
        const ThMem *A = &th_m[i], *B = &th_m[j];
        for (int a = 0; a < A->ns; a++) for (int b = 0; b < B->ns; b++) {
            rc = kd(m, &t.a, a, &t.b, b, iot, &v);
            if (rc == -2) TR_FAIL(-2, "KernelOf %s: correspondences need rational responses", hn);
            if (rc == -3) TR_FAIL(-2, "KernelOf %s: graded correspondence on Edge %s (crisp 0/1 degrees only)", hn, t.name);
            cc[a][b] = (unsigned char)v;
        }
        for (int a = 0; a < A->ns; a++) for (int b = 0; b < B->ns; b++) {
            int val = cc[a][b];
            if (sat) { val = 0; for (int u = 0; u < A->ns; u++) for (int w = 0; w < B->ns; w++) if (al[i][a][u] && cc[u][w] && al[j][w][b]) val = 1; }
            int P = base[i] + a, Q = base[j] + b;
            if (H[P][Q] >= 0 && H[P][Q] != val) TR_FAIL(-2, "KernelOf %s: conflicting edges between %s and %s", hn, A->sys.name, B->sys.name);
            H[P][Q] = H[Q][P] = (signed char)val;
        }
    }
    *nmo = nm;
    return 0;
}
/* review-1 F4: (KernelOf TransferHive (Saturate Gauge)?) as a request.  Checked, with a construction certificate:
 * the member list, every node, and every block-kernel entry (Kernel 1 = related, 0 = not, Unmeasured = no edge). */
static Sx *tr_kernelof(DcRun *r, const Sx *q) {
    DcModule *m = r->m; char why[300]; const char *names[TH_MAXM]; int cars[TH_MAXM], nvs[TH_MAXM], nm = 0, base[TH_MAXM], nn = 0;
    static signed char H[64][64];
    int rc = dc_kernel_of(m, q, names, cars, nvs, &nm, H, why, sizeof why);
    if (rc == -1) return dc_invalid(m, "%s", why);
    if (rc) return dc_unsupported(m, "%s", why);
    Sx *mem = dc_form("Members", NULL), *nodes = dc_form("Nodes", NULL), *ent = dc_form("Entries", NULL);
    for (int i = 0; i < nm; i++) {
        base[i] = nn; nn += nvs[i];
        sx_push(mem, dc_form("Member", dc_sym(names[i]), dc_sym(m->car[cars[i]].name), dc_form("States", dc_int((long)nvs[i]), NULL), NULL));
        for (int v = 0; v < nvs[i]; v++) sx_push(nodes, dc_form("Node", dc_sym(names[i]), sx_copy(m->car[cars[i]].elems[v]), NULL));
    }
    long ones = 0, unm = 0;
    for (int i = 0; i < nm; i++) for (int j = i; j < nm; j++) for (int a = 0; a < nvs[i]; a++) for (int b = 0; b < nvs[j]; b++) {
        int P = base[i] + a, Q = base[j] + b; if (P > Q) continue;
        Sx *e = dc_form("Entry", dc_form("Node", dc_sym(names[i]), sx_copy(m->car[cars[i]].elems[a]), NULL),
                        dc_form("Node", dc_sym(names[j]), sx_copy(m->car[cars[j]].elems[b]), NULL),
                        H[P][Q] < 0 ? dc_sym("Unmeasured") : dc_int((long)H[P][Q]), NULL);
        if (H[P][Q] < 0) unm++; else if (H[P][Q]) ones++;
        sx_push(ent, e);
    }
    Sx *subj = dc_form("Subject", dc_form("TransferHive", sx_copy(q->items[1]), NULL), NULL);
    Sx *val = dc_form("Value", dc_form("KernelHive", mem, NULL), NULL);
    Sx *ev = dc_form("Evidence", dc_form("Construction", dc_form("Kind", dc_sym("KernelOf"), NULL), nodes, ent,
                     dc_form("Related", dc_int(ones), NULL), dc_form("Unmeasured", dc_int(unm), NULL), NULL), NULL);
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), subj, val, ev, NULL);
}
Sx *dc_req_transfers(DcRun *r, const Sx *q, const char *h) {
    if (!strcmp(h, "KernelOf")) return tr_kernelof(r, q);
    if (!strcmp(h, "CheckTransferHive")) return tr_hive(r, q);
    if (!strcmp(h, "CheckTransfer")) return tr_check(r, q);
    if (!strcmp(h, "CheckValuePullback")) return tr_vpb(r, q);
    if (!strcmp(h, "LibraryGap")) return tr_gap(r, q);
    if (!strcmp(h, "ComposeTransfers")) return tr_compose(r, q);
    return dc_unsupported(r->m, "%s is not evaluated yet in the M6 Transfers subset", h);
}
