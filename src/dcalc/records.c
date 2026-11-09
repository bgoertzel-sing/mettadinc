/* Boundaries 2, 4, 5, 6: records and rules fixed in M0 (see records.h). */
#include "records.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *GROUND[] = { "None", "Exact", "Replayed", "Witness", "Statistical" };
const char *dc_ground_name(DcGround g) { return (unsigned)g < 5 ? GROUND[g] : "None"; }

DcStatus dc_assure_grounded(DcVerdict v, DcGround g, int n_assumptions) {
    if (v == VERDICT_UNSUPPORTED) return DC_UNSUPPORTED;
    if (v == VERDICT_INVALID) return DC_INVALID_INPUT;
    if (g == GROUND_STATISTICAL) return n_assumptions ? DC_CONDITIONAL : DC_ESTIMATED;
    if (n_assumptions && g != GROUND_NONE) return DC_CONDITIONAL;
    if (v == VERDICT_HOLDS) return (g == GROUND_EXACT || g == GROUND_REPLAYED) ? DC_CHECKED : DC_UNKNOWN;
    if (v == VERDICT_FAILS) return g == GROUND_WITNESS ? DC_REFUTED : DC_UNKNOWN;
    return DC_INVALID_INPUT;
}

static const char *GOAL[] = { "InformationalRefinement", "InformationalEquivalence", "MeaningPreservation" };
const char *dc_goal_result_name(DcGoalResult r) { return (unsigned)r < 3 ? GOAL[r] : "?"; }
int dc_goal_change_is_renaming(int eq, int meaning) { return eq && meaning; }

static int copy_field(const Sx *x, const char *name, char *dst, size_t dn, char *err, size_t en) {
    const Sx *f = sx_find(x, name, 1);
    if (!f || f->n != 2 || f->items[1]->kind == SX_LIST) { snprintf(err, en, "Estimate: field %s missing or not atomic", name); return -1; }
    if (strlen(f->items[1]->text) >= dn) { snprintf(err, en, "Estimate: field %s too long", name); return -1; }
    snprintf(dst, dn, "%s", f->items[1]->text); return 0;
}

int dc_estimate_parse(const Sx *x, DcEstimate *e, char *err, size_t en) {
    memset(e, 0, sizeof *e);
    if (!sx_head_is(x, "Estimate")) { snprintf(err, en, "Estimate: expected (Estimate ...)"); return -1; }
    if (copy_field(x, "Population", e->population, sizeof e->population, err, en)) return -1;
    if (copy_field(x, "Selection", e->selection, sizeof e->selection, err, en)) return -1;
    if (copy_field(x, "PolicyVersion", e->policy_version, sizeof e->policy_version, err, en)) return -1;
    if (copy_field(x, "Estimand", e->estimand, sizeof e->estimand, err, en)) return -1;
    const Sx *d = sx_find(x, "SelectionDependsOnPolicy", 1);
    if (d) {
        if (d->n != 2 || !(sx_is_sym(d->items[1], "True") || sx_is_sym(d->items[1], "False"))) {
            snprintf(err, en, "Estimate: field SelectionDependsOnPolicy is not True or False"); return -1;
        }
        e->selection_depends_on_policy = sx_is_sym(d->items[1], "True");
    }
    for (size_t i = 1; i < x->n; i++) {
        const Sx *f = x->items[i];
        static const char *K[] = { "Population", "Selection", "PolicyVersion", "Estimand", "SelectionDependsOnPolicy" };
        int known = 0;
        for (int k = 0; k < 5; k++) if (sx_head_is(f, K[k])) known = 1;
        if (!known) { snprintf(err, en, "Estimate: field %zu is not a known field", i); return -1; }
    }
    return 0;
}

Sx *dc_estimate_sx(const DcEstimate *e) {
    return dc_form("Estimate", dc_form("Population", sx_sym(e->population), NULL),
                   dc_form("Selection", sx_sym(e->selection), NULL),
                   dc_form("PolicyVersion", sx_sym(e->policy_version), NULL),
                   dc_form("Estimand", sx_sym(e->estimand), NULL),
                   dc_form("SelectionDependsOnPolicy", sx_sym(e->selection_depends_on_policy ? "True" : "False"), NULL), NULL);
}

