/* AC3: one test group per M0 boundary (docs/e0/MILESTONES.md, M0 section).
 * Links build/dcalc/libdcalc.a.  Prints one line per check; exit 0 iff all pass. */
#include "records.h"
#include "binding.h"
#include "obligations.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int fails, total;
#define CHECK(c, msg) do { total++; if (c) printf("ok   %s\n", msg); else { fails++; printf("FAIL %s\n", msg); } } while (0)

static Sx *parse1(const char *s) {
    const char *e; int l; Sx *all = sx_parse_all(s, &e, &l);
    if (!all || all->n < 1) { fprintf(stderr, "parse error\n"); exit(2); }
    Sx *x = sx_copy(all->items[0]); sx_free(all); return x;
}
static const char *reason_of(const Sx *res) {
    const Sx *r = sx_find(res, "Reason", 1); return r && r->n == 2 ? r->items[1]->text : "";
}

static const char *TINY =
 "(DC.Module Tiny (Profile Crisp)"
 " (Carrier Three (Of Nat) (Enum 0 1 2)) (Carrier Bit (Of Nat) (Enum 0 1))"
 " (Map obs (From Three) (To Bit) (Table (0 0) (1 0) (2 1)))"
 " (Map hop (From Three) (To Three) (Table (0 1) (1 2) (2 2)))"
 " (Map code (From Three) (To Bit) (Table (0 0) (1 0) (2 1)))"
 " (Machine M (States Three) (Observe o obs) (Action h hop))"
 " (Representation R (Of M) (Encode code)))";

static void boundary1_binding(void) {
    /* admission and request binding errors name the field */
    DcModule m; char err[512];
    Sx *bad = parse1("(DC.Module B (Carrier Bit (Of Nat) (Enum 0 1)) (Map f (From Bit) (To Nope) (Table (0 0))))");
    CHECK(dc_admit(bad, &m, err, sizeof err) != 0 && strstr(err, "field To"), "B1 admission: undeclared carrier -> error naming field To");
    sx_free(bad);
    Sx *tiny = parse1(TINY); CHECK(dc_admit(tiny, &m, err, sizeof err) == 0, "B1 admission: Tiny admitted");
    DcRun *r = dc_run_new(&m);
    Sx *q = parse1("(MeasureNow Missing)"); Sx *res = dc_run(r, q);
    CHECK(dc_result_status(res) == DC_INVALID_INPUT && strstr(reason_of(res), "field Representation"), "B1 request: unknown representation -> InvalidInput naming field Representation");
    sx_free(q); sx_free(res);
    q = parse1("(CheckUpdates R (Within -1))"); res = dc_run(r, q);
    CHECK(dc_result_status(res) == DC_INVALID_INPUT && strstr(reason_of(res), "field Within"), "B1 request: negative Within -> InvalidInput naming field Within");
    sx_free(q); sx_free(res);
    q = parse1("(Frobnicate R)"); res = dc_run(r, q);
    CHECK(dc_result_status(res) == DC_UNSUPPORTED, "B1 request: unknown request head -> Unsupported");
    sx_free(q); sx_free(res);
    dc_run_free(r); dc_module_free(&m); sx_free(tiny);
    /* raw-source binding rules */
    Sx *kd = parse1("(DC.Module K (Store S (Of ItemM)) (Statistic St (Of OtherM)) (Keyed X (Of S) (Item St)))");
    DcBad b[4]; int nb = dc_binding_scan(kd, ".", b, 4);
    CHECK(nb == 1 && strstr(b[0].reason, "field Item"), "B1 binding: Keyed statistic of another machine -> field Item");
    sx_free(kd);
    kd = parse1("(DC.Module K (Store S (Of ItemM)) (Statistic St (Of OtherM)) (Keyed X (Of S) (Item St) (View OtherM)))");
    CHECK(dc_binding_scan(kd, ".", b, 4) == 0, "B1 binding: same Keyed with a matching View is accepted");
    sx_free(kd);
    Sx *sm = parse1("(DC.Module S (Simulation Sim (Source A) (Target B)))");
    char why[256]; Sx *rq = parse1("(CheckSafety C (Never x) (Via Sim))");
    CHECK(dc_binding_request(sm, NULL, 0, rq, why, sizeof why) && strstr(why, "field Via"), "B1 binding: CheckSafety Via a simulation of another machine -> field Via");
    sx_free(rq); rq = parse1("(CheckSafety B (Never x) (Via Sim))");
    CHECK(!dc_binding_request(sm, NULL, 0, rq, why, sizeof why), "B1 binding: CheckSafety Via a matching simulation is accepted");
    sx_free(rq); sx_free(sm);
}

