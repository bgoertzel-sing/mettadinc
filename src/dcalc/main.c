/* dcalc CLI: admit every DC.Module in a file and evaluate each
 * !(dc.run Module Request) form, printing one result envelope per line:
 *   <Module> <request> => <envelope>
 * Order of checks per request (one place):
 *   1. binding validation on the raw source (boundary 1)  -> InvalidInput
 *   2. admission failure: construct outside M0 ("[M0]")   -> Unsupported
 *                         malformed declaration           -> InvalidInput
 *   3. dc_run (profile gate, then the M0 requests).
 * Exit 0 unless the file cannot be read or parsed. */
#include "ops.h"
#include "api.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *slurp(const char *path) {
    FILE *f = fopen(path, "rb"); if (!f) return NULL;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *b = malloc((size_t)n + 1); if (!b) { fclose(f); return NULL; }
    size_t got = fread(b, 1, (size_t)n, f); b[got] = 0; fclose(f); return b;
}

#define MAXM 16
int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: dcalc FILE.metta\n"); return 2; }
    char *src = slurp(argv[1]);
    if (!src) { fprintf(stderr, "dcalc: cannot read %s\n", argv[1]); return 2; }
    char basedir[1024]; snprintf(basedir, sizeof basedir, "%s", argv[1]);
    char *slash = strrchr(basedir, '/'); if (slash) *slash = 0; else snprintf(basedir, sizeof basedir, ".");
    const char *err = NULL; int line = 0;
    Sx *all = sx_parse_all(src, &err, &line); free(src);
    if (!all) { fprintf(stderr, "dcalc: parse error line %d: %s\n", line, err); return 2; }
    for (size_t i = 0; i + 1 < all->n; i++) {
        if (!sx_is_sym(all->items[i], "!")) continue;
        const Sx *c = all->items[i + 1];
        if (!sx_head_is(c, "dc.run") || c->n != 3) continue;
        const char *mn = c->items[1]->kind == SX_SYM ? c->items[1]->text : "?";
        char *rq = sx_print(c->items[2]);
        Sx *res = dc_eval_request(all, basedir, mn, c->items[2]);
        char *out = sx_print(res);
        printf("%s %s => %s\n", mn, rq, out);
        free(out); free(rq); sx_free(res);
    }
    sx_free(all);
    return 0;
}
