#include "ops_internal.h"
#include "ops_run.h"
#include "binding.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* M6 (opt-in, beyond release only): affine contracts, spec section 9.
 * (Implementation I (Ideal f) (Actual f-hat) (Audit X) (InputDistance D) (OutputDistance E)) is read from
 * m->source.  (CheckImplementation I (Grade L eta)) is Checked iff for every ordered audited pair (xh, x)
 * E(f-hat(xh), f(x)) <= L * D(xh, x) + eta, else Refuted with the violating pair.  (ThenContracts P Q)
 * composes two Checked CheckImplementation premises by Proposition 9.1: grade (Lq Lp, Lq etap + etaq),
 * after the binding check (P's output distance is Q's input distance and every value P's Ideal and
 * Actual produce on its audit set lies in Q's audit carrier).  Only OneMinusAbsoluteDifference
 * distances are evaluated here; other distances answer Unsupported. */
static Sx *rsx(DcRat r) { return dc_form("Rat", dc_int((long)r.n), dc_int((long)r.d), NULL); }
static const Sx *kid(const Sx *x, const char *h) {
    if (!x || x->kind != SX_LIST) return NULL;
    for (size_t i = 1; i < x->n; i++) if (sx_head_is(x->items[i], h)) return x->items[i];
    return NULL;
}
static const char *ct_sym(const Sx *d, const char *h) { const Sx *k = kid(d, h); return k && k->n == 2 && k->items[1]->kind == SX_SYM ? k->items[1]->text : NULL; }
typedef struct { const char *name; int ideal, actual, audit, tin, tout; } CtImpl;
static int ct_load(const DcModule *m, const char *name, CtImpl *c, char *why, size_t wn) {
    const Sx *d = NULL;
    for (size_t i = 2; m->source && i < m->source->n; i++)
        if (sx_head_is(m->source->items[i], "Implementation") && m->source->items[i]->n >= 2 && sx_is_sym(m->source->items[i]->items[1], name)) { d = m->source->items[i]; break; }
    if (!d) { snprintf(why, wn, "names no declared Implementation (%s)", name); return -1; }
    const char *ia = ct_sym(d, "Ideal"), *aa = ct_sym(d, "Actual"), *au = ct_sym(d, "Audit"), *di = ct_sym(d, "InputDistance"), *dout = ct_sym(d, "OutputDistance");
    if (!ia || !aa || !au || !di || !dout) { snprintf(why, wn, "Implementation %s needs Ideal, Actual, Audit, InputDistance and OutputDistance", name); return -1; }
    c->name = name; c->ideal = dc_find_map(m, ia); c->actual = dc_find_map(m, aa); c->audit = dc_find_carrier(m, au); c->tin = dc_find_tol(m, di); c->tout = dc_find_tol(m, dout);
    if (c->ideal < 0 || c->actual < 0) { snprintf(why, wn, "Implementation %s: Ideal/Actual names no declared Map", name); return -1; }
    if (c->audit < 0) { snprintf(why, wn, "Implementation %s: Audit names no declared Carrier", name); return -1; }
    if (c->tin < 0 || c->tout < 0) { snprintf(why, wn, "Implementation %s: a distance names no declared Tolerance", name); return -1; }
    if (m->tol[c->tin].kind != DC_TOL_ONE_MINUS_ABS || m->tol[c->tout].kind != DC_TOL_ONE_MINUS_ABS) { snprintf(why, wn, "Implementation %s: only OneMinusAbsoluteDifference distances are evaluated", name); return -2; }
    if (m->map[c->ideal].from != c->audit || m->map[c->actual].from != c->audit) { snprintf(why, wn, "Implementation %s: Ideal and Actual must map from the Audit carrier", name); return -1; }
    return 0;
}
static int ct_val(const DcModule *m, int car, int i, DcRat *v) { return i < 0 || (size_t)i >= m->car[car].n || dc_sx_rat(m->car[car].elems[i], v); }
static int ct_out(const DcModule *m, int map, int i, DcRat *v) { const DcMap *f = &m->map[map]; return ct_val(m, f->to, f->table[i], v); }
static int ct_grade(const Sx *g, DcRat *L, DcRat *e) {
    return !sx_head_is(g, "Grade") || g->n != 3 || dc_sx_rat(g->items[1], L) || dc_sx_rat(g->items[2], e) || L->n < 0 || e->n < 0;
}
static Sx *ct_check(DcRun *r, const Sx *q) {
    DcModule *m = r->m; char why[240]; CtImpl c; DcRat L, eta; int ovf = 0;
    if (q->n != 3 || q->items[1]->kind != SX_SYM || ct_grade(q->items[2], &L, &eta))
        return dc_invalid(m, "CheckImplementation: expected (CheckImplementation Implementation (Grade L eta)) with L, eta >= 0");
    int rc = ct_load(m, q->items[1]->text, &c, why, sizeof why);
    if (rc == -2) return dc_unsupported(m, "CheckImplementation: %s", why);
    if (rc) return dc_invalid(m, "CheckImplementation: %s", why);
    size_t n = m->car[c.audit].n;
    Sx *subj = dc_form("Subject", dc_form("Implementation", dc_sym(c.name), NULL), NULL);
    for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++) {
        DcRat a, b, u, v;
        if (ct_val(m, c.audit, (int)i, &a) || ct_val(m, c.audit, (int)j, &b) || ct_out(m, c.actual, (int)i, &u) || ct_out(m, c.ideal, (int)j, &v)) { sx_free(subj); return dc_unsupported(m, "CheckImplementation %s: an audited value is not rational", c.name); }
        DcRat din = dc_rat_abs(dc_rat_sub(a, b, &ovf)), dout = dc_rat_abs(dc_rat_sub(u, v, &ovf)), bound = dc_rat_add(dc_rat_mul(L, din, &ovf), eta, &ovf);
        if (ovf) { sx_free(subj); return dc_unsupported(m, "CheckImplementation %s: rational overflow", c.name); }
        if (dc_rat_cmp(dout, bound) > 0) {
            Sx *w = dc_form("Witness", dc_form("Pair", dc_form("Audited", rsx(a), NULL), dc_form("Reference", rsx(b), NULL), NULL),
                            dc_form("OutputGap", rsx(dout), NULL), dc_form("Bound", rsx(bound), NULL), NULL);
            return dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), subj, NULL, dc_form("Evidence", w, NULL), "an audited pair violates the affine bound");
        }
    }
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), subj, dc_form("Value", dc_form("Grade", rsx(L), rsx(eta), NULL), NULL),
                       dc_form("Evidence", dc_form("AuditedPairs", dc_int((int)(n * n)), NULL), NULL), NULL);
}
/* Resolve (Output D Value) to a Checked/Conditional Derive slot (mirrors ops_abs.c output_slot). */
static int ct_slot(DcRun *r, const Sx *x, char *why, size_t wn) {
    if (!sx_head_is(x, "Output") || x->n != 3 || x->items[1]->kind != SX_SYM || !sx_is_sym(x->items[2], "Value")) { snprintf(why, wn, "expected (Output Derive Value)"); return -1; }
    int d = dc_find_derive(r->m, x->items[1]->text);
    if (d < 0) { snprintf(why, wn, "names no declared Derive (%s)", x->items[1]->text); return -1; }
    const Sx *res = dc_run_derive(r, d);
    if (!res) { snprintf(why, wn, "Derive %s: cyclic reference", x->items[1]->text); return -1; }
    DcStatus st = dc_result_status(res);
    if (st == DC_UNSUPPORTED) { snprintf(why, wn, "premise Derive %s is Unsupported", x->items[1]->text); return -2; }
    if (st != DC_CHECKED && st != DC_CONDITIONAL) { snprintf(why, wn, "Derive %s is neither Checked nor Conditional (%s)", x->items[1]->text, dc_status_name(st)); return -3; }
    return d;
}
static Sx *ct_then(DcRun *r, const Sx *q) {
    DcModule *m = r->m; char why[240]; CtImpl c[2]; DcRat L[2], e[2]; int ovf = 0;
    if (q->n != 3) return dc_invalid(m, "ThenContracts: expected (ThenContracts (Output First Value) (Output Second Value))");
    for (int k = 0; k < 2; k++) {
        int d = ct_slot(r, q->items[1 + k], why, sizeof why);
        if (d == -2) return dc_unsupported(m, "ThenContracts: %s", why);
        if (d == -3) return dc_invalid(m, "ThenContracts: %s", why);
        if (d < 0) return dc_invalid(m, "ThenContracts: %s", why);
        const Sx *res = dc_run_derive(r, d), *cl = kid(res, "Claim"), *rq = cl && cl->n >= 2 ? cl->items[1] : NULL;
        if (!rq || !sx_head_is(rq, "CheckImplementation") || rq->n != 3 || rq->items[1]->kind != SX_SYM) return dc_invalid(m, "ThenContracts: premise %d is not a CheckImplementation", k + 1);
        int rc = ct_load(m, rq->items[1]->text, &c[k], why, sizeof why);
        if (rc == -2) return dc_unsupported(m, "ThenContracts: %s", why);
        if (rc) return dc_invalid(m, "ThenContracts: %s", why);
        if (ct_grade(kid(kid(res, "Value"), "Grade"), &L[k], &e[k])) return dc_invalid(m, "ThenContracts: premise %d carries no (Value (Grade L eta))", k + 1);
    }
    if (c[0].tout != c[1].tin) return dc_invalid(m, "ThenContracts: %s's OutputDistance is not %s's InputDistance", c[0].name, c[1].name);
    for (size_t i = 0; i < m->car[c[0].audit].n; i++) for (int w = 0; w < 2; w++) {
        DcRat v, y; int found = 0;
        if (ct_out(m, w ? c[0].actual : c[0].ideal, (int)i, &v)) return dc_unsupported(m, "ThenContracts: a value of %s is not rational", c[0].name);
        for (size_t j = 0; j < m->car[c[1].audit].n && !found; j++) found = !ct_val(m, c[1].audit, (int)j, &y) && !dc_rat_cmp(v, y);
        if (!found) return dc_invalid(m, "ThenContracts: a value %s's %s produces lies outside %s's Audit carrier", c[0].name, w ? "Actual" : "Ideal", c[1].name);
    }
    DcRat Lc = dc_rat_mul(L[1], L[0], &ovf), ec = dc_rat_add(dc_rat_mul(L[1], e[0], &ovf), e[1], &ovf);
    if (ovf) return dc_unsupported(m, "ThenContracts: rational overflow");
    Sx *ev = dc_form("Evidence", dc_form("Composition", dc_form("Rule", dc_sym("AffineComposition"), NULL),
                     dc_form("First", dc_sym(c[0].name), dc_form("Grade", rsx(L[0]), rsx(e[0]), NULL), NULL),
                     dc_form("Second", dc_sym(c[1].name), dc_form("Grade", rsx(L[1]), rsx(e[1]), NULL), NULL), NULL), NULL);
    Sx *subj = dc_form("Subject", dc_form("Composite", dc_sym(c[0].name), dc_sym(c[1].name), NULL), NULL);
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), subj, dc_form("Value", dc_form("Grade", rsx(Lc), rsx(ec), NULL), NULL), ev, NULL);
}
Sx *dc_req_contracts(DcRun *r, const Sx *q, const char *h) {
    if (!strcmp(h, "CheckImplementation")) return ct_check(r, q);
    if (!strcmp(h, "ThenContracts")) return ct_then(r, q);
    return NULL;
}
