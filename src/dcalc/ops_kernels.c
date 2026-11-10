/* M2 GradedKernels library (spec Section 9.1): PathClosure (Lukasiewicz01),
 * Bracket under an independent uniform pair law, Delta between two brackets,
 * Threshold to a crisp relation, CheckTransitive (Boolean on relations,
 * Lukasiewicz on kernels).  Kernels are exact rational tables; a kernel output
 * is (Kernel (On C) (Entries (Entry a b r) ...)) and is read back from the
 * Checked premise, never recomputed from the fixture. */
#include "graded.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int car; size_t n; DcRat *k; int *rel; } GK;   /* rel != NULL: a crisp relation */
static const DcRat KZ = {0, 1}, K1 = {1, 1};
static Sx *rs(DcRat r) { char b[48]; dc_rat_str(r, b, sizeof b); return dc_sym(b); }
static void gk_free(GK *g) { free(g->k); free(g->rel); }
static int uses(const DcModule *m, const char *lib) {
    const Sx *src = m->source;
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (sx_head_is(d, "Use")) for (size_t k = 1; k < d->n; k++) if (sx_is_sym(d->items[k], lib)) return 1;
    }
    return 0;
}
/* (Output D what): the Value body of a Checked premise, NULL with *err set otherwise. */
static const Sx *premise(DcRun *run, const Sx *x, const char *what, const char *head, const char *req, Sx **err) {
    DcModule *m = run->m;
    if (!sx_head_is(x, "Output") || x->n != 3 || x->items[1]->kind != SX_SYM || !sx_is_sym(x->items[2], what)) {
        *err = dc_invalid(m, "%s: expected (Output D %s)", req, what); return NULL; }
    const char *dn = x->items[1]->text; int d = dc_find_derive(m, dn);
    if (d < 0) { *err = dc_invalid(m, "%s: names no declared Derive (%s)", req, dn); return NULL; }
    const Sx *pr = dc_run_derive(run, d);
    if (!pr) { *err = dc_invalid(m, "%s: Derive %s: cyclic reference", req, dn); return NULL; }
    DcStatus st = dc_result_status(pr);
    if (st == DC_UNSUPPORTED) { *err = dc_unsupported(m, "%s: premise Derive %s is outside the M2 fragment", req, dn); return NULL; }
    if (st != DC_CHECKED) { *err = dc_invalid(m, "%s: Output projects only from Checked results (Derive %s is %s)", req, dn, dc_status_name(st)); return NULL; }
    const Sx *v = sx_find(pr, "Value", 1), *b = v && v->n == 2 ? v->items[1] : NULL;
    if (!b || !sx_head_is(b, head)) { *err = dc_invalid(m, "%s: Derive %s has no %s output", req, dn, what); return NULL; }
    return b;
}
static int parse_table(const DcModule *m, const Sx *b, const char *list, GK *g, int rel) {
    const Sx *on = sx_find(b, "On", 1), *en = sx_find(b, list, 1);
    if (!on || on->n != 2 || on->items[1]->kind != SX_SYM || !en) return -1;
    if ((g->car = dc_find_carrier(m, on->items[1]->text)) < 0) return -1;
    size_t n = m->car[g->car].n, N = n ? n * n : 1; g->n = n;
    if (rel) g->rel = calloc(N, sizeof(int)); else g->k = calloc(N, sizeof(DcRat));
    char *set = calloc(N, 1); int bad = 0;
    for (size_t k = 1; k < en->n && !bad; k++) {
        const Sx *e = en->items[k]; DcRat v = K1;
        if (e->kind != SX_LIST || e->n != (size_t)(rel ? 3 : 4) || (!rel && dc_sx_rat(e->items[3], &v))) { bad = 1; break; }
        int a = dc_carrier_index(&m->car[g->car], e->items[1]), c = dc_carrier_index(&m->car[g->car], e->items[2]);
        if (a < 0 || c < 0 || (!rel && set[(size_t)a * n + c])) { bad = 1; break; }
        set[(size_t)a * n + c] = 1;
        if (rel) g->rel[(size_t)a * n + c] = 1; else g->k[(size_t)a * n + c] = v;
    }
    for (size_t i = 0; i < n * n && !bad && !rel; i++) if (!set[i]) bad = 1;
    free(set); return bad ? -1 : 0;
}
/* A kernel operand: a SymmetricTable tolerance or (Output D Kernel); with rel_ok also (Output D Relation). */
static Sx *operand(DcRun *run, const Sx *x, const char *req, int rel_ok, GK *g) {
    DcModule *m = run->m; memset(g, 0, sizeof *g); Sx *e = NULL;
    if (x->kind == SX_SYM) {
        int t = dc_find_tol(m, x->text);
        if (t < 0) return dc_declared_unsupported(m, x->text) ? dc_unsupported(m, "%s: kernel %s is outside the M2 fragment", req, x->text)
                                                              : dc_invalid(m, "%s: names no declared kernel (%s)", req, x->text);
        if (m->tol[t].kind != DC_TOL_SYM_TABLE) return dc_invalid(m, "%s: tolerance %s is not a kernel table", req, x->text);
        g->car = m->tol[t].on; g->n = m->car[g->car].n; g->k = malloc((g->n ? g->n * g->n : 1) * sizeof(DcRat));
        memcpy(g->k, m->tol[t].table, g->n * g->n * sizeof(DcRat)); return NULL;
    }
    if (rel_ok && sx_head_is(x, "Output") && x->n == 3 && sx_is_sym(x->items[2], "Relation")) {
        const Sx *b = premise(run, x, "Relation", "Relation", req, &e); if (!b) return e;
        if (parse_table(m, b, "Pairs", g, 1)) { gk_free(g); return dc_invalid(m, "%s: malformed Relation output", req); }
        return NULL;
    }
    const Sx *b = premise(run, x, "Kernel", "Kernel", req, &e); if (!b) return e;
    if (parse_table(m, b, "Entries", g, 0)) { gk_free(g); return dc_invalid(m, "%s: malformed Kernel output", req); }
    return NULL;
}
static Sx *kernel_sx(const DcModule *m, const GK *g) {
    const DcCarrier *C = &m->car[g->car]; size_t n = g->n; Sx *e = dc_form("Entries", NULL);
    for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++)
        sx_push(e, dc_form("Entry", sx_copy(C->elems[i]), sx_copy(C->elems[j]), rs(g->k[i * n + j]), NULL));
    return dc_form("Kernel", dc_form("On", dc_sym(C->name), NULL), e, NULL);
}
static Sx *relation_sx(const DcModule *m, const GK *g) {
    const DcCarrier *C = &m->car[g->car]; size_t n = g->n; Sx *e = dc_form("Pairs", NULL);
    for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++)
        if (g->rel[i * n + j]) sx_push(e, dc_form("Pair", sx_copy(C->elems[i]), sx_copy(C->elems[j]), NULL));
    return dc_form("Relation", dc_form("On", dc_sym(C->name), NULL), e, NULL);
}
static DcRat luk(DcRat a, DcRat b, int *ovf) { return dc_rat_max(KZ, dc_rat_sub(dc_rat_add(a, b, ovf), K1, ovf)); }
/* first (i,j,k) with T(i,j) and T(j,k) not below T(i,k); -1 if transitive */
static int intransitive(const GK *g, int *ti, int *tj, int *tk) {
    size_t n = g->n; int ovf = 0;
    for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++) for (size_t k = 0; k < n; k++) {
        int bad = g->rel ? (g->rel[i * n + j] && g->rel[j * n + k] && !g->rel[i * n + k])
                         : dc_rat_cmp(g->k[i * n + k], luk(g->k[i * n + j], g->k[j * n + k], &ovf)) < 0;
        if (bad) { *ti = (int)i; *tj = (int)j; *tk = (int)k; return 1; }
    }
    return 0;
}
static void push_path(Sx *p, const DcCarrier *C, const int *via, size_t n, int i, int j, size_t depth) {
    int k = via[(size_t)i * n + j]; if (k < 0 || depth > n) return;
    push_path(p, C, via, n, i, k, depth + 1); sx_push(p, sx_copy(C->elems[k])); push_path(p, C, via, n, k, j, depth + 1);
}

