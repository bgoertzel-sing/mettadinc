/* M4-estimates seeded coverage simulations (t-2026-11-12-mettadinc-m4-estimates).
 * Usage: sim_coverage [seed] [trials].  Every draw comes from splitmix64(seed),
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
    const double ps[] = { 0.03, 0.2, 0.5 }; const long N = 400; const double a = 0.05;
    printf("seed %llu trials %ld steps %ld\n", (unsigned long long)seed, T, N);
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
    printf("coverage: %d/%d passed\n", total - fails, total);
    return fails ? 1 : 0;
}
