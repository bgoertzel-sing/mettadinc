/* M4-estimates: frozen Stream reader and the Estimates library math.
 * See estimates.h.  The reader accepts exactly the bundle's stream shape:
 * {"schema":[names...], "provenance":{...}, "rows":[[cell...]...]} where a
 * cell is a JSON number or string.  Anything else is refused with a reason. */
#include "estimates.h"
#include "model.h"
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *p, *e; } J;
static void ws(J *j) { while (j->p < j->e && isspace((unsigned char)*j->p)) j->p++; }
static int lit(J *j, char c) { ws(j); if (j->p < j->e && *j->p == c) { j->p++; return 1; } return 0; }
/* a JSON string into dst (escapes kept verbatim except \" and \\) */
static int jstr(J *j, char *dst, size_t dn) {
    ws(j); if (j->p >= j->e || *j->p != '"') return -1;
    j->p++; size_t k = 0;
    while (j->p < j->e && *j->p != '"') {
        char c = *j->p++;
        if (c == '\\') { if (j->p >= j->e) return -1; c = *j->p++; if (c != '"' && c != '\\' && c != '/') return -1; }
        if (k + 1 >= dn) return -1;
        dst[k++] = c;
    }
    if (j->p >= j->e) return -1;
    j->p++; dst[k] = 0; return 0;
}
static int jnum(J *j, char *dst, size_t dn) {
    ws(j); const char *s = j->p;
    if (j->p < j->e && *j->p == '-') j->p++;
    while (j->p < j->e && (isdigit((unsigned char)*j->p) || *j->p == '.' || *j->p == 'e' || *j->p == 'E' || *j->p == '+' || *j->p == '-')) j->p++;
    size_t n = (size_t)(j->p - s);
    if (!n || n >= dn) return -1;
    memcpy(dst, s, n); dst[n] = 0; return 0;
}
static int jskip(J *j, int depth) {
    char tmp[256];
    if (depth > 32) return -1;
    ws(j); if (j->p >= j->e) return -1;
    char c = *j->p;
    if (c == '"') { /* long strings: scan */ j->p++; while (j->p < j->e && *j->p != '"') { if (*j->p == '\\') j->p++; j->p++; } if (j->p >= j->e) return -1; j->p++; return 0; }
    if (c == '{' || c == '[') {
        char close = c == '{' ? '}' : ']'; j->p++;
        if (lit(j, close)) return 0;
        do {
            if (c == '{') { if (jskip(j, depth + 1) || !lit(j, ':')) return -1; }
            if (jskip(j, depth + 1)) return -1;
        } while (lit(j, ','));
        return lit(j, close) ? 0 : -1;
    }
    if (!strncmp(j->p, "true", 4) && j->e - j->p >= 4) { j->p += 4; return 0; }
    if (!strncmp(j->p, "false", 5) && j->e - j->p >= 5) { j->p += 5; return 0; }
    if (!strncmp(j->p, "null", 4) && j->e - j->p >= 4) { j->p += 4; return 0; }
    return jnum(j, tmp, sizeof tmp);
}

static char *dupstr(const char *s) {   /* strdup is not C11 */
    size_t n = strlen(s) + 1; char *d = malloc(n);
    if (d) memcpy(d, s, n);
    return d;
}
static int fail(char *err, size_t en, const char *why) { snprintf(err, en, "%s", why); return -1; }

