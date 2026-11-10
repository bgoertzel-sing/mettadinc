/* Run context: memoised Derive results, derived machine views and arrows. */
#ifndef DCALC_OPS_RUN_H
#define DCALC_OPS_RUN_H
#include "ops_internal.h"

#define DC_MAX_DERIVE 32

struct DcRun {
    DcModule *m;
    Sx *memo[DC_MAX_DERIVE];        /* result envelope of Derive i */
    int busy[DC_MAX_DERIVE];        /* cycle guard */
    int has_view[DC_MAX_DERIVE];    /* Derive i produced a quotient machine */
    DcView view[DC_MAX_DERIVE];
    int arrow_kind[DC_MAX_DERIVE];  /* 0 none, 1 abstraction arrow, 2 checked map, 3 composed */
    DcArrow arrow[DC_MAX_DERIVE];
};

/* Evaluate Derive slot once (memoised); returns the borrowed envelope. */
const Sx *dc_run_derive(DcRun *r, int slot);
int dc_declared_unsupported(const DcModule *m, const char *name);
Sx *dc_claim_of(const Sx *q, const char *equality);
Sx *dc_req_measure_now(DcRun *r, const Sx *q);
Sx *dc_req_check_updates(DcRun *r, const Sx *q);
Sx *dc_req_check_now(DcRun *r, const Sx *q);
Sx *dc_req_induce_exact(DcRun *r, const Sx *q, int derive_slot);
Sx *dc_req_check_abs(DcRun *r, const Sx *q, int derive_slot);
Sx *dc_req_then(DcRun *r, const Sx *q, int derive_slot);
/* M2 graded requests (ops_graded.c). */
int dc_repr_graded(const DcModule *m, int ri);
Sx *dc_req_graded(DcRun *r, const Sx *q, const char *head);
#endif
