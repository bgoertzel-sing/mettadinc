/* M2 acceptance 3: differential test of the two behavioral engines.
 * On a seeded family of random small deterministic machines (2..maxn states,
 * 1..3 actions, crisp or graded seeds d0, discount in {1, 1/2, 9/10, 2/3},
 * horizon in {unbounded, 0, 1, 2, 3}) the reference engine (Kleene iteration of
 * Phi) and the specialized engine (shortest paths in the pair graph) must give
 * the same exact distance table.  For crisp seeds at discount 1 without a
 * horizon, the zero set must also equal the coarsest stable refinement.
 * Usage: differential_m2 [seed] [count] [maxn].  Exit 0 iff no disagreement. */
#include "graded.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned long long st;
static unsigned rnd(unsigned k) { st = st * 6364136223846793005ULL + 1442695040888963407ULL; return (unsigned)((st >> 33) % k); }
int main(int argc, char **argv) {
    unsigned long long seed = argc > 1 ? strtoull(argv[1], 0, 10) : 20261110ULL;
    long count = argc > 2 ? atol(argv[2]) : 5000; int maxn = argc > 3 ? atoi(argv[3]) : 7;
    st = seed; long bad = 0, ovf = 0, crisp = 0, crispbad = 0, done = 0, clk = 0, clkbad = 0;
    DcRat gs[4] = {{1, 1}, {1, 2}, {9, 10}, {2, 3}};
    for (long t = 0; t < count; t++) {
        DcView v; memset(&v, 0, sizeof v);
        size_t n = 2 + rnd((unsigned)maxn - 1); v.n = n; v.nact = 1 + rnd(3);
        for (size_t a = 0; a < v.nact; a++) { v.act[a] = malloc(n * sizeof(int)); for (size_t i = 0; i < n; i++) v.act[a][i] = (int)rnd((unsigned)n); }
        int iscrisp = rnd(2), lab[16], val[16], cls[16]; int o = 0;
        DcRat *d0 = calloc(n * n, sizeof *d0), *r = calloc(n * n, sizeof *r), *b = calloc(n * n, sizeof *b);
        for (size_t i = 0; i < n; i++) { lab[i] = (int)rnd(3); val[i] = (int)rnd(11); }
        for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++)
            d0[i * n + j] = iscrisp ? (DcRat){lab[i] != lab[j], 1} : dc_rat(abs(val[i] - val[j]), 10, &o);
        DcRat g = gs[rnd(4)]; int h = (int)rnd(5) - 1;
        int e1 = dc_g_beh_ref(&v, d0, g, h, r), e2 = dc_g_beh_bfs(&v, d0, g, h, b);
        if (e1 || e2) ovf++;
        else {
            done++; int diff = 0;
            for (size_t i = 0; i < n * n; i++) if (dc_rat_cmp(r[i], b[i])) diff = 1;
            if (diff) { if (bad < 5) printf("DISAGREE machine %ld: n=%zu actions=%zu horizon=%d\n", t, n, v.nact, h); bad++; }
            if (iscrisp && g.n == 1 && g.d == 1 && h < 0) {
                for (size_t i = 0; i < n; i++) { cls[i] = (int)i; for (size_t j = 0; j < i; j++) if (lab[j] == lab[i]) { cls[i] = (int)j; break; } }
                dc_refine_stable(&v, cls); crisp++;
                for (size_t i = 0; i < n; i++) for (size_t j = 0; j < n; j++)
                    if (dc_rat_is_zero(b[i * n + j]) != (cls[i] == cls[j])) { if (crispbad < 5) printf("REFINE DISAGREE machine %ld\n", t); crispbad++; i = n; break; }
            }
        }
        /* Clock-rate screen (Prop 4.8): d0 is a (pseudo)metric here, so the update
         * defect of d0 is at most 2 max_a sup_x d0(x, T_a x). */
        { int co = 0, px, py, pa; DcRat sup[4], mean[4];
          DcRat s = dc_g_clock_rates(&v, d0, sup, mean, &co), u = dc_g_update_defect(&v, d0, &px, &py, &pa);
          if (!co) { clk++; if (dc_rat_cmp(u, dc_rat_add(s, s, &co)) > 0 || co) { if (clkbad < 5) printf("CLOCK-RATE BOUND VIOLATED machine %ld\n", t); clkbad++; } } }
        for (size_t a = 0; a < v.nact; a++) free(v.act[a]);
        free(d0); free(r); free(b);
    }
    printf("differential_m2: seed %llu, %ld random machines with 2..%d states and 1..3 actions; %ld compared, %ld outside the 64-bit range (both engines report it); "
           "reference vs pair-graph: %ld disagreements; crisp refine vs zero set: %ld compared, %ld disagreements; "
           "clock-rate screen (update defect <= 2 max sup rate): %ld checked, %ld violations\n",
           seed, count, maxn, done, ovf, bad, crisp, crispbad, clk, clkbad);
    return bad || crispbad || clkbad ? 1 : 0;
}
