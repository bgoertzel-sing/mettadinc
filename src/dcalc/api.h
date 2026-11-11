/* Embedding API: one call evaluates one request against module source text.
 * Used by the dcalc CLI and by the CeTTa native module (dcalc:run).
 * The check order is defined here once:
 *   1. binding validation on the raw source            -> InvalidInput
 *   2. M1 admission (admit.c, registry-driven): a diagnostic -> InvalidInput,
 *      profile or library outside the first release           -> Unsupported
 *   3. M0 admission: construct outside M0 ("[M0]" errors) -> Unsupported
 *                    malformed declaration                -> InvalidInput
 *   4. dc_run: profile gate, then the M0 requests. */
#ifndef DCALC_API_H
#define DCALC_API_H
#include "sexp.h"

/* all: every top-level form of the file; basedir resolves Stream sources.
 * Returns a newly allocated result envelope (never NULL). */
Sx *dc_eval_request(const Sx *all, const char *basedir, const char *module, const Sx *request);

/* Text form: source and request as s-expression text; returns the printed
 * envelope (caller frees). Parse errors give an InvalidInput envelope. */
char *dc_eval_text(const char *source, const char *basedir, const char *module, const char *request);

/* File name used in admission diagnostics (file:line:col); default "input".
 * The pointer is kept, not copied. */
void dc_eval_set_source_name(const char *name);

/* M4 opt-in (default 0): when set, modules whose only first-release gap is
 * Dynamics Stochastic are evaluated by stoch.c instead of answering
 * Unsupported.  The default keeps the release-1 manifest answers. */
void dc_eval_set_beyond_release(int on);
int dc_eval_beyond_release(void);
#endif
