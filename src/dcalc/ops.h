/* The M0 requests on enumerated deterministic modules.
 * dc_run evaluates one request against an admitted module and returns the
 * result envelope as an s-expression:
 *   (Result (Status S) (Claim ...) (Binding ...) (Scope ...) (Value ...)
 *           (Evidence ...) (Assumptions ...) (Assurance ...) [(Reason ...)])
 * Every status is assigned by dc_assure (one assurance policy). */
#ifndef DCALC_OPS_H
#define DCALC_OPS_H
#include "model.h"

typedef enum {
    DC_CHECKED, DC_REFUTED, DC_CONDITIONAL, DC_ESTIMATED, DC_UNKNOWN,
    DC_UNSUPPORTED, DC_INVALID_INPUT
} DcStatus;
const char *dc_status_name(DcStatus s);

/* An arrow: a total map between the state carriers of two machines that
 * has been checked to commute with every observation and action. */
typedef struct {
    int src, tgt;          /* machine indices, -1 for a derived machine */
    int src_car, tgt_car;  /* state carriers of source and target */
    int *table;            /* src state index -> tgt state index */
    int surjective;
    int *src_valid, *tgt_valid;     /* review 4 F6: valid states of the source/target views (owned, may be NULL = all) */
    char src_id[160], tgt_id[160];  /* interface identities */
} DcArrow;

/* Per-run context: memoised Derive results. */
typedef struct DcRun DcRun;
DcRun *dc_run_new(DcModule *m);
void dc_run_free(DcRun *r);

/* Evaluate a request form (a list, or a Derive name).  Never crashes on
 * a malformed request: it returns InvalidInput naming the field. */
Sx *dc_run(DcRun *r, const Sx *request);

/* A refusal envelope without a module (admission failures, CLI errors). */
Sx *dc_refusal_text(DcStatus st, const char *field, const char *reason);
/* Admission errors marked "[M0]" are fragment limits (Unsupported); every
 * other admission error is a binding/validation failure (InvalidInput). */
DcStatus dc_admission_status(const char *err);
int dc_is_m0_request(const char *head);

/* Status of a result envelope (DC_INVALID_INPUT if not an envelope). */
DcStatus dc_result_status(const Sx *result);
#endif
