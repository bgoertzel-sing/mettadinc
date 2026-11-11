/* M3 negative test 7 (review 1 F3): the sampled clock-rate screen on the forty-bit
 * ZeroMachine.  The exact behavioral partition (8 classes) comes from symbolic
 * refinement; the screen then draws N fixed-seed uniform words x (default 10^6) and,
 * for each coordinate i, counts samples where flipping bit i changes the class.
 * Bits 0 and 1 always do.  A tail bit changes the class only when the 38-bit tail is
 * 0 or e_i, so its exact mean rate is 2^-37 and a 10^6 sample sees none.  The screen
 * therefore proposes the four-class encoding Keep01 (bits 0 and 1), which neg 8
 * refutes with behavioral defect 1: a screen proposes, refinement certifies.
 * Build: make -C src/dcalc tests.  Usage (repository root): screen_m3 [fixture] [N] [seed].
 * Exit 0 iff the screen keeps exactly bits 0 and 1 and is reproducible for its seed. */
#include "ops_sym.c"
#include <stdio.h>
static uint64_t sm(uint64_t *s) {   /* splitmix64 */
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL; z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL; return z ^ (z >> 31);
}
static int cls_of(const DcBddMgr *bm, const DcBdd *cl, int ncl, uint64_t x) {
    int j = -1; for (int k = 0; k < ncl; k++) if (dc_bdd_eval(bm, cl[k], x)) { if (j >= 0) return -2; j = k; }
    return j;
}
static int screen(const DcBddMgr *bm, const DcBdd *cl, int ncl, int W, long N, uint64_t seed, long *hits) {
    uint64_t st = seed, mask = W >= 64 ? ~0ULL : (1ULL << W) - 1;
    for (int i = 0; i < W; i++) hits[i] = 0;
    for (long s = 0; s < N; s++) {
        uint64_t x = sm(&st) & mask; int j = cls_of(bm, cl, ncl, x);
        if (j < 0) return -1;   /* not a partition */
        for (int i = 0; i < W; i++) if (!dc_bdd_eval(bm, cl[j], x ^ (1ULL << i))) hits[i]++;
    }
    return 0;
}
int main(int argc, char **argv) {
    const char *F = argc > 1 ? argv[1] : "docs/e0/docs/01_language_specification/validation_package/fixtures/forty_bits.metta";
    long N = argc > 2 ? atol(argv[2]) : 1000000L; uint64_t seed = argc > 3 ? strtoull(argv[3], 0, 10) : 20261111ULL;
    FILE *fp = fopen(F, "rb"); if (!fp) { printf("cannot open %s\n", F); return 2; }
    static char src[1 << 20]; size_t n = fread(src, 1, sizeof src - 1, fp); src[n] = 0; fclose(fp);
    const char *e; int el; Sx *all = sx_parse_all(src, &e, &el); if (!all) { printf("parse: %s line %d\n", e, el); return 2; }
    const Sx *mod = NULL; for (size_t i = 0; i < all->n; i++) if (sx_head_is(all->items[i], "DC.Module")) { mod = all->items[i]; break; }
    static SymMod S; char err[256] = "";
    if (!mod || sym_read(mod, &S, err, sizeof err)) { printf("read: %s\n", err); return 2; }
    int zi = sfind_mach(&S, "ZeroMachine"); if (zi < 0) { puts("ZeroMachine missing"); return 2; }
    const SMach *Z = &S.mach[zi]; int W = S.car[Z->states].width;
    SymEnv E; if (senv_init(&E, W)) return 2;
    DcBddMgr *bm = E.bm;
    static SymVal av[8], ob[8]; static STest T[SYM_MAXT]; static DcBdd cl[SYM_MAXCL]; int nt = 0, ncl = 0;
    if (mach_acts(&E, &S, Z, av, err, sizeof err)) { printf("acts: %s\n", err); return 2; }
    for (int p = 0; p < Z->nobs; p++) if (sym_apply(bm, &S, Z->obs[p].map, E.xv, &ob[p], err, sizeof err)) { printf("obs: %s\n", err); return 2; }
    if (sym_refine(bm, &S, Z, av, ob, E.xv, T, &nt, cl, &ncl, err, sizeof err)) { printf("refine: %s\n", err); return 2; }
    printf("ZeroMachine: width %d, behavioral classes %d (symbolic refinement)\n", W, ncl);
    static long hits[64], h2[64];
    if (screen(bm, cl, ncl, W, N, seed, hits)) { puts("classes do not partition the carrier"); return 1; }
    int kept = 0, k0 = 0, k1 = 0;
    printf("sampled screen (N %ld, seed %llu): kept", N, (unsigned long long)seed);
    for (int i = 0; i < W; i++) if (hits[i] > 0) { kept++; printf(" x%d(%ld)", i, hits[i]); if (i == 0) k0 = 1; if (i == 1) k1 = 1; }
    printf("; %d of %d coordinates have zero hits\n", W - kept, W);
    int ok = kept == 2 && k0 && k1;
    printf("candidate encoding: %s\n", ok ? "Keep01 (bits 0 and 1, four classes) -- refuted by neg 8, behavioral defect 1" : "unexpected");
    long Nr = N < 1000 ? N : 1000; static long h3[64];
    int rep = !screen(bm, cl, ncl, W, Nr, seed, h2) && !screen(bm, cl, ncl, W, Nr, seed, h3) && !memcmp(h2, h3, sizeof h2);
    printf("same seed gives the same screen: %s\n", rep ? "yes" : "no");
    dc_bdd_free(bm);
    printf("screen_m3: %s\n", ok && rep && ncl == 8 ? "PASS" : "FAIL");
    return !(ok && rep && ncl == 8);
}