int dc_estimate_transport(const DcEstimate *e, const char *new_policy, int declared_argument) {
    if (!strcmp(e->policy_version, new_policy)) return 1;      /* no policy change */
    if (e->selection_depends_on_policy) return 0;             /* blocked */
    return declared_argument ? 1 : 0;                         /* else: new estimation task */
}

/* ---- PolicyTreeWitness admissibility ---- */
static int prefix_of(const Sx *parent, const Sx *child) {   /* child = parent + 2 items */
    if (child->n != parent->n + 2) return 0;
    for (size_t i = 1; i < parent->n; i++) if (!sx_equal(parent->items[i], child->items[i])) return 0;
    return 1;
}

int dc_policy_tree_admissible(const Sx *w, char *why, size_t wn) {
    if (!sx_head_is(w, "PolicyTreeWitness")) { snprintf(why, wn, "PolicyTreeWitness: wrong head"); return 0; }
    static const char *F[] = { "Pair", "Tree", "Event", "Left", "Right" };
    for (int k = 0; k < 5; k++) if (!sx_find(w, F[k], 1)) { snprintf(why, wn, "PolicyTreeWitness: field %s missing", F[k]); return 0; }
    const Sx *pr = sx_find(w, "Pair", 1);
    if (pr->n != 3) { snprintf(why, wn, "PolicyTreeWitness: field Pair needs two states"); return 0; }
    const Sx *t = sx_find(w, "Tree", 1);
    if (t->n < 2) { snprintf(why, wn, "PolicyTreeWitness: field Tree is empty"); return 0; }
    int roots = 0;
    for (size_t i = 1; i < t->n; i++) {
        const Sx *nd = t->items[i], *h = sx_head_is(nd, "Node") ? sx_find(nd, "History", 1) : NULL;
        if (!h || h->n < 2 || h->n % 2 != 0) { snprintf(why, wn, "PolicyTreeWitness: field Tree node %zu: History must be (y0 a1 y1 ... ak yk)", i - 1); return 0; }
        const Sx *act = sx_find(nd, "Act", 1), *law = sx_find(nd, "Law", 1);
        if (!!act == !!law || (act && act->n != 2)) { snprintf(why, wn, "PolicyTreeWitness: field Tree node %zu must name one action or one law", i - 1); return 0; }
        for (size_t j = 1; j < i; j++) {
            const Sx *h2 = sx_find(t->items[j], "History", 1);
            if (sx_equal(h, h2)) { snprintf(why, wn, "PolicyTreeWitness: field Tree: history of node %zu repeated", i - 1); return 0; }
        }
        if (h->n == 2) { roots++; continue; }
        int has_parent = 0;
        for (size_t j = 1; j < t->n && !has_parent; j++) {
            const Sx *h2 = sx_find(t->items[j], "History", 1);
            if (h2 && prefix_of(h2, h)) {
                /* the child's action must be the action the parent node names */
                const Sx *pa = sx_find(t->items[j], "Act", 1);
                if (pa && !sx_equal(pa->items[1], h->items[h->n - 2])) {
                    snprintf(why, wn, "PolicyTreeWitness: field Tree node %zu: action differs from its parent's action", i - 1); return 0;
                }
                has_parent = 1;
            }
        }
        if (!has_parent) { snprintf(why, wn, "PolicyTreeWitness: field Tree node %zu has no parent history", i - 1); return 0; }
    }
    if (roots != 1) { snprintf(why, wn, "PolicyTreeWitness: field Tree needs exactly one root keyed by the initial observation"); return 0; }
    return 1;
}

DcStatus dc_distance_status(int has_lo, double lo, int has_hi, double hi, double precision) {
    if (!has_lo || !has_hi || lo > hi) return DC_UNKNOWN;
    if (precision <= 0) return hi == lo ? DC_CHECKED : DC_UNKNOWN;
    return hi - lo <= precision ? DC_CHECKED : DC_UNKNOWN;
}