int dc_stream_load(const char *path, const char *want_digest, DcStream *s, char *err, size_t en) {
    memset(s, 0, sizeof *s);
    FILE *f = fopen(path, "rb");
    if (!f) return fail(err, en, "stream source cannot be read");
    fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
    if (len < 0 || len > (64L << 20)) { fclose(f); return fail(err, en, "stream source too large (limit 64 MiB)"); }
    char *buf = malloc((size_t)len + 1); size_t got = buf ? fread(buf, 1, (size_t)len, f) : 0; fclose(f);
    if (!buf) return fail(err, en, "out of memory");
    buf[got] = 0;
    dc_sha256_hex(buf, got, s->digest);
    /* the same bytes are hashed and parsed: no window between check and read */
    if (want_digest && (strncmp(want_digest, "sha256:", 7) || strcmp(want_digest + 7, s->digest))) {
        free(buf); snprintf(err, en, "stream bytes have sha256 %s, not the declared digest", s->digest); return -1;
    }
    J j = { buf, buf + got }; char key[64]; size_t cap = 0; int rc = -1;
    if (!lit(&j, '{')) { fail(err, en, "stream is not a JSON object"); goto out; }
    int have_schema = 0, have_rows = 0;
    do {
        if (jstr(&j, key, sizeof key) || !lit(&j, ':')) { fail(err, en, "stream: bad object key"); goto out; }
        if (!strcmp(key, "schema")) {
            if (!lit(&j, '[')) { fail(err, en, "stream: schema is not an array"); goto out; }
            if (!lit(&j, ']')) {
                do {
                    if (s->ncol == DC_STREAM_MAXCOL) { fail(err, en, "stream: too many columns (limit 16)"); goto out; }
                    if (jstr(&j, s->col[s->ncol], 64)) { fail(err, en, "stream: schema entry is not a short string"); goto out; }
                    s->ncol++;
                } while (lit(&j, ','));
                if (!lit(&j, ']')) { fail(err, en, "stream: schema not closed"); goto out; }
            }
            have_schema = 1;
        } else if (!strcmp(key, "rows")) {
            if (!have_schema) { fail(err, en, "stream: rows before schema"); goto out; }
            if (!lit(&j, '[')) { fail(err, en, "stream: rows is not an array"); goto out; }
            if (!lit(&j, ']')) {
                do {
                    if (!lit(&j, '[')) { fail(err, en, "stream: a row is not an array"); goto out; }
                    if ((s->nrows + 1) * (size_t)s->ncol > cap) {
                        size_t nc = cap ? cap * 2 : 1024; char **nn = realloc(s->cell, nc * sizeof *nn);
                        if (!nn) { fail(err, en, "out of memory"); goto out; }
                        memset(nn + cap, 0, (nc - cap) * sizeof *nn);
                        s->cell = nn; cap = nc;
                    }
                    for (int c = 0; c < s->ncol; c++) {
                        char v[128];
                        if (c && !lit(&j, ',')) { s->nrows++; fail(err, en, "stream: a row is shorter than the schema"); goto out; }
                        ws(&j);
                        if ((*j.p == '"' ? jstr(&j, v, sizeof v) : jnum(&j, v, sizeof v))) { s->nrows++; fail(err, en, "stream: a cell is not a number or short string"); goto out; }
                        if (!(s->cell[s->nrows * (size_t)s->ncol + (size_t)c] = dupstr(v))) { s->nrows++; fail(err, en, "out of memory"); goto out; }
                    }
                    if (!lit(&j, ']')) { s->nrows++; fail(err, en, "stream: a row is longer than the schema"); goto out; }
                    s->nrows++;
                } while (lit(&j, ','));
                if (!lit(&j, ']')) { fail(err, en, "stream: rows not closed"); goto out; }
            }
            have_rows = 1;
        } else if (jskip(&j, 0)) { fail(err, en, "stream: malformed value"); goto out; }
    } while (lit(&j, ','));
    if (!lit(&j, '}')) { fail(err, en, "stream: object not closed"); goto out; }
    ws(&j); if (j.p != j.e) { fail(err, en, "stream: trailing bytes"); goto out; }
    if (!have_schema || !have_rows) { fail(err, en, "stream: schema or rows missing"); goto out; }
    rc = 0;
out:
    free(buf);
    if (rc) dc_stream_free(s);
    return rc;
}

void dc_stream_free(DcStream *s) {
    if (s->cell) for (size_t k = 0; k < s->nrows * (size_t)s->ncol; k++) free(s->cell[k]);
    free(s->cell);
    char keep[65]; memcpy(keep, s->digest, sizeof keep);
    memset(s, 0, sizeof *s); memcpy(s->digest, keep, sizeof keep);
}

int dc_stream_col(const DcStream *s, const char *name) {
    for (int c = 0; c < s->ncol; c++) if (!strcmp(s->col[c], name)) return c;
    return -1;
}

/* ---------------- Estimates math ---------------- */
static double lbeta(double a, double b) { return lgamma(a) + lgamma(b) - lgamma(a + b); }

double dc_cs_logmix(long S, long n, double p) {
    if (p <= 0) return S == 0 ? 0.0 : INFINITY;
    if (p >= 1) return S == n ? 0.0 : INFINITY;
    return lbeta(S + 1.0, n - S + 1.0) - S * log(p) - (n - S) * log1p(-p);
}

