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
    Sx *r = dc_form("Result", dc_form("Status", dc_sym(dc_status_name(st)), NULL), NULL);
    sx_push(r, claim ? claim : dc_form("Claim", NULL));
    sx_push(r, dc_form("Binding", dc_form("Module", dc_sym(m ? m->name : "?"), NULL),
                       dc_form("Digest", sx_str(m ? m->digest : ""), NULL),
                       subject ? subject : dc_form("Subject", NULL), NULL));
    sx_push(r, dc_form("Scope", dc_form("Profile", dc_sym(m && m->profile[0] ? m->profile : "Crisp"), NULL),
                       dc_form("Fragment", dc_sym("M0-EnumeratedDeterministic"), NULL), NULL));
    sx_push(r, value ? value : dc_form("Value", NULL));
    sx_push(r, evidence ? evidence : dc_form("Evidence", NULL));
    sx_push(r, dc_form("Assumptions", NULL));
    sx_push(r, dc_form("Assurance", dc_form("Policy", dc_sym("M0-ExactReplay"), NULL),
                       dc_form("Replayed", dc_sym(replays ? "True" : "False"), NULL),
                       dc_form("Ground", dc_sym(dc_ground_name(!replays || v > VERDICT_FAILS ? GROUND_NONE : (v == VERDICT_FAILS ? GROUND_WITNESS : GROUND_REPLAYED))), NULL), NULL));
    if (reason) sx_push(r, dc_form("Reason", sx_str(reason), NULL));
    return r;
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
