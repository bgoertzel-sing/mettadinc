/* M0 requests, part 2: InduceExact (quotient machine + abstraction arrow). */
#include "ops_internal.h"
#include "obligations.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Build the quotient view of representation ri: states are the codes in the
 * image of the encoding; observations and actions are read through any
 * preimage (well defined because the obligations hold). */
static void quotient_view(const DcModule *m, int ri, const char *id, DcView *v) {
    const DcRepr *r = &m->rep[ri]; const DcMachine *mc = &m->mach[r->machine];
    const DcMap *enc = &m->map[r->encode];
    size_t ns = m->car[mc->states].n, nc = m->car[enc->to].n;
    memset(v, 0, sizeof *v);
    snprintf(v->id, sizeof v->id, "%s", id);
    v->states = enc->to; v->n = nc;
    v->valid = calloc(nc ? nc : 1, sizeof(int));
    int *pre = malloc((nc ? nc : 1) * sizeof(int));
    for (size_t c = 0; c < nc; c++) pre[c] = -1;
    for (size_t s = 0; s < ns; s++) if (pre[enc->table[s]] < 0) { pre[enc->table[s]] = (int)s; v->valid[enc->table[s]] = 1; }
    v->nobs = mc->nobs; v->nact = mc->nact;
    for (size_t k = 0; k < mc->nobs; k++) {
        snprintf(v->obs_label[k], DC_MAX_NAME, "%s", mc->obs[k].label);
        v->obs_car[k] = m->map[mc->obs[k].map].to;
        v->obs[k] = calloc(nc ? nc : 1, sizeof(int));
        for (size_t c = 0; c < nc; c++) if (pre[c] >= 0) v->obs[k][c] = m->map[mc->obs[k].map].table[pre[c]];
    }
    for (size_t k = 0; k < mc->nact; k++) {
        snprintf(v->act_label[k], DC_MAX_NAME, "%s", mc->act[k].label);
        v->act[k] = calloc(nc ? nc : 1, sizeof(int));
        for (size_t c = 0; c < nc; c++) if (pre[c] >= 0) v->act[k][c] = enc->table[m->map[mc->act[k].map].table[pre[c]]];
    }
    free(pre);
}