static void boundary2_assurance(void) {
    CHECK(dc_assure_grounded(VERDICT_HOLDS, GROUND_EXACT, 0) == DC_CHECKED, "B2 holds+Exact -> Checked");
    CHECK(dc_assure_grounded(VERDICT_HOLDS, GROUND_REPLAYED, 0) == DC_CHECKED, "B2 holds+Replayed -> Checked");
    CHECK(dc_assure_grounded(VERDICT_HOLDS, GROUND_WITNESS, 0) == DC_UNKNOWN, "B2 holds+Witness -> not Checked");
    CHECK(dc_assure_grounded(VERDICT_FAILS, GROUND_WITNESS, 0) == DC_REFUTED, "B2 fails+Witness -> Refuted");
    CHECK(dc_assure_grounded(VERDICT_FAILS, GROUND_EXACT, 0) == DC_UNKNOWN, "B2 fails without a witness -> not Refuted");
    CHECK(dc_assure_grounded(VERDICT_HOLDS, GROUND_STATISTICAL, 0) == DC_ESTIMATED, "B2 Statistical -> Estimated");
    CHECK(dc_assure_grounded(VERDICT_HOLDS, GROUND_STATISTICAL, 1) == DC_CONDITIONAL, "B2 Statistical with an assumption -> Conditional");
    CHECK(dc_assure_grounded(VERDICT_HOLDS, GROUND_REPLAYED, 1) == DC_CONDITIONAL, "B2 assumption (unreplayed backend / premise) -> Conditional");
    CHECK(dc_assure_grounded(VERDICT_HOLDS, GROUND_NONE, 0) == DC_UNKNOWN, "B2 no ground -> Unknown");
    CHECK(dc_assure(VERDICT_HOLDS, 0) == DC_UNKNOWN && dc_assure(VERDICT_HOLDS, 1) == DC_CHECKED, "B2 dc_assure is the M0 case of the same policy");
}

static void boundary3_obligations(void) {
    DcOblKind ks[3]; size_t n = dc_obligations_for_induce(ks);
    CHECK(n == 3 && ks[0] == OBL_CURRENT && ks[1] == OBL_UPDATE && ks[2] == OBL_CONGRUENCE, "B3 InduceExact generates Current, Update, Congruence in order");
    DcModule m; char err[256]; Sx *tiny = parse1(TINY); dc_admit(tiny, &m, err, sizeof err);
    Sx *w = NULL;
    CHECK(dc_obligation(&m, 0, OBL_CURRENT, &w) == 1, "B3 Tiny: Current holds");
    int upd = dc_obligation(&m, 0, OBL_UPDATE, &w);
    CHECK(upd == 0 && w && dc_obligation_replay(&m, 0, OBL_UPDATE, w), "B3 Tiny: Update fails with a witness that replays");
    if (w) {
        char *s = sx_print(w); CHECK(strstr(s, "(Pair 0 1) (Action h)") != NULL, "B3 Tiny: least witness is pair (0,1) under h"); free(s);
        Sx *forged = parse1("(UpdateWitness (Pair 0 2) (Action h) (Codes 0 1) (Left 0) (Right 1))");
        CHECK(!dc_obligation_replay(&m, 0, OBL_UPDATE, forged), "B3 replay refuses a forged witness (pair not sharing a code)");
        sx_free(forged); sx_free(w);
    }
    dc_module_free(&m); sx_free(tiny);
}

