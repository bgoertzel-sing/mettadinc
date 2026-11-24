/* Arbitrary-precision exact rationals for the stochastic paths (D1, see
 * docs/RATIONALS.md).  A DcQ is either small (b == NULL: n/d in int64,
 * d > 0, gcd 1, exactly like DcRat) or big (b != NULL: sign and magnitude
 * live in b; n holds the sign as -1/0/+1 and d = 1 so sign tests written
 * as q.n < 0 keep working).  Values are immutable; big storage comes from
 * a per-request arena (dc_q_arena_reset), so struct copies and memcpy are
 * safe.  No valid input overflows: the only failure is the arena memory
 * cap, reported through *ovf = 2 ("memory limit"), never a wrong value. */
#ifndef DCALC_QRAT_H
#define DCALC_QRAT_H
#include <stdint.h>
#include <stddef.h>
#include "rat.h"
typedef struct DcQBig DcQBig;
typedef struct { int64_t n, d; const DcQBig *b; } DcQ;
DcQ dc_q(int64_t n, int64_t d, int *ovf);
DcQ dc_q_from_rat(DcRat a);
/* Back to int64 DcRat; sets *ovf = 1 when the value does not fit. */
DcRat dc_q_to_rat(DcQ a, int *ovf);
DcQ dc_q_add(DcQ a, DcQ b, int *ovf);
DcQ dc_q_sub(DcQ a, DcQ b, int *ovf);
DcQ dc_q_mul(DcQ a, DcQ b, int *ovf);
DcQ dc_q_div(DcQ a, DcQ b, int *ovf);
int dc_q_cmp(DcQ a, DcQ b);           /* -1, 0, 1 */
int dc_q_sign(DcQ a);                 /* -1, 0, 1 */
DcQ dc_q_max(DcQ a, DcQ b);
DcQ dc_q_min(DcQ a, DcQ b);
DcQ dc_q_abs(DcQ a);
int dc_q_is_zero(DcQ a);
int dc_q_is_big(DcQ a);
/* "p/q" or "p", any length.  Returns a pointer into buf when it fits in n
 * bytes, otherwise a pointer into arena storage (valid until reset). */
const char *dc_q_str(DcQ a, char *buf, size_t n);
int dc_q_parse(const char *s, DcQ *out);  /* "p", "p/q", "-p/q", any length */
/* Arena: reset frees every big value; mark/release frees those made after
 * the mark.  dc_q_arena_cap sets the byte cap (default 1 GiB). */
void dc_q_arena_reset(void);
size_t dc_q_arena_mark(void);
void dc_q_arena_release(size_t mark);
void dc_q_arena_cap(size_t bytes);
size_t dc_q_arena_peak(void);
/* Test hook: nonzero forces every result through the big path. */
extern int dc_q_force_big;
#endif
