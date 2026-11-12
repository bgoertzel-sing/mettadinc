/* M4-estimates seeded coverage simulations (t-2026-11-12-mettadinc-m4-estimates).
 * Usage: sim_coverage [seed] [trials] [level].  Every draw comes from splitmix64(seed),
 * so a run replays exactly.  Each check passes iff the observed miss count is
 * at most the nominal level plus a binomial tolerance (3 sd); the canary
 * (peeking normal-approximation interval) must FAIL that bound, proving the
 * harness can see an optional-stopping violation.  Exit 0 iff all pass. */
#include "estimates.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static int fails, total;
static double unif(uint64_t *st) { return (double)(dc_splitmix64(st) >> 11) * (1.0 / 9007199254740992.0); }
static int within(long miss, long T, double a) { return miss <= a * T + 3.0 * sqrt(a * (1 - a) * T) + 1; }
static void report(const char *name, long miss, long T, double a, int expect_ok) {
    int ok = within(miss, T, a) == expect_ok; total++; fails += !ok;
    printf("%-4s %-64s miss %ld/%ld (level %.3g, bound %.1f)\n", ok ? "ok" : "FAIL", name, miss, T, a, a * T + 3.0 * sqrt(a * (1 - a) * T) + 1);
}
int main(int argc, char **argv) {
    uint64_t seed = argc > 1 ? strtoull(argv[1], NULL, 10) : 20261112ULL;
    long T = argc > 2 ? atol(argv[2]) : 2000;
    const double ps[] = { 0.03, 0.2, 0.5 }; const long N = 400;
    /* review 2 F4: optional third argument = level; run-all runs 0.05 and 0.01 (the surface requests use 1/100) */
    const double a = argc > 3 ? atof(argv[3]) : 0.05;
    printf("seed %llu trials %ld steps %ld level %.3g\n", (unsigned long long)seed, T, N, a);
    for (int pi = 0; pi < 3; pi++) {
        double p = ps[pi]; uint64_t st = seed + (uint64_t)pi * 1000003ULL;
        long cs_miss = 0, cp_miss = 0, hf_miss = 0, wald_peek = 0; double thr = log(1.0 / a);
        for (long t = 0; t < T; t++) {
            long S = 0; int cs_out = 0, wp_out = 0;
            for (long n = 1; n <= N; n++) {
                S += unif(&st) < p;
                if (!cs_out && dc_cs_logmix(S, n, p) >= thr) cs_out = 1;          /* time-uniform: any n */
                if (n >= 10 && !wp_out) {                                         /* canary: peeking Wald */
                    double ph = (double)S / n, h = 1.96 * sqrt(ph * (1 - ph) / n);
                    if (p < ph - h || p > ph + h) wp_out = 1;
                }
            }
            double lo, hi; dc_exact_binom_interval(S, N, a, &lo, &hi);
            cp_miss += p < lo || p > hi;
            hf_miss += fabs((double)S / N - p) > dc_hoeffding_eps(N, a);
            cs_miss += cs_out; wald_peek += wp_out;
        }
        char b[128];
        snprintf(b, sizeof b, "p=%.2f anytime CS, optional stopping over n<=%ld", p, N); report(b, cs_miss, T, a, 1);
        snprintf(b, sizeof b, "p=%.2f exact-binomial (Clopper-Pearson) at n=%ld", p, N); report(b, cp_miss, T, a, 1);
        snprintf(b, sizeof b, "p=%.2f Hoeffding at n=%ld", p, N); report(b, hf_miss, T, a, 1);
        snprintf(b, sizeof b, "p=%.2f CANARY peeking Wald must violate", p); report(b, wald_peek, T, a, 0);
    }
    /* review 1 F1: the order-2 U-statistic (pairwise duplicate rate) with its
     * Hoeffding bound over floor(n/2) independent pairs, on key distributions
     * whose duplicate rate theta = sum_k w_k^2 is known exactly.  Canary: the
     * same bound with m = C(n,2) (pretending every pair is independent) must
     * violate on the non-degenerate skewed model. */
    {
        static const char *K[20] = { "k0","k1","k2","k3","k4","k5","k6","k7","k8","k9",
                                     "k10","k11","k12","k13","k14","k15","k16","k17","k18","k19" };
        static const double W0[] = { 0.5, 0.25, 0.15, 0.1 };
        double W1[20], W2[10], z = 0;
        for (int i = 0; i < 20; i++) { W1[i] = pow(0.8, i); z += W1[i]; }
        for (int i = 0; i < 20; i++) W1[i] /= z;
        for (int i = 0; i < 10; i++) W2[i] = 0.1;
        const double *W[3] = { W0, W1, W2 }; const int nk[3] = { 4, 20, 10 };
        const char *nm[3] = { "skewed 4 keys (0.5,0.25,0.15,0.1)", "geometric 20 keys (ratio 0.8)", "uniform 10 keys" };
        const long NU = 100; const char *keys[100];
        for (int di = 0; di < 3; di++) {
            double th = 0; for (int i = 0; i < nk[di]; i++) th += W[di][i] * W[di][i];
            uint64_t st = seed + 7000003ULL + (uint64_t)di * 1000003ULL;
            double eps = dc_hoeffding_eps(NU / 2, a), eps_bad = dc_hoeffding_eps(NU * (NU - 1) / 2, a);
            long miss = 0, miss_bad = 0;
            for (long t = 0; t < T; t++) {
                for (long i = 0; i < NU; i++) {
                    double u = unif(&st), c = 0; int k = nk[di] - 1;
                    for (int j = 0; j < nk[di]; j++) { c += W[di][j]; if (u < c) { k = j; break; } }
                    keys[i] = K[k];
                }
                long long num, den; dc_ustat_dup(keys, (size_t)NU, &num, &den);
                double dev = fabs((double)num / (double)den - th);
                miss += dev > eps; miss_bad += dev > eps_bad;
            }
            char b[128];
            snprintf(b, sizeof b, "U-stat dup rate, %s, theta=%.4f, n=%ld", nm[di], th, NU); report(b, miss, T, a, 1);
            if (di == 0) { snprintf(b, sizeof b, "U-stat CANARY m=C(n,2) bound must violate (%s)", nm[di]); report(b, miss_bad, T, a, 0); }
        }
    }
    printf("coverage: %d/%d passed\n", total - fails, total);
    return fails ? 1 : 0;
}
