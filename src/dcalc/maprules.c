/* One shared admission loader for the map rules: see maprules.h. */
#include "maprules.h"

void dc_mr_init(DcMrTab *t, int n, int *buf) {
    t->n = n; t->val = buf; t->nset = 0;
    for (int k = 0; k < n; k++) buf[k] = -1;
}
int dc_mr_put(DcMrTab *t, int key, int value) {
    if (key < 0 || key >= t->n) return DC_MR_KEY;
    if (value < 0) return DC_MR_CODOMAIN;
    if (t->val[key] >= 0) return DC_MR_DUP;
    t->val[key] = value; t->nset++;
    return DC_MR_OK;
}
int dc_mr_mark(DcMrTab *t, int key) { return dc_mr_put(t, key, 0); }
int dc_mr_value(int value) { return value < 0 ? DC_MR_CODOMAIN : DC_MR_OK; }
int dc_mr_missing(const DcMrTab *t, int key) { return key >= 0 && key < t->n && t->val[key] >= 0 ? DC_MR_OK : DC_MR_PARTIAL; }
int dc_mr_total(const DcMrTab *t, int *missing) {
    for (int k = 0; k < t->n; k++) if (dc_mr_missing(t, k)) { if (missing) *missing = k; return DC_MR_PARTIAL; }
    return DC_MR_OK;
}
int dc_mr_mass_entry(DcQ w) { return dc_q_sign(w) < 0 ? DC_MR_MASS_NEG : DC_MR_OK; }
int dc_mr_mass_row(DcQ sum) {
    int ovf = 0;
    return dc_q_cmp(sum, dc_q(1, 1, &ovf)) ? DC_MR_MASS_SUM : DC_MR_OK;
}
