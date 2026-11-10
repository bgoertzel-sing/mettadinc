/* Exact rationals with overflow detection (see rat.h). */
#include "rat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

typedef __int128 i128;
static i128 gcd128(i128 a, i128 b) { if (a < 0) a = -a; if (b < 0) b = -b; while (b) { i128 t = a % b; a = b; b = t; } return a; }
static DcRat norm(i128 n, i128 d, int *ovf) {
    DcRat r = {0, 1};
    if (d == 0) { *ovf = 1; return r; }
    if (d < 0) { n = -n; d = -d; }
    i128 g = gcd128(n, d); if (g > 1) { n /= g; d /= g; }
    if (n > INT64_MAX || n < -INT64_MAX || d > INT64_MAX) { *ovf = 1; return r; }
    r.n = (int64_t)n; r.d = (int64_t)d; return r;
}
DcRat dc_rat(int64_t n, int64_t d, int *ovf) { return norm(n, d, ovf); }
DcRat dc_rat_add(DcRat a, DcRat b, int *ovf) { return norm((i128)a.n * b.d + (i128)b.n * a.d, (i128)a.d * b.d, ovf); }
DcRat dc_rat_sub(DcRat a, DcRat b, int *ovf) { return norm((i128)a.n * b.d - (i128)b.n * a.d, (i128)a.d * b.d, ovf); }
DcRat dc_rat_mul(DcRat a, DcRat b, int *ovf) { return norm((i128)a.n * b.n, (i128)a.d * b.d, ovf); }
DcRat dc_rat_div(DcRat a, DcRat b, int *ovf) { return norm((i128)a.n * b.d, (i128)a.d * b.n, ovf); }
int dc_rat_cmp(DcRat a, DcRat b) { i128 l = (i128)a.n * b.d, r = (i128)b.n * a.d; return l < r ? -1 : l > r; }
DcRat dc_rat_max(DcRat a, DcRat b) { return dc_rat_cmp(a, b) >= 0 ? a : b; }
DcRat dc_rat_min(DcRat a, DcRat b) { return dc_rat_cmp(a, b) <= 0 ? a : b; }
DcRat dc_rat_abs(DcRat a) { if (a.n < 0) a.n = -a.n; return a; }
int dc_rat_is_zero(DcRat a) { return a.n == 0; }
void dc_rat_str(DcRat a, char *buf, size_t n) {
    if (a.d == 1) snprintf(buf, n, "%lld", (long long)a.n);
    else snprintf(buf, n, "%lld/%lld", (long long)a.n, (long long)a.d);
}
int dc_rat_parse(const char *s, DcRat *out) {
    char *e; errno = 0;
    long long p = strtoll(s, &e, 10), q = 1;
    if (e == s || errno) return -1;
    if (*e == '/') { const char *t = e + 1; q = strtoll(t, &e, 10); if (e == t || errno || q <= 0) return -1; }
    if (*e) return -1;
    int ovf = 0; *out = norm(p, q, &ovf); return ovf ? -1 : 0;
}