/* ---- 2b. assumptions, agreed_by, Accepts ---- */
static int all_atoms(const Sx *a, size_t from) {
    for (size_t k = from; k < a->n; k++) if (a->items[k]->kind == SX_LIST) return 0;
    return 1;
}
int dc_assumption_wellformed(const Sx *a, char *why, size_t wn) {
    if (!a || a->kind != SX_LIST || a->n == 0) { snprintf(why, wn, "assumption: expected a form"); return 0; }
    if (sx_head_is(a, "TrustedBackend")) {
        if (a->n != 5 || !all_atoms(a, 1)) { snprintf(why, wn, "TrustedBackend: expected solver version logic obligation-digest"); return 0; }
        return 1;
    }
    if (sx_head_is(a, "Assumption")) {
        if (a->n != 3 || !all_atoms(a, 1)) { snprintf(why, wn, "Assumption: expected name digest"); return 0; }
        return 1;
    }
    if (sx_head_is(a, "EstimatedPremise")) {
        if (a->n != 3 || !all_atoms(a, 1)) { snprintf(why, wn, "EstimatedPremise: expected result-digest delta"); return 0; }
        return 1;
    }
    snprintf(why, wn, "assumption: unknown kind %s", a->items[0]->kind == SX_LIST ? "(list)" : a->items[0]->text);
    return 0;
}
const Sx *dc_result_assumptions(const Sx *env) {
    return env && env->kind == SX_LIST ? sx_find(env, "Assumptions", 0) : NULL;
}
void dc_assumptions_union(Sx *dst, const Sx *src) {
    if (!dst || !src) return;
    for (size_t k = 1; k < src->n; k++) {
        int have = 0;
        for (size_t j = 1; j < dst->n && !have; j++) have = sx_equal(dst->items[j], src->items[k]);
        if (!have) sx_push(dst, sx_copy(src->items[k]));
    }
}
Sx *dc_agreed_by(const char *const *solver, const char *const *version, size_t n) {
    Sx *l = sx_list(); sx_push(l, sx_sym("AgreedBy"));
    for (size_t k = 0; k < n; k++) {
        Sx *b = sx_list(); sx_push(b, sx_sym("Backend")); sx_push(b, sx_sym(solver[k])); sx_push(b, sx_sym(version[k]));
        sx_push(l, b);
    }
    return l;
}
int dc_accepts_parse(const Sx *x, DcAccepts *a, char *why, size_t wn) {
    memset(a, 0, sizeof *a);
    if (!sx_head_is(x, "Accepts") || x->n < 2) { snprintf(why, wn, "Accepts: expected (Accepts status...)"); return -1; }
    for (size_t k = 1; k < x->n; k++) {
        const Sx *e = x->items[k];
        if (sx_is_sym(e, "Checked")) { a->checked = 1; continue; }
        if (sx_head_is(e, "Conditional") && e->n == 2 && sx_head_is(e->items[1], "TrustedBackend")
            && e->items[1]->n == 2 && e->items[1]->items[1]->kind == SX_SYM) {
            if (a->nbackend == DC_ACCEPTS_MAX) { snprintf(why, wn, "Accepts: too many backends"); return -1; }
            snprintf(a->backend[a->nbackend++], sizeof a->backend[0], "%s", e->items[1]->items[1]->text);
            continue;
        }
        snprintf(why, wn, "Accepts: entry %zu is neither Checked nor (Conditional (TrustedBackend solver))", k);
        return -1;
    }
    return 0;
}
int dc_accepts_result(const DcAccepts *a, DcStatus st, const Sx *as) {
    size_t n = as ? as->n : 0;
    if (st == DC_CHECKED) return a->checked && n <= 1;
    if (st != DC_CONDITIONAL || n <= 1) return 0;
    for (size_t k = 1; k < n; k++) {
        const Sx *x = as->items[k]; int ok = 0;
        if (sx_head_is(x, "TrustedBackend") && x->n == 5)
            for (size_t b = 0; b < a->nbackend && !ok; b++) ok = !strcmp(a->backend[b], x->items[1]->text);
        if (!ok) return 0;
    }
    return 1;
}
size_t dc_gate_inadequate(const DcAccepts *a, const DcStatus *st, const Sx *const *as, size_t n) {
    size_t bad = 0;
    for (size_t k = 0; k < n; k++) bad += !dc_accepts_result(a, st[k], as ? as[k] : NULL);
    return bad;
}