static void boundary4_results(void) {
    CHECK(!strcmp(dc_goal_result_name(RT_INFORMATIONAL_REFINEMENT), "InformationalRefinement") &&
          !strcmp(dc_goal_result_name(RT_INFORMATIONAL_EQUIVALENCE), "InformationalEquivalence") &&
          !strcmp(dc_goal_result_name(RT_MEANING_PRESERVATION), "MeaningPreservation"), "B4 goal adequacy result types named");
    CHECK(!dc_goal_change_is_renaming(1, 0), "B4 equivalence without meaning preservation is not a renaming (anti-nag)");
    CHECK(dc_goal_change_is_renaming(1, 1), "B4 equivalence with meaning preservation is a renaming");
}

static void boundary5_estimate(void) {
    DcEstimate e; char err[256];
    Sx *x = parse1("(Estimate (Population replies) (Selection all-replies) (PolicyVersion v1) (Estimand stale-rate))");
    CHECK(dc_estimate_parse(x, &e, err, sizeof err) == 0, "B5 Estimate with the four fields parses"); sx_free(x);
    x = parse1("(Estimate (Population replies) (PolicyVersion v1) (Estimand stale-rate))");
    CHECK(dc_estimate_parse(x, &e, err, sizeof err) != 0 && strstr(err, "field Selection"), "B5 missing Selection -> error naming field Selection"); sx_free(x);
    x = parse1("(Estimate (Population p) (Selection s) (PolicyVersion v1) (Estimand q) (SelectionDependsOnPolicy True))");
    dc_estimate_parse(x, &e, err, sizeof err); sx_free(x);
    CHECK(!dc_estimate_transport(&e, "v2", 1), "B5 policy-dependent selection blocks transport to a new policy");
    e.selection_depends_on_policy = 0;
    CHECK(dc_estimate_transport(&e, "v2", 1) && !dc_estimate_transport(&e, "v2", 0), "B5 otherwise transport needs a declared argument");
}

static void boundary6_witnesses(void) {
    char why[256];
    Sx *ok = parse1("(PolicyTreeWitness (Pair x y) (Tree (Node (History y0) (Act a)) (Node (History y0 a y1) (Law (Rat 1 2))))"
                    " (Event (Shows z True)) (Left (Rat 1 2)) (Right 0))");
    CHECK(dc_policy_tree_admissible(ok, why, sizeof why), "B6 admissible PolicyTreeWitness accepted"); sx_free(ok);
    Sx *b1 = parse1("(PolicyTreeWitness (Pair x y) (Tree (Node (History y0) (Act a)) (Node (History y0 b y1) (Act a)))"
                    " (Event e) (Left 1) (Right 0))");
    CHECK(!dc_policy_tree_admissible(b1, why, sizeof why) && strstr(why, "field Tree"), "B6 child reached by an action its parent does not take -> refused (field Tree)"); sx_free(b1);
    Sx *b2 = parse1("(PolicyTreeWitness (Pair x y) (Tree (Node (History y0) (Act a))) (Left 1) (Right 0))");
    CHECK(!dc_policy_tree_admissible(b2, why, sizeof why) && strstr(why, "field Event"), "B6 missing Event -> refused (field Event)"); sx_free(b2);
    Sx *b3 = parse1("(PolicyTreeWitness (Pair x y) (Tree (Node (History y0 a y1) (Act a))) (Event e) (Left 1) (Right 0))");
    CHECK(!dc_policy_tree_admissible(b3, why, sizeof why), "B6 tree without a root -> refused"); sx_free(b3);
    CHECK(dc_distance_status(1, 0.25, 1, 0.25, 0) == DC_CHECKED, "B6 distance: Precision 0 with meeting lower and upper certificates -> Checked");
    CHECK(dc_distance_status(1, 0.2, 1, 0.25, 0) == DC_UNKNOWN, "B6 distance: Precision 0, bounds do not meet -> Unknown");
    CHECK(dc_distance_status(0, 0, 1, 0.25, 0) == DC_UNKNOWN, "B6 distance: no lower certificate -> Unknown");
    CHECK(dc_distance_status(1, 0.2, 1, 0.25, 0.1) == DC_CHECKED, "B6 distance: within requested precision -> Checked");
}

int main(void) {
    boundary1_binding(); boundary2_assurance(); boundary3_obligations();
    boundary4_results(); boundary5_estimate(); boundary6_witnesses();
    printf("boundaries: %d/%d passed\n", total - fails, total);
    return fails ? 1 : 0;
}
