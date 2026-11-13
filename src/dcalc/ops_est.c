/* M4-estimates: EstimateRate over a frozen, digest-pinned Stream.
 * The answer is Estimated (ground Statistical), never Checked (inv 17), and
 * carries the full ten-field Estimate record.  The stream is read only from
 * bytes whose sha256 equals the declared digest: a changed receipt stream
 * yields InvalidInput, never an Estimated value. */
#include "ops_run.h"
#include "records.h"
#include "estimates.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const Sx *decl_stream(const DcModule *m, const char *nm) {
    const Sx *src = m->source;
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (sx_head_is(d, "Stream") && d->n >= 2 && d->items[1]->kind != SX_LIST && !strcmp(d->items[1]->text, nm)) return d;
    }
    return NULL;
}
static const char *fld(const Sx *d, const char *k) {
    const Sx *f = sx_find(d, k, 1);
    return f && f->n == 2 && f->items[1]->kind != SX_LIST ? f->items[1]->text : NULL;
}
static const Sx *arg(const Sx *q, const char *k) {
    const Sx *f = sx_find(q, k, 1);
    return f && f->n == 2 ? f->items[1] : NULL;
}
static Sx *rat_sx(long long num, long long den) {
    int ovf = 0; DcRat r = dc_rat(num, den, &ovf);
    return dc_form("Rat", dc_int((long)r.n), dc_int((long)r.d), NULL);
}

/* the envelope: status through the single policy dc_assure_grounded */
static Sx *est_env(DcModule *m, const Sx *q, const char *sname, Sx *val, Sx *ev, Sx *estimate) {
    DcScope sc = { "M4-Estimates", -1, "1", NULL };
    Sx *r = dc_envelope_scoped(m, VERDICT_HOLDS, 1, dc_form("Claim", sx_copy(q), NULL),
                               dc_form("Subject", dc_form("Stream", dc_sym(sname), NULL), NULL), val, ev, NULL, &sc);
    Sx *st = sx_find(r, "Status", 1);
    if (st && st->n == 2) { sx_free(st->items[1]); st->items[1] = dc_sym(dc_status_name(dc_assure_grounded(VERDICT_HOLDS, GROUND_STATISTICAL, 0))); }
    for (size_t i = 1; i < r->n; i++)
        if (sx_head_is(r->items[i], "Assurance")) {
            sx_free(r->items[i]);
            r->items[i] = dc_form("Assurance", dc_form("Policy", dc_sym("M4-Estimates"), NULL),
                                  /* review 2 F4: a statistical ground is not a replayed certificate */
                                  dc_form("Replayed", dc_sym("False"), NULL),
                                  dc_form("Ground", dc_sym(dc_ground_name(GROUND_STATISTICAL)), NULL), NULL);
        }
    sx_push(r, estimate);
    return r;
}

static int nat_arg(const Sx *q, const char *k, long long *v) {   /* 1 present, 0 absent, -1 malformed */
    const Sx *a = arg(q, k);
    if (!a) return 0;
    if (a->kind == SX_LIST) return -1;
    char *e = NULL; long long x = strtoll(a->text, &e, 10);
    if (!e || *e || x < 0) return -1;
    *v = x; return 1;
}

/* EstimateRate, CompareRates and (review 1 F2) EstimateDupRate.  Review 1:
 * F2 (Estimator ConfidenceSequence|Hoeffding|ExactBinomial) and the U-statistic,
 * F4 (Sample k) (Seed s): a seeded simple random sample, Seed and
 *    SamplePopulation recorded in the Estimate record and the Evidence,
 * F5 (ReuseUnder policy) [(Argument ..)]: dc_estimate_transport at the surface. */
