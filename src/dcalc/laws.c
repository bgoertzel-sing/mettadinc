/* Library Laws (t-2026-11-27-mettadinc-laws); see laws.h.  Reference: metta_eval.py l.223-248. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "laws.h"
#include "model.h"

void dc_law_init(DcLaw *L) { memset(L, 0, sizeof *L); }
void dc_law_free(DcLaw *L) {
    for (size_t i = 0; i < L->n; i++) sx_free(L->val[i]);
    free(L->val); free(L->m); memset(L, 0, sizeof *L);
}
int dc_law_add(DcLaw *L, const Sx *v, DcQ m, int *ovf) {
    if (dc_q_is_zero(m)) return 0;
    for (size_t i = 0; i < L->n; i++) if (sx_equal(L->val[i], v)) { L->m[i] = dc_q_add(L->m[i], m, ovf); return 0; }
    if (L->n == L->cap) {
        size_t c = L->cap ? 2 * L->cap : 8;
        Sx **nv = realloc(L->val, c * sizeof *nv); if (!nv) return -1; L->val = nv;
        DcQ *nm = realloc(L->m, c * sizeof *nm); if (!nm) return -1; L->m = nm;
        L->cap = c;
    }
    L->val[L->n] = sx_copy(v); L->m[L->n] = m; L->n++;
    return 0;
}
int dc_law_head(const Sx *e) {
    return sx_head_is(e, "Point") || sx_head_is(e, "Coin") || sx_head_is(e, "Indep") || sx_head_is(e, "Image") || sx_head_is(e, "LawOf") || sx_head_is(e, "%Masses");
}
static int q_of(const Sx *v, DcQ *o) {
    DcRat r; if (dc_sx_rat(v, &r)) return -1; *o = dc_q_from_rat(r); return 0;
}
/* body with every occurrence of symbol var replaced by val (fresh) */
static Sx *subst(const Sx *b, const char *var, const Sx *val) {
    if (b->kind == SX_SYM && !strcmp(b->text, var)) return sx_copy(val);
    if (b->kind != SX_LIST) return sx_copy(b);
    Sx *l = sx_list();
    for (size_t i = 0; i < b->n; i++) sx_push(l, subst(b->items[i], var, val));
    return l;
}
#define WHY(...) do { snprintf(why, ws, __VA_ARGS__); return -1; } while (0)
int dc_law_eval(const Sx *e, DcLawLeaf leaf, void *ctx, DcLaw *out, int *ovf, char *why, size_t ws) {
    if (sx_head_is(e, "LawOf")) {
        if (e->n != 2) WHY("(LawOf ...) takes 1 argument");
        return dc_law_eval(e->items[1], leaf, ctx, out, ovf, why, ws);
    }
    if (sx_head_is(e, "Point")) {
        if (e->n != 2) WHY("(Point ...) takes 1 argument");
        int ok = 1; Sx *v = leaf(e->items[1], ctx, &ok);
        if (ok != 1) { sx_free(v); WHY("the value of a Point does not evaluate"); }
        int r = dc_law_add(out, v, dc_q(1, 1, ovf), ovf); sx_free(v);
        if (r) WHY("out of memory in a law");
        return 0;
    }
    if (sx_head_is(e, "Coin")) {
        if (e->n != 2) WHY("(Coin ...) takes 1 argument");
        int ok = 1; Sx *v = leaf(e->items[1], ctx, &ok); DcQ p;
        if (ok != 1 || q_of(v, &p)) { sx_free(v); WHY("the probability of a Coin is not a rational"); }
        sx_free(v);
        if (dc_q_sign(p) < 0 || dc_q_cmp(p, dc_q(1, 1, ovf)) > 0) WHY("the probability of a Coin is outside [0, 1]");
        Sx *one = sx_sym("1"), *zero = sx_sym("0");
        int r = dc_law_add(out, one, p, ovf) || dc_law_add(out, zero, dc_q_sub(dc_q(1, 1, ovf), p, ovf), ovf);
        sx_free(one); sx_free(zero);
        if (r) WHY("out of memory in a law");
        return 0;
    }
    if (sx_head_is(e, "Indep")) {
        if (e->n < 2) WHY("(Indep ...) needs at least one law");
        DcLaw acc; dc_law_init(&acc);
        Sx *t = sx_list(); sx_push(t, sx_sym("Tuple"));
        if (dc_law_add(&acc, t, dc_q(1, 1, ovf), ovf)) { sx_free(t); WHY("out of memory in a law"); }
        sx_free(t);
        for (size_t k = 1; k < e->n; k++) {
            DcLaw f, nx; dc_law_init(&f); dc_law_init(&nx);
            if (dc_law_eval(e->items[k], leaf, ctx, &f, ovf, why, ws)) { dc_law_free(&f); dc_law_free(&acc); return -1; }
            for (size_t i = 0; i < acc.n; i++) for (size_t j = 0; j < f.n; j++) {
                Sx *v = sx_copy(acc.val[i]); sx_push(v, sx_copy(f.val[j]));
                int r = dc_law_add(&nx, v, dc_q_mul(acc.m[i], f.m[j], ovf), ovf); sx_free(v);
                if (r) { dc_law_free(&f); dc_law_free(&nx); dc_law_free(&acc); WHY("out of memory in a law"); }
            }
            dc_law_free(&f); dc_law_free(&acc); acc = nx;
        }
        for (size_t i = 0; i < acc.n; i++) if (dc_law_add(out, acc.val[i], acc.m[i], ovf)) { dc_law_free(&acc); WHY("out of memory in a law"); }
        dc_law_free(&acc);
        return 0;
    }
    if (sx_head_is(e, "Image")) {
        if (e->n != 4 || e->items[1]->kind != SX_SYM || e->items[1]->text[0] != '$') WHY("(Image $x body law) takes a variable, a body and a law");
        DcLaw in; dc_law_init(&in);
        if (dc_law_eval(e->items[3], leaf, ctx, &in, ovf, why, ws)) { dc_law_free(&in); return -1; }
        for (size_t i = 0; i < in.n; i++) {
            Sx *b = subst(e->items[2], e->items[1]->text, in.val[i]); int ok = 1;
            Sx *w = leaf(b, ctx, &ok); sx_free(b);
            if (ok != 1) { sx_free(w); dc_law_free(&in); WHY("the body of an Image does not evaluate"); }
            int r = dc_law_add(out, w, in.m[i], ovf); sx_free(w);
            if (r) { dc_law_free(&in); WHY("out of memory in a law"); }
        }
        dc_law_free(&in);
        return 0;
    }
    if (sx_head_is(e, "%Masses")) {   /* a declared measure as the leaf expands it: (%Masses (v q) ..) */
        DcQ sum = dc_q(0, 1, ovf);
        for (size_t k = 1; k < e->n; k++) {
            const Sx *c = e->items[k]; DcQ q;
            if (c->kind != SX_LIST || c->n != 2 || q_of(c->items[1], &q) || dc_q_sign(q) < 0) WHY("a mass of a measure is not a non-negative rational");
            sum = dc_q_add(sum, q, ovf);
            if (dc_law_add(out, c->items[0], q, ovf)) WHY("out of memory in a law");
        }
        if (dc_q_cmp(sum, dc_q(1, 1, ovf))) WHY("the masses of a measure do not sum to 1");
        return 0;
    }
    /* anything else: a leaf that must itself denote a law (e.g. a map call returning a law) */
    int ok = 1; Sx *v = leaf(e, ctx, &ok);
    if (ok == 1 && dc_law_head(v) && !sx_equal(v, e)) { int r = dc_law_eval(v, leaf, ctx, out, ovf, why, ws); sx_free(v); return r; }
    sx_free(v);
    WHY("expression is not a law");
}
int dc_law_expect(const DcLaw *L, DcQ *out, int *ovf) {
    DcQ s = dc_q(0, 1, ovf);
    for (size_t i = 0; i < L->n; i++) { DcQ v; if (q_of(L->val[i], &v)) return -1; s = dc_q_add(s, dc_q_mul(v, L->m[i], ovf), ovf); }
    *out = s; return 0;
}

