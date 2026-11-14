/* Embedding API (see api.h). */
#include "api.h"
#include "ops.h"
#include "binding.h"
#include "admit.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static Sx *bare(const char *status, const char *mod, const char *reason) {
    Sx *l = sx_list(); sx_push(l, sx_sym("Result"));
    Sx *s = sx_list(); sx_push(s, sx_sym("Status")); sx_push(s, sx_sym(status)); sx_push(l, s);
    Sx *b = sx_list(); sx_push(b, sx_sym("Binding"));
    Sx *m = sx_list(); sx_push(m, sx_sym("Module")); sx_push(m, sx_sym(mod)); sx_push(b, m); sx_push(l, b);
    Sx *r = sx_list(); sx_push(r, sx_sym("Reason")); sx_push(r, sx_str(reason)); sx_push(l, r);
    return l;
}

/* M1 admission (admit.c, registry-driven): 0 admitted, 1 InvalidInput, 2 outside
 * the first release (Unsupported); why gets the first diagnostic of module mn or
 * of this run form, or the release reason. */
static const char *g_source_name = "input";
void dc_eval_set_source_name(const char *name) { g_source_name = name && *name ? name : "input"; }
static int g_beyond = 0;   /* M4 opt-in, see api.h */
void dc_eval_set_beyond_release(int on) { g_beyond = on ? 1 : 0; }
int dc_eval_beyond_release(void) { return g_beyond; }

static int m1_admission(const Sx *all, const char *mn, const Sx *req, char *why, size_t wn) {
    DcAdmission a; int rc = 0;
    dc_admit_modules(all, g_source_name, &a);
    Sx *run = sx_list(); sx_push(run, sx_sym("dc.run")); sx_push(run, sx_sym(mn)); sx_push(run, sx_copy(req));
    size_t before = a.diag.n;
    dc_admit_run(&a, run);
    /* An Import of a module that is not in this file cannot be resolved in a
     * single-file run (dcalc --admit FILE... resolves it across files).  As in
     * M0, the module is answered Unsupported, not InvalidInput: nothing is
     * wrong with it that this run can see. */
    for (size_t i = 0; i < before && !rc; i++)
        if (!strcmp(a.diag.v[i].mod, mn) && strstr(a.diag.v[i].msg, ": Import of unknown module ")) {
            snprintf(why, wn, "%s (imported from outside this file; a single-file run cannot resolve it)", a.diag.v[i].msg); rc = 2;
        }
    for (size_t i = 0; i < a.diag.n && !rc; i++)
        if (!strcmp(a.diag.v[i].mod, mn) || i >= before) { snprintf(why, wn, "%s", a.diag.v[i].msg); rc = 1; }
    if (!rc) { DcAModule *m = dc_admit_find(&a, mn); char b[256]; const char *u = m ? (g_beyond ? dc_admit_unsupported_beyond : dc_admit_unsupported)(m, b, sizeof b) : NULL;
               if (u) { snprintf(why, wn, "%s", u); rc = 2; } }
    sx_free(run); dc_admission_free(&a);
    return rc;
}

/* M6 opt-in (beyond release, (Use Contracts)): a same-file (Import M (Only n ...)) copies M's Carrier,
 * Map and Tolerance declarations named in Only into the importing module at the Import, in M's order.
 * Returns a new module form, or NULL when nothing changes. */
static Sx *m6_inline_imports(const Sx *all, const Sx *raw) {
    int uses = 0, any = 0;
    for (size_t i = 2; i < raw->n; i++) if (sx_head_is(raw->items[i], "Use"))
        for (size_t k = 1; k < raw->items[i]->n; k++) if (sx_is_sym(raw->items[i]->items[k], "Contracts") || sx_is_sym(raw->items[i]->items[k], "Transfers")) uses = 1;   /* M6: Contracts, Transfers */
    if (!uses) return NULL;
    Sx *out = sx_list();
    for (size_t i = 0; i < raw->n; i++) {
        const Sx *d = raw->items[i]; sx_push(out, sx_copy(d));
        if (i < 2 || !sx_head_is(d, "Import") || d->n < 3 || d->items[1]->kind != SX_SYM) continue;
        const Sx *only = NULL, *src = NULL;
        for (size_t k = 2; k < d->n; k++) if (sx_head_is(d->items[k], "Only")) only = d->items[k];
        for (size_t k = 0; all && k < all->n; k++)
            if (sx_head_is(all->items[k], "DC.Module") && all->items[k]->n >= 2 && sx_is_sym(all->items[k]->items[1], d->items[1]->text)) { src = all->items[k]; break; }
        if (!only || !src) continue;
        for (size_t k = 2; k < src->n; k++) {
            const Sx *e = src->items[k];
            /* m6-rest review 2 F1: a Machine named in Only is copied too, but only when a Fork of the importing
             * module names it in (Of Machine), so the spec's split (merge machine in one module, contract in another)
             * can carry a Fork.  Nothing else changes for modules without such a Fork. */
            int forked = 0;
            if (sx_head_is(e, "Machine") && e->n >= 2 && e->items[1]->kind == SX_SYM)
                for (size_t q = 2; q < raw->n; q++) { const Sx *f = raw->items[q];
                    if (!sx_head_is(f, "Fork")) continue;
                    for (size_t r = 2; r < f->n; r++) if (sx_head_is(f->items[r], "Of") && f->items[r]->n == 2 && sx_is_sym(f->items[r]->items[1], e->items[1]->text)) forked = 1; }
            if (!(sx_head_is(e, "Carrier") || sx_head_is(e, "Map") || sx_head_is(e, "Tolerance") || forked) || e->n < 2 || e->items[1]->kind != SX_SYM) continue;
            for (size_t j = 1; j < only->n; j++) if (sx_is_sym(only->items[j], e->items[1]->text)) { sx_push(out, sx_copy(e)); any = 1; break; }
        }
    }
    if (!any) { sx_free(out); return NULL; }
    return out;
}

