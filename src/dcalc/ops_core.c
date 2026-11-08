/* Result envelope, the single assurance policy, and machine views. */
#include "ops_internal.h"
#include "records.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

static const char *STATUS[] = { "Checked", "Refuted", "Conditional", "Estimated", "Unknown", "Unsupported", "InvalidInput" };
const char *dc_status_name(DcStatus s) { return (unsigned)s < 7 ? STATUS[s] : "InvalidInput"; }

Sx *dc_sym(const char *s) { return sx_sym(s); }
Sx *dc_int(long v) { char b[32]; snprintf(b, sizeof b, "%ld", v); return sx_sym(b); }
Sx *dc_form(const char *head, ...) {
    Sx *l = sx_list(); sx_push(l, sx_sym(head));
    va_list ap; va_start(ap, head);
    for (Sx *x; (x = va_arg(ap, Sx *)) != NULL;) sx_push(l, x);
    va_end(ap); return l;
}

/* ---- the one assurance policy ----
 * Every request reports a verdict; dc_assure alone turns it into a status.
 *   VERDICT_HOLDS     + certificate that replays      -> Checked
 *   VERDICT_FAILS     + witness that replays          -> Refuted
 *   VERDICT_HOLDS/FAILS without replayable evidence   -> Unknown (never Checked/Refuted)
 *   VERDICT_UNSUPPORTED                               -> Unsupported
 *   VERDICT_INVALID                                   -> InvalidInput
 * M0 never emits Conditional or Estimated: there are no assumptions and no
 * sampling in the deterministic exact fragment. */
DcStatus dc_assure(DcVerdict v, int evidence_replays) {
    /* M0 special case of the single policy dc_assure_grounded (records.c):
     * a replayed certificate is the ground Replayed, a replayed witness the
     * ground Witness, and M0 carries no assumptions. */
    DcGround g = !evidence_replays ? GROUND_NONE : (v == VERDICT_FAILS ? GROUND_WITNESS : GROUND_REPLAYED);
    return dc_assure_grounded(v, g, 0);
}