/* Closed value arithmetic for law bodies (Image bodies, Coin probabilities), the subset of the
 * reference evaluator metta_eval.py ev l.155-215 that law terms use: numerals and (Rat p q) as exact
 * rationals (normalised: integer -> numeral, else (Rat p q)), Tuple/GetTuple, If/Eq/Lt/Le/And/Or/Not,
 * Add/Sub/Mul/Div/Min/Max.  Other symbols stay symbols.  *ok = 0 on anything else (variables, map calls,
 * division by zero, a non-boolean condition), so the caller reports "does not evaluate", never a guess. */
static Sx *q_sx(DcQ q) {
    char buf[128]; const char *s = dc_q_str(q, buf, sizeof buf), *sl = strchr(s, '/');
    if (!sl) return sx_sym(s);
    size_t k = (size_t)(sl - s); char *a = malloc(k + 1); if (!a) return NULL;
    memcpy(a, s, k); a[k] = 0;
    Sx *l = sx_list(); sx_push(l, sx_sym("Rat")); sx_push(l, sx_sym(a)); sx_push(l, sx_sym(sl + 1)); free(a);
    return l;
}
static int as_bool(const Sx *v, int *b) {
    if (sx_is_sym(v, "True")) { *b = 1; return 0; }
    if (sx_is_sym(v, "False")) { *b = 0; return 0; }
    return -1;
}
static Sx *bad(const Sx *e, int *ok) { *ok = 0; return sx_copy(e); }
/* evaluate e->items[i] to a rational */
static int arg_q(const Sx *e, size_t i, DcQ *q, int *ok, int *ovf) {
    Sx *v = dc_law_arith(e->items[i], ok, ovf); int r = *ok == 1 && !q_of(v, q) ? 0 : -1; sx_free(v); return r;
}
static int arg_b(const Sx *e, size_t i, int *b, int *ok, int *ovf) {
    Sx *v = dc_law_arith(e->items[i], ok, ovf); int r = *ok == 1 && !as_bool(v, b) ? 0 : -1; sx_free(v); return r;
}
static Sx *arith_leaf(const Sx *e, void *ctx, int *ok) { return dc_law_arith(e, ok, (int *)ctx); }
Sx *dc_law_arith(const Sx *e, int *ok, int *ovf) {
    if (e->kind == SX_SYM) {
        DcQ q; if (e->text[0] == '$') return bad(e, ok);
        if (!q_of(e, &q)) return q_sx(q);
        return sx_copy(e);
    }
    if (e->kind != SX_LIST || e->n == 0) return sx_copy(e);
    if (sx_head_is(e, "Rat")) { DcQ q; if (q_of(e, &q)) return bad(e, ok); return q_sx(q); }
    if (sx_head_is(e, "Tuple")) {
        Sx *l = sx_list(); sx_push(l, sx_sym("Tuple"));
        for (size_t i = 1; i < e->n; i++) sx_push(l, dc_law_arith(e->items[i], ok, ovf));
        return l;
    }
    if (sx_head_is(e, "GetTuple") && e->n == 3 && e->items[2]->kind == SX_SYM) {
        char *end; long k = strtol(e->items[2]->text, &end, 10);
        Sx *t = dc_law_arith(e->items[1], ok, ovf);
        if (*ok == 1 && !*end && sx_head_is(t, "Tuple") && k >= 0 && (size_t)k + 1 < t->n) { Sx *r = sx_copy(t->items[k + 1]); sx_free(t); return r; }
        sx_free(t); return bad(e, ok);
    }
    if (sx_head_is(e, "If") && e->n == 4) { int b; if (arg_b(e, 1, &b, ok, ovf)) return bad(e, ok); return dc_law_arith(e->items[b ? 2 : 3], ok, ovf); }
    if (sx_head_is(e, "Not") && e->n == 2) { int b; if (arg_b(e, 1, &b, ok, ovf)) return bad(e, ok); return sx_sym(b ? "False" : "True"); }
    if ((sx_head_is(e, "And") || sx_head_is(e, "Or")) && e->n >= 1) {   /* short-circuit, like all()/any() */
        int isand = sx_head_is(e, "And");
        for (size_t i = 1; i < e->n; i++) { int b; if (arg_b(e, i, &b, ok, ovf)) return bad(e, ok); if (b != isand) return sx_sym(b ? "True" : "False"); }
        return sx_sym(isand ? "True" : "False");
    }
    if (sx_head_is(e, "Eq") && e->n == 3) {
        Sx *a = dc_law_arith(e->items[1], ok, ovf), *b = dc_law_arith(e->items[2], ok, ovf);
        int eq = sx_equal(a, b); sx_free(a); sx_free(b);
        if (*ok != 1) return bad(e, ok);
        return sx_sym(eq ? "True" : "False");
    }
    if ((sx_head_is(e, "Lt") || sx_head_is(e, "Le") || sx_head_is(e, "Sub") || sx_head_is(e, "Div")
         || sx_head_is(e, "Min") || sx_head_is(e, "Max")) && e->n == 3) {
        DcQ a, b; if (arg_q(e, 1, &a, ok, ovf) || arg_q(e, 2, &b, ok, ovf)) return bad(e, ok);
        int c = dc_q_cmp(a, b);
        if (sx_head_is(e, "Lt")) return sx_sym(c < 0 ? "True" : "False");
        if (sx_head_is(e, "Le")) return sx_sym(c <= 0 ? "True" : "False");
        if (sx_head_is(e, "Sub")) return q_sx(dc_q_sub(a, b, ovf));
        if (sx_head_is(e, "Min")) return q_sx(c <= 0 ? a : b);
        if (sx_head_is(e, "Max")) return q_sx(c >= 0 ? a : b);
        if (dc_q_is_zero(b)) return bad(e, ok);
        return q_sx(dc_q_div(a, b, ovf));
    }
    if (sx_head_is(e, "Add") || sx_head_is(e, "Mul")) {
        int add = sx_head_is(e, "Add"); DcQ s = dc_q(add ? 0 : 1, 1, ovf);
        for (size_t i = 1; i < e->n; i++) { DcQ a; if (arg_q(e, i, &a, ok, ovf)) return bad(e, ok); s = add ? dc_q_add(s, a, ovf) : dc_q_mul(s, a, ovf); }
        return q_sx(s);
    }
    if (sx_head_is(e, "Expect") && e->n == 2) {   /* metta_eval.py l.247: sum v*m over the law */
        DcLaw L; DcQ x; char why[160]; dc_law_init(&L);
        int r = dc_law_eval(e->items[1], arith_leaf, ovf, &L, ovf, why, sizeof why) || dc_law_expect(&L, &x, ovf);
        dc_law_free(&L);
        if (r) return bad(e, ok);
        return q_sx(x);
    }
    return bad(e, ok);
}
