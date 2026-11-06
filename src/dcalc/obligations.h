/* Obligation generator interface (boundary 3).
 * A request that makes an exactness claim is reduced to an ordered list of
 * obligations; each obligation is checked exhaustively over pairs of states
 * and either holds or yields its least witness (witness order: pairs in
 * lexicographic carrier order, then observations / actions in declaration
 * order).  The mutation harness (tests/dcalc) perturbs one table entry of a
 * module and checks that some obligation flips. */
#ifndef DCALC_OBLIGATIONS_H
#define DCALC_OBLIGATIONS_H
#include "model.h"

typedef enum { OBL_CURRENT = 0, OBL_UPDATE = 1, OBL_CONGRUENCE = 2 } DcOblKind;
const char *dc_obl_name(DcOblKind k);

/* The obligations an InduceExact claim generates, in check order. */
size_t dc_obligations_for_induce(DcOblKind out[3]);

/* Check one obligation for representation ri.  Current and Update compare
 * codes under the representation's code tolerance; Congruence always
 * compares codes literally.  Returns 1 when it holds, 0 when it fails (then
 * *wit receives the least witness, owned by the caller). */
int dc_obligation(const DcModule *m, int ri, DcOblKind k, Sx **wit);

/* Replay a witness against the module directly (no search): 1 if the
 * witness exhibits a real failure of obligation k for representation ri. */
int dc_obligation_replay(const DcModule *m, int ri, DcOblKind k, const Sx *wit);
#endif
