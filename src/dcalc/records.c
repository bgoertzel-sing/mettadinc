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

static int copy_text(const Sx *it, char *dst, size_t dn) {   /* atom text or canonical print */
    if (it->kind != SX_LIST) { if (strlen(it->text) >= dn) return -1; snprintf(dst, dn, "%s", it->text); return 0; }
    char *s = sx_print(it); if (!s) return -1;
    int bad = strlen(s) >= dn; if (!bad) snprintf(dst, dn, "%s", s);
    free(s); return bad ? -1 : 0;
}
static int opt_field(const Sx *x, const char *name, char *dst, size_t dn, char *err, size_t en) {
    const Sx *f = sx_find(x, name, 1);
    if (!f) return 0;
    if (f->n != 2 || copy_text(f->items[1], dst, dn)) { snprintf(err, en, "Estimate: field %s malformed or too long", name); return -1; }
    return 0;
}

int dc_estimate_parse(const Sx *x, DcEstimate *e, char *err, size_t en) {
    memset(e, 0, sizeof *e);
    e->sample_size = -1;
    if (!sx_head_is(x, "Estimate")) { snprintf(err, en, "Estimate: expected (Estimate ...)"); return -1; }
    if (copy_field(x, "Population", e->population, sizeof e->population, err, en)) return -1;
    if (copy_field(x, "Selection", e->selection, sizeof e->selection, err, en)) return -1;
    /* the registry envelope names it (Policy digest); (PolicyVersion v) is the M4 spelling */
    if (sx_find(x, "Policy", 1)) { if (copy_field(x, "Policy", e->policy_version, sizeof e->policy_version, err, en)) return -1; }
    else if (copy_field(x, "PolicyVersion", e->policy_version, sizeof e->policy_version, err, en)) return -1;
    if (copy_field(x, "Estimand", e->estimand, sizeof e->estimand, err, en)) return -1;
    const Sx *d = sx_find(x, "SelectionDependsOnPolicy", 1);
    if (d) {
        if (d->n != 2 || !(sx_is_sym(d->items[1], "True") || sx_is_sym(d->items[1], "False"))) {
            snprintf(err, en, "Estimate: field SelectionDependsOnPolicy is not True or False"); return -1;
        }
        e->selection_depends_on_policy = sx_is_sym(d->items[1], "True");
    }
    if (opt_field(x, "Estimator", e->estimator, sizeof e->estimator, err, en)) return -1;
    if (opt_field(x, "Protocol", e->protocol, sizeof e->protocol, err, en)) return -1;
    if (opt_field(x, "Dependence", e->dependence, sizeof e->dependence, err, en)) return -1;
    if (opt_field(x, "Combination", e->combination, sizeof e->combination, err, en)) return -1;
    const Sx *ss = sx_find(x, "SampleSize", 1);
    if (ss) {
        char *end = NULL;
        if (ss->n != 2 || ss->items[1]->kind == SX_LIST) { snprintf(err, en, "Estimate: field SampleSize is not a natural number"); return -1; }
        long long v = strtoll(ss->items[1]->text, &end, 10);
        if (!end || *end || v < 0) { snprintf(err, en, "Estimate: field SampleSize is not a natural number"); return -1; }
        e->sample_size = v;
    }
    const Sx *er = sx_find(x, "Error", 1);
    if (er) {
        if (er->n != 3 || copy_text(er->items[1], e->eps, sizeof e->eps) || copy_text(er->items[2], e->delta, sizeof e->delta)) {
            snprintf(err, en, "Estimate: field Error is not (Error epsilon delta)"); return -1;
        }
    }
    for (size_t i = 1; i < x->n; i++) {
        const Sx *f = x->items[i];
        static const char *K[] = { "Population", "Selection", "PolicyVersion", "Policy", "Estimand", "SelectionDependsOnPolicy",
                                   "Estimator", "Protocol", "SampleSize", "Error", "Dependence", "Combination",
                                   "SamplePopulation", "Seed",   /* review 1 F4 */
                                   "Transport", "Replay" };      /* gaps task: review 3 gaps 1 and 4 */
        int known = 0;
        for (size_t k = 0; k < sizeof K / sizeof K[0]; k++) if (sx_head_is(f, K[k])) known = 1;
        if (!known) { snprintf(err, en, "Estimate: field %zu is not a known field", i); return -1; }
    }
    return 0;
}

int dc_estimate_complete(const DcEstimate *e, char *why, size_t wn) {
    const char *miss = !e->estimand[0] ? "Estimand" : !e->population[0] ? "Population" : !e->selection[0] ? "Selection"
        : !e->policy_version[0] ? "Policy" : !e->estimator[0] ? "Estimator" : !e->protocol[0] ? "Protocol"
        : e->sample_size < 0 ? "SampleSize" : (!e->eps[0] || !e->delta[0]) ? "Error"
        : !e->dependence[0] ? "Dependence" : !e->combination[0] ? "Combination" : NULL;
    if (miss) { snprintf(why, wn, "Estimate: field %s missing", miss); return 0; }
    return 1;
}

