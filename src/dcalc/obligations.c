/* Obligation generator (boundary 3): Current, Update, Congruence. */
#include "obligations.h"
#include "ops_internal.h"
#include <stdlib.h>
#include <string.h>

static const char *OBL[] = { "Current", "Update", "Congruence" };
const char *dc_obl_name(DcOblKind k) { return (unsigned)k < 3 ? OBL[k] : "?"; }

size_t dc_obligations_for_induce(DcOblKind out[3]) {
    out[0] = OBL_CURRENT; out[1] = OBL_UPDATE; out[2] = OBL_CONGRUENCE; return 3;
}

/* code equality: literal, or under the representation's trivial tolerance */
static int code_eq(const DcRepr *r, int a, int b, int literal) {
    if (!literal && r->codes == DC_CODES_ALL) return 1;
    return a == b;
}

/* Least failing (pair, port) for obligation k, or -1/-1 when it holds. */
static int search(const DcModule *m, int ri, DcOblKind k, int *pi, int *pj, int *pk) {
    const DcRepr *r = &m->rep[ri];
    const DcMachine *mc = &m->mach[r->machine];
    const int *enc = m->map[r->encode].table;
    size_t n = m->car[mc->states].n;
    int literal = (k == OBL_CONGRUENCE);
    for (size_t i = 0; i < n; i++)
        for (size_t j = i + 1; j < n; j++) {
            if (!code_eq(r, enc[i], enc[j], literal)) continue;
            if (k == OBL_CURRENT) {
                for (size_t p = 0; p < mc->nobs; p++) {
                    const int *o = m->map[mc->obs[p].map].table;
                    if (o[i] != o[j]) { *pi = (int)i; *pj = (int)j; *pk = (int)p; return 0; }
                }
            } else {
                for (size_t p = 0; p < mc->nact; p++) {
                    const int *a = m->map[mc->act[p].map].table;
                    if (!code_eq(r, enc[a[i]], enc[a[j]], literal)) { *pi = (int)i; *pj = (int)j; *pk = (int)p; return 0; }
                }
            }
        }
    return 1;
}

int dc_obligation(const DcModule *m, int ri, DcOblKind k, Sx **wit) {
    int i, j, p;
    if (wit) *wit = NULL;
    if (search(m, ri, k, &i, &j, &p)) return 1;
    if (!wit) return 0;
    const DcRepr *r = &m->rep[ri];
    const DcMachine *mc = &m->mach[r->machine];
    const DcCarrier *S = &m->car[mc->states];
    const int *enc = m->map[r->encode].table;
    const DcCarrier *C = &m->car[m->map[r->encode].to];
    Sx *pair = dc_form("Pair", sx_copy(S->elems[i]), sx_copy(S->elems[j]), NULL);
    if (k == OBL_CURRENT) {
        const DcMap *o = &m->map[mc->obs[p].map]; const DcCarrier *O = &m->car[o->to];
        *wit = dc_form("CurrentWitness", pair, dc_form("Observe", dc_sym(mc->obs[p].label), NULL),
                       dc_form("Codes", sx_copy(C->elems[enc[i]]), sx_copy(C->elems[enc[j]]), NULL),
                       dc_form("Left", sx_copy(O->elems[o->table[i]]), NULL),
                       dc_form("Right", sx_copy(O->elems[o->table[j]]), NULL), NULL);
    } else {
        const int *a = m->map[mc->act[p].map].table;
        *wit = dc_form(k == OBL_UPDATE ? "UpdateWitness" : "CongruenceWitness", pair,
                       dc_form("Action", dc_sym(mc->act[p].label), NULL),
                       dc_form("Codes", sx_copy(C->elems[enc[i]]), sx_copy(C->elems[enc[j]]), NULL),
                       dc_form("Left", sx_copy(C->elems[enc[a[i]]]), NULL),
                       dc_form("Right", sx_copy(C->elems[enc[a[j]]]), NULL), NULL);
    }
    return 0;
}

/* Replay: recompute the failure for exactly the states/port named in wit. */
int dc_obligation_replay(const DcModule *m, int ri, DcOblKind k, const Sx *wit) {
    static const char *H[] = { "CurrentWitness", "UpdateWitness", "CongruenceWitness" };
    if (!wit || !sx_head_is(wit, H[k])) return 0;
    const DcRepr *r = &m->rep[ri];
    const DcMachine *mc = &m->mach[r->machine];
    const DcCarrier *S = &m->car[mc->states];
    const int *enc = m->map[r->encode].table;
    const Sx *pr = sx_find(wit, "Pair", 1), *po = sx_find(wit, k == OBL_CURRENT ? "Observe" : "Action", 1);
    if (!pr || pr->n != 3 || !po || po->n != 2 || po->items[1]->kind != SX_SYM) return 0;
    int i = dc_carrier_index(S, pr->items[1]), j = dc_carrier_index(S, pr->items[2]);
    if (i < 0 || j < 0 || i == j) return 0;
    int literal = (k == OBL_CONGRUENCE);
    if (!code_eq(r, enc[i], enc[j], literal)) return 0;
    if (k == OBL_CURRENT) {
        for (size_t p = 0; p < mc->nobs; p++) if (!strcmp(mc->obs[p].label, po->items[1]->text)) {
            const int *o = m->map[mc->obs[p].map].table; return o[i] != o[j];
        }
        return 0;
    }
    for (size_t p = 0; p < mc->nact; p++) if (!strcmp(mc->act[p].label, po->items[1]->text)) {
        const int *a = m->map[mc->act[p].map].table; return !code_eq(r, enc[a[i]], enc[a[j]], literal);
    }
    return 0;
}
