/* Table tests for the sampled clock-rate screen (OQ2; spec Section 11.3, MILESTONES M3 gate).
 * Zero machine on 2+k bits (k <= 10, so at most 4096 table states): observe x0; swap01;
 * rotate the tail; inject flips x1 iff the tail is all zero.  The behavioral classes are
 * (x0, x1, tail==0), 8 classes.  Flipping a tail bit changes the class only when the tail
 * has weight 0 or 1, so its exact mean clock rate is 2/2^k: a small fixed-seed sample sees
 * no tail bit, and the screen proposes the candidate encoding (x0, x1).  That candidate is
 * then checked on the table and refuted with behavioral defect 1.  A large sample keeps
 * every coordinate and its candidate has defect 0; estimates agree with the exact rates.
 * Usage: screen_m2 [seed].  Exit 0 iff every check passes. */
#include "graded.h"
#include "ops_run.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fails = 0;
static void check(int ok, const char *what) { printf("%s %s\n", ok ? "PASS" : "FAIL", what); if (!ok) fails++; }
/* behavioral defect of a candidate encoding (coordinate subset): 1 iff two states agree on
 * every kept coordinate but lie in different behavioral classes (crisp, discount 1). */
static int cand_defect(size_t n, const int *cls, const int *keep, size_t nc) {
    unsigned mask = 0; for (size_t i = 0; i < nc; i++) if (keep[i]) mask |= 1u << i;
    int *rep = malloc(sizeof(int) * (1u << nc)), d = 0;
    for (size_t i = 0; i < (1u << nc); i++) rep[i] = -1;
    for (size_t x = 0; x < n; x++) { unsigned key = (unsigned)x & mask;
        if (rep[key] < 0) rep[key] = cls[x]; else if (rep[key] != cls[x]) d = 1; }
    free(rep); return d;
}
int main(int argc, char **argv) {
    uint64_t seed = argc > 1 ? strtoull(argv[1], 0, 10) : 20261110ULL;
    const size_t k = 10, nc = 2 + k, n = (size_t)1 << nc; const unsigned tail = ((1u << k) - 1) << 2;
    DcView v; memset(&v, 0, sizeof v); v.n = n; v.nact = 3;
    for (size_t a = 0; a < 3; a++) v.act[a] = malloc(n * sizeof(int));
    int *cls = malloc(n * sizeof(int)), *flip = malloc(nc * n * sizeof(int)), keep[16], keep2[16];
    long hits[16], hits2[16];
    for (size_t x = 0; x < n; x++) {
        unsigned w = (unsigned)x, t = (w & tail) >> 2, b0 = w & 1, b1 = (w >> 1) & 1;
        v.act[0][x] = (int)((w & ~3u) | (b0 << 1) | b1);
        v.act[1][x] = (int)((w & 3u) | ((((t << 1) | (t >> (k - 1))) & ((1u << k) - 1)) << 2));
        v.act[2][x] = (int)(t == 0 ? w ^ 2u : w);
        cls[x] = (int)b0;                                   /* K_O: observe x0 */
        for (size_t i = 0; i < nc; i++) flip[i * n + x] = (int)(w ^ (1u << i));
    }
    for (size_t x = 0; x < n; x++) { int c = cls[x]; cls[x] = -1; for (size_t y = 0; y < x; y++) if (cls[y] >= 0 && (((unsigned)y & 1) == (unsigned)c)) { cls[x] = (int)y; break; } if (cls[x] < 0) cls[x] = (int)x; }
    dc_refine_stable(&v, cls);
    { int nb = 0; for (size_t x = 0; x < n; x++) if (cls[x] == (int)x) nb++;
      int ok = 1; for (size_t x = 0; x < n; x++) for (size_t y = 0; y < x && ok; y += 97) {
          unsigned a = (unsigned)x, b = (unsigned)y; int same = (a & 3) == (b & 3) && ((a & tail) == 0) == ((b & tail) == 0);
          if (same != (cls[x] == cls[y])) ok = 0; }
      printf("behavioral classes: %d\n", nb); check(nb == 8 && ok, "zero machine has the 8 behavioral classes (x0, x1, tail==0)"); }
    /* exact mean clock rates over all states */
    double exact[16];
    for (size_t i = 0; i < nc; i++) { long c = 0; for (size_t x = 0; x < n; x++) c += cls[flip[i * n + x]] != cls[x]; exact[i] = (double)c / (double)n; }
    check(exact[0] == 1.0 && exact[1] == 1.0, "exact rate of x0 and x1 is 1");
    { int ok = 1; for (size_t i = 2; i < nc; i++) if (fabs(exact[i] - 2.0 / 1024.0) > 1e-12) ok = 0; check(ok, "exact rate of every tail bit is 2/2^k"); }
    /* small fixed-seed sample: the screen misses the tail */
    int kept = dc_g_sampled_screen(n, cls, nc, flip, seed, 40, hits, keep);
    printf("small sample (40, seed %llu): kept %d; hits", (unsigned long long)seed, kept);
    for (size_t i = 0; i < nc; i++) printf(" %ld", hits[i]);
    printf("\n");
    check(kept == 2 && keep[0] && keep[1], "small sample proposes the candidate encoding (x0, x1)");
    check(cand_defect(n, cls, keep, nc) == 1, "candidate (x0, x1) is refuted with behavioral defect 1");
    /* determinism */
    { long h3[16]; int k3[16]; int kk = dc_g_sampled_screen(n, cls, nc, flip, seed, 40, h3, k3);
      check(kk == kept && !memcmp(h3, hits, nc * sizeof(long)), "same seed gives the same screen"); }
    /* large sample: every coordinate kept, estimates near exact rates */
    long N = 200000; int kept2 = dc_g_sampled_screen(n, cls, nc, flip, seed, N, hits2, keep2);
    printf("large sample (%ld): kept %d\n", N, kept2);
    check(kept2 == (int)nc, "large sample keeps every coordinate");
    check(cand_defect(n, cls, keep2, nc) == 0, "candidate of all coordinates has behavioral defect 0");
    { int ok = 1; for (size_t i = 0; i < nc; i++) { double p = exact[i], est = (double)hits2[i] / (double)N, sd = sqrt(p * (1 - p) / (double)N);
          if (fabs(est - p) > 5 * sd + 1e-12) ok = 0; } check(ok, "estimates within 5 sigma of exact rates"); }
    /* invalid input */
    { int bad[1] = {(int)n}; check(dc_g_sampled_screen(n, cls, 1, bad, seed, 10, hits, keep) == -1, "out-of-range flip is invalid input");
      check(dc_g_sampled_screen(n, cls, nc, flip, seed, 0, hits, keep) == -1, "zero samples is invalid input"); }
    for (size_t a = 0; a < 3; a++) free(v.act[a]);
    free(cls); free(flip);
    printf("screen_m2: %s\n", fails ? "FAIL" : "PASS");
    return fails ? 1 : 0;
}
