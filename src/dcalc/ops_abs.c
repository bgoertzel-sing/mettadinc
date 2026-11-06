/* M0 requests, part 3: CheckAbstractionMap and Then (composition). */
#include "ops_internal.h"
#include "ops_run.h"
#include "binding.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Resolve (Output D Machine|AbstractionMap|Value) to a Derive slot, running it. */
static int output_slot(DcRun *r, const Sx *x, const char *what, char *why, size_t wn) {
    if (!sx_head_is(x, "Output") || x->n != 3 || x->items[1]->kind != SX_SYM || !sx_is_sym(x->items[2], what)) {
        snprintf(why, wn, "expected (Output Derive %s)", what); return -1;
    }
    int d = dc_find_derive(r->m, x->items[1]->text);
    if (d < 0) { snprintf(why, wn, "names no declared Derive (%s)", x->items[1]->text); return -1; }
    const Sx *res = dc_run_derive(r, d);
    if (!res) { snprintf(why, wn, "Derive %s: cyclic reference", x->items[1]->text); return -1; }
    DcStatus st = dc_result_status(res);
    /* A premise outside M0 makes the whole request outside M0 (-2 -> Unsupported). */
    if (st == DC_UNSUPPORTED) { snprintf(why, wn, "premise Derive %s is outside the M0 fragment", x->items[1]->text); return -2; }
    /* Checked and Conditional premises compose; Conditional passes its assumptions on. */
    if (st != DC_CHECKED && st != DC_CONDITIONAL) { snprintf(why, wn, "Derive %s is neither Checked nor Conditional (%s)", x->items[1]->text, dc_status_name(st)); return -1; }
    return d;
}

static Sx *arrow_cert(const DcModule *m, const DcArrow *A, const DcView *src) {
    const DcCarrier *S = &m->car[A->src_car], *T = &m->car[A->tgt_car];
    Sx *t = dc_form("Table", NULL);
    for (size_t s = 0; s < S->n; s++) if (!src || src->valid[s])
        sx_push(t, dc_form("Row", sx_copy(S->elems[s]), sx_copy(T->elems[A->table[s]]), NULL));
    return t;
}

/* Replay: the table rows are exactly the map on valid source states, and the
 * square commutes for every row, observation and action (by label). */
static int replay_commute(const DcModule *m, const Sx *table, const DcView *sv, const DcView *tv) {
    const DcCarrier *S = &m->car[sv->states], *T = &m->car[tv->states];
    size_t rows = 0; int *f = malloc((S->n ? S->n : 1) * sizeof(int));
    for (size_t i = 0; i < S->n; i++) f[i] = -1;
    for (size_t k = 1; k < table->n; k++) {
        const Sx *row = table->items[k];
        if (!sx_head_is(row, "Row") || row->n != 3) { free(f); return 0; }
        int s = dc_carrier_index(S, row->items[1]), t = dc_carrier_index(T, row->items[2]);
        if (s < 0 || t < 0 || !sv->valid[s] || !tv->valid[t] || f[s] >= 0) { free(f); return 0; }
        f[s] = t; rows++;
    }
    int ok = 1;
    for (size_t s = 0; s < S->n && ok; s++) {
        if (!sv->valid[s]) continue;
        if (f[s] < 0) { ok = 0; break; }
        for (size_t p = 0; p < sv->nobs && ok; p++) {
            size_t q; for (q = 0; q < tv->nobs && strcmp(tv->obs_label[q], sv->obs_label[p]); q++) ;
            if (q == tv->nobs || sv->obs_car[p] != tv->obs_car[q] || sv->obs[p][s] != tv->obs[q][f[s]]) ok = 0;
        }
        for (size_t p = 0; p < sv->nact && ok; p++) {
            size_t q; for (q = 0; q < tv->nact && strcmp(tv->act_label[q], sv->act_label[p]); q++) ;
            if (q == tv->nact || f[sv->act[p][s]] != tv->act[q][f[s]]) ok = 0;
        }
    }
    free(f); (void)rows; return ok;
}

