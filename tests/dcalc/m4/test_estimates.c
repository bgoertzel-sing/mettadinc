/* M4-estimates gates (t-2026-11-12-mettadinc-m4-estimates), C API level.
 * Usage: test_estimates <validation_bundle_dir>.  Sources are inline; no
 * fixture under tests/dcalc/mutations/ is named.  Exit 0 iff all pass. */
#include "ops_run.h"
#include "records.h"
#include "estimates.h"
#include "api.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static int fails, total;
#define CHECK(c, msg) do { total++; if (c) printf("ok   %s\n", msg); else { fails++; printf("FAIL %s\n", msg); } } while (0)
#define DIG "sha256:1f5d10eff762371dffdef5e0be4f940e39366a8fe2c6b9227bb7cdb66c82ca0f"
static const char *MOD_FMT =
    "(DC.Module EstT (Profile Stochastic) (Use Estimates)\n"
    "  (Stream Replies (Source \"streams/replies.json\") (Digest \"%s\")\n"
    "    (Population \"replies to items at most seven days old\") (Selection \"one receipt per reply\") (Policy \"wmtm-v1\")))\n";
static const char *REQ = "(EstimateRate (On Replies) (Column \"stale\") (Equals 1) (Level (Rat 1 100)))";

static Sx *eval(const char *bundle, const char *digest, int beyond) {
    char src[1024]; snprintf(src, sizeof src, MOD_FMT, digest);
    dc_eval_set_beyond_release(beyond);
    char *out = dc_eval_text(src, bundle, "EstT", REQ);
    const char *err = NULL; int line = 0;
    Sx *all = sx_parse_all(out, &err, &line); free(out);
    Sx *r = all && all->n == 1 ? sx_copy(all->items[0]) : NULL;
    if (all) sx_free(all);
    return r;
}
static const char *status(const Sx *r) {
    const Sx *s = r ? sx_find(r, "Status", 1) : NULL;
    return s && s->n == 2 ? s->items[1]->text : "missing";
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: test_estimates <bundle_dir>\n"); return 2; }
    const char *B = argv[1]; char why[256];

    /* release gate: both modes */
    Sx *rel = eval(B, DIG, 0);
    CHECK(!strcmp(status(rel), "Unsupported"), "release mode: EstimateRate answers Unsupported");
    Sx *r = eval(B, DIG, 1);
    CHECK(!strcmp(status(r), "Estimated"), "beyond-release: EstimateRate answers Estimated (inv 17: never Checked)");
    const Sx *est = r ? sx_find(r, "Estimate", 1) : NULL;
    DcEstimate e; int parsed = est && dc_estimate_parse(est, &e, why, sizeof why) == 0;
    if (!parsed) printf("     parse: %s\n", est ? why : "no Estimate field");
    CHECK(parsed, "Estimated result carries a parseable Estimate record");
    CHECK(parsed && dc_estimate_complete(&e, why, sizeof why), "Estimate record has all ten envelope fields");
    CHECK(parsed && e.sample_size == 916 && !strcmp(e.policy_version, "wmtm-v1"), "record: SampleSize 916, Policy wmtm-v1");

    /* negative gate 1: changed receipt stream -> no Estimated value */
    Sx *bad = eval(B, "sha256:0000000000000000000000000000000000000000000000000000000000000000", 1);
    CHECK(!strcmp(status(bad), "InvalidInput") && !sx_find(bad, "Estimate", 1), "changed stream digest: InvalidInput, no Estimate (both modes refuse)");
    Sx *bad0 = eval(B, "sha256:0000000000000000000000000000000000000000000000000000000000000000", 0);
    CHECK(strcmp(status(bad0), "Estimated") != 0, "changed stream digest, release mode: not Estimated");

    /* negative gate 2: duplicate-rate bound reused under a new policy (spec 7.4) */
    const char *v1[] = { "k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8", "k9", "k1" };
    const char *wh[] = { "k1", "k1" };   /* the withholding policy keeps only the duplicate */
    long long n1, d1, n2, d2;
    dc_ustat_dup(v1, 10, &n1, &d1); dc_ustat_dup(wh, 2, &n2, &d2);
    CHECK(n1 == 1 && d1 == 45, "U-statistic: pairwise duplicate rate 1/45 under v1 (ten keys, one repeat)");
    CHECK(n2 == 1 && d2 == 1, "U-statistic: 1/1 under the withholding policy: the bound does not survive");
    CHECK(fabs(dc_hoeffding_eps(10 / 2, 0.05) - 0.607370) < 1e-5, "Hoeffding for order-2 U-statistic uses floor(n/2)");
    DcEstimate dup = e; snprintf(dup.estimand, sizeof dup.estimand, "pairwise duplicate rate among proposed keys");
    dup.selection_depends_on_policy = 0;
    CHECK(!dc_estimate_transport(&dup, "wmtm-withhold-first", 0), "dup-rate bound under a new policy without argument: refused");
    CHECK(dc_estimate_transport(&dup, "wmtm-withhold-first", 1), "dup-rate bound with a declared fixed-population argument: accepted");
    CHECK(dc_estimate_transport(&dup, "wmtm-v1", 0), "same policy: no transport needed");
    /* negative gate 3: policy-dependent selection blocks transport */
    dup.selection_depends_on_policy = 1;
    CHECK(!dc_estimate_transport(&dup, "wmtm-withhold-first", 1), "policy-dependent selection: blocked even with an argument");

    /* seeded sampling: replay */
    size_t a[50], b[50], c[50];
    dc_sample_indices(20261112, 916, 50, a); dc_sample_indices(20261112, 916, 50, b); dc_sample_indices(20261113, 916, 50, c);
    CHECK(!memcmp(a, b, sizeof a), "seeded sample replays byte for byte from (seed, population size)");
    CHECK(memcmp(a, c, sizeof a) != 0, "a different seed draws a different sample");

    Sx *fr[] = { rel, r, bad, bad0 };
    for (size_t k = 0; k < 4; k++) if (fr[k]) sx_free(fr[k]);
    printf("estimates: %d/%d passed\n", total - fails, total);
    return fails ? 1 : 0;
}
