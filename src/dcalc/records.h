/* Boundaries 2, 4, 5 and 6: records and rules that M0 fixes so later
 * milestones build on them (MILESTONES.md, M0 section).
 *   2. assurance grounds: the one policy maps (verdict, ground, assumptions)
 *      to a status (dc_assure_grounded; dc_assure is its M0 special case);
 *   4. result types for goal adequacy and the meaning-preservation obligation;
 *   5. the Estimate record carried by empirical results;
 *   6. the PolicyTreeWitness format with its admissibility check, and the
 *      distance-interval rule (Unknown when Precision-0 certificates do not meet). */
#ifndef DCALC_RECORDS_H
#define DCALC_RECORDS_H
#include "ops_internal.h"

/* ---- 2. assurance grounds ---- */
typedef enum { GROUND_NONE, GROUND_EXACT, GROUND_REPLAYED, GROUND_WITNESS, GROUND_STATISTICAL } DcGround;
const char *dc_ground_name(DcGround g);
/* Checked only on Exact|Replayed, Refuted only on Witness, Estimated only on
 * Statistical; any assumption (unreplayed backend, declared assumption,
 * Estimated or Conditional premise) makes a holding/failing verdict Conditional. */
DcStatus dc_assure_grounded(DcVerdict v, DcGround g, int n_assumptions);

/* ---- 4. goal adequacy result types ---- */
typedef enum { RT_INFORMATIONAL_REFINEMENT, RT_INFORMATIONAL_EQUIVALENCE, RT_MEANING_PRESERVATION } DcGoalResult;
const char *dc_goal_result_name(DcGoalResult r);
/* A goal change is a renaming only when informational equivalence AND
 * meaning preservation (declared, protected decoders) both hold. */
int dc_goal_change_is_renaming(int equivalence_holds, int meaning_preserved);

/* ---- 5. Estimate record ---- */
typedef struct {
    char population[160], selection[160], policy_version[96], estimand[160];
    int selection_depends_on_policy;
    /* M4-estimates: the rest of the registry envelope (result_envelope.Estimate).
     * Optional in a declared Estimate; required (dc_estimate_complete) on an
     * Estimated result.  Rationals are kept as canonical text, e.g. (Rat 1 100). */
    char estimator[96], protocol[256], dependence[160], combination[128];
    char eps[64], delta[64];
    long long sample_size;                /* -1 when absent */
} DcEstimate;
/* 1 when all ten envelope fields are present (else why names the first missing). */
int dc_estimate_complete(const DcEstimate *e, char *why, size_t wn);
/* Parse (Estimate (Population ..) (Selection ..) (PolicyVersion ..) (Estimand ..)
 * [(SelectionDependsOnPolicy True)]).  0 ok; else err names the missing field. */
int dc_estimate_parse(const Sx *x, DcEstimate *e, char *err, size_t en);
Sx *dc_estimate_sx(const DcEstimate *e);
/* Transport after a policy change: 1 passes (declared argument), 0 blocked
 * (selection rule depends on the policy) or needs a new estimation task. */
int dc_estimate_transport(const DcEstimate *e, const char *new_policy, int declared_argument);

/* ---- 6. witness forms ---- */
/* PolicyTreeWitness admissibility: (PolicyTreeWitness (Pair x y) (Tree node...)
 * (Event ..) (Left p) (Right q)); node = (Node (History y0 a1 y1 ...) (Act a)|(Law ...)).
 * Checks: root keyed by one observation, every other key extends its parent's
 * key by one action and one observation, every node names an action or a law,
 * keys unique.  Returns 1 admissible; else 0 with why naming the field. */
int dc_policy_tree_admissible(const Sx *w, char *why, size_t wn);
/* Distance interval rule: lo/hi are the bounds certified by registered lower
 * and upper certificates (has_lo/has_hi).  Precision 0: Checked iff both exist
 * and meet, else Unknown.  Precision p > 0: Checked iff hi - lo <= p. */
DcStatus dc_distance_status(int has_lo, double lo, int has_hi, double hi, double precision);
/* ---- 2b. assumptions, agreed_by evidence and Accepts declarations ---- */
/* One assumption is (TrustedBackend solver version logic obligation-digest),
 * (Assumption name digest) or (EstimatedPremise result-digest delta).
 * Returns 1 when well formed; else 0 with why naming the field. */
int dc_assumption_wellformed(const Sx *a, char *why, size_t wn);
/* (Assumptions a...) of a result envelope, or NULL. */
const Sx *dc_result_assumptions(const Sx *envelope);
/* Union: append to dst (Assumptions ...) every assumption of src that dst
 * lacks (structural equality).  Derived results call this once per premise. */
void dc_assumptions_union(Sx *dst, const Sx *src);
/* (AgreedBy (Backend solver version)...): evidence only, never a ground. */
Sx *dc_agreed_by(const char *const *solver, const char *const *version, size_t n);
/* A consumer's (Accepts Checked [(Conditional (TrustedBackend solver))...]). */
#define DC_ACCEPTS_MAX 8
typedef struct {
    int checked;                          /* lists Checked */
    int estimated;                        /* lists Estimated (empirical consumer) */
    size_t nbackend;                      /* Conditional on these solvers */
    char backend[DC_ACCEPTS_MAX][64];
    size_t nassume;                       /* Conditional on these declared assumptions */
    char assume[DC_ACCEPTS_MAX][64];
} DcAccepts;
/* 0 ok; else -1 with why naming the field. */
int dc_accepts_parse(const Sx *x, DcAccepts *a, char *why, size_t wn);
/* 1 when the consumer accepts a result (registry assurance.accepts):
 * Checked iff it lists Checked; Estimated iff it lists Estimated (inv 17:
 * an Estimated result is never accepted as Checked); Conditional iff every
 * undischarged assumption is covered: TrustedBackend by a listed solver (any
 * version), (Assumption name ..) by a listed name, (EstimatedPremise ..) only
 * when Estimated is listed.  Every other status is not accepted. */
int dc_accepts_result(const DcAccepts *a, DcStatus st, const Sx *assumptions);
/* Gate: number of results the consumer does not accept (inadequate coverage). */
size_t dc_gate_inadequate(const DcAccepts *a, const DcStatus *st,
                          const Sx *const *assumptions, size_t n);
#endif