Sx *dc_req_check_abs(DcRun *r, const Sx *q, int slot) {
    DcModule *m = r->m; char why[256];
    if (q->n != 2 || q->items[1]->kind != SX_SYM) return dc_invalid(m, "CheckAbstractionMap: field AbstractionMap missing or not a name");
    const char *nm = q->items[1]->text; int ai = dc_find_abs(m, nm);
    if (ai < 0) {
        if (dc_declared_unsupported(m, nm)) return dc_unsupported(m, "CheckAbstractionMap: AbstractionMap %s is outside the M0 fragment", nm);
        return dc_invalid(m, "CheckAbstractionMap: field AbstractionMap names no declared abstraction map (%s)", nm);
    }
    const DcAbsMap *a = &m->abs[ai]; const DcMap *mp = &m->map[a->map];
    DcView sv, tv;
    if (a->source->kind == SX_SYM) {
        int si = dc_find_machine(m, a->source->text);
        if (si < 0) {
            if (dc_declared_unsupported(m, a->source->text)) return dc_unsupported(m, "CheckAbstractionMap %s: Source %s is outside the M0 fragment", nm, a->source->text);
            return dc_invalid(m, "CheckAbstractionMap %s: field Source names no declared machine (%s)", nm, a->source->text);
        }
        dc_view_of_machine(m, si, &sv);
    } else {
        int d = output_slot(r, a->source, "Machine", why, sizeof why);
        if (d == -2) return dc_unsupported(m, "CheckAbstractionMap %s: %s", nm, why);
        if (d < 0) return dc_invalid(m, "CheckAbstractionMap %s: field Source %s", nm, why);
        if (!r->has_view[d]) return dc_invalid(m, "CheckAbstractionMap %s: field Source: Derive %s has no machine output", nm, m->der[d].name);
        dc_view_copy(&r->view[d], &sv);
    }
    if (mp->from != sv.states) { dc_view_free(&sv); return dc_invalid(m, "CheckAbstractionMap %s: field Map does not start at the source states", nm); }
    dc_view_of_machine(m, a->target, &tv);
    DcArrow A; memset(&A, 0, sizeof A);
    A.src = -1; A.tgt = a->target; A.src_car = sv.states; A.tgt_car = tv.states;
    A.table = malloc((sv.n ? sv.n : 1) * sizeof(int)); memcpy(A.table, mp->table, sv.n * sizeof(int));
    snprintf(A.src_id, sizeof A.src_id, "%s", sv.id); snprintf(A.tgt_id, sizeof A.tgt_id, "%s", tv.id);
    /* search for the least failing (state, port) */
    Sx *wit = NULL; const DcCarrier *S = &m->car[sv.states], *T = &m->car[tv.states];
    for (size_t s = 0; s < sv.n && !wit; s++) {
        if (!sv.valid[s]) continue;
        int fs = A.table[s];
        for (size_t p = 0; p < sv.nobs && !wit; p++) {
            size_t k; for (k = 0; k < tv.nobs && strcmp(tv.obs_label[k], sv.obs_label[p]); k++) ;
            if (k == tv.nobs) { dc_view_free(&sv); dc_view_free(&tv); free(A.table); return dc_invalid(m, "CheckAbstractionMap %s: Target has no observation %s", nm, sv.obs_label[p]); }
            if (sv.obs[p][s] != tv.obs[k][fs]) {
                const DcCarrier *O = &m->car[sv.obs_car[p]];
                wit = dc_form("CommutationWitness", dc_form("State", sx_copy(S->elems[s]), NULL), dc_form("Observe", dc_sym(sv.obs_label[p]), NULL),
                              dc_form("Left", sx_copy(O->elems[sv.obs[p][s]]), NULL), dc_form("Right", sx_copy(m->car[tv.obs_car[k]].elems[tv.obs[k][fs]]), NULL), NULL);
            }
        }
        for (size_t p = 0; p < sv.nact && !wit; p++) {
            size_t k; for (k = 0; k < tv.nact && strcmp(tv.act_label[k], sv.act_label[p]); k++) ;
            if (k == tv.nact) { dc_view_free(&sv); dc_view_free(&tv); free(A.table); return dc_invalid(m, "CheckAbstractionMap %s: Target has no action %s", nm, sv.act_label[p]); }
            if (A.table[sv.act[p][s]] != tv.act[k][fs])
                wit = dc_form("CommutationWitness", dc_form("State", sx_copy(S->elems[s]), NULL), dc_form("Action", dc_sym(sv.act_label[p]), NULL),
                              dc_form("Left", sx_copy(T->elems[A.table[sv.act[p][s]]]), NULL), dc_form("Right", sx_copy(T->elems[tv.act[k][fs]]), NULL), NULL);
        }
    }
    Sx *subject = dc_form("Subject", dc_form("AbstractionMap", dc_sym(nm), NULL), dc_form("Source", dc_sym(sv.id), NULL), dc_form("Target", dc_sym(tv.id), NULL), NULL);
    Sx *res;
    if (wit) {
        /* replay the witness: a one-row table must fail the commutation check */
        res = dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), subject,
                          dc_form("Value", dc_form("Refutation", dc_form("Obligation", dc_sym("Commutation"), NULL), NULL), NULL),
                          dc_form("Evidence", dc_form("Witness", wit, NULL), NULL), NULL);
        free(A.table);
    } else {
        int *hit = calloc(tv.n ? tv.n : 1, sizeof(int)); A.surjective = 1;
        for (size_t s = 0; s < sv.n; s++) if (sv.valid[s]) hit[A.table[s]] = 1;
        for (size_t t = 0; t < tv.n; t++) if (tv.valid[t] && !hit[t]) A.surjective = 0;
        free(hit);
        Sx *table = arrow_cert(m, &A, &sv);
        int rep = replay_commute(m, table, &sv, &tv);
        res = dc_envelope(m, VERDICT_HOLDS, rep, dc_claim_of(q, "Literal"), subject,
                          dc_form("Value", dc_form("CheckedAbstractionMap", dc_form("Kind", dc_sym(A.surjective ? "Quotient" : "Homomorphism"), NULL),
                                  dc_form("Surjective", dc_sym(A.surjective ? "True" : "False"), NULL), NULL), NULL),
                          dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("rule"), NULL), dc_form("Rule", dc_sym("Commutation"), NULL), table, NULL), NULL), NULL);
        dc_result_bind_models(res, A.src_id, A.tgt_id);
        if (slot >= 0) { r->arrow[slot] = A; r->arrow_kind[slot] = 2; } else free(A.table);
    }
    dc_view_free(&sv); dc_view_free(&tv);
    return res;
}