Sx *dc_req_estimates(DcRun *run, const Sx *q, const char *head) {
    DcModule *m = run->m;
    int cmp = !strcmp(head, "CompareRates"), dup = !strcmp(head, "EstimateDupRate");
    const Sx *on = arg(q, "On");
    if (!on || on->kind == SX_LIST) return dc_invalid(m, "%s: field On must name a Stream", head);
    const char *sn = on->text; const Sx *d = decl_stream(m, sn);
    if (!d) return dc_invalid(m, "%s: On %s names no declared Stream", head, sn);
    const char *src = fld(d, "Source"), *dig = fld(d, "Digest");
    if (!src || !dig) return dc_invalid(m, "%s: Stream %s needs (Source path) and (Digest sha256:..)", head, sn);
    const Sx *lv = arg(q, "Level"); DcRat L;
    if (!lv || dc_sx_rat(lv, &L) || L.n <= 0 || L.n >= L.d) return dc_invalid(m, "%s: field Level is not a rational in (0,1)", head);
    const Sx *eq = dup ? NULL : arg(q, "Equals"), *col = arg(q, cmp ? "First" : "Column"), *col2 = cmp ? arg(q, "Second") : NULL;
    if (!dup && (!eq || eq->kind == SX_LIST)) return dc_invalid(m, "%s: field Equals must be a number or string", head);
    if (!col || col->kind == SX_LIST) return dc_invalid(m, "%s: field %s must name a column", head, cmp ? "First" : "Column");
    if (cmp && (!col2 || col2->kind == SX_LIST)) return dc_invalid(m, "%s: field Second must name a column", head);
    const Sx *es = arg(q, "Estimator");
    if (es && es->kind == SX_LIST) return dc_invalid(m, "%s: field Estimator must be a symbol", head);
    const char *est = es ? es->text : dup ? "Hoeffding" : "ConfidenceSequence";
    if (dup ? strcmp(est, "Hoeffding") != 0
            : (strcmp(est, "ConfidenceSequence") && strcmp(est, "Hoeffding") && strcmp(est, "ExactBinomial")))
        return dc_invalid(m, "%s: Estimator %s is not one of %s", head, est, dup ? "Hoeffding" : "ConfidenceSequence, Hoeffding, ExactBinomial");
    long long K = -1, seed = 0;
    int hs = nat_arg(q, "Sample", &K), hd = nat_arg(q, "Seed", &seed);
    if (hs < 0 || hd < 0) return dc_invalid(m, "%s: fields Sample and Seed must be natural numbers", head);
    if (hs && !hd) return dc_invalid(m, "%s: (Sample %lld) needs (Seed s); the seed is recorded so the sample replays", head, K);
    if (hd && !hs) return dc_invalid(m, "%s: (Seed %lld) without (Sample k)", head, seed);
    const char *pol = fld(d, "Policy"), *dep = fld(d, "SelectionDependsOnPolicy");
    int seldep = dep && !strcmp(dep, "True");
    const Sx *ru = arg(q, "ReuseUnder");
    if (ru) {                                     /* F5: policy transport, decided before any row is read */
        if (ru->kind == SX_LIST) return dc_invalid(m, "%s: field ReuseUnder must name a policy digest", head);
        /* gaps task, review 3 gap 1: a Stream with no Policy has no source policy for the
         * transport check (guide 1.x boundary 5); it is InvalidInput, never "undeclared". */
        if (!pol)
            return dc_invalid(m, "%s: ReuseUnder %s: Stream %s declares no Policy, so the transport check has no source policy; declare (Policy ..) on the Stream", head, ru->text, sn);
        DcEstimate te; memset(&te, 0, sizeof te);
        snprintf(te.policy_version, sizeof te.policy_version, "%s", pol);
        te.selection_depends_on_policy = seldep;
        if (!dc_estimate_transport(&te, ru->text, arg(q, "Argument") != NULL)) {
            if (seldep)
                return dc_invalid(m, "%s: ReuseUnder %s: the selection rule of Stream %s depends on the policy, so the estimate does not transport (blocked even with an Argument); a new estimate is needed", head, ru->text, sn);
            return dc_invalid(m, "%s: ReuseUnder %s: Stream %s was produced under policy %s; reusing the estimate needs a new estimate or a declared (Argument ..)", head, ru->text, sn, te.policy_version);
        }
    }
    char path[1100];
    if (src[0] == '/' || !m->basedir[0]) snprintf(path, sizeof path, "%s", src);
    else snprintf(path, sizeof path, "%s/%s", m->basedir, src);
    DcStream s; char err[256];
    if (dc_stream_load(path, dig, &s, err, sizeof err))
        return dc_invalid(m, "%s: Stream %s: %s; a changed receipt stream yields no Estimated value", head, sn, err);
    int k = dc_stream_col(&s, col->text);
    if (k < 0) { dc_stream_free(&s); return dc_invalid(m, "%s: Stream %s has no column %s", head, sn, col->text); }
    int k2 = cmp ? dc_stream_col(&s, col2->text) : -1;
    if (cmp && k2 < 0) { dc_stream_free(&s); return dc_invalid(m, "%s: Stream %s has no column %s", head, sn, col2->text); }
    size_t rows = s.nrows, nr = rows;
    size_t *ix = malloc((rows ? rows : 1) * sizeof *ix);
    if (!ix) { dc_stream_free(&s); return dc_unsupported(m, "%s: out of memory", head); }
    if (hs) {                                     /* F4: seeded simple random sample without replacement */
        if (K < (dup ? 2 : 1) || (size_t)K > rows || dc_sample_indices((uint64_t)seed, rows, (size_t)K, ix)) {
            free(ix); dc_stream_free(&s);
            return dc_invalid(m, "%s: (Sample %lld) is outside %d..%zu, the rows of Stream %s", head, K, dup ? 2 : 1, rows, sn);
        }
        nr = (size_t)K;
    } else
        for (size_t i = 0; i < rows; i++) ix[i] = i;
#define CELL(i, c) s.cell[ix[i] * (size_t)s.ncol + (size_t)(c)]
    long S = 0, n = (long)nr; long long num = 0, den = 1;
    if (cmp) {
        long a = 0, b = 0;
        for (size_t i = 0; i < nr; i++) {
            int x = !strcmp(CELL(i, k), eq->text), y = !strcmp(CELL(i, k2), eq->text);
            a += x && !y; b += !x && y;
        }
        S = a; n = a + b;
    } else if (dup) {
        if (nr < 2) { free(ix); dc_stream_free(&s); return dc_invalid(m, "%s: Stream %s has fewer than two rows", head, sn); }
        const char **keys = malloc(nr * sizeof *keys);
        if (!keys) { free(ix); dc_stream_free(&s); return dc_unsupported(m, "%s: out of memory", head); }
        for (size_t i = 0; i < nr; i++) keys[i] = CELL(i, k);
        dc_ustat_dup(keys, nr, &num, &den); free(keys);
    } else
        for (size_t i = 0; i < nr; i++) S += !strcmp(CELL(i, k), eq->text);
#undef CELL
    free(ix);
    double al = (double)L.n / (double)L.d, lo = 0, hi = 1;
    int cs = !dup && !strcmp(est, "ConfidenceSequence"), hf = !strcmp(est, "Hoeffding");
    if (dup) { double c = (double)num / (double)den, e = dc_hoeffding_eps((long)(nr / 2), al); lo = c - e; hi = c + e; }
    else if (n <= 0) { lo = 0; hi = 1; }
    else if (hf) { double c = (double)S / (double)n, e = dc_hoeffding_eps(n, al); lo = c - e; hi = c + e; }
    else if (!cs) dc_exact_binom_interval(S, n, al, &lo, &hi);
    else dc_cs_interval(S, n, al, &lo, &hi);
    if (lo < 0) lo = 0;
    if (hi > 1) hi = 1;
    long long loD = dc_dyadic_floor(lo), hiD = dc_dyadic_ceil(hi);
    char estimand[256], proto[512], samp[256], estname[200];
    if (cmp) snprintf(estimand, sizeof estimand, "share, among rows of %s where exactly one of %s, %s equals %s, of those where it is %s", sn, col->text, col2->text, eq->text, col->text);
    else if (dup) snprintf(estimand, sizeof estimand, "pairwise duplicate rate: share of unordered row pairs of %s with equal %s", sn, col->text);
    else snprintf(estimand, sizeof estimand, "rate of rows of %s with %s = %s", sn, col->text, eq->text);
    if (hs) snprintf(samp, sizeof samp, "a seeded simple random sample (splitmix64, partial Fisher-Yates, seed %lld) of %lld of the %zu rows", seed, K, rows);
    else snprintf(samp, sizeof samp, "every row (census of %zu rows)", rows);
    snprintf(proto, sizeof proto, "%s of frozen stream %s, %s, read once; %s", samp, sn, dig,
             cs ? "anytime-valid, so optional stopping is allowed" : "fixed-sample interval: the sample size is fixed before reading, not valid under optional stopping");
    snprintf(estname, sizeof estname, "%s", dup ? "order-2 U-statistic (pairs with equal key / C(n,2)) with Hoeffding half-width sqrt(log(2/delta)/(2 floor(n/2)))"
             : cs ? "confidence sequence of the uniform-prior (Beta(1,1)) binomial mixture"
             : hf ? "Hoeffding interval: sample proportion +- sqrt(log(2/delta)/(2n))" : "two-sided exact-binomial (Clopper-Pearson) interval");
    Sx *estimate = dc_form("Estimate", dc_form("Estimand", sx_str(estimand), NULL),
        dc_form("Population", sx_str(fld(d, "Population") ? fld(d, "Population") : "undeclared"), NULL),
        dc_form("Selection", sx_str(fld(d, "Selection") ? fld(d, "Selection") : "undeclared"), NULL),
        dc_form("Policy", sx_str(pol ? pol : "undeclared"), NULL),
        dc_form("Estimator", sx_str(estname), NULL),
        dc_form("Protocol", sx_str(proto), NULL),
        dc_form("SampleSize", dc_int(dup ? (long)nr : n), NULL),   /* CompareRates: the discordant rows, as before */
        dc_form("Error", rat_sx(hiD - loD, 2 * DC_DYADIC_DEN), sx_copy(lv), NULL),
        dc_form("Dependence", sx_str(dup ? "rows independent with identically distributed keys (declared, not checked)"
                                         : "rows independent Bernoulli with a common rate (declared, not checked)"), NULL),
        dc_form("Combination", sx_str("single estimate; derived results carry (EstimatedPremise digest delta) and (EstimatedDelta sum): the deltas add"), NULL),
        dc_form("SelectionDependsOnPolicy", dc_sym(seldep ? "True" : "False"), NULL),
        dc_form("SamplePopulation", dc_int((long)rows), NULL), NULL);
    if (hs) sx_push(estimate, dc_form("Seed", dc_int((long)seed), NULL));
    if (ru) {   /* gaps task, review 3 gap 1: the transport trace (source policy, target policy, argument passed on) */
        const Sx *ar = arg(q, "Argument");
        sx_push(estimate, dc_form("Transport", dc_form("FromPolicy", sx_str(pol), NULL),
                                  dc_form("ToPolicy", sx_str(ru->text), NULL),
                                  ar ? dc_form("Argument", sx_copy(ar), NULL) : dc_form("Argument", dc_sym("None"), NULL),
                                  dc_form("Rule", sx_str(!strcmp(pol, ru->text) ? "same policy" : "declared argument"), NULL), NULL));
    }
    {   /* gaps task, review 3 gap 4: an explicit replay command.  Re-running Request (which already
         * names Seed and Sample) under --beyond-release against a stream whose digest is StreamDigest
         * and whose population is SamplePopulation reproduces this result byte for byte. */
        char cmdline[512];
        snprintf(cmdline, sizeof cmdline, "dcalc --beyond-release FILE.metta, where FILE.metta holds module %s (Stream %s with Digest %s, %zu rows) and the line !(dc.run %s <Request>)",
                 m->name[0] ? m->name : "<module>", sn, dig, rows, m->name[0] ? m->name : "<module>");
        Sx *rp = dc_form("Replay", dc_form("Request", sx_copy(q), NULL),
                         dc_form("StreamDigest", sx_str(dig), NULL),
                         dc_form("SamplePopulation", dc_int((long)rows), NULL), NULL);
        if (hs) sx_push(rp, dc_form("Seed", dc_int((long)seed), NULL));
        else sx_push(rp, dc_form("Seed", dc_sym("None"), NULL));
        sx_push(rp, dc_form("Mode", dc_sym("BeyondRelease"), NULL));
        sx_push(rp, dc_form("Command", sx_str(cmdline), NULL));
        sx_push(estimate, rp);
    }
    Sx *inner = cmp ? dc_form("PairedComparison", dc_form("FirstOnly", dc_int(S), NULL), dc_form("SecondOnly", dc_int(n - S), NULL), NULL)
              : dup ? dc_form("RateEstimate", dc_form("Count", dc_int((long)num), NULL), dc_form("Observations", dc_int((long)den), NULL), NULL)
                    : dc_form("RateEstimate", dc_form("Count", dc_int(S), NULL), dc_form("Observations", dc_int(n), NULL), NULL);
    sx_push(inner, dc_form("Lower", rat_sx(loD, DC_DYADIC_DEN), NULL));
    sx_push(inner, dc_form("Upper", rat_sx(hiD, DC_DYADIC_DEN), NULL));
    sx_push(inner, dc_form("Estimand", sx_str(estimand), NULL));
    Sx *proc = cs ? dc_form("ConfidenceSequence", dc_sym("BinomialMixture"), dc_form("Prior", dc_sym("Beta"), dc_int(1), dc_int(1), NULL), NULL)
             : dup ? dc_form("UStatistic", dc_form("Order", dc_int(2), NULL), dc_form("Bound", dc_sym("Hoeffding"), NULL),
                             dc_form("IndependentPairs", dc_int((long)(nr / 2)), NULL), NULL)
             : dc_form(hf ? "Hoeffding" : "ExactBinomial", NULL);
    sx_push(proc, dc_form("Level", sx_copy(lv), NULL));
    sx_push(proc, dc_form("Rounding", dc_sym("OutwardDyadic30"), NULL));
    sx_push(inner, dc_form("Procedure", proc, NULL));
    sx_push(inner, dc_form("Assumptions", dc_sym(cmp ? "DiscordantRowsIndependentCommonShare" : dup ? "RowsIndependentIdenticallyDistributedKeys" : "RowsIndependentCommonRate"), NULL));
    /* review 1 F3: the error probability this estimate spends; a result derived
     * from it carries (EstimatedPremise digest delta) and the deltas add. */
    sx_push(inner, dc_form("Delta", sx_copy(lv), NULL));
    Sx *val = dc_form("Value", inner, NULL);
    Sx *smp = dc_form("Sample", dc_form("Stream", dc_sym(sn), NULL), dc_form("Digest", sx_str(dig), NULL),
        dc_form("Rows", dc_int((long)nr), NULL), dc_form("SamplePopulation", dc_int((long)rows), NULL), NULL);
    if (hs) sx_push(smp, dc_form("Seed", dc_int((long)seed), NULL));
    if (!dup) sx_push(smp, dc_form("Events", dc_int(S), NULL));
    Sx *ev = dc_form("Evidence", smp, NULL);
    dc_stream_free(&s);
    return est_env(m, q, sn, val, ev, estimate);
}

