/* M4-estimates: frozen Stream reader and the Estimates library math.
 * A Stream is read only from bytes whose sha256 equals the declared digest:
 * a changed receipt stream yields no Estimated value (InvalidInput). */
#ifndef DCALC_ESTIMATES_H
#define DCALC_ESTIMATES_H
#include <stddef.h>
#include <stdint.h>
#define DC_STREAM_MAXCOL 16
typedef struct {
    int ncol;
    char col[DC_STREAM_MAXCOL][64];
    size_t nrows;
    char **cell;            /* nrows*ncol cells, row-major: number literal or string text */
    char digest[65];        /* sha256 hex of the bytes read */
} DcStream;
/* 0 ok; else err says why.  want_digest is "sha256:<hex>" or NULL (no check). */
int dc_stream_load(const char *path, const char *want_digest, DcStream *s, char *err, size_t en);
void dc_stream_free(DcStream *s);
int dc_stream_col(const DcStream *s, const char *name);   /* -1 when absent */

/* ---- Estimates math (doubles; endpoints are reported outward-rounded to
 * dyadic rationals num/2^30 so the reported interval contains the computed one) ---- */
/* log M_n(p) of the uniform-prior binomial mixture (models/cs.py log_mix). */
double dc_cs_logmix(long S, long n, double p);
/* Anytime-valid confidence sequence at level alpha: {p : log M_n(p) < log(1/alpha)}. */
void dc_cs_interval(long S, long n, double alpha, double *lo, double *hi);
/* Hoeffding half-width sqrt(log(2/delta) / (2 m)), m = n (proportion) or floor(n/2) (U-statistic). */
double dc_hoeffding_eps(long m, double delta);
/* Two-sided exact-binomial (Clopper-Pearson) interval at level delta. */
void dc_exact_binom_interval(long S, long n, double delta, double *lo, double *hi);
/* Outward rounding to num/2^30: floor for lo, ceil for hi. */
long long dc_dyadic_floor(double x);
long long dc_dyadic_ceil(double x);
#define DC_DYADIC_DEN (1LL << 30)
/* Pairwise duplicate rate as an exact rational: pairs i<j with equal keys / C(n,2). */
void dc_ustat_dup(const char *const *keys, size_t n, long long *num, long long *den);
/* Seeded sampling: splitmix64; k distinct indices of [0,n) by partial Fisher-Yates. */
uint64_t dc_splitmix64(uint64_t *state);
int dc_sample_indices(uint64_t seed, size_t n, size_t k, size_t *out);
#endif