/* bisection as models/cs.py cs_interval (200 iterations; doubles converge long before) */
void dc_cs_interval(long S, long n, double alpha, double *lo, double *hi) {
    double thr = log(1.0 / alpha), phat = n ? (double)S / n : 0.5;
    *lo = 0.0; *hi = 1.0;
    if (S > 0) {
        double a = 0.0, b = phat;
        for (int i = 0; i < 200; i++) { double m = (a + b) / 2; if (dc_cs_logmix(S, n, m) >= thr) a = m; else b = m; }
        *lo = a;
    }
    if (S < n) {
        double a = phat, b = 1.0;
        for (int i = 0; i < 200; i++) { double m = (a + b) / 2; if (dc_cs_logmix(S, n, m) >= thr) b = m; else a = m; }
        *hi = b;
    }
}

double dc_hoeffding_eps(long m, double delta) {
    if (m <= 0) return INFINITY;
    return sqrt(log(2.0 / delta) / (2.0 * (double)m));
}

/* P(X <= S) for X ~ Bin(n, p), summed in log space */
static double binom_cdf(long S, long n, double p) {
    if (p <= 0) return 1.0;
    if (p >= 1) return S >= n ? 1.0 : 0.0;
    double lp = log(p), lq = log1p(-p), acc = 0.0;
    double lc = lgamma(n + 1.0);
    for (long k = 0; k <= S; k++) acc += exp(lc - lgamma(k + 1.0) - lgamma(n - k + 1.0) + k * lp + (n - k) * lq);
    return acc > 1.0 ? 1.0 : acc;
}

void dc_exact_binom_interval(long S, long n, double delta, double *lo, double *hi) {
    *lo = 0.0; *hi = 1.0;
    if (S > 0) {   /* lo: P(X >= S; lo) = delta/2, i.e. 1 - cdf(S-1) = delta/2 */
        double a = 0.0, b = (double)S / n;
        for (int i = 0; i < 100; i++) { double m = (a + b) / 2; if (1.0 - binom_cdf(S - 1, n, m) < delta / 2) a = m; else b = m; }
        *lo = a;
    }
    if (S < n) {   /* hi: cdf(S; hi) = delta/2 */
        double a = (double)S / n, b = 1.0;
        for (int i = 0; i < 100; i++) { double m = (a + b) / 2; if (binom_cdf(S, n, m) < delta / 2) b = m; else a = m; }
        *hi = b;
    }
}

long long dc_dyadic_floor(double x) {
    if (x <= 0) return 0;
    if (x >= 1) return DC_DYADIC_DEN;
    long long v = (long long)floor(x * (double)DC_DYADIC_DEN);
    return v > 0 ? v - 1 : 0;           /* one extra ulp of slack for double error */
}
long long dc_dyadic_ceil(double x) {
    if (x <= 0) return 0;
    if (x >= 1) return DC_DYADIC_DEN;
    long long v = (long long)ceil(x * (double)DC_DYADIC_DEN) + 1;
    return v < DC_DYADIC_DEN ? v : DC_DYADIC_DEN;
}

static int cmpstr(const void *a, const void *b) { return strcmp(*(const char *const *)a, *(const char *const *)b); }
void dc_ustat_dup(const char *const *keys, size_t n, long long *num, long long *den) {
    *num = 0; *den = n >= 2 ? (long long)n * (long long)(n - 1) / 2 : 0;
    if (n < 2) return;
    const char **s = malloc(n * sizeof *s);
    if (!s) { *den = 0; return; }
    memcpy(s, keys, n * sizeof *s);
    qsort(s, n, sizeof *s, cmpstr);
    for (size_t i = 0; i < n;) {        /* a run of r equal keys gives C(r,2) pairs */
        size_t j = i; while (j < n && !strcmp(s[i], s[j])) j++;
        long long r = (long long)(j - i); *num += r * (r - 1) / 2; i = j;
    }
    free(s);
}

uint64_t dc_splitmix64(uint64_t *st) {
    uint64_t z = (*st += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}
int dc_sample_indices(uint64_t seed, size_t n, size_t k, size_t *out) {
    if (k > n) return -1;
    size_t *perm = malloc((n ? n : 1) * sizeof *perm);
    if (!perm) return -1;
    for (size_t i = 0; i < n; i++) perm[i] = i;
    uint64_t st = seed;
    for (size_t i = 0; i < k; i++) {    /* rejection-free modulo bias is < 2^-40 for n < 2^24; recorded */
        size_t j = i + (size_t)(dc_splitmix64(&st) % (uint64_t)(n - i));
        size_t tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp; out[i] = perm[i];
    }
    free(perm); return 0;
}
