/* Exact rationals for the M2 graded core.  num/den in int64 with den > 0
 * and gcd(num,den) = 1.  Every operation reports overflow through *ovf
 * (set to 1, never cleared) instead of wrapping: a caller that sees it
 * answers Unsupported naming the limit, never a silently wrong value. */
#ifndef DCALC_RAT_H
#define DCALC_RAT_H
#include <stdint.h>
#include <stddef.h>
typedef struct { int64_t n, d; } DcRat;
DcRat dc_rat(int64_t n, int64_t d, int *ovf);
DcRat dc_rat_add(DcRat a, DcRat b, int *ovf);
DcRat dc_rat_sub(DcRat a, DcRat b, int *ovf);
DcRat dc_rat_mul(DcRat a, DcRat b, int *ovf);
DcRat dc_rat_div(DcRat a, DcRat b, int *ovf);
int dc_rat_cmp(DcRat a, DcRat b);           /* -1, 0, 1 */
DcRat dc_rat_max(DcRat a, DcRat b);
DcRat dc_rat_min(DcRat a, DcRat b);
DcRat dc_rat_abs(DcRat a);
int dc_rat_is_zero(DcRat a);
/* "p/q" or "p" (q = 1); the printed form the oracle keys use. */
void dc_rat_str(DcRat a, char *buf, size_t n);
/* Parse "p", "p/q" or "-p/q"; returns 0 on success. */
int dc_rat_parse(const char *s, DcRat *out);
#endif