Sx *dc_envelope(const DcModule *m, DcVerdict v, int replays, Sx *claim, Sx *subject,
                Sx *value, Sx *evidence, const char *reason) {
    DcStatus st = dc_assure(v, replays);
    /* review 2 F5: fill the binding from the subject instead of placeholders.
     * Representation subjects bind Source = machine, Target = code carrier and
     * Interface = the declared code tolerance (Exact when Codes are literal);
     * subjects that name (Source s) (Target t) bind those. */
    const char *src_id = "None", *tgt_id = "None", *tol = "Exact";
    if (m && subject) {
        const Sx *rp = sx_find(subject, "Representation", 1);
        if (rp && rp->n == 2 && rp->items[1]->kind == SX_SYM) {
            int ri = dc_find_repr(m, rp->items[1]->text);
            if (ri >= 0) {
                const DcRepr *R = &m->rep[ri];
                if (R->machine >= 0) src_id = m->mach[R->machine].name;
                if (R->encode >= 0) tgt_id = m->car[m->map[R->encode].to].name;
                if (R->codes == DC_CODES_ALL && R->tol >= 0) tol = m->tol[R->tol].name;
            }
        }
        const Sx *ss = sx_find(subject, "Source", 1), *ts = sx_find(subject, "Target", 1);
        if (ss && ss->n == 2 && ss->items[1]->kind == SX_SYM) src_id = ss->items[1]->text;
        if (ts && ts->n == 2 && ts->items[1]->kind == SX_SYM) tgt_id = ts->items[1]->text;
    }
    Sx *r = dc_form("Result", dc_form("Status", dc_sym(dc_status_name(st)), NULL), NULL);
    sx_push(r, claim ? claim : dc_form("Claim", NULL));
    sx_push(r, dc_form("Binding", dc_form("Module", dc_sym(m ? m->name : "?"), NULL),
                       dc_form("Digest", sx_str(m ? m->digest : ""), NULL),
                       subject ? subject : dc_form("Subject", NULL),
                       /* boundary 1: model identities and the checked interface;
                        * operations that know them fill them in (dc_result_bind_models) */
                       dc_form("Source", dc_sym(src_id), NULL), dc_form("Target", dc_sym(tgt_id), NULL),
                       dc_form("Interface", dc_form("Tolerance", dc_sym(tol), NULL), NULL), NULL));
    /* boundary 1: the scope of the claim.  M0 checks enumerated deterministic
     * machines from every declared state, unbounded horizon, no discount,
     * no policy quantifier. */
    sx_push(r, dc_form("Scope", dc_form("Profile", dc_sym(m && m->profile[0] ? m->profile : "Crisp"), NULL),
                       dc_form("Fragment", dc_sym("M0-EnumeratedDeterministic"), NULL),
                       dc_form("InitialStates", dc_sym("AllDeclared"), NULL),
                       dc_form("ReachableStates", dc_sym("AllDeclared"), NULL),
                       dc_form("Horizon", dc_sym("Unbounded"), NULL),
                       dc_form("Discount", dc_sym("1"), NULL),
                       dc_form("PolicyClass", dc_sym("None"), NULL), NULL));
    sx_push(r, value ? value : dc_form("Value", NULL));
    sx_push(r, evidence ? evidence : dc_form("Evidence", NULL));
    sx_push(r, dc_form("Assumptions", NULL));
    sx_push(r, dc_form("Assurance", dc_form("Policy", dc_sym("M0-ExactReplay"), NULL),
                       dc_form("Replayed", dc_sym(replays ? "True" : "False"), NULL),
                       dc_form("Ground", dc_sym(dc_ground_name(!replays || v > VERDICT_FAILS ? GROUND_NONE : (v == VERDICT_FAILS ? GROUND_WITNESS : GROUND_REPLAYED))), NULL), NULL));
    if (reason) sx_push(r, dc_form("Reason", sx_str(reason), NULL));
    return r;
}

/* Boundary 1: record source/target model identities in a result's binding. */
void dc_result_bind_models(Sx *res, const char *src_id, const char *tgt_id) {
    Sx *b = sx_find(res, "Binding", 1);
    if (!b) return;
    Sx *s = sx_find(b, "Source", 1), *t = sx_find(b, "Target", 1);
    if (s && s->n == 2 && src_id) { sx_free(s->items[1]); s->items[1] = sx_str(src_id); }
    if (t && t->n == 2 && tgt_id) { sx_free(t->items[1]); t->items[1] = sx_str(tgt_id); }
}

/* Boundary 2: a derived result takes the union of its premises' assumptions.
 * A Conditional premise passes its assumptions on; an Estimated premise adds
 * (EstimatedPremise name delta).  Any assumption turns Checked/Refuted into
 * Conditional (dc_assure_grounded). */
void dc_result_add_premise(Sx *res, const Sx *premise, const char *premise_name) {
    Sx *dst = sx_find(res, "Assumptions", 0);
    if (!dst || !premise) return;
    DcStatus ps = dc_result_status(premise);
    if (ps == DC_CONDITIONAL) dc_assumptions_union(dst, dc_result_assumptions(premise));
    if (ps == DC_ESTIMATED) {
        /* review 2 F5: (EstimatedPremise result-digest delta): sha256 of the
         * premise envelope's canonical print, and the premise's declared
         * (Delta d) if it carries one, else Unknown.  premise_name is kept
         * only for diagnostics. */
        (void)premise_name;
        char *txt = sx_print(premise); char dg[65];
        dc_sha256_hex(txt, strlen(txt), dg); free(txt);
        const Sx *dl = NULL; const Sx *val = sx_find(premise, "Value", 1);
        for (size_t i = 1; val && i < val->n && !dl; i++)
            if (val->items[i]->kind == SX_LIST) { const Sx *x = sx_head_is(val->items[i], "Delta") ? val->items[i] : sx_find(val->items[i], "Delta", 1); if (x && x->n == 2 && x->items[1]->kind == SX_SYM) dl = x; }
        Sx *e = dc_form("EstimatedPremise", sx_str(dg), dc_sym(dl ? dl->items[1]->text : "Unknown"), NULL);
        Sx *one = dc_form("Assumptions", e, NULL);
        dc_assumptions_union(dst, one); sx_free(one);
    }
    if (dst->n > 1 && res->n > 1 && sx_head_is(res->items[1], "Status") && res->items[1]->n == 2) {
        DcStatus st = dc_result_status(res);
        if (st == DC_CHECKED || st == DC_REFUTED) {
            sx_free(res->items[1]->items[1]);
            res->items[1]->items[1] = dc_sym(dc_status_name(DC_CONDITIONAL));
        }
    }
}

