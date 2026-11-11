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
#include "admit.h"
#include "registry.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *slurp(const char *path) {
    FILE *f = fopen(path, "rb"); if (!f) return NULL;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *b = malloc((size_t)n + 1); if (!b) { fclose(f); return NULL; }
    size_t got = fread(b, 1, (size_t)n, f); b[got] = 0; fclose(f); return b;
}

/* dcalc --admit FILE...: M1 admission only.  The files form one universe
 * (imports resolve across them, as in check_fixtures.py).  Output:
 *   registry <digest>
 *   module <Name> <Admitted|Unsupported|InvalidInput> <ndiag> [reason]  (one per module)
 *   diag <file:line:col: where: message>             (in order)
 * Exit 1 if any diagnostic, 0 otherwise.  Nothing is evaluated. */
static int admit_mode(int nf, char **paths) {
    Sx **alls = calloc((size_t)nf, sizeof *alls);
    const char **names = calloc((size_t)nf, sizeof *names);
    int rc = 0;
    if (!alls || !names) return 2;
    printf("registry %s\n", dc_registry_digest_hex());
    for (int i = 0; i < nf; i++) {
        const char *base = strrchr(paths[i], '/'); names[i] = base ? base + 1 : paths[i];
        char *src = slurp(paths[i]);
        if (!src) { fprintf(stderr, "dcalc: cannot read %s\n", paths[i]); rc = 2; goto out; }
        const char *err = NULL; int line = 0;
        alls[i] = sx_parse_all(src, &err, &line); free(src);
        if (!alls[i]) { printf("diag %s:%d:0: %s: parse error: %s\n", names[i], line, names[i], err); rc = 1; goto out; }
    }
    DcAdmission a;
    size_t nd = dc_admit_files((const Sx *const *)alls, names, (size_t)nf, &a);
    for (size_t i = 0; i < a.nmod; i++) {
        size_t k = dc_admit_module_ndiag(&a, a.mods[i].name);
        char why[256]; const char *u = k ? NULL : dc_admit_unsupported(&a.mods[i], why, sizeof why);
        if (u) printf("module %s Unsupported 0 %s\n", a.mods[i].name, u);
        else printf("module %s %s %zu\n", a.mods[i].name, k ? "InvalidInput" : "Admitted", k);
    }
    for (size_t i = 0; i < a.diag.n; i++) printf("diag %s\n", a.diag.v[i].msg);
    dc_admission_free(&a);
    rc = nd ? 1 : 0;
out:
    for (int i = 0; i < nf; i++) sx_free(alls[i]);
    free(alls); free(names); dc_registry_free();
    return rc;
}

/* dcalc --ir MODULE FILE...: the admitted snapshot of one module (M1
 * acceptance 5).  Prints, one item per line:
 *   (IR (Module M) (Registry <digest>) (Profile (Dynamics D) (Values V) (Carriers C))
 *   (Libraries L...) (Decl <name> <kind> <own|imported> (At file line col) <canonical form>)...
 *   (Digest <sha256 of the canonical module text, as in the Binding of every result>)
 * Exit 1 if the module has diagnostics or is not found. */
void dc_sha256_hex(const char *data, size_t n, char out[65]);
static int ir_mode(const char *mn, int nf, char **paths) {
    Sx **alls = calloc((size_t)nf, sizeof *alls);
    const char **names = calloc((size_t)nf, sizeof *names);
    int rc = 1;
    if (!alls || !names) return 2;
    for (int i = 0; i < nf; i++) {
        const char *base = strrchr(paths[i], '/'); names[i] = base ? base + 1 : paths[i];
        char *src = slurp(paths[i]);
        if (!src) { fprintf(stderr, "dcalc: cannot read %s\n", paths[i]); rc = 2; goto out; }
        const char *err = NULL; int line = 0;
        alls[i] = sx_parse_all(src, &err, &line); free(src);
        if (!alls[i]) { printf("diag %s:%d:0: %s: parse error: %s\n", names[i], line, names[i], err); goto out; }
    }
    DcAdmission a;
    dc_admit_files((const Sx *const *)alls, names, (size_t)nf, &a);
    DcAModule *m = dc_admit_find(&a, mn);
    if (!m) printf("diag module %s not found\n", mn);
    else if (dc_admit_module_ndiag(&a, mn)) {
        for (size_t i = 0; i < a.diag.n; i++) if (!strcmp(a.diag.v[i].mod, mn)) printf("diag %s\n", a.diag.v[i].msg);
    } else {
        printf("(IR (Module %s)\n (Registry %s)\n", m->name, dc_registry_digest_hex());
        printf(" (Profile (Dynamics %s) (Values %s) (Carriers %s))\n (Libraries", m->dynamics, m->values, m->carriers);
        for (size_t i = 0; i < m->libraries.n; i++) printf(" %s", m->libraries.v[i]);
        printf(")\n");
        for (size_t i = 0; i < m->ndecl; i++) {
            const DcADecl *d = &m->decls[i];
            char *t = sx_print(d->form);
            printf(" (Decl %s %s %s (At %s %d %d) %s)\n", d->name, d->kind, d->own ? "own" : "imported",
                   m->fname, d->form->line, d->form->col, t);
            free(t);
        }
        char *canon = sx_print(m->form), hex[65];
        dc_sha256_hex(canon, strlen(canon), hex); free(canon);
        printf(" (Digest \"%s\"))\n", hex);
        rc = 0;
    }
    dc_admission_free(&a);
out:
    for (int i = 0; i < nf; i++) sx_free(alls[i]);
    free(alls); free(names); dc_registry_free();
    return rc;
}

#define MAXM 16
int main(int argc, char **argv) {
    /* M4 opt-in: capabilities beyond the first release (default off). */
    if (argc >= 2 && !strcmp(argv[1], "--beyond-release")) { dc_eval_set_beyond_release(1); argc--; argv++; }
    if (argc >= 3 && !strcmp(argv[1], "--admit")) return admit_mode(argc - 2, argv + 2);
    if (argc >= 4 && !strcmp(argv[1], "--ir")) return ir_mode(argv[2], argc - 3, argv + 3);
    if (argc < 2) { fprintf(stderr, "usage: dcalc FILE.metta | dcalc --admit FILE.metta... | dcalc --ir MODULE FILE.metta...\n"); return 2; }
    char *src = slurp(argv[1]);
    if (!src) { fprintf(stderr, "dcalc: cannot read %s\n", argv[1]); return 2; }
    char basedir[1024]; snprintf(basedir, sizeof basedir, "%s", argv[1]);
    char *slash = strrchr(basedir, '/'); if (slash) *slash = 0; else snprintf(basedir, sizeof basedir, ".");
    { const char *b = strrchr(argv[1], '/'); dc_eval_set_source_name(b ? b + 1 : argv[1]); }
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
