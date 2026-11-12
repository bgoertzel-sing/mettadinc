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
                                  dc_form("Replayed", dc_sym("True"), NULL),
                                  dc_form("Ground", dc_sym(dc_ground_name(GROUND_STATISTICAL)), NULL), NULL);
        }
    sx_push(r, estimate);
    return r;
}

Sx *dc_req_estimates(DcRun *run, const Sx *q, const char *head) {
    DcModule *m = run->m;
    const Sx *on = arg(q, "On");
    if (!on || on->kind == SX_LIST) return dc_invalid(m, "%s: field On must name a Stream", head);
    const char *sn = on->text; const Sx *d = decl_stream(m, sn);
    if (!d) return dc_invalid(m, "%s: On %s names no declared Stream", head, sn);
    const char *src = fld(d, "Source"), *dig = fld(d, "Digest");
    if (!src || !dig) return dc_invalid(m, "%s: Stream %s needs (Source path) and (Digest sha256:..)", head, sn);
    const Sx *lv = arg(q, "Level"); DcRat L;
    if (!lv || dc_sx_rat(lv, &L) || L.n <= 0 || L.n >= L.d) return dc_invalid(m, "%s: field Level is not a rational in (0,1)", head);
    int cmp = !strcmp(head, "CompareRates");   /* paired rows: share of discordant rows with First only */
    const Sx *eq = arg(q, "Equals"), *col = arg(q, cmp ? "First" : "Column"), *col2 = cmp ? arg(q, "Second") : NULL;
    if (!eq || eq->kind == SX_LIST) return dc_invalid(m, "%s: field Equals must be a number or string", head);
    if (!col || col->kind == SX_LIST) return dc_invalid(m, "%s: field %s must name a column", head, cmp ? "First" : "Column");
    if (cmp && (!col2 || col2->kind == SX_LIST)) return dc_invalid(m, "%s: field Second must name a column", head);
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
    long rows = (long)s.nrows, n = rows, S = 0;
    if (cmp) {
        long a = 0, b = 0;
        for (long i = 0; i < rows; i++) {
            int x = !strcmp(s.cell[(size_t)i * (size_t)s.ncol + (size_t)k], eq->text);
            int y = !strcmp(s.cell[(size_t)i * (size_t)s.ncol + (size_t)k2], eq->text);
            a += x && !y; b += !x && y;
        }
        S = a; n = a + b;
    } else
        for (long i = 0; i < n; i++) S += !strcmp(s.cell[(size_t)i * (size_t)s.ncol + (size_t)k], eq->text);
    double lo, hi; dc_cs_interval(S, n, (double)L.n / (double)L.d, &lo, &hi);
    long long loD = dc_dyadic_floor(lo), hiD = dc_dyadic_ceil(hi);
    char estimand[256], proto[256];
    if (cmp) snprintf(estimand, sizeof estimand, "share, among rows of %s where exactly one of %s, %s equals %s, of those where it is %s", sn, col->text, col2->text, eq->text, col->text);
    else snprintf(estimand, sizeof estimand, "rate of rows of %s with %s = %s", sn, col->text, eq->text);
    snprintf(proto, sizeof proto, "every row of frozen stream %s, %s, read once; anytime-valid, so optional stopping is allowed", sn, dig);
    const char *dep = fld(d, "SelectionDependsOnPolicy");
    Sx *estimate = dc_form("Estimate", dc_form("Estimand", sx_str(estimand), NULL),
        dc_form("Population", sx_str(fld(d, "Population") ? fld(d, "Population") : "undeclared"), NULL),
        dc_form("Selection", sx_str(fld(d, "Selection") ? fld(d, "Selection") : "undeclared"), NULL),
        dc_form("Policy", sx_str(fld(d, "Policy") ? fld(d, "Policy") : "undeclared"), NULL),
        dc_form("Estimator", sx_str("confidence sequence of the uniform-prior (Beta(1,1)) binomial mixture"), NULL),
        dc_form("Protocol", sx_str(proto), NULL),
        dc_form("SampleSize", dc_int(n), NULL),
        dc_form("Error", rat_sx(hiD - loD, 2 * DC_DYADIC_DEN), sx_copy(lv), NULL),
        dc_form("Dependence", sx_str("rows independent Bernoulli with a common rate (declared, not checked)"), NULL),
        dc_form("Combination", sx_str("single estimate; derived results carry (EstimatedPremise digest delta) and deltas add"), NULL),
        dc_form("SelectionDependsOnPolicy", dc_sym(dep && !strcmp(dep, "True") ? "True" : "False"), NULL), NULL);
    Sx *inner = cmp ? dc_form("PairedComparison", dc_form("FirstOnly", dc_int(S), NULL), dc_form("SecondOnly", dc_int(n - S), NULL), NULL)
                    : dc_form("RateEstimate", dc_form("Count", dc_int(S), NULL), dc_form("Observations", dc_int(n), NULL), NULL);
    sx_push(inner, dc_form("Lower", rat_sx(loD, DC_DYADIC_DEN), NULL));
    sx_push(inner, dc_form("Upper", rat_sx(hiD, DC_DYADIC_DEN), NULL));
    sx_push(inner, dc_form("Estimand", sx_str(estimand), NULL));
    sx_push(inner, dc_form("Procedure", dc_form("ConfidenceSequence", dc_sym("BinomialMixture"), dc_form("Prior", dc_sym("Beta"), dc_int(1), dc_int(1), NULL),
                                                dc_form("Level", sx_copy(lv), NULL), dc_form("Rounding", dc_sym("OutwardDyadic30"), NULL), NULL), NULL));
    sx_push(inner, dc_form("Assumptions", dc_sym(cmp ? "DiscordantRowsIndependentCommonShare" : "RowsIndependentCommonRate"), NULL));
    Sx *val = dc_form("Value", inner, NULL);
    Sx *ev = dc_form("Evidence", dc_form("Sample", dc_form("Stream", dc_sym(sn), NULL), dc_form("Digest", sx_str(dig), NULL),
        dc_form("Rows", dc_int(rows), NULL), dc_form("Events", dc_int(S), NULL), NULL), NULL);
    dc_stream_free(&s);
    return est_env(m, q, sn, val, ev, estimate);
}
