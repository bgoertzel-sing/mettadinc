/* M0 requests, part 1: run context, MeasureNow, CheckUpdates, InduceExact. */
#include "ops_internal.h"
#include "obligations.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

DcRun *dc_run_new(DcModule *m) { DcRun *r = calloc(1, sizeof *r); if (!r) abort(); r->m = m; return r; }
void dc_run_free(DcRun *r) {
    if (!r) return;
    for (int i = 0; i < DC_MAX_DERIVE; i++) {
        sx_free(r->memo[i]);
        if (r->has_view[i]) dc_view_free(&r->view[i]);
        if (r->arrow_kind[i]) free(r->arrow[i].table);
    }
    free(r);
}

/* A name that is declared in the source but was not admitted is outside M0. */
int dc_declared_unsupported(const DcModule *m, const char *name) {
    const Sx *src = m->source;
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (d->kind == SX_LIST && d->n > 1 && sx_is_sym(d->items[1], name)) return 1;
    }
    return 0;
}

static int need_repr(const DcModule *m, const Sx *q, const char *req, Sx **out) {
    if (q->n < 2 || q->items[1]->kind != SX_SYM) { *out = dc_invalid(m, "%s: field Representation missing or not a name", req); return -1; }
    const char *nm = q->items[1]->text; int ri = dc_find_repr(m, nm);
    if (ri >= 0) return ri;
    if (dc_declared_unsupported(m, nm)) *out = dc_unsupported(m, "%s: Representation %s is outside the M0 fragment", req, nm);
    else *out = dc_invalid(m, "%s: field Representation names no declared representation (%s)", req, nm);
    return -1;
}

Sx *dc_claim_of(const Sx *q, const char *equality) {
    return dc_form("Claim", sx_copy(q), dc_form("Equality", dc_sym(equality), NULL), NULL);
}
static Sx *subject_repr(const DcModule *m, int ri) {
    return dc_form("Subject", dc_form("Representation", dc_sym(m->rep[ri].name), NULL),
                   dc_form("Machine", dc_sym(m->mach[m->rep[ri].machine].name), NULL), NULL);
}
static Sx *defect(int d) { return dc_form("Defect", dc_form("Interval", dc_int(d), dc_int(d), NULL), NULL); }

/* Partition certificate: the code classes of the representation (literal
 * codes, or one block under the trivial tolerance). */
static int same_code(const DcRepr *r, const int *enc, size_t i, size_t j, int literal) {
    return (!literal && r->codes == DC_CODES_ALL) ? 1 : enc[i] == enc[j];
}
static Sx *partition_cert(const DcModule *m, int ri, int literal, const char *checks) {
    const DcRepr *r = &m->rep[ri]; const DcCarrier *S = &m->car[m->mach[r->machine].states];
    const int *enc = m->map[r->encode].table;
    int *done = calloc(S->n ? S->n : 1, sizeof(int));
    Sx *blocks = dc_form("Blocks", NULL);
    for (size_t i = 0; i < S->n; i++) {
        if (done[i]) continue;
        Sx *b = dc_form("Block", NULL);
        for (size_t j = i; j < S->n; j++) if (!done[j] && same_code(r, enc, i, j, literal)) { done[j] = 1; sx_push(b, sx_copy(S->elems[j])); }
        sx_push(blocks, b);
    }
    free(done);
    return dc_form("Certificate", dc_form("Kind", dc_sym("Prefixpoint"), NULL),
                   dc_form("Codes", dc_sym(literal ? "Literal" : (r->codes == DC_CODES_ALL ? "Tolerance" : "Literal")), NULL),
                   dc_form("Checks", dc_sym(checks), NULL), blocks, NULL);
}

/* Replay a partition certificate from its own data: the blocks must be
 * exactly the code classes, observations constant on blocks, and (when
 * actions is set) every action must send a block into one block. */