Sx *dc_invalid(const DcModule *m, const char *fmt, ...) {
    char buf[512]; va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
    return dc_envelope(m, VERDICT_INVALID, 0, NULL, NULL, NULL, NULL, buf);
}
Sx *dc_unsupported(const DcModule *m, const char *fmt, ...) {
    char buf[512]; va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
    return dc_envelope(m, VERDICT_UNSUPPORTED, 0, NULL, NULL, NULL, NULL, buf);
}

DcStatus dc_result_status(const Sx *res) {
    const Sx *s = sx_head_is(res, "Result") ? sx_find(res, "Status", 1) : NULL;
    if (!s || s->n != 2) return DC_INVALID_INPUT;
    for (int i = 0; i < 7; i++) if (sx_is_sym(s->items[1], STATUS[i])) return (DcStatus)i;
    return DC_INVALID_INPUT;
}

/* ---- machine views ---- */
void dc_view_of_machine(const DcModule *m, int mi, DcView *v) {
    const DcMachine *mc = &m->mach[mi];
    memset(v, 0, sizeof *v);
    snprintf(v->id, sizeof v->id, "%s", mc->name);
    v->states = mc->states; v->n = m->car[mc->states].n;
    v->valid = malloc(v->n * sizeof(int)); for (size_t i = 0; i < v->n; i++) v->valid[i] = 1;
    v->nobs = mc->nobs; v->nact = mc->nact;
    for (size_t k = 0; k < mc->nobs; k++) {
        snprintf(v->obs_label[k], DC_MAX_NAME, "%s", mc->obs[k].label);
        v->obs_car[k] = m->map[mc->obs[k].map].to;
        v->obs[k] = malloc(v->n * sizeof(int)); memcpy(v->obs[k], m->map[mc->obs[k].map].table, v->n * sizeof(int));
    }
    for (size_t k = 0; k < mc->nact; k++) {
        snprintf(v->act_label[k], DC_MAX_NAME, "%s", mc->act[k].label);
        v->act[k] = malloc(v->n * sizeof(int)); memcpy(v->act[k], m->map[mc->act[k].map].table, v->n * sizeof(int));
    }
}
void dc_view_free(DcView *v) {
    free(v->valid);
    for (size_t k = 0; k < v->nobs; k++) free(v->obs[k]);
    for (size_t k = 0; k < v->nact; k++) free(v->act[k]);
    memset(v, 0, sizeof *v);
}
void dc_view_copy(const DcView *a, DcView *b) {
    *b = *a;
    b->valid = malloc(a->n * sizeof(int)); memcpy(b->valid, a->valid, a->n * sizeof(int));
    for (size_t k = 0; k < a->nobs; k++) { b->obs[k] = malloc(a->n * sizeof(int)); memcpy(b->obs[k], a->obs[k], a->n * sizeof(int)); }
    for (size_t k = 0; k < a->nact; k++) { b->act[k] = malloc(a->n * sizeof(int)); memcpy(b->act[k], a->act[k], a->n * sizeof(int)); }
}
