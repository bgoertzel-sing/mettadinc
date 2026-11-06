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
    /* the one premise validation routine */
    {
        char w[256];
        DcBindingRef e = { "dA", "M1", NULL, 3, -1, NULL };
        DcBindingRef ok = { "dA", "M1", "M2", 3, 4, NULL };
        DcBindingRef wrongsrc = { "dA", "M9", "M2", 3, 4, NULL };
        DcBindingRef wrongmod = { "dB", "M1", "M2", 3, 4, NULL };
        DcBindingRef wrongtol = { "dA", "M1", "M2", 3, 4, "Coarse" };
        CHECK(dc_binding_validate("Then", "Second", &e, &ok, w, sizeof w) == 0, "B1 validate: matching premise accepted");
        CHECK(dc_binding_validate("Then", "Second", &e, &wrongsrc, w, sizeof w) == -1 && strstr(w, "field Second") && strstr(w, "interface mismatch"), "B1 validate: wrong source interface -> names the field");
        CHECK(dc_binding_validate("Lift", "Store", &e, &wrongmod, w, sizeof w) == -1 && strstr(w, "Lift: field Store") && strstr(w, "module digest"), "B1 validate: wrong module digest -> names the field");
        CHECK(dc_binding_validate("Then", "Second", &e, &wrongtol, w, sizeof w) == -1 && strstr(w, "tolerance"), "B1 validate: premise under another tolerance refused");
    }
    /* envelope carries model identities, interface tolerance and the scope fields */
    {
        Sx *env = dc_envelope(NULL, VERDICT_HOLDS, 1, NULL, NULL, NULL, NULL, NULL);
        dc_result_bind_models(env, "M1", "M2");
        Sx *b = sx_find(env, "Binding", 1), *s = sx_find(env, "Scope", 1);
        CHECK(b && sx_find(b, "Source", 1) && sx_find(b, "Target", 1) && sx_find(b, "Interface", 1), "B1 envelope binding has Source, Target and Interface (tolerance)");
        CHECK(s && sx_find(s, "InitialStates", 1) && sx_find(s, "ReachableStates", 1) && sx_find(s, "Horizon", 1)
              && sx_find(s, "Discount", 1) && sx_find(s, "PolicyClass", 1), "B1 envelope scope has initial/reachable states, horizon, discount, policy class");
        Sx *src = b ? sx_find(b, "Source", 1) : NULL;
        CHECK(src && src->n == 2 && src->items[1]->kind == SX_STR && !strcmp(src->items[1]->text, "M1"), "B1 dc_result_bind_models records the source identity");
        sx_free(env);
    }
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
    char why[256];
    /* assumption records */
    Sx *tb = parse1("(TrustedBackend cvc5 1.1.2 QF_LIA \"d1\")");
    Sx *tz = parse1("(TrustedBackend z3 4.13 QF_LIA \"d2\")");
    Sx *badtb = parse1("(TrustedBackend cvc5 1.1.2)");
    CHECK(dc_assumption_wellformed(tb, why, sizeof why), "B2 TrustedBackend solver version logic digest is well formed");
    CHECK(!dc_assumption_wellformed(badtb, why, sizeof why) && strstr(why, "TrustedBackend"), "B2 short TrustedBackend refused, naming the field");
    /* union of premises' assumptions, no duplicates */
    Sx *a1 = parse1("(Assumptions (TrustedBackend cvc5 1.1.2 QF_LIA \"d1\"))");
    Sx *a2 = parse1("(Assumptions (TrustedBackend cvc5 1.1.2 QF_LIA \"d1\") (TrustedBackend z3 4.13 QF_LIA \"d2\"))");
    Sx *u = parse1("(Assumptions)");
    dc_assumptions_union(u, a1); dc_assumptions_union(u, a2);
    CHECK(u->n == 3, "B2 derived result takes the union of premise assumptions (2 distinct of 3)");
    /* agreed_by is evidence, not a ground */
    const char *sv[] = { "cvc5", "z3" }, *vv[] = { "1.1.2", "4.13" };
    Sx *ab = dc_agreed_by(sv, vv, 2);
    CHECK(sx_head_is(ab, "AgreedBy") && ab->n == 3, "B2 agreed_by record lists each agreeing backend");
    /* Accepts declarations */
    DcAccepts strict, cvc;
    Sx *d1 = parse1("(Accepts Checked)");
    Sx *d2 = parse1("(Accepts Checked (Conditional (TrustedBackend cvc5)))");
    Sx *d3 = parse1("(Accepts Maybe)");
    CHECK(dc_accepts_parse(d1, &strict, why, sizeof why) == 0 && strict.checked && strict.nbackend == 0, "B2 (Accepts Checked) parsed");
    CHECK(dc_accepts_parse(d2, &cvc, why, sizeof why) == 0 && cvc.nbackend == 1, "B2 (Accepts Checked (Conditional (TrustedBackend cvc5))) parsed");
    DcAccepts junk;
    CHECK(dc_accepts_parse(d3, &junk, why, sizeof why) == -1 && strstr(why, "Accepts"), "B2 malformed Accepts refused");
    Sx *none = parse1("(Assumptions)");
    CHECK(dc_accepts_result(&strict, DC_CHECKED, none), "B2 strict consumer accepts Checked");
    CHECK(!dc_accepts_result(&strict, DC_CONDITIONAL, a1), "B2 strict consumer refuses Conditional(cvc5)");
    CHECK(dc_accepts_result(&cvc, DC_CONDITIONAL, a1), "B2 cvc5 consumer accepts Conditional(cvc5)");
    CHECK(!dc_accepts_result(&cvc, DC_CONDITIONAL, a2), "B2 cvc5 consumer refuses Conditional(cvc5+z3)");
    CHECK(!dc_accepts_result(&cvc, DC_ESTIMATED, none), "B2 Estimated is never accepted as Checked/Conditional");
    DcStatus sts[3] = { DC_CHECKED, DC_CONDITIONAL, DC_CONDITIONAL };
    const Sx *as[3] = { none, a1, a2 };
    CHECK(dc_gate_inadequate(&strict, sts, as, 3) == 2 && dc_gate_inadequate(&cvc, sts, as, 3) == 1,
          "B2 gate counts results the consumer does not accept as inadequate coverage");
    /* a Conditional premise makes a derived Checked result Conditional */
    Sx *prem = parse1("(Result (Status Conditional) (Assumptions (TrustedBackend cvc5 1.1.2 QF_LIA \"d1\")))");
    Sx *der = parse1("(Result (Status Checked) (Assumptions))");
    dc_result_add_premise(der, prem, "P");
    CHECK(dc_result_status(der) == DC_CONDITIONAL && sx_find(der, "Assumptions", 0)->n == 2,
          "B2 derived result from a Conditional premise is Conditional and carries its assumption");
    Sx *est = parse1("(Result (Status Estimated) (Assumptions))");
    Sx *der2 = parse1("(Result (Status Checked) (Assumptions))");
    dc_result_add_premise(der2, est, "E");
    CHECK(dc_result_status(der2) == DC_CONDITIONAL, "B2 derived result from an Estimated premise is Conditional on it");
    Sx *fr[] = { tb, tz, badtb, a1, a2, u, ab, d1, d2, d3, none, prem, der, est, der2 };
    for (size_t k = 0; k < sizeof fr / sizeof fr[0]; k++) sx_free(fr[k]);
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
