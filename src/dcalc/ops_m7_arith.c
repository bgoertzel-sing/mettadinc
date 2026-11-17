#include "ops_internal.h"
#include "ops_run.h"
#include "model.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdlib.h>
/* M7 (Use Discovery) draft: exact F7 4x4 matrix evaluator for arithmetic_probes (X01-X04). */
#define P7 7
typedef struct { int a[4][4]; } M4;
typedef struct { const char *kvar; const Sx *kval; const char *ivar; long ival; } A7Env;
static int md(long x) { x %= P7; return x < 0 ? (int)x + P7 : (int)x; }
static int a7_int(const Sx *s, const A7Env *e, long *out) {
    if (!s || s->kind != SX_SYM) return 0;
    if (e && e->ivar && !strcmp(s->text, e->ivar)) { *out = e->ival; return 1; }
    char *x; long v = strtol(s->text, &x, 10); if (*x || x == s->text) return 0; *out = v; return 1;
}
static int a7_rank(int *M, int r, int c) {   /* Gaussian elimination mod 7, M is r x c, destroyed */
    int rk = 0;
    for (int col = 0; col < c && rk < r; col++) {
        int p = -1; for (int i = rk; i < r; i++) if (M[i * c + col]) { p = i; break; }
        if (p < 0) continue;
        for (int j = 0; j < c; j++) { int t = M[p * c + j]; M[p * c + j] = M[rk * c + j]; M[rk * c + j] = t; }
        int inv = 1; while (md((long)M[rk * c + col] * inv) != 1) inv++;
        for (int j = 0; j < c; j++) M[rk * c + j] = md((long)M[rk * c + j] * inv);
        for (int i = 0; i < r; i++) if (i != rk && M[i * c + col]) {
            int f = M[i * c + col]; for (int j = 0; j < c; j++) M[i * c + j] = md(M[i * c + j] - (long)f * M[rk * c + j]);
        }
        rk++;
    }
    return rk;
}
static const Sx *a7_field(const Sx *d, const char *h) {
    for (size_t i = 1; d && d->kind == SX_LIST && i < d->n; i++) if (sx_head_is(d->items[i], h)) return d->items[i];
    return NULL;
}
static int a7_mat_lit(const Sx *x, M4 *o) {
    if (!sx_head_is(x, "Matrix4") || x->n != 5) return 0;
    for (int i = 0; i < 4; i++) { const Sx *r = x->items[i + 1]; if (r->kind != SX_LIST || r->n != 4) return 0;
        for (int j = 0; j < 4; j++) { long v; if (!a7_int(r->items[j], NULL, &v)) return 0; o->a[i][j] = md(v); } }
    return 1;
}
static void a7_mul(const M4 *x, const M4 *y, M4 *o) {
    M4 t; for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) { long s = 0; for (int k = 0; k < 4; k++) s += (long)x->a[i][k] * y->a[k][j]; t.a[i][j] = md(s); } *o = t;
}
static int a7_mrank(const M4 *x) { int M[16]; for (int i = 0; i < 16; i++) M[i] = x->a[i / 4][i % 4]; return a7_rank(M, 4, 4); }
/* matrix-valued terms: I4, (Get $k F), (Sub A B), (Scale c A), (Square A) */
static int a7_mat(const Sx *b, const A7Env *e, M4 *o) {
    if (sx_is_sym(b, "I4")) { memset(o, 0, sizeof *o); for (int i = 0; i < 4; i++) o->a[i][i] = 1; return 1; }
    if (sx_head_is(b, "Get") && b->n == 3 && e->kvar && sx_is_sym(b->items[1], e->kvar) && b->items[2]->kind == SX_SYM) {
        const Sx *f = a7_field(e->kval, b->items[2]->text); return f && f->n == 2 && a7_mat_lit(f->items[1], o);
    }
    M4 x, y; long c;
    if (sx_head_is(b, "Sub") && b->n == 3 && a7_mat(b->items[1], e, &x) && a7_mat(b->items[2], e, &y)) {
        for (int i = 0; i < 16; i++) o->a[i / 4][i % 4] = md(x.a[i / 4][i % 4] - y.a[i / 4][i % 4]);
        return 1;
    }
    if (sx_head_is(b, "Scale") && b->n == 3 && a7_int(b->items[1], e, &c) && a7_mat(b->items[2], e, &x)) {
        for (int i = 0; i < 16; i++) o->a[i / 4][i % 4] = md(c * x.a[i / 4][i % 4]);
        return 1;
    }
    if (sx_head_is(b, "Square") && b->n == 2 && a7_mat(b->items[1], e, &x)) { a7_mul(&x, &x, o); return 1; }
    return 0;
}
/* value terms: (Rank A) -> n, (PowerRanks A n) -> (Tuple r1..rn), (Tuple v...) */
static Sx *a7_val(const Sx *b, const A7Env *e) {
    M4 x; long n; char buf[16];
    if (sx_head_is(b, "Rank") && b->n == 2 && a7_mat(b->items[1], e, &x)) { snprintf(buf, sizeof buf, "%d", a7_mrank(&x)); return sx_sym(buf); }
    if (sx_head_is(b, "PowerRanks") && b->n == 3 && a7_mat(b->items[1], e, &x) && a7_int(b->items[2], NULL, &n) && n >= 1 && n <= 8) {
        Sx *t = sx_list(); sx_push(t, sx_sym("Tuple")); M4 p = x;
        for (long i = 0; i < n; i++) { snprintf(buf, sizeof buf, "%d", a7_mrank(&p)); sx_push(t, sx_sym(buf)); a7_mul(&p, &x, &p); }
        return t;
    }
    if (sx_head_is(b, "Tuple")) {
        Sx *t = sx_list(); sx_push(t, sx_sym("Tuple"));
        for (size_t i = 1; i < b->n; i++) { Sx *v = a7_val(b->items[i], e); if (!v) { sx_free(t); return NULL; } sx_push(t, v); }
        return t;
    }
    return NULL;
}
/* dim {X : X A_f = B_f X for every field f} over F7 */
static int a7_hom_dim(const M4 *A, const M4 *B, int nf) {
    int rows = 16 * nf, M[16 * 4 * 16]; if (nf > 4) return -1; memset(M, 0, sizeof(int) * rows * 16);
    for (int f = 0; f < nf; f++) for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) {
        int *row = M + (f * 16 + i * 4 + j) * 16;
        for (int k = 0; k < 4; k++) { row[i * 4 + k] = md(row[i * 4 + k] + A[f].a[k][j]); row[k * 4 + j] = md(row[k * 4 + j] - B[f].a[i][k]); }
    }
    return 16 - a7_rank(M, rows, 16);
}
/* ---- request wrappers (X01-X04), appended after the a7 evaluator; gated on m->discovery ---- */
static const Sx *ar_decl(const DcModule *m, const char *head, const char *name) {
    const Sx *f = m->source;
    for (size_t i = 2; f && i < f->n; i++) { const Sx *d = f->items[i];
        if (sx_head_is(d, head) && d->n >= 2 && sx_is_sym(d->items[1], name)) return d; }
    return NULL;
}
static const Sx *ar_const(const DcModule *m, const char *name) { const Sx *c = ar_decl(m, "Const", name); return c && c->n == 4 ? c->items[3] : NULL; }
static Sx *ar_unsup(const DcModule *m, const DcScope *sc, Sx *claim, const char *why) {
    return dc_envelope_scoped(m, VERDICT_UNSUPPORTED, 0, claim, NULL, NULL, NULL, why, sc);
}
/* value of a Body map (Body ($k) e) on candidate constant `cand` */
static Sx *ar_apply(const DcModule *m, const Sx *map, const char *cand) {
    const Sx *bd = a7_field(map, "Body"); const Sx *k = ar_const(m, cand);
    if (!bd || bd->n != 3 || bd->items[1]->kind != SX_LIST || bd->items[1]->n != 1 || !k) return NULL;
    A7Env e = {bd->items[1]->items[0]->text, k, NULL, 0};
    return a7_val(bd->items[2], &e);
}
static int ar_enum(const DcModule *m, const char *car, const char **out, int max) {
    const Sx *c = ar_decl(m, "Carrier", car), *en = a7_field(c, "Enum"); int n = 0;
    for (size_t i = 1; en && i < en->n && n < max; i++) if (en->items[i]->kind == SX_SYM) out[n++] = en->items[i]->text;
    return n;
}
/* X01 (MinimizeForQueries Mach) and X03 (CheckNow Rep): observation codes of Body maps on candidate constants */
static Sx *ar_observe(DcRun *r, const Sx *q, const char *h) {
    DcModule *m = r->m; DcScope sc = {"M7-Discovery", -1, "", NULL}; Sx *claim = dc_claim_of(q, "Literal");
    const Sx *mach = NULL, *rep = NULL, *enc = NULL;
    if (!strcmp(h, "CheckNow")) { rep = ar_decl(m, "Representation", q->items[1]->text); if (!rep) return NULL;
        const Sx *of = a7_field(rep, "Of"), *en = a7_field(rep, "Encode");
        if (!of || !en) return ar_unsup(m, &sc, claim, "CheckNow: M7-Discovery reads (Representation R (Of M) (Encode map))");
        mach = ar_decl(m, "Machine", of->items[1]->text); enc = ar_decl(m, "Map", en->items[1]->text);
    } else mach = ar_decl(m, "Machine", q->items[1]->text);
    const Sx *st = a7_field(mach, "States"); const char *X[16]; int n = st ? ar_enum(m, st->items[1]->text, X, 16) : 0;
    int cand = n >= 1;   /* Discovery candidates only: states are declared Consts and every Observe map is a Body map */
    for (int i = 0; i < n; i++)
        if (!ar_const(m, X[i])) cand = 0;
    for (size_t j = 2; cand && j < mach->n; j++) {
        const Sx *o = mach->items[j];
        if (sx_head_is(o, "Observe") && o->n == 3 && !a7_field(ar_decl(m, "Map", o->items[2]->text), "Body")) cand = 0;
    }
    if (!cand) { sx_free(claim); return NULL; }   /* thread-A 04:33: fall through (e.g. FortyBits ZeroMachine) */
    /* obs[i] = printed tuple of all Observe map values on X[i]; code[i] = Encode value */
    char *obs[16] = {0}, *code[16] = {0}; int ok = 1;
    for (int i = 0; i < n && ok; i++) {
        Sx *row = sx_list();
        for (size_t j = 2; j < mach->n; j++) { const Sx *o = mach->items[j];
            if (!sx_head_is(o, "Observe") || o->n != 3) continue;
            Sx *v = ar_apply(m, ar_decl(m, "Map", o->items[2]->text), X[i]); if (!v) { ok = 0; break; } sx_push(row, v); }
        obs[i] = sx_print(row); sx_free(row);
        if (ok && enc) { Sx *v = ar_apply(m, enc, X[i]); if (!v) ok = 0; else { code[i] = sx_print(v); sx_free(v); } }
    }
    Sx *res = NULL;
    if (!ok) res = ar_unsup(m, &sc, claim, "M7-Discovery: an Observe/Encode map body is outside the F7 matrix evaluator");
    else if (enc) {   /* CheckNow: Refuted iff two states share a code but differ on an observation */
        Sx *wit = sx_list(); sx_push(wit, dc_sym("Witnesses"));
        for (int i = 0; i < n; i++) for (int j = i + 1; j < n; j++)
            if (!strcmp(code[i], code[j]) && strcmp(obs[i], obs[j])) sx_push(wit, dc_form("Pair", dc_sym(X[i]), dc_sym(X[j]), NULL));
        int bad = wit->n > 1;
        res = dc_envelope_scoped(m, bad ? VERDICT_FAILS : VERDICT_HOLDS, 1, claim,
            dc_form("Subject", dc_form("Representation", dc_sym(q->items[1]->text), NULL), NULL), NULL, dc_form("Evidence", wit, NULL), NULL, &sc);
    } else {   /* Minimize: blocks of equal observation rows, in carrier order */
        Sx *part = sx_list(); sx_push(part, dc_sym("Partition")); int used[16] = {0};
        for (int i = 0; i < n; i++) { if (used[i]) continue; Sx *b = sx_list(); sx_push(b, dc_sym("Block"));
            for (int j = i; j < n; j++) if (!used[j] && !strcmp(obs[i], obs[j])) { used[j] = 1; sx_push(b, dc_sym(X[j])); }
            sx_push(part, b);
        }
        res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, dc_form("Subject", dc_form("Machine", dc_sym(q->items[1]->text), NULL), NULL),
            dc_form("Value", dc_form("Refinement", dc_form("Representation", dc_sym("?"), NULL), part, NULL), NULL), NULL, NULL, &sc);
    }
    for (int i = 0; i < n; i++) { free(obs[i]); free(code[i]); }
    return res;
}
/* ---- X02 SeekSeparator over a generated ObserverFamily, X04 DecideEquivalence via Hom-dimensions ---- */
static int ar_field_mats(const DcModule *m, const char *cand, const Sx *fields, M4 *out) {
    const Sx *k = ar_const(m, cand); int nf = 0;
    for (size_t i = 1; k && fields && i < fields->n && nf < 4; i++) {
        const Sx *f = a7_field(k, fields->items[i]->text);
        if (!f || f->n != 2 || !a7_mat_lit(f->items[1], &out[nf])) return -1;
        nf++;
    }
    return k ? nf : -1;
}
static Sx *ar_separator(DcRun *r, const Sx *q) {
    DcModule *m = r->m; DcScope sc = {"M7-Discovery", -1, "", NULL}; Sx *claim = dc_claim_of(q, "Literal");
    const Sx *pr = a7_field(q, "Pair"), *fa = a7_field(q, "Family"), *bu = a7_field(q, "Budget");
    if (!pr || pr->n != 3 || !fa || fa->n != 2) return ar_unsup(m, &sc, claim, "SeekSeparator: (Pair A B) and (Family F) are required");
    const Sx *fam = ar_decl(m, "ObserverFamily", fa->items[1]->text), *gen = a7_field(fam, "Generate");
    const Sx *fo = gen && gen->n == 3 && sx_head_is(gen->items[1], "For") ? gen->items[1] : NULL;
    const Sx *ex = gen && gen->n == 3 ? gen->items[2] : NULL, *lam = ex && ex->n == 2 ? ex->items[1] : NULL;
    if (!fo || fo->n != 3 || !sx_head_is(fo->items[2], "Elements") || !sx_is_sym(fo->items[2]->items[1], "F7")
        || !sx_head_is(lam, "Lambda") || lam->n != 3 || lam->items[1]->n != 1)
        return ar_unsup(m, &sc, claim, "SeekSeparator: M7 reads (Generate (For $b (Elements F7)) (Expr (Lambda (($k T)) e))) only");
    long budget = 7; if (bu && bu->n == 2 && sx_head_is(bu->items[1], "Probes")) a7_int(bu->items[1]->items[1], NULL, &budget);
    const char *kv = lam->items[1]->items[0]->items[0]->text, *bv = fo->items[1]->text;
    const Sx *KA = ar_const(m, pr->items[1]->text), *KB = ar_const(m, pr->items[2]->text);
    if (!KA || !KB) return ar_unsup(m, &sc, claim, "SeekSeparator: pair members must be declared constants");
    Sx *tab = sx_list(); sx_push(tab, dc_sym("Table")); long found = -1; char va[32] = "", vb[32] = "";
    for (long b = 0; b < 7 && b < budget && found < 0; b++) {
        A7Env ea = {kv, KA, bv, b}, eb = {kv, KB, bv, b};
        Sx *x = a7_val(lam->items[2], &ea), *y = a7_val(lam->items[2], &eb);
        if (!x || !y) { sx_free(x); sx_free(y); sx_free(tab); return ar_unsup(m, &sc, claim, "SeekSeparator: probe body outside the F7 matrix evaluator"); }
        char bs[24]; snprintf(bs, sizeof bs, "%ld", b);
        char *px = sx_print(x), *py = sx_print(y);
        sx_push(tab, dc_form("Row", dc_form("Param", dc_sym(bs), NULL), dc_form(pr->items[1]->text, x, NULL), dc_form(pr->items[2]->text, y, NULL), NULL));
        if (strcmp(px, py)) { found = b; snprintf(va, sizeof va, "%s", px); snprintf(vb, sizeof vb, "%s", py); }
        free(px); free(py);
    }
    if (found < 0) return dc_envelope_scoped(m, VERDICT_FAILS, 1, claim, NULL, NULL, dc_form("Evidence", tab, NULL), NULL, &sc);
    char bs[24]; snprintf(bs, sizeof bs, "%ld", found);
    Sx *val = dc_form("SeparatorResult", dc_form("Observer", dc_form("Instance", dc_sym(fa->items[1]->text), dc_form(bv, dc_sym(bs), NULL), NULL), NULL),
        dc_form("Evaluations", tab, NULL),
        dc_form("Invariance", dc_form("Certificate", dc_form("Kind", dc_sym("StructuralMatrixRules"), NULL),
            dc_form("Rule", dc_sym("RankOfConjugationCovariantPolynomial"), NULL), NULL), NULL), NULL);
    return dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, dc_form("Subject", dc_form("Pair", dc_sym(pr->items[1]->text), dc_sym(pr->items[2]->text), NULL), NULL),
        dc_form("Value", val, NULL), NULL, NULL, &sc);
}
static Sx *ar_decide(DcRun *r, const Sx *q) {
    DcModule *m = r->m; DcScope sc = {"M7-Discovery", -1, "", NULL}; Sx *claim = dc_claim_of(q, "Literal");
    const Sx *os = q->n >= 3 && q->items[1]->kind == SX_SYM ? ar_decl(m, "ObserverSource", q->items[1]->text) : NULL;
    const Sx *pc = a7_field(os, "Procedure"), *pr = a7_field(q, "Pair");
    if (!os || !pc || !sx_is_sym(pc->items[1], "SimultaneousConjugacy") || !pr || pr->n != 3)
        return ar_unsup(m, &sc, claim, "DecideEquivalence: M7 decides (ObserverSource S (Procedure SimultaneousConjugacy)) on a (Pair A B) only");
    const Sx *rec = ar_decl(m, "Record", "MarkedPair"); Sx *fl = sx_list(); sx_push(fl, dc_sym("Fields"));
    for (size_t i = 2; rec && i < rec->n; i++) if (rec->items[i]->kind == SX_LIST && rec->items[i]->n >= 1) sx_push(fl, dc_sym(rec->items[i]->items[0]->text));
    M4 A[4], B[4]; int na = ar_field_mats(m, pr->items[1]->text, fl, A), nb = ar_field_mats(m, pr->items[2]->text, fl, B);
    sx_free(fl);
    if (na < 1 || na != nb) return ar_unsup(m, &sc, claim, "DecideEquivalence: pair members must be records of F7 4x4 matrices");
    int eA = a7_hom_dim(A, A, na), hAB = a7_hom_dim(A, B, na), eB = a7_hom_dim(B, B, na);
    char s1[8], s2[8], s3[8]; snprintf(s1, 8, "%d", eA); snprintf(s2, 8, "%d", hAB); snprintf(s3, 8, "%d", eB);
    int iso_possible = (eA == hAB && hAB == eB);
    Sx *tab = dc_form("Table", dc_form("Row", dc_sym("EndA"), dc_sym(s1), NULL), dc_form("Row", dc_sym("HomAB"), dc_sym(s2), NULL), dc_form("Row", dc_sym("EndB"), dc_sym(s3), NULL), NULL);
    if (iso_possible) return ar_unsup(m, &sc, claim, "DecideEquivalence: Hom-dimensions agree; M7 has no conjugator search");
    Sx *val = dc_form("EquivalenceDecision", dc_form("HomDimensions", tab, NULL),
        dc_form("Certificate", dc_form("Kind", dc_sym("HomDimensionMismatch"), NULL), NULL), NULL);
    return dc_envelope_scoped(m, VERDICT_FAILS, 1, claim, dc_form("Subject", dc_form("Pair", dc_sym(pr->items[1]->text), dc_sym(pr->items[2]->text), NULL), NULL),
        dc_form("Value", val, NULL), NULL, NULL, &sc);
}
Sx *dc_req_m7_arith(DcRun *r, const Sx *q, const char *h) {
    if (!r->m->discovery) return NULL;
    if (!strcmp(h, "SeekSeparator")) return ar_separator(r, q);
    if (!strcmp(h, "DecideEquivalence")) return ar_decide(r, q);
    if ((!strcmp(h, "MinimizeForQueries") || !strcmp(h, "CheckNow")) && q->n == 2 && q->items[1]->kind == SX_SYM) return ar_observe(r, q, h);
    return NULL;
}
