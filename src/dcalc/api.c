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
        for (size_t k = 1; k < raw->items[i]->n; k++) if (sx_is_sym(raw->items[i]->items[k], "Contracts")) uses = 1;
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
            if (!(sx_head_is(e, "Carrier") || sx_head_is(e, "Map") || sx_head_is(e, "Tolerance")) || e->n < 2 || e->items[1]->kind != SX_SYM) continue;
            for (size_t j = 1; j < only->n; j++) if (sx_is_sym(only->items[j], e->items[1]->text)) { sx_push(out, sx_copy(e)); any = 1; break; }
        }
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