/* review 1 F3: a consuming operation.  (RatesSeparated A B) reads two Derive'd
 * Estimated rate results and decides, exactly, Upper(A) < Lower(B).  The
 * comparison itself is checked; dc_result_add_premise turns it Conditional on
 * (EstimatedPremise digest delta) per premise and adds (EstimatedDelta sum). */
static int est_bound(const Sx *res, const char *which, DcRat *out) {
    const Sx *st = sx_find(res, "Status", 1), *val = sx_find(res, "Value", 1);
    if (!st || st->n != 2 || !sx_is_sym(st->items[1], "Estimated") || !val) return -1;
    for (size_t i = 1; i < val->n; i++) {
        const Sx *b = val->items[i]->kind == SX_LIST ? sx_find(val->items[i], which, 1) : NULL;
        if (b && b->n == 2 && !dc_sx_rat(b->items[1], out)) return 0;
    }
    return -1;
}
Sx *dc_req_separated(DcRun *run, const Sx *q) {
    DcModule *m = run->m;
    if (q->n != 3 || q->items[1]->kind == SX_LIST || q->items[2]->kind == SX_LIST)
        return dc_invalid(m, "RatesSeparated: expected two Derive names");
    int dd[2]; const Sx *pr[2]; DcRat b[2];
    for (int k = 0; k < 2; k++) {
        const char *nm = q->items[k + 1]->text;
        dd[k] = dc_find_derive(m, nm);
        if (dd[k] < 0) return dc_invalid(m, "RatesSeparated: %s is not a Derive", nm);
        if (run->busy[dd[k]]) return dc_invalid(m, "RatesSeparated: %s: cyclic reference", nm);
        pr[k] = dc_run_derive(run, dd[k]);
        if (!pr[k]) return dc_invalid(m, "RatesSeparated: %s: cyclic reference", nm);
        if (est_bound(pr[k], k ? "Lower" : "Upper", &b[k]))
            return dc_invalid(m, "RatesSeparated: %s is not an Estimated rate result with %s", nm, k ? "Lower" : "Upper");
    }
    int sep = (__int128)b[0].n * b[1].d < (__int128)b[1].n * b[0].d;
    Sx *val = dc_form("Value", dc_form("RateSeparation", dc_form("Separated", dc_sym(sep ? "True" : "False"), NULL),
        dc_form("FirstUpper", dc_form("Rat", dc_int((long)b[0].n), dc_int((long)b[0].d), NULL), NULL),
        dc_form("SecondLower", dc_form("Rat", dc_int((long)b[1].n), dc_int((long)b[1].d), NULL), NULL), NULL), NULL);
    Sx *ev = dc_form("Evidence", dc_form("ExactRationalComparison", sx_copy(q->items[1]), sx_copy(q->items[2]), NULL), NULL);
    DcScope sc = { "M4-Estimates", -1, "1", NULL };   /* review 2 F4: not the M0 fragment */
    Sx *r = dc_envelope_scoped(m, sep ? VERDICT_HOLDS : VERDICT_FAILS, 1, dc_form("Claim", sx_copy(q), NULL),
                        dc_form("Subject", sx_copy(q->items[1]), sx_copy(q->items[2]), NULL), val, ev, NULL, &sc);
    for (int k = 0; k < 2; k++) dc_result_add_premise(r, pr[k], m->der[dd[k]].name);
    /* gaps task, review 3 gap 2: the derived result names the estimates policy, not M2-ExactReplay,
     * and carries each premise's Estimate record (the rates it compares are statistical). */
    for (size_t i = 1; i < r->n; i++)
        if (sx_head_is(r->items[i], "Assurance")) {
            sx_free(r->items[i]);
            r->items[i] = dc_form("Assurance", dc_form("Policy", dc_sym("M4-Estimates"), NULL),
                                  dc_form("Replayed", dc_sym("False"), NULL),
                                  dc_form("Ground", dc_sym(dc_ground_name(GROUND_STATISTICAL)), NULL), NULL);
        }
    Sx *ests = dc_form("Estimates", NULL);
    for (int k = 0; k < 2; k++) {
        const Sx *e = sx_find(pr[k], "Estimate", 1);
        sx_push(ests, dc_form("Premise", dc_sym(m->der[dd[k]].name), e ? sx_copy(e) : dc_sym("None"), NULL));
    }
    sx_push(r, ests);
    return r;
}
