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

/* review 4 F6: copy a view's valid-state mask for an arrow kept in a slot */
static int *mask_dup(const int *v, size_t n) {
    int *c = malloc((n ? n : 1) * sizeof(int));
    for (size_t i = 0; i < n; i++) c[i] = v ? v[i] : 1;
    return c;
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

/* Review 2 F2: replay a CommutationWitness on its own, without trusting the
 * search that produced it.  Both sides are recomputed from the source view,
 * the target view and the map table; the witness must name a valid source
 * state and a port present on both machines, its Left/Right values must equal
 * the recomputed sides, and the two sides must differ.  Returns 1 only then. */
static int replay_witness(const DcModule *m, const Sx *wit, const DcView *sv, const DcView *tv, const int *table) {
    if (!sx_head_is(wit, "CommutationWitness") || wit->n != 5) return 0;
    const Sx *st = wit->items[1], *port = wit->items[2], *L = wit->items[3], *R = wit->items[4];
    if (!sx_head_is(st, "State") || st->n != 2 || !sx_head_is(L, "Left") || L->n != 2 || !sx_head_is(R, "Right") || R->n != 2) return 0;
    if (port->n != 2 || port->items[1]->kind != SX_SYM) return 0;
    const DcCarrier *S = &m->car[sv->states], *T = &m->car[tv->states];
    int s = dc_carrier_index(S, st->items[1]);
    if (s < 0 || (size_t)s >= sv->n || !sv->valid[s]) return 0;
    int fs = table[s];
    const char *lab = port->items[1]->text;
    size_t p, k;
    if (sx_head_is(port, "Observe")) {
        for (p = 0; p < sv->nobs && strcmp(sv->obs_label[p], lab); p++) ;
        for (k = 0; k < tv->nobs && strcmp(tv->obs_label[k], lab); k++) ;
        if (p == sv->nobs || k == tv->nobs) return 0;
        int l = dc_carrier_index(&m->car[sv->obs_car[p]], L->items[1]);
        int rr = dc_carrier_index(&m->car[tv->obs_car[k]], R->items[1]);
        if (l < 0 || rr < 0 || l != sv->obs[p][s] || rr != tv->obs[k][fs]) return 0;
        return sv->obs_car[p] != tv->obs_car[k] || l != rr;
    }
    if (sx_head_is(port, "Action")) {
        for (p = 0; p < sv->nact && strcmp(sv->act_label[p], lab); p++) ;
        for (k = 0; k < tv->nact && strcmp(tv->act_label[k], lab); k++) ;
        if (p == sv->nact || k == tv->nact) return 0;
        int l = dc_carrier_index(T, L->items[1]), rr = dc_carrier_index(T, R->items[1]);
        if (l < 0 || rr < 0 || l != table[sv->act[p][s]] || rr != tv->act[k][fs]) return 0;
        return l != rr;
    }
    return 0;
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
    /* review 4 F4 (spec Definition 3.5): a homomorphism relates two machines with
     * the same interface.  Every observation and action label of either side must
     * exist on the other, with the same observation carrier; a target port the
     * source lacks is not silently ignored. */
    {
        const char *bad = NULL, *side = NULL, *kind = NULL;
        for (size_t p = 0; p < sv.nobs && !bad; p++) {
            size_t k; for (k = 0; k < tv.nobs && strcmp(tv.obs_label[k], sv.obs_label[p]); k++) ;
            if (k == tv.nobs) { bad = sv.obs_label[p]; side = "Target has no"; kind = "observation"; }
        }
        for (size_t k = 0; k < tv.nobs && !bad; k++) {
            size_t p; for (p = 0; p < sv.nobs && strcmp(sv.obs_label[p], tv.obs_label[k]); p++) ;
            if (p == sv.nobs) { bad = tv.obs_label[k]; side = "Source has no"; kind = "observation"; }
            else if (sv.obs_car[p] != tv.obs_car[k]) { bad = tv.obs_label[k]; side = "Source and Target differ in the carrier of"; kind = "observation"; }
        }
        for (size_t p = 0; p < sv.nact && !bad; p++) {
            size_t k; for (k = 0; k < tv.nact && strcmp(tv.act_label[k], sv.act_label[p]); k++) ;
            if (k == tv.nact) { bad = sv.act_label[p]; side = "Target has no"; kind = "action"; }
        }
        for (size_t k = 0; k < tv.nact && !bad; k++) {
            size_t p; for (p = 0; p < sv.nact && strcmp(sv.act_label[p], tv.act_label[k]); p++) ;
            if (p == sv.nact) { bad = tv.act_label[k]; side = "Source has no"; kind = "action"; }
        }
        if (bad) {
            /* format before the views are freed: bad points into sv/tv */
            Sx *res = dc_invalid(m, "CheckAbstractionMap %s: interfaces differ: %s %s %s", nm, side, kind, bad);
            dc_view_free(&sv); dc_view_free(&tv); free(A.table); return res;
        }
    }
    /* search for the least failing (state, port) */
    Sx *wit = NULL; const DcCarrier *S = &m->car[sv.states], *T = &m->car[tv.states];
    for (size_t s = 0; s < sv.n && !wit; s++) {
        if (!sv.valid[s]) continue;
        int fs = A.table[s];
        for (size_t p = 0; p < sv.nobs && !wit; p++) {
            size_t k; for (k = 0; k < tv.nobs && strcmp(tv.obs_label[k], sv.obs_label[p]); k++) ;
            if (k == tv.nobs) { Sx *e = dc_invalid(m, "CheckAbstractionMap %s: Target has no observation %s", nm, sv.obs_label[p]); dc_view_free(&sv); dc_view_free(&tv); free(A.table); return e; }
            if (sv.obs[p][s] != tv.obs[k][fs]) {
                const DcCarrier *O = &m->car[sv.obs_car[p]];
                wit = dc_form("CommutationWitness", dc_form("State", sx_copy(S->elems[s]), NULL), dc_form("Observe", dc_sym(sv.obs_label[p]), NULL),
                              dc_form("Left", sx_copy(O->elems[sv.obs[p][s]]), NULL), dc_form("Right", sx_copy(m->car[tv.obs_car[k]].elems[tv.obs[k][fs]]), NULL), NULL);
            }
        }
        for (size_t p = 0; p < sv.nact && !wit; p++) {
            size_t k; for (k = 0; k < tv.nact && strcmp(tv.act_label[k], sv.act_label[p]); k++) ;
            if (k == tv.nact) { Sx *e = dc_invalid(m, "CheckAbstractionMap %s: Target has no action %s", nm, sv.act_label[p]); dc_view_free(&sv); dc_view_free(&tv); free(A.table); return e; }
            if (A.table[sv.act[p][s]] != tv.act[k][fs])
                wit = dc_form("CommutationWitness", dc_form("State", sx_copy(S->elems[s]), NULL), dc_form("Action", dc_sym(sv.act_label[p]), NULL),
                              dc_form("Left", sx_copy(T->elems[A.table[sv.act[p][s]]]), NULL), dc_form("Right", sx_copy(T->elems[tv.act[k][fs]]), NULL), NULL);
        }
    }
    Sx *subject = dc_form("Subject", dc_form("AbstractionMap", dc_sym(nm), NULL), dc_form("Source", dc_sym(sv.id), NULL), dc_form("Target", dc_sym(tv.id), NULL), NULL);
    Sx *res;
    if (wit) {
        /* replay the witness independently (review 2 F2): Refuted needs a replayed Witness */
        int rep = replay_witness(m, wit, &sv, &tv, A.table);
        res = dc_envelope(m, VERDICT_FAILS, rep, dc_claim_of(q, "Literal"), subject,
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
        if (slot >= 0) { A.src_valid = mask_dup(sv.valid, sv.n); A.tgt_valid = mask_dup(tv.valid, tv.n); r->arrow[slot] = A; r->arrow_kind[slot] = 2; } else free(A.table);
    }
    dc_view_free(&sv); dc_view_free(&tv);
    return res;
}

/* m6-graded step 2b: Then on graded arrows (spec Table 4 l.893-909: Graded arrows are functions, defects add,
 * l.802 delta(g o h) <= delta(h) + delta(g)).  The only producer of a graded arrow is InduceApprox, whose
 * (Output D AbstractionMap) has Source = an admitted machine and Target = the induced machine (Output D Machine).
 * InduceApprox never accepts an induced machine as its source, so target(first) = source(second) cannot hold:
 * the registry entry for Then answers a target/source mismatch with InvalidInput, and the reason says why the
 * chain is unreachable.  A premise that is not Checked is a missing hypothesis -> Unsupported.  A graded arrow
 * next to an arrow of another kind -> InvalidInput (kinds are never coerced). */
int dc_eval_beyond_release(void);   /* api.h */
static int then_is_graded(const DcModule *m, const Sx *x) {
    if (!sx_head_is(x, "Output") || x->n != 3 || x->items[1]->kind != SX_SYM) return 0;
    int d = dc_find_derive(m, x->items[1]->text);
    return d >= 0 && sx_head_is(m->der[d].request, "InduceApprox");
}
static const char *then_bind(const Sx *res, const char *f) {
    const Sx *b = sx_find(res, "Binding", 1), *s = b ? sx_find(b, f, 1) : NULL;
    return s && s->n == 2 && s->items[1]->kind == SX_SYM ? s->items[1]->text : "?";
}
static Sx *then_graded(DcRun *r, const Sx *q) {
    DcModule *m = r->m; const Sx *res[2]; const char *dn[2];
    for (int k = 0; k < 2; k++) {
        const Sx *x = q->items[k + 1];
        if (!then_is_graded(m, x)) return dc_invalid(m, "Then: %s is not a graded arrow but the other premise is (InduceApprox); spec Table 4 composes arrows of one kind, kinds are never coerced", x->n >= 2 && x->items[1]->kind == SX_SYM ? x->items[1]->text : "a premise");
        if (!sx_is_sym(x->items[2], "AbstractionMap")) return dc_invalid(m, "Then: a graded premise is (Output D AbstractionMap)");
        dn[k] = x->items[1]->text; int d = dc_find_derive(m, dn[k]);
        res[k] = dc_run_derive(r, d);
        if (!res[k]) return dc_invalid(m, "Then: Derive %s: cyclic reference", dn[k]);
        DcStatus st = dc_result_status(res[k]);
        if (st != DC_CHECKED) return dc_unsupported(m, "Then: premise Derive %s is %s, not Checked: the hypothesis that it is a graded arrow is missing, so there is nothing to compose", dn[k], dc_status_name(st));
    }
    return dc_invalid(m, "Then: the target of %s is the induced machine (Output %s Machine) but %s abstracts the admitted machine %s; graded arrows compose only when target(first) = source(second) "
                      "(defects would add, spec l.802), and InduceApprox does not take an induced machine as its source in this release, so no graded chain exists to compose", dn[0], dn[0], dn[1], then_bind(res[1], "Source"));
}
Sx *dc_req_then(DcRun *r, const Sx *q, int slot) {
    DcModule *m = r->m; char why[256]; int d[2];
    if (q->n != 3) return dc_invalid(m, "Then: expected two arrows");
    if (dc_eval_beyond_release() && (then_is_graded(m, q->items[1]) || then_is_graded(m, q->items[2]))) return then_graded(r, q);   /* m6-graded step 2b (beyond release only; release answers stay byte-identical) */
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
    /* review 4 F6: classify the composite by its own image, not by f && g:
     * surjective iff g(f(s)) over the valid source states hits every valid
     * target state (a non-surjective f can compose to a surjective g . f). */
    {
        int *hit = calloc(T->n ? T->n : 1, sizeof(int));
        for (size_t s = 0; s < S->n; s++) if (!f->src_valid || f->src_valid[s]) hit[A.table[s]] = 1;
        A.surjective = 1;
        for (size_t t = 0; t < T->n; t++) if ((!g->tgt_valid || g->tgt_valid[t]) && !hit[t]) A.surjective = 0;
        free(hit);
    }
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
    if (slot >= 0) { A.src_valid = mask_dup(f->src_valid, S->n); A.tgt_valid = mask_dup(g->tgt_valid, T->n); r->arrow[slot] = A; r->arrow_kind[slot] = 3; } else free(A.table);
    return res;
}
