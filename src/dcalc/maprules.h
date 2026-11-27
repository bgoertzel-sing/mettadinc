/* One shared admission loader for the map rules (t-2026-11-26-mettadinc-shared-loader;
 * docs/review/SYSTEM_REVIEW.md s5 step 3, the D1 class of gap).
 * Every loader that admits a map (model.c, ops_nondet.c, stoch.c incl. the Reach reader, ops_m7.c,
 * and the Families elaborator's output path) decides the shared rules here and only here:
 *   R1 totality   every element of the From carrier has a value       (spec 5.4)
 *   R2 duplicate  no element has two cases / Table rows / kernel Rows  (spec 5.4, D1)
 *   R3 codomain   every value lies in the To carrier / To type
 *   R4 mass       a kernel row's masses are nonnegative rationals summing to exactly 1
 * Loaders keep their own message texts; this module returns a rule code and the offending index,
 * so answers stay byte-identical wherever a loader already enforced the rule. */
#ifndef DC_MAPRULES_H
#define DC_MAPRULES_H
#include "qrat.h"

enum { DC_MR_OK = 0, DC_MR_KEY = 1, DC_MR_CODOMAIN = 2, DC_MR_DUP = 3, DC_MR_PARTIAL = 4,
       DC_MR_MASS_NEG = 5, DC_MR_MASS_SUM = 6 };

typedef struct { int n; int *val; int nset; } DcMrTab;   /* val[k] = -1: no value yet */

void dc_mr_init(DcMrTab *t, int n, int *buf);             /* buf has n slots, all set to -1 */
/* R2 + R3 (+ key in From), checked in this order: key < 0 -> DC_MR_KEY, value < 0 -> DC_MR_CODOMAIN,
 * key already set -> DC_MR_DUP (the order model.c's Table loader already used) */
int  dc_mr_put(DcMrTab *t, int key, int value);
/* R2 for a key with no single value (nondet Choice, kernel Row): mark key seen */
int  dc_mr_mark(DcMrTab *t, int key);
/* R3 alone, for one of several values of a key (nondet Choice) */
int  dc_mr_value(int value);
/* R1 for one key, for loaders that report totality per input in loop order */
int  dc_mr_missing(const DcMrTab *t, int key);   /* DC_MR_PARTIAL if key has no value */
/* R1: DC_MR_PARTIAL and *missing = first key with no value, else DC_MR_OK */
int  dc_mr_total(const DcMrTab *t, int *missing);
/* R4 */
int  dc_mr_mass_entry(DcQ w);                             /* DC_MR_MASS_NEG if w < 0 */
int  dc_mr_mass_row(DcQ sum);                             /* DC_MR_MASS_SUM unless sum == 1 */
#endif
