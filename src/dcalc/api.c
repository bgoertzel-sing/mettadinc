/* Embedding API (see api.h). */
#include "api.h"
#include "ops.h"
#include "binding.h"
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
    Sx *res;
    if (dc_binding_request(raw, bad, nbad, req, why, sizeof why)) res = bare("InvalidInput", mn, why);
    else {
        DcModule *m = calloc(1, sizeof *m); char err[512];
        if (dc_admit(raw, m, err, sizeof err) != 0) {
            res = bare(strncmp(err, "[M0]", 4) ? "InvalidInput" : "Unsupported", mn, err);
            dc_module_free(m);   /* review 2 F6: release partially admitted carrier tables */
        }
        else { DcRun *run = dc_run_new(m); res = dc_run(run, req); dc_run_free(run); dc_module_free(m); }
        free(m);
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