Sx *dc_req_kernels(DcRun *run, const Sx *q, const char *h, int slot) {
    DcModule *m = run->m; (void)slot; GK g; Sx *e, *val, *ev; DcVerdict vd = VERDICT_HOLDS; int rep = 1, ovf = 0;
    if (!uses(m, "GradedKernels")) return dc_unsupported(m, "%s: the module does not use GradedKernels", h);
    if (q->n < 2) return dc_invalid(m, "%s: operand missing", h);
    if (!strcmp(h, "PathClosure")) {
        const Sx *al = q->n == 3 ? q->items[2] : NULL;
        if (!sx_head_is(al, "Algebra") || al->n != 2) return dc_invalid(m, "PathClosure: expected (PathClosure K (Algebra Lukasiewicz01))");
        if (!sx_is_sym(al->items[1], "Lukasiewicz01")) return dc_unsupported(m, "PathClosure: algebra outside the M2 fragment");
        if ((e = operand(run, q->items[1], h, 0, &g))) return e;
        size_t n = g.n, N = n ? n * n : 1; DcRat *k0 = malloc(N * sizeof *k0); int *via = malloc(N * sizeof *via);
        memcpy(k0, g.k, n * n * sizeof *k0); for (size_t i = 0; i < N; i++) via[i] = -1;
        for (size_t k = 0; k < n; k++) for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++) {
            DcRat c = luk(g.k[i * n + k], g.k[k * n + j], &ovf);
            if (dc_rat_cmp(c, g.k[i * n + j]) > 0) { g.k[i * n + j] = c; via[i * n + j] = (int)k; }
        }
        const DcCarrier *C = &m->car[g.car]; Sx *raised = dc_form("Raised", NULL);
        for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++) if (dc_rat_cmp(g.k[i * n + j], k0[i * n + j]) > 0) {
            Sx *p = dc_form("Path", sx_copy(C->elems[i]), NULL); push_path(p, C, via, n, (int)i, (int)j, 0); sx_push(p, sx_copy(C->elems[j]));
            sx_push(raised, dc_form("Entry", sx_copy(C->elems[i]), sx_copy(C->elems[j]), rs(g.k[i * n + j]), p, NULL));
        }
        int a, b, c; rep = !intransitive(&g, &a, &b, &c);
        val = kernel_sx(m, &g);
        ev = dc_form("Certificate", dc_form("Kind", dc_sym("PathClosure"), NULL), dc_form("Algebra", dc_sym("Lukasiewicz01"), NULL), raised, NULL);
        free(k0); free(via);
    } else if (!strcmp(h, "Bracket")) {
        const Sx *un = q->n == 3 ? q->items[2] : NULL;
        if (!sx_head_is(un, "Under") || un->n != 2 || un->items[1]->kind != SX_SYM) return dc_invalid(m, "Bracket: expected (Bracket K (Under PairLaw))");
        const Sx *pl = NULL;
        for (size_t i = 2; m->source && i < m->source->n; i++) { const Sx *d = m->source->items[i];
            if (sx_head_is(d, "PairLaw") && d->n > 1 && sx_is_sym(d->items[1], un->items[1]->text)) pl = d; }
        if (!pl) return dc_invalid(m, "Bracket: field Under names no declared PairLaw (%s)", un->items[1]->text);
        if ((e = operand(run, q->items[1], h, 0, &g))) return e;
        const Sx *in = pl->n == 4 ? pl->items[2] : NULL; int ok = pl->n == 4 && sx_head_is(in, "Independent") && in->n == 3
            && sx_head_is(pl->items[3], "Diagonal") && pl->items[3]->n == 2 && sx_is_sym(pl->items[3]->items[1], "Included");
        for (size_t s = 1; ok && s < 3; s++) {
            int l = in->items[s]->kind == SX_SYM ? dc_find_meas(m, in->items[s]->text) : -1;
            ok = l >= 0 && m->meas[l].uniform && m->meas[l].on == g.car;
        }
        if (!ok) { gk_free(&g); return dc_unsupported(m, "Bracket: pair law %s is outside the M2 fragment (independent uniform laws on the kernel carrier, diagonal included)", un->items[1]->text); }
        DcRat sum = KZ; size_t n = g.n; for (size_t i = 0; i < n * n; i++) sum = dc_rat_add(sum, g.k[i], &ovf);
        DcRat mean = dc_rat_div(sum, dc_rat((int64_t)(n * n), 1, &ovf), &ovf);
        val = dc_form("Bracket", dc_form("Mean", rs(mean), NULL), dc_form("Under", dc_sym(un->items[1]->text), NULL), dc_form("Pairs", dc_int((long)(n * n)), NULL), NULL);
        ev = dc_form("Certificate", dc_form("Kind", dc_sym("rule"), NULL), dc_form("Rule", dc_sym("UniformMean"), NULL), dc_form("Sum", rs(sum), NULL), NULL);
    } else if (!strcmp(h, "Delta")) {
        const Sx *f = q->n == 3 ? q->items[1] : NULL, *t = q->n == 3 ? q->items[2] : NULL;
        if (!sx_head_is(f, "From") || f->n != 2 || !sx_head_is(t, "To") || t->n != 2) return dc_invalid(m, "Delta: expected (Delta (From (Output D Value)) (To (Output D Value)))");
        const Sx *bf = premise(run, f->items[1], "Value", "Bracket", h, &e); if (!bf) return e;
        const Sx *bt = premise(run, t->items[1], "Value", "Bracket", h, &e); if (!bt) return e;
        DcRat x, y; const Sx *mx = sx_find(bf, "Mean", 1), *my = sx_find(bt, "Mean", 1);
        if (!mx || !my || mx->n != 2 || my->n != 2 || dc_sx_rat(mx->items[1], &x) || dc_sx_rat(my->items[1], &y)) return dc_invalid(m, "Delta: a premise has no Mean value");
        memset(&g, 0, sizeof g);
        val = dc_form("Delta", dc_form("From", rs(x), NULL), dc_form("To", rs(y), NULL), dc_form("Increase", rs(dc_rat_sub(y, x, &ovf)), NULL), NULL);
        ev = dc_form("Certificate", dc_form("Kind", dc_sym("rule"), NULL), dc_form("Rule", dc_sym("Difference"), NULL), NULL);
    } else if (!strcmp(h, "Threshold")) {
        const Sx *al = q->n == 3 ? q->items[2] : NULL; DcRat r;
        if (!sx_head_is(al, "AtLeast") || al->n != 2 || dc_sx_rat(al->items[1], &r)) return dc_invalid(m, "Threshold: expected (Threshold K (AtLeast r))");
        if ((e = operand(run, q->items[1], h, 0, &g))) return e;
        size_t n = g.n; g.rel = calloc(n ? n * n : 1, sizeof(int));
        for (size_t i = 0; i < n * n; i++) g.rel[i] = dc_rat_cmp(g.k[i], r) >= 0;
        val = relation_sx(m, &g);
        ev = dc_form("Certificate", dc_form("Kind", dc_sym("rule"), NULL), dc_form("Rule", dc_sym("Threshold"), NULL), dc_form("AtLeast", rs(r), NULL), NULL);
    } else {   /* CheckTransitive */
        if (q->n > 3) return dc_invalid(m, "CheckTransitive: expected (CheckTransitive X [(Algebra A)])");
        if ((e = operand(run, q->items[1], h, 1, &g))) return e;
        const char *alg = g.rel ? "Boolean" : "Lukasiewicz01";
        if (q->n == 3) {
            const Sx *al = q->items[2];
            if (!sx_head_is(al, "Algebra") || al->n != 2 || al->items[1]->kind != SX_SYM) { gk_free(&g); return dc_invalid(m, "CheckTransitive: field 2 expects (Algebra A)"); }
            const char *a = al->items[1]->text; int isb = !strcmp(a, "Boolean"), isl = !strcmp(a, "Lukasiewicz") || !strcmp(a, "Lukasiewicz01");
            if (!isb && !isl) { gk_free(&g); return dc_unsupported(m, "CheckTransitive: algebra %s is outside the M2 fragment", a); }
            if (isb != !!g.rel) { gk_free(&g); return dc_invalid(m, "CheckTransitive: Algebra Boolean applies to relations, Lukasiewicz to kernels"); }
        }
        int i, j, k; const DcCarrier *C = &m->car[g.car];
        if (intransitive(&g, &i, &j, &k)) {
            vd = VERDICT_FAILS; size_t n = g.n; Sx *vals = dc_form("Values", NULL);
            int ix[3][2] = {{i, j}, {j, k}, {i, k}};
            for (int s = 0; s < 3; s++) { size_t p = (size_t)ix[s][0] * n + ix[s][1]; sx_push(vals, g.rel ? dc_int(g.rel[p]) : rs(g.k[p])); }
            ev = dc_form("Witness", dc_form("TransitivityWitness", dc_form("Triple", sx_copy(C->elems[i]), sx_copy(C->elems[j]), sx_copy(C->elems[k]), NULL), vals, NULL), NULL);
        } else ev = dc_form("Certificate", dc_form("Kind", dc_sym("rule"), NULL), dc_form("Rule", dc_sym("Transitivity"), NULL), g.rel ? relation_sx(m, &g) : kernel_sx(m, &g), NULL);
        val = dc_form("Verdict", dc_form("Holds", dc_sym(vd == VERDICT_HOLDS ? "True" : "False"), NULL), dc_form("Algebra", dc_sym(alg), NULL), NULL);
    }
    gk_free(&g);
    if (ovf) { sx_free(val); sx_free(ev); return dc_unsupported(m, "%s: a rational left the 64-bit exact range", h); }
    DcScope sc = {"M2-GradedDeterministic", -1, ""};
    return dc_envelope_scoped(m, vd, rep, dc_claim_of(q, "Literal"), dc_form("Subject", dc_form("Operand", sx_copy(q->items[1]), NULL), NULL),
                              dc_form("Value", val, NULL), dc_form("Evidence", ev, NULL), NULL, &sc);
}
