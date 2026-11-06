/* Internal interfaces shared by the M0 request implementations. */
#ifndef DCALC_OPS_INTERNAL_H
#define DCALC_OPS_INTERNAL_H
#include "ops.h"

typedef enum { VERDICT_HOLDS, VERDICT_FAILS, VERDICT_UNSUPPORTED, VERDICT_INVALID } DcVerdict;

/* The one assurance policy: verdict + whether the evidence replayed -> status. */
DcStatus dc_assure(DcVerdict v, int evidence_replays);

/* A machine view: a declared machine, or a derived quotient machine whose
 * states are the image of an encoding inside the code carrier. */
#define DC_MAX_PORTS 16
typedef struct {
    char id[160];              /* interface identity, e.g. "Concrete" or "(Output AB Machine)" */
    int states;                /* carrier index of the state set */
    size_t n;                  /* carrier size */
    int *valid;                /* valid[i]: state i is a state of this view */
    size_t nobs, nact;
    char obs_label[DC_MAX_PORTS][DC_MAX_NAME];
    int obs_car[DC_MAX_PORTS];
    int *obs[DC_MAX_PORTS];    /* obs[k][i] index in obs_car[k] (valid i only) */
    char act_label[DC_MAX_PORTS][DC_MAX_NAME];
    int *act[DC_MAX_PORTS];    /* act[k][i] state index (valid i only) */
} DcView;

void dc_view_of_machine(const DcModule *m, int mi, DcView *v);
void dc_view_copy(const DcView *a, DcView *b);
void dc_view_free(DcView *v);

/* Envelope builders (all statuses pass through dc_assure). */
Sx *dc_sym(const char *s);
Sx *dc_int(long v);
Sx *dc_form(const char *head, ...);   /* NULL-terminated children */
Sx *dc_envelope(const DcModule *m, DcVerdict v, int replays, Sx *claim, Sx *subject,
                Sx *value, Sx *evidence, const char *reason);
Sx *dc_invalid(const DcModule *m, const char *fmt, ...);
Sx *dc_unsupported(const DcModule *m, const char *fmt, ...);
/* Boundary 2: union a premise's assumptions into a derived result (ops_core.c). */
void dc_result_add_premise(Sx *res, const Sx *premise, const char *premise_name);
#endif