Sx *dc_req_induce_exact(DcRun *r, const Sx *q, int slot) {
    DcModule *m = r->m;
    if (q->n < 2 || q->items[1]->kind != SX_SYM) return dc_invalid(m, "InduceExact: field Representation missing or not a name");
    const char *nm = q->items[1]->text; int ri = dc_find_repr(m, nm);
    if (ri < 0) {
        if (dc_declared_unsupported(m, nm)) return dc_unsupported(m, "InduceExact: Representation %s is outside the M0 fragment", nm);
        return dc_invalid(m, "InduceExact: field Representation names no declared representation (%s)", nm);
    }
    if (q->n != 2) return dc_invalid(m, "InduceExact: field 2 is unexpected; InduceExact takes one Representation");
    const DcRepr *rp = &m->rep[ri];
    Sx *subject = dc_form("Subject", dc_form("Representation", dc_sym(rp->name), NULL),
                          dc_form("Machine", dc_sym(m->mach[rp->machine].name), NULL), NULL);
    /* Boundary 3: obligations come from the admitted IR and carry its digest. */
    DcObligationRec ob[3]; size_t nk = dc_obligations_emit(m, ri, ob);
    DcOblKind ks[3]; for (size_t i = 0; i < nk; i++) ks[i] = ob[i].kind;
    Sx *checked = dc_form("Obligations", NULL);
    for (size_t i = 0; i < nk; i++) {
        Sx *w = NULL;
        if (!dc_obligation(m, ri, ks[i], &w)) {
            int rep = dc_obligation_replay(m, ri, ks[i], w);
            sx_free(checked);
            return dc_envelope(m, VERDICT_FAILS, rep, dc_claim_of(q, "Literal"), subject,
                dc_form("Value", dc_form("Refutation", dc_form("Obligation", dc_sym(dc_obl_name(ks[i])), NULL), NULL), NULL),
                dc_form("Evidence", dc_obligation_form(m, &ob[i]), dc_form("Witness", w, NULL), NULL), NULL);
        }
        sx_push(checked, dc_obligation_form(m, &ob[i]));
    }
    /* All obligations hold: the quotient exists.  Certificate = the code
     * classes (literal), replayed independently of the search above. */
    const DcMachine *mc = &m->mach[rp->machine]; const DcCarrier *S = &m->car[mc->states];
    const DcMap *enc = &m->map[rp->encode]; const DcCarrier *C = &m->car[enc->to];
    Sx *fib = dc_form("Fibers", NULL);
    for (size_t c = 0; c < C->n; c++) {
        Sx *b = NULL;
        for (size_t s = 0; s < S->n; s++) if (enc->table[s] == (int)c) {
            if (!b) b = dc_form("Fiber", sx_copy(C->elems[c]), NULL);
            sx_push(b, sx_copy(S->elems[s]));
        }
        if (b) sx_push(fib, b);
    }
    /* replay: every state in exactly one fiber, fiber code = encode(state),
     * obs constant and actions fiber-to-fiber inside each fiber */
    int ok = 1; size_t seen = 0;
    for (size_t b = 1; b < fib->n && ok; b++) {
        const Sx *F = fib->items[b]; int c = dc_carrier_index(C, F->items[1]); int s0 = -1;
        for (size_t k = 2; k < F->n && ok; k++) {
            int s = dc_carrier_index(S, F->items[k]);
            if (s < 0 || c < 0 || enc->table[s] != c) { ok = 0; break; }
            seen++;
            if (s0 < 0) { s0 = s; continue; }
            for (size_t p = 0; p < mc->nobs; p++) if (m->map[mc->obs[p].map].table[s] != m->map[mc->obs[p].map].table[s0]) ok = 0;
            for (size_t p = 0; p < mc->nact; p++) { const int *a = m->map[mc->act[p].map].table; if (enc->table[a[s]] != enc->table[a[s0]]) ok = 0; }
        }
    }
    if (seen != S->n) ok = 0;
    char id[160] = "(Output ? Machine)";
    if (slot >= 0) {
        snprintf(id, sizeof id, "(Output %s Machine)", m->der[slot].name);
        r->has_view[slot] = 1; quotient_view(m, ri, id, &r->view[slot]);
        DcArrow *A = &r->arrow[slot]; r->arrow_kind[slot] = 1;
        A->src = rp->machine; A->tgt = -1; A->src_car = mc->states; A->tgt_car = enc->to;
        A->table = malloc((S->n ? S->n : 1) * sizeof(int)); memcpy(A->table, enc->table, S->n * sizeof(int));
        A->surjective = 1;
        snprintf(A->src_id, sizeof A->src_id, "%s", mc->name); snprintf(A->tgt_id, sizeof A->tgt_id, "%s", id);
    }
    size_t nblocks = fib->n - 1;
    Sx *cert = dc_form("Certificate", dc_form("Kind", dc_sym("Prefixpoint"), NULL), dc_form("Checks", sx_copy(checked), NULL), fib, NULL);
    sx_free(checked);
    return dc_envelope(m, VERDICT_HOLDS, ok, dc_claim_of(q, "Literal"), subject,
        dc_form("Value", dc_form("ExactAbstraction", dc_form("Defect", dc_form("Interval", dc_int(0), dc_int(0), NULL), NULL),
                 dc_form("Machine", dc_sym(id), NULL), dc_form("States", dc_int((long)nblocks), NULL),
                 dc_form("Encode", dc_sym(enc->name), NULL), NULL), NULL),
        dc_form("Evidence", cert, NULL), NULL);
}
