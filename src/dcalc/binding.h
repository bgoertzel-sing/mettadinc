/* Boundary 1: binding validation.  Runs on the raw DC.Module source, before
 * admission and before the profile gate, so a binding error is InvalidInput
 * naming the field even on a module whose requests are otherwise outside M0.
 * Rules (negative suite entries 1-3):
 *   Keyed X (Of Store) (Item Stat) [(View V)]: Stat must be a statistic of V,
 *     or, without View, of the Store's item machine            -> field Item
 *   CheckSafety S ... (Via Sim): Sim must be a Simulation whose Target is S
 *                                                               -> field Via
 *   Stream N (Source path) (Digest "sha256:h"): the file's digest must be h
 *                                                               -> field Digest */
#ifndef DCALC_BINDING_H
#define DCALC_BINDING_H
#include "sexp.h"

typedef struct { char name[64]; char reason[320]; } DcBad;

/* Scan declarations; returns the number of bad ones written to out. basedir
 * resolves relative Stream sources (the fixture's directory). */
/* Give the scanner every top-level form of the file (for Import resolution). */
void dc_binding_set_universe(const Sx *all);
int dc_binding_scan(const Sx *module, const char *basedir, DcBad *out, int max);

/* 1 if req (after resolving a Derive name) breaks a binding rule; reason set. */
int dc_binding_request(const Sx *module, const DcBad *bad, int nbad, const Sx *req,
                       char *reason, size_t rn);
/* Boundary 1: the ONE validation routine every consuming operation runs on a
 * premise before using it (Then and transfer composition, safety transfer,
 * lift, rebuild, stream/snapshot reads, gates).  expect is what the operation
 * names; have is the premise's binding.  NULL/negative fields are not checked.
 * Returns 0 when they agree; else -1 with why naming the field
 * ("<op>: field <field>: ..."), which the caller reports as InvalidInput. */
typedef struct {
    const char *module_digest;   /* module the premise was admitted under */
    const char *source_id;       /* source model identity */
    const char *target_id;       /* target model identity */
    int source_carrier, target_carrier;   /* state carriers, -1 unchecked */
    const char *tolerance;       /* checked interface tolerance, NULL = Exact */
} DcBindingRef;
int dc_binding_validate(const char *op, const char *field, const DcBindingRef *expect,
                        const DcBindingRef *have, char *why, size_t wn);
#endif
