/* M3 translation-validation harness (t-2026-11-11-mettadinc-m3-tv-suite).
 * Runs the production CNF encoders of ops_sym.c (sym_cnf_partition per obligation and
 * All, sym_cnf_minimize, sym_cnf_now) on a small module and writes each CNF WITHOUT the
 * goal unit that sym_prove adds, plus the goal literal and the number of primary
 * variables (word bits).  tests/dcalc/tv_m3.py then checks every CNF against an
 * independent Python semantics over all assignments of the primaries; this program
 * does no checking of its own.
 * usage: tv_m3 MODULE.metta OUTDIR spec...   spec = partition:P:M | minimize:M[:k] | now:R */
#include "ops_sym.c"
#include <stdio.h>
static int dump(const char *dir, const char *tag, const Cnf *c, int goal, int np, const char *extra) {
    char p[700]; snprintf(p, sizeof p, "%s/%s.tv", dir, tag);
    FILE *f = fopen(p, "w"); if (!f) return -1;
    fprintf(f, "c tv %s\nc goal %d\nc prim %d\nc tru %d\n%s", tag, goal, np, c->tru, extra ? extra : "");
    fprintf(f, "p cnf %d %zu\n", c->nv, c->ncl);
    for (size_t i = 0; i < c->n; i++) { if (c->cl[i]) fprintf(f, "%d ", c->cl[i]); else fputs("0\n", f); }
    printf("wrote %s (vars %d, clauses %zu)\n", p, c->nv, c->ncl);
    return fclose(f);
}
int main(int argc, char **argv) {
    if (argc < 4) { puts("usage: tv_m3 MODULE OUTDIR spec..."); return 2; }
    FILE *fp = fopen(argv[1], "rb"); if (!fp) { printf("cannot open %s\n", argv[1]); return 2; }
    static char src[1 << 20]; size_t n = fread(src, 1, sizeof src - 1, fp); src[n] = 0; fclose(fp);
    const char *e; int el; Sx *all = sx_parse_all(src, &e, &el); if (!all) { printf("parse: %s line %d\n", e, el); return 2; }
    const Sx *mod = NULL; for (size_t i = 0; i < all->n; i++) if (sx_head_is(all->items[i], "DC.Module")) { mod = all->items[i]; break; }
    static SymMod S; char err[256] = "";
    if (!mod || sym_read(mod, &S, err, sizeof err)) { printf("read: %s\n", err); return 2; }
    for (int a = 3; a < argc; a++) {
        char sp[256], tag[400], ex[8192]; snprintf(sp, sizeof sp, "%s", argv[a]);
        char *k = strtok(sp, ":"), *x1 = strtok(NULL, ":"), *x2 = strtok(NULL, ":");
        Cnf cn; int goal; ex[0] = 0;
        if (k && x1 && x2 && !strcmp(k, "partition")) {
            const Sx *bp = sfind_decl(&S, x1); int mi = sfind_mach(&S, x2), ci; const char *cn_;
            if (!bp || mi < 0 || sname(sfield(bp, "On"), 1, &cn_) || (ci = sfind_car(&S, cn_)) < 0) { printf("bad spec %s\n", argv[a]); return 2; }
            const SMach *M = &S.mach[mi]; RNode *nd = NULL; int nn = 0;
            if (S.car[ci].reach) {
                const Sx *rf = S.car[ci].reach; int ri = sfind_mach(&S, rf->items[1]->text); uint64_t st; static SymVal rav[8];
                SymEnv E; if (ri < 0 || !lit_of(rf->items[2]->items[1], &st) || senv_init(&E, S.car[ci].width)) { puts("bad reach"); return 2; }
                if (mach_acts(&E, &S, &S.mach[ri], rav, err, sizeof err) || sym_reach(&E, rav, S.mach[ri].nact, st, &nd, &nn, err, sizeof err)) { printf("reach: %s\n", err); return 2; }
                dc_bdd_free(E.bm);
            }
            int nob = 1;
            for (int ob = -1; ob < nob; ob++) {
                const char *on = "All"; memset(&cn, 0, sizeof cn);
                if (sym_cnf_partition(&cn, &S, M, bp, nd, nn, ob, &nob, &on, &goal)) { printf("partition %s: CNF generation failed\n", x1); return 2; }
                if (ob < 0) snprintf(tag, sizeof tag, "partition-%s-all", x1); else snprintf(tag, sizeof tag, "partition-%s-%d", x1, ob);
                snprintf(ex, sizeof ex, "c kind partition %s %s %d %s\n", x1, x2, ob, on);
                if (dump(argv[2], tag, &cn, goal, S.car[M->states].width, ex)) return 2;
                cnf_free(&cn);
            }
            free(nd);
        } else if (k && x1 && !strcmp(k, "minimize")) {
            int mi = sfind_mach(&S, x1); if (mi < 0) { printf("bad spec %s\n", argv[a]); return 2; }
            const SMach *M = &S.mach[mi]; int W = S.car[M->states].width;
            SymEnv E; if (senv_init(&E, W)) return 2;
            static SymVal av[8], ob[8]; static STest T[SYM_MAXT]; static DcBdd cl[SYM_MAXCL]; int nt = 0, ncl = 0;
            if (mach_acts(&E, &S, M, av, err, sizeof err)) { printf("acts: %s\n", err); return 2; }
            for (int p = 0; p < M->nobs; p++) if (sym_apply(E.bm, &S, M->obs[p].map, E.xv, &ob[p], err, sizeof err)) { printf("obs: %s\n", err); return 2; }
            if (sym_refine(E.bm, &S, M, av, ob, E.xv, T, &nt, cl, &ncl, err, sizeof err)) { printf("refine: %s\n", err); return 2; }
            if (x2 && atoi(x2) >= 0 && atoi(x2) < nt) nt = atoi(x2);   /* minimize:M:k keeps the first k tests (a SAT case) */
            size_t o = (size_t)snprintf(ex, sizeof ex, "c kind minimize %s classes %d\n", x1, ncl);
            for (int t = 0; t < nt && o < sizeof ex - 200; t++) {   /* test = action names of the word, then port name and bit */
                o += (size_t)snprintf(ex + o, sizeof ex - o, "c test %s %d", M->obs[T[t].port].name, T[t].bit);
                for (int w = 0; w < T[t].nw; w++) o += (size_t)snprintf(ex + o, sizeof ex - o, " %s", M->act[T[t].word[w]].name);
                o += (size_t)snprintf(ex + o, sizeof ex - o, "\n");
            }
            memset(&cn, 0, sizeof cn);
            if (sym_cnf_minimize(&cn, &S, M, T, nt, &goal)) { puts("minimize: CNF generation failed"); return 2; }
            if (x2) snprintf(tag, sizeof tag, "minimize-%s-k%s", x1, x2); else snprintf(tag, sizeof tag, "minimize-%s", x1);
            if (dump(argv[2], tag, &cn, goal, 2 * W, ex)) return 2;
            cnf_free(&cn); dc_bdd_free(E.bm);
        } else if (k && x1 && !strcmp(k, "now")) {
            const Sx *rd = sfind_decl(&S, x1); const char *mn, *en; int mi, ei;
            if (!rd || sname(sfield(rd, "Of"), 1, &mn) || sname(sfield(rd, "Encode"), 1, &en) || (mi = sfind_mach(&S, mn)) < 0 || (ei = sfind_map(&S, en)) < 0) { printf("bad spec %s\n", argv[a]); return 2; }
            const SMach *M = &S.mach[mi]; memset(&cn, 0, sizeof cn);
            if (sym_cnf_now(&cn, &S, M, ei, &goal)) { puts("now: CNF generation failed"); return 2; }
            snprintf(tag, sizeof tag, "now-%s", x1); snprintf(ex, sizeof ex, "c kind now %s %s %s\n", x1, mn, en);
            if (dump(argv[2], tag, &cn, goal, 2 * S.car[M->states].width, ex)) return 2;
            cnf_free(&cn);
        } else { printf("bad spec %s\n", argv[a]); return 2; }
    }
    puts("tv_m3: dumped");
    return 0;
}
