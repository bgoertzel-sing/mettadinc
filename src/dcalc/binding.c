/* Boundary 1: binding validation on raw module source (see binding.h). */
#include "binding.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void dc_sha256_hex(const char *data, size_t n, char out[65]);

/* All top-level forms of the file, so an (Import M (Only ...)) can be resolved. */
static const Sx *g_universe;
void dc_binding_set_universe(const Sx *all) { g_universe = all; }

static const Sx *decl_local(const Sx *mod, const char *head, const char *name) {
    for (size_t i = 2; mod && i < mod->n; i++) {
        const Sx *d = mod->items[i];
        if (sx_head_is(d, head) && d->n > 1 && sx_is_sym(d->items[1], name)) return d;
    }
    return NULL;
}
/* 1 if name is brought in by an Import of mod (whole module, or listed in Only). */
static const Sx *import_of(const Sx *mod, const char *name) {
    for (size_t i = 2; mod && i < mod->n; i++) {
        const Sx *d = mod->items[i];
        if (!sx_head_is(d, "Import") || d->n < 2 || d->items[1]->kind != SX_SYM) continue;
        const Sx *only = sx_find(d, "Only", 2);
        if (!only) return d;
        for (size_t k = 1; k < only->n; k++) if (sx_is_sym(only->items[k], name)) return d;
    }
    return NULL;
}
static int g_unresolved;   /* set when a name is imported from a module not in this file */
static const Sx *decl(const Sx *mod, const char *head, const char *name) {
    const Sx *d = decl_local(mod, head, name);
    if (d) return d;
    const Sx *imp = import_of(mod, name);
    if (!imp) return NULL;
    for (size_t i = 0; g_universe && i < g_universe->n; i++) {
        const Sx *m = g_universe->items[i];
        if (sx_head_is(m, "DC.Module") && m->n > 1 && sx_is_sym(m->items[1], imp->items[1]->text))
            return decl_local(m, head, name);
    }
    g_unresolved = 1;   /* imported from another file: cannot be bound here */
    return NULL;
}
static const char *field1(const Sx *d, const char *f) {   /* (f Sym) -> Sym */
    const Sx *x = sx_find(d, f, 2);
    return x && x->n == 2 && x->items[1]->kind == SX_SYM ? x->items[1]->text : NULL;
}
static const char *field1s(const Sx *d, const char *f) {  /* (f "str") -> str */
    const Sx *x = sx_find(d, f, 2);
    return x && x->n == 2 && x->items[1]->kind == SX_STR ? x->items[1]->text : NULL;
}
static void add(DcBad *out, int *n, int max, const char *name, const char *fmt, const char *a, const char *b, const char *c) {
    if (*n >= max) return;
    snprintf(out[*n].name, sizeof out[*n].name, "%s", name);
    snprintf(out[*n].reason, sizeof out[*n].reason, fmt, a, b, c);
    (*n)++;
}

int dc_binding_scan(const Sx *mod, const char *basedir, DcBad *out, int max) {
    int n = 0;
    for (size_t i = 2; mod && i < mod->n; i++) {
        const Sx *d = mod->items[i];
        if (!(d->kind == SX_LIST && d->n > 1 && d->items[1]->kind == SX_SYM)) continue;
        const char *nm = d->items[1]->text;
        if (sx_head_is(d, "Keyed")) {
            const char *store = field1(d, "Of"), *stat = field1(d, "Item"), *view = field1(d, "View");
            g_unresolved = 0;
            const Sx *sd = store ? decl(mod, "Store", store) : NULL, *td = stat ? decl(mod, "Statistic", stat) : NULL;
            if (g_unresolved) continue;   /* an imported name from another file: not checkable, not an error */
            if (!sd) { add(out, &n, max, nm, "Keyed %s: field Of names no declared Store (%s)%s", nm, store ? store : "?", ""); continue; }
            if (!td) { add(out, &n, max, nm, "Keyed %s: field Item names no declared Statistic (%s)%s", nm, stat ? stat : "?", ""); continue; }
            const char *want = view ? view : field1(sd, "Of"), *have = field1(td, "Of");
            if (!want || !have || strcmp(want, have))
                add(out, &n, max, nm, "Keyed %s: field Item: statistic %s is of %s", nm, stat, have ? have : "?"),
                snprintf(out[n - 1].reason + strlen(out[n - 1].reason), sizeof out[n - 1].reason - strlen(out[n - 1].reason),
                         ", not of %s%s", want ? want : "?", view ? " (the View)" : " (the Store's item machine); declare (View ...)");
        } else if (sx_head_is(d, "Stream")) {
            const char *src = field1s(d, "Source"), *dig = field1s(d, "Digest");
            if (!src || !dig) continue;              /* no declared digest: nothing to bind */
            if (strncmp(dig, "sha256:", 7)) { add(out, &n, max, nm, "Stream %s: field Digest is not sha256:<hex> (%s)%s", nm, dig, ""); continue; }
            char path[1024]; snprintf(path, sizeof path, "%s/%s", basedir ? basedir : ".", src);
            FILE *f = fopen(path, "rb");
            if (!f) { add(out, &n, max, nm, "Stream %s: field Source cannot be read (%s)%s", nm, src, ""); continue; }
            fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
            char *buf = malloc((size_t)len + 1); size_t got = buf ? fread(buf, 1, (size_t)len, f) : 0; fclose(f);
            char hex[65]; dc_sha256_hex(buf ? buf : "", got, hex); free(buf);
            if (strcmp(hex, dig + 7)) add(out, &n, max, nm, "Stream %s: field Digest: the source %s has sha256 %s, not the declared digest", nm, src, hex);
        }
    }
    return n;
}

static const char *mentions(const Sx *x, const DcBad *bad, int nbad) {
    if (x->kind == SX_SYM) { for (int i = 0; i < nbad; i++) if (!strcmp(bad[i].name, x->text)) return bad[i].reason; return NULL; }
    for (size_t i = 0; x->kind == SX_LIST && i < x->n; i++) { const char *r = mentions(x->items[i], bad, nbad); if (r) return r; }
    return NULL;
}

int dc_binding_request(const Sx *mod, const DcBad *bad, int nbad, const Sx *req, char *reason, size_t rn) {
    for (int hop = 0; req && req->kind == SX_SYM && hop < 16; hop++) {   /* resolve Derive names */
        const Sx *d = decl(mod, "Derive", req->text);
        if (!d || d->n != 3) break;
        req = d->items[2];
    }
    if (!req) return 0;
    if (sx_head_is(req, "CheckSafety") && req->n > 1 && req->items[1]->kind == SX_SYM) {
        const char *subj = req->items[1]->text, *via = field1(req, "Via");
        if (via) {
            const Sx *sim = decl(mod, "Simulation", via); const char *tgt = sim ? field1(sim, "Target") : NULL;
            if (!sim) { snprintf(reason, rn, "CheckSafety %s: field Via names no declared Simulation (%s)", subj, via); return 1; }
            if (!tgt || strcmp(tgt, subj)) { snprintf(reason, rn, "CheckSafety %s: field Via: simulation %s targets %s, not %s", subj, via, tgt ? tgt : "?", subj); return 1; }
        }
    }
    const char *r = mentions(req, bad, nbad);
    if (r) { snprintf(reason, rn, "%s", r); return 1; }
    return 0;
}