static Sx *text_sx(const char *s) {          /* reparse canonical text so (Rat 1 100) round-trips */
    if (s[0] != '(') return sx_sym(s);
    const char *er = NULL; int el = 0;
    Sx *all = sx_parse_all(s, &er, &el);
    if (!all || all->n != 1) { if (all) sx_free(all); return sx_sym(s); }
    Sx *r = sx_copy(all->items[0]); sx_free(all); return r;
}

Sx *dc_estimate_sx(const DcEstimate *e) {
    Sx *r = dc_form("Estimate", dc_form("Estimand", sx_str(e->estimand), NULL),
                    dc_form("Population", sx_str(e->population), NULL),
                    dc_form("Selection", sx_str(e->selection), NULL),
                    dc_form("Policy", sx_str(e->policy_version), NULL), NULL);   /* review 1 F6: the registry envelope spelling */
    if (e->estimator[0]) sx_push(r, dc_form("Estimator", sx_str(e->estimator), NULL));
    if (e->protocol[0]) sx_push(r, dc_form("Protocol", sx_str(e->protocol), NULL));
    if (e->sample_size >= 0) { char b[32]; snprintf(b, sizeof b, "%lld", e->sample_size); sx_push(r, dc_form("SampleSize", sx_sym(b), NULL)); }
    if (e->eps[0] && e->delta[0]) sx_push(r, dc_form("Error", text_sx(e->eps), text_sx(e->delta), NULL));
    if (e->dependence[0]) sx_push(r, dc_form("Dependence", sx_str(e->dependence), NULL));
    if (e->combination[0]) sx_push(r, dc_form("Combination", sx_str(e->combination), NULL));
    sx_push(r, dc_form("SelectionDependsOnPolicy", sx_sym(e->selection_depends_on_policy ? "True" : "False"), NULL));
    return r;
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
        if (sx_is_sym(e, "Estimated")) { a->estimated = 1; continue; }
        if (sx_head_is(e, "Conditional") && e->n >= 2) {
            for (size_t c = 1; c < e->n; c++) {
                const Sx *y = e->items[c];
                int tb = sx_head_is(y, "TrustedBackend"), as = sx_head_is(y, "Assumption");
                if ((!tb && !as) || y->n < 2) {
                    snprintf(why, wn, "Accepts: entry %zu: clause item %zu is neither (TrustedBackend solver...) nor (Assumption name...)", k, c);
                    return -1;
                }
                for (size_t s = 1; s < y->n; s++) {
                    if (y->items[s]->kind != SX_SYM) { snprintf(why, wn, "Accepts: entry %zu: clause item %zu names a non-symbol", k, c); return -1; }
                    size_t *cnt = tb ? &a->nbackend : &a->nassume;
                    char (*dst)[64] = tb ? a->backend : a->assume;
                    if (*cnt == DC_ACCEPTS_MAX) { snprintf(why, wn, "Accepts: too many %s entries", tb ? "backend" : "assumption"); return -1; }
                    snprintf(dst[(*cnt)++], 64, "%s", y->items[s]->text);
                }
            }
            continue;
        }
        snprintf(why, wn, "Accepts: entry %zu is neither Checked, Estimated nor (Conditional (TrustedBackend solver...)|(Assumption name...))", k);
        return -1;
    }
    return 0;
}
static int accepts_covers(const DcAccepts *a, const Sx *x) {
    if (sx_head_is(x, "TrustedBackend") && x->n == 5 && x->items[1]->kind == SX_SYM) {
        for (size_t b = 0; b < a->nbackend; b++) if (!strcmp(a->backend[b], x->items[1]->text)) return 1;
        return 0;
    }
    if (sx_head_is(x, "Assumption") && x->n >= 2 && x->items[1]->kind == SX_SYM) {
        for (size_t b = 0; b < a->nassume; b++) if (!strcmp(a->assume[b], x->items[1]->text)) return 1;
        return 0;
    }
    if (sx_head_is(x, "EstimatedPremise") && x->n == 3) return a->estimated;
    return 0;
}
int dc_accepts_result(const DcAccepts *a, DcStatus st, const Sx *as) {
    size_t n = as ? as->n : 0;
    if (st == DC_CHECKED) return a->checked && n <= 1;
    if (st == DC_ESTIMATED) {
        if (!a->estimated) return 0;
        for (size_t k = 1; k < n; k++) if (!accepts_covers(a, as->items[k])) return 0;
        return 1;
    }
    if (st != DC_CONDITIONAL || n <= 1) return 0;
    for (size_t k = 1; k < n; k++) if (!accepts_covers(a, as->items[k])) return 0;
    return 1;
}
size_t dc_gate_inadequate(const DcAccepts *a, const DcStatus *st, const Sx *const *as, size_t n) {
    size_t bad = 0;
    for (size_t k = 0; k < n; k++) bad += !dc_accepts_result(a, st[k], as ? as[k] : NULL);
    return bad;
}