/* M7 opt-in (beyond release, (Use Hyperseed), M01): source-level expansion.
 * - (Import M (Only n ...)) of a module in the run universe copies M's declarations other than Profile, Use,
 *   Import and Derive at the Import (every Only name must be declared in M);
 * - Schema and Method declarations are dropped; (Derive X (Method args...)) binds the Method's Parameters to the
 *   arguments and unfolds its Body: (LetResult $v E B) becomes (Derive X__v E) and B with $v := X__v, ending
 *   with (Derive X E).  Returns a new module form, or NULL when nothing is expanded. */
#define M7_NV 16
static Sx *m7_subst(const Sx *x, const char **var, Sx **val, int n) {
    if (x->kind == SX_SYM) { for (int i = n - 1; i >= 0; i--) if (sx_is_sym(x, var[i])) return sx_copy(val[i]); return sx_copy(x); }
    if (x->kind != SX_LIST) return sx_copy(x);
    Sx *l = sx_list(); for (size_t i = 0; i < x->n; i++) sx_push(l, m7_subst(x->items[i], var, val, n)); return l;
}
static int m7_body(Sx *out, const char *dn, const Sx *b, const char **var, Sx **val, int n, int depth) {
    if (depth > 8) return -1;
    if (sx_head_is(b, "LetResult") && b->n == 4 && b->items[1]->kind == SX_SYM && b->items[1]->text[0] == '$' && n < M7_NV) {
        char nm[256]; snprintf(nm, sizeof nm, "%s__%s", dn, b->items[1]->text + 1);
        Sx *d = sx_list(); sx_push(d, sx_sym("Derive")); sx_push(d, sx_sym(nm)); sx_push(d, m7_subst(b->items[2], var, val, n)); sx_push(out, d);
        var[n] = b->items[1]->text; val[n] = sx_sym(nm);
        int rc = m7_body(out, dn, b->items[3], var, val, n + 1, depth + 1); sx_free(val[n]); return rc;
    }
    Sx *d = sx_list(); sx_push(d, sx_sym("Derive")); sx_push(d, sx_sym(dn)); sx_push(d, m7_subst(b, var, val, n)); sx_push(out, d);
    return 0;
}
static const Sx *m7_named(const Sx *raw, const char *head, const char *name) {
    for (size_t i = 2; i < raw->n; i++) { const Sx *d = raw->items[i];
        if (sx_head_is(d, head) && d->n >= 2 && sx_is_sym(d->items[1], name)) return d; }
    return NULL;
}
static Sx *m7_expand(const Sx *all, const Sx *raw) {
    int uses = 0, any = 0;
    for (size_t i = 2; i < raw->n; i++) if (sx_head_is(raw->items[i], "Use"))
        for (size_t k = 1; k < raw->items[i]->n; k++) if (sx_is_sym(raw->items[i]->items[k], "Hyperseed")) uses = 1;
    if (!uses) return NULL;
    Sx *out = sx_list();
    for (size_t i = 0; i < raw->n; i++) {
        const Sx *d = raw->items[i];
        if (i >= 2 && (sx_head_is(d, "Schema") || sx_head_is(d, "Method"))) { any = 1; continue; }
        if (i >= 2 && sx_head_is(d, "Derive") && d->n == 3 && d->items[1]->kind == SX_SYM && d->items[2]->kind == SX_LIST
            && d->items[2]->n >= 1 && d->items[2]->items[0]->kind == SX_SYM) {
            const Sx *mt = m7_named(raw, "Method", d->items[2]->items[0]->text);
            const Sx *pa = mt ? sx_find(mt, "Parameters", 2) : NULL, *bo = mt ? sx_find(mt, "Body", 2) : NULL;
            if (mt && pa && bo && bo->n == 2 && pa->n == d->items[2]->n && pa->n - 1 <= M7_NV) {
                const char *var[M7_NV]; Sx *val[M7_NV]; int n = 0, ok = 1;
                for (size_t k = 1; k < pa->n && ok; k++) {
                    const Sx *p = pa->items[k];
                    if (p->kind != SX_LIST || p->n < 1 || p->items[0]->kind != SX_SYM || p->items[0]->text[0] != '$') { ok = 0; break; }
                    var[n] = p->items[0]->text; val[n] = sx_copy(d->items[2]->items[k]); n++;
                }
                if (ok && m7_body(out, d->items[1]->text, bo->items[1], var, val, n, 0) == 0) any = 1;
                else ok = 0;
                for (int k = 0; k < n; k++) sx_free(val[k]);
                if (ok) continue;
            }
        }
        sx_push(out, sx_copy(d));
        if (i < 2 || !sx_head_is(d, "Import") || d->n < 3 || d->items[1]->kind != SX_SYM) continue;
        const Sx *only = NULL, *src = NULL;
        for (size_t k = 2; k < d->n; k++) if (sx_head_is(d->items[k], "Only")) only = d->items[k];
        for (size_t k = 0; all && k < all->n; k++)
            if (sx_head_is(all->items[k], "DC.Module") && all->items[k]->n >= 2 && sx_is_sym(all->items[k]->items[1], d->items[1]->text)) { src = all->items[k]; break; }
        if (!only || !src || src == raw) continue;
        int found = 1;
        for (size_t j = 1; j < only->n && found; j++) {
            found = 0;
            for (size_t k = 2; k < src->n; k++) { const Sx *e = src->items[k];
                if (e->kind == SX_LIST && e->n >= 2 && sx_is_sym(e->items[1], only->items[j]->kind == SX_SYM ? only->items[j]->text : "")) found = 1; }
        }
        if (!found) continue;
        for (size_t k = 2; k < src->n; k++) { const Sx *e = src->items[k];
            if (sx_head_is(e, "Profile") || sx_head_is(e, "Use") || sx_head_is(e, "Import") || sx_head_is(e, "Derive")) continue;
            if (e->n >= 2 && e->items[1]->kind == SX_SYM && m7_named(raw, e->items[0]->kind == SX_SYM ? e->items[0]->text : "", e->items[1]->text)) continue;   /* the importer's own declaration wins */
            sx_push(out, sx_copy(e)); any = 1; }
    }
    if (!any) { sx_free(out); return NULL; }
    return out;
}