Sx *dc_req_then(DcRun *r, const Sx *q, int slot) {
    DcModule *m = r->m; char why[256]; int d[2];
    if (q->n != 3) return dc_invalid(m, "Then: expected two arrows");
    for (int k = 0; k < 2; k++) {
        const Sx *x = q->items[k + 1];
        const char *what = sx_head_is(x, "Output") && x->n == 3 && sx_is_sym(x->items[2], "Value") ? "Value" : "AbstractionMap";
        d[k] = output_slot(r, x, what, why, sizeof why);
        if (d[k] == -2) return dc_unsupported(m, "Then: field %s: %s", k ? "Second" : "First", why);
        if (d[k] < 0) return dc_invalid(m, "Then: field %s %s", k ? "Second" : "First", why);
        if (!r->arrow_kind[d[k]]) return dc_invalid(m, "Then: field %s: Derive %s produced no arrow", k ? "Second" : "First", m->der[d[k]].name);
    }
    const DcArrow *f = &r->arrow[d[0]], *g = &r->arrow[d[1]];
    /* Boundary 1: the one validation routine (binding.c) checks the second
     * premise against the interface the first one ends at. */
    DcBindingRef want = { m->digest, f->tgt_id, NULL, f->tgt_car, -1, NULL };
    DcBindingRef have = { m->digest, g->src_id, g->tgt_id, g->src_car, g->tgt_car, NULL };
    if (dc_binding_validate("Then", "Second", &want, &have, why, sizeof why))
        return dc_invalid(m, "%s", why);
    const DcCarrier *S = &m->car[f->src_car], *T = &m->car[g->tgt_car];
    DcArrow A; memset(&A, 0, sizeof A);
    A.src = f->src; A.tgt = g->tgt; A.src_car = f->src_car; A.tgt_car = g->tgt_car;
    A.table = malloc((S->n ? S->n : 1) * sizeof(int));
    for (size_t s = 0; s < S->n; s++) A.table[s] = g->table[f->table[s]];
    A.surjective = f->surjective && g->surjective;
    snprintf(A.src_id, sizeof A.src_id, "%s", f->src_id); snprintf(A.tgt_id, sizeof A.tgt_id, "%s", g->tgt_id);
    Sx *table = dc_form("Table", NULL);
    for (size_t s = 0; s < S->n; s++) sx_push(table, dc_form("Row", sx_copy(S->elems[s]), sx_copy(T->elems[A.table[s]]), NULL));
    /* replay: each row equals g(f(s)) recomputed from the component tables */
    int rep = table->n == S->n + 1;
    for (size_t s = 0; s < S->n && rep; s++) {
        const Sx *row = table->items[s + 1];
        int si = dc_carrier_index(S, row->items[1]), ti = dc_carrier_index(T, row->items[2]);
        if (si < 0 || ti != g->table[f->table[si]]) rep = 0;
    }
    Sx *res = dc_envelope(m, VERDICT_HOLDS, rep, dc_claim_of(q, "Literal"),
        dc_form("Subject", dc_form("First", dc_sym(m->der[d[0]].name), NULL), dc_form("Second", dc_sym(m->der[d[1]].name), NULL), NULL),
        dc_form("Value", dc_form("ComposedArrow", dc_form("Source", dc_sym(A.src_id), NULL), dc_form("Target", dc_sym(A.tgt_id), NULL),
                dc_form("Kind", dc_sym(A.surjective ? "Quotient" : "Homomorphism"), NULL), NULL), NULL),
        dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("rule"), NULL), dc_form("Rule", dc_sym("Composition"), NULL), table, NULL), NULL), NULL);
    /* Boundary 2: the composed result carries the union of both premises' assumptions. */
    for (int k = 0; k < 2; k++) dc_result_add_premise(res, r->memo[d[k]], m->der[d[k]].name);
    dc_result_bind_models(res, A.src_id, A.tgt_id);
    if (slot >= 0) { r->arrow[slot] = A; r->arrow_kind[slot] = 3; } else free(A.table);
    return res;
}