static int replay_partition(const DcModule *m, int ri, const Sx *cert, int literal, int actions) {
    const DcRepr *r = &m->rep[ri]; const DcMachine *mc = &m->mach[r->machine];
    const DcCarrier *S = &m->car[mc->states]; const int *enc = m->map[r->encode].table;
    const Sx *bl = sx_find(cert, "Blocks", 1);
    if (!bl) return 0;
    size_t n = S->n; int ok = 1;
    int *cls = malloc((n ? n : 1) * sizeof(int));
    for (size_t i = 0; i < n; i++) cls[i] = -1;
    for (size_t b = 1; b < bl->n && ok; b++) {
        const Sx *B = bl->items[b];
        if (!sx_head_is(B, "Block")) { ok = 0; break; }
        for (size_t k = 1; k < B->n; k++) {
            int i = dc_carrier_index(S, B->items[k]);
            if (i < 0 || cls[i] >= 0) { ok = 0; break; }
            cls[i] = (int)b;
        }
    }
    for (size_t i = 0; ok && i < n; i++) if (cls[i] < 0) ok = 0;
    for (size_t i = 0; ok && i < n; i++)
        for (size_t j = 0; ok && j < n; j++) {
            int same = cls[i] == cls[j];
            if (same != same_code(r, enc, i, j, literal)) { ok = 0; break; }
            if (!same) continue;
            for (size_t p = 0; p < mc->nobs; p++) if (m->map[mc->obs[p].map].table[i] != m->map[mc->obs[p].map].table[j]) ok = 0;
            if (actions) for (size_t p = 0; p < mc->nact; p++) {
                const int *a = m->map[mc->act[p].map].table;
                if (cls[a[i]] != cls[a[j]]) ok = 0;
            }
        }
    free(cls); return ok;
}

Sx *dc_req_measure_now(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Sx *e = NULL; int ri = need_repr(m, q, "MeasureNow", &e);
    if (ri < 0) return e;
    if (q->n != 2) return dc_invalid(m, "MeasureNow: field %zu is unexpected; MeasureNow takes one Representation", (size_t)2);
    Sx *w = NULL; int holds = dc_obligation(m, ri, OBL_CURRENT, &w), rep; Sx *ev;
    if (holds) { Sx *c = partition_cert(m, ri, 0, "Current"); rep = replay_partition(m, ri, c, 0, 0); ev = dc_form("Evidence", c, NULL); }
    else { rep = dc_obligation_replay(m, ri, OBL_CURRENT, w); ev = dc_form("Evidence", dc_form("Witness", w, NULL), NULL); }
    return dc_envelope(m, VERDICT_HOLDS, rep, dc_claim_of(q, "Literal"), subject_repr(m, ri),
        dc_form("Value", dc_form("DefectMeasurement", defect(holds ? 0 : 1), dc_form("Equality", dc_sym("Literal"), NULL), NULL), NULL), ev, NULL);
}

/* CheckUpdates and CheckNow share one shape: a defect against a Within bound.
 * CheckNow checks the Current obligation, CheckUpdates the Update obligation. */
static Sx *check_bounded(DcRun *r, const Sx *q, const char *req, DcOblKind kind);
Sx *dc_req_check_updates(DcRun *r, const Sx *q) { return check_bounded(r, q, "CheckUpdates", OBL_UPDATE); }
Sx *dc_req_check_now(DcRun *r, const Sx *q) { return check_bounded(r, q, "CheckNow", OBL_CURRENT); }
static Sx *check_bounded(DcRun *r, const Sx *q, const char *req, DcOblKind kind) {
    DcModule *m = r->m; Sx *e = NULL; int ri = need_repr(m, q, req, &e);
    if (ri < 0) return e;
    double within = 0; char wtxt[64] = "0";
    for (size_t i = 2; i < q->n; i++) {
        const Sx *f = q->items[i]; char *end;
        if (!sx_head_is(f, "Within") || f->n != 2 || f->items[1]->kind != SX_SYM)
            return dc_invalid(m, "%s: field %zu is not (Within bound)", req, i - 1);
        within = strtod(f->items[1]->text, &end);
        if (end == f->items[1]->text || *end || within < 0) return dc_invalid(m, "%s: field Within is not a non-negative number (%s)", req, f->items[1]->text);
        snprintf(wtxt, sizeof wtxt, "%s", f->items[1]->text);
    }
    Sx *w = NULL; int holds = dc_obligation(m, ri, kind, &w), d = holds ? 0 : 1, rep; Sx *ev;
    if (holds) { Sx *c = partition_cert(m, ri, 0, kind == OBL_UPDATE ? "Update" : "Current"); rep = replay_partition(m, ri, c, 0, kind == OBL_UPDATE); ev = dc_form("Evidence", c, NULL); }
    else { rep = dc_obligation_replay(m, ri, kind, w); ev = dc_form("Evidence", dc_form("Witness", w, NULL), NULL); }
    return dc_envelope(m, d <= within ? VERDICT_HOLDS : VERDICT_FAILS, rep, dc_claim_of(q, "Literal"), subject_repr(m, ri),
        dc_form("Value", dc_form("DefectCheck", defect(d), dc_form("Bound", dc_sym(wtxt), NULL), dc_form("Equality", dc_sym("Literal"), NULL), NULL), NULL), ev, NULL);
}