Sx *dc_eval_request(const Sx *all, const char *basedir, const char *mn, const Sx *req) {
    const Sx *raw = NULL;
    for (size_t i = 0; all && i < all->n; i++) {
        const Sx *f = all->items[i];
        if (sx_head_is(f, "DC.Module") && f->n >= 2 && sx_is_sym(f->items[1], mn)) { raw = f; break; }
    }
    if (!raw) return bare("InvalidInput", mn, "dc.run: field Module names no declared module");
    if (!req) return bare("InvalidInput", mn, "dc.run: field Request missing");
    dc_binding_set_universe(all);
    DcBad *bad = calloc(32, sizeof *bad); char why[512];
    int nbad = dc_binding_scan(raw, basedir, bad, 32);
    Sx *res; int adm;
    if (dc_binding_request(raw, bad, nbad, req, why, sizeof why)) res = bare("InvalidInput", mn, why);
    else if ((adm = m1_admission(all, mn, req, why, sizeof why)) != 0) res = bare(adm == 1 ? "InvalidInput" : "Unsupported", mn, why);
    else {
        DcModule *m = calloc(1, sizeof *m); char err[512];
        Sx *inl = g_beyond ? m6_inline_imports(all, raw) : NULL;   /* M6 opt-in */
        if (!inl && g_beyond) inl = m7_expand(all, raw);   /* M7 opt-in */
        if (dc_admit(inl ? inl : raw, m, err, sizeof err) != 0) {
            res = bare(strncmp(err, "[M0]", 4) ? "InvalidInput" : "Unsupported", mn, err);
            dc_module_free(m);   /* review 2 F6: release partially admitted carrier tables */
        }
        else { if (basedir) snprintf(m->basedir, sizeof m->basedir, "%s", basedir);
               DcRun *run = dc_run_new(m); res = dc_run(run, req); dc_run_free(run); dc_module_free(m); }
        free(m); if (inl) sx_free(inl);
    }
    free(bad);
    return res;
}

char *dc_eval_text(const char *source, const char *basedir, const char *mn, const char *request) {
    const char *err = NULL; int line = 0; char why[256];
    Sx *all = sx_parse_all(source ? source : "", &err, &line);
    if (!all) { snprintf(why, sizeof why, "dc.run: field Source does not parse (line %d: %s)", line, err); Sx *r = bare("InvalidInput", mn, why); char *s = sx_print(r); sx_free(r); return s; }
    Sx *rq = sx_parse_all(request ? request : "", &err, &line);
    Sx *res;
    if (!rq || rq->n != 1) res = bare("InvalidInput", mn, "dc.run: field Request is not one s-expression");
    else res = dc_eval_request(all, basedir, mn, rq->items[0]);
    char *s = sx_print(res);
    sx_free(res); sx_free(rq); sx_free(all);
    return s;
}
