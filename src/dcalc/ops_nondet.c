/* M5 (opt-in, beyond the first release): requests on a Dynamics Nondeterministic
 * module (docs/e0/MILESTONES.md "M5: nondeterminism and simulation").
 * Declarations are read from m->source (model.c skips them when m->nondet is set).
 * Sets of states are 64-bit masks: a carrier has at most 64 elements. */
#include "ops_internal.h"
#include "ops_run.h"
#include "model.h"
#include "rat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* review 2 F7: Unsupported/InvalidInput answers from this file carry the M5 fragment and
 * replay policy, not the M0 defaults of dc_envelope with no scope.  Function-like macros are
 * not re-expanded inside their own body, so the inner calls reach the ops_core functions. */
static void nd_resym(Sx *in, const char *name, const char *val) {
    Sx *f = in ? (Sx *)sx_find(in, name, 1) : NULL;
    if (f && f->n == 2) { sx_free(f->items[1]); f->items[1] = dc_sym(val); }
}
static Sx *nd_rescope(Sx *r) {
    if (!r) return r;
    nd_resym((Sx *)sx_find(r, "Scope", 1), "Fragment", "M5-Nondeterministic");
    nd_resym((Sx *)sx_find(r, "Assurance", 1), "Policy", "M5-NondeterministicReplay");
    return r;
}
#define dc_invalid(...) nd_rescope(dc_invalid(__VA_ARGS__))
#define dc_unsupported(...) nd_rescope(dc_unsupported(__VA_ARGS__))

#define ND_MAXC 64
#define ND_MAXN 32
typedef uint64_t NdSet;
typedef struct { char name[DC_MAX_NAME]; int n; char el[ND_MAXC][DC_MAX_NAME]; } NdCar;
typedef struct { char name[DC_MAX_NAME]; int from, to, choice; NdSet img[ND_MAXC]; } NdMap;   /* img[x]: successor set */
typedef struct { char name[DC_MAX_NAME]; int map; } NdNamed;
typedef struct { char name[DC_MAX_NAME]; int states; NdNamed obs[8]; int nobs; NdNamed act[8]; int nact; int bag_multiset, has_bag; } NdMach;
typedef struct { char name[DC_MAX_NAME]; char rule[DC_MAX_NAME]; } NdSched;
typedef struct { char name[DC_MAX_NAME]; int src, tgt, map; int pairs; NdSet rel[ND_MAXC]; char unsup[200]; } NdSim;   /* unsup: declared semantics the check does not implement (review 2 F2) */   /* rel[x]: related abstract states */
typedef struct {
    NdCar car[ND_MAXN]; int ncar; NdMap map[ND_MAXN]; int nmap; NdMach mach[ND_MAXN]; int nmach;
    NdSched sch[8]; int nsch; NdSim sim[ND_MAXN]; int nsim;
    char relname[ND_MAXN][DC_MAX_NAME]; NdSet relp[ND_MAXN][ND_MAXC]; int relsrc[ND_MAXN], reltgt[ND_MAXN], nrel;
} NdMod;

static const char *nm_of(const Sx *x) { return x && x->kind == SX_SYM ? x->text : NULL; }
static const Sx *fld(const Sx *d, const char *h) { for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], h)) return d->items[i]; return NULL; }
static const char *fld1(const Sx *d, const char *h) { const Sx *f = fld(d, h); return f && f->n == 2 ? nm_of(f->items[1]) : NULL; }
#define ND_FIND(arr, cnt) for (int i = 0; i < (cnt); i++) if (!strcmp((arr)[i].name, nm)) return i; return -1;
static int nd_car(const NdMod *s, const char *nm) { if (!nm) return -1; ND_FIND(s->car, s->ncar) }
static int nd_map(const NdMod *s, const char *nm) { if (!nm) return -1; ND_FIND(s->map, s->nmap) }
static int nd_mach(const NdMod *s, const char *nm) { if (!nm) return -1; ND_FIND(s->mach, s->nmach) }
static int nd_sim(const NdMod *s, const char *nm) { if (!nm) return -1; ND_FIND(s->sim, s->nsim) }
static int nd_sch(const NdMod *s, const char *nm) { if (!nm) return -1; ND_FIND(s->sch, s->nsch) }
static int nd_el(const NdCar *c, const char *v) { if (!v) return -1; for (int i = 0; i < c->n; i++) if (!strcmp(c->el[i], v)) return i; return -1; }
static int nd_err(char *err, size_t es, const char *fmt, const char *a, const char *b) { snprintf(err, es, fmt, a ? a : "", b ? b : ""); return -1; }
static int popc(NdSet s) { int n = 0; while (s) { s &= s - 1; n++; } return n; }

/* ---- reader: Carrier / Map (Cases|Choice) / Machine / Scheduler / Relation / Simulation ---- */
static int nd_read_map(NdMod *s, const Sx *d, char *err, size_t es) {
    if (s->nmap >= ND_MAXN) return nd_err(err, es, "too many Maps%s%s", NULL, NULL);
    NdMap *M = &s->map[s->nmap]; memset(M, 0, sizeof *M);
    snprintf(M->name, sizeof M->name, "%s", nm_of(d->items[1]));
    M->from = nd_car(s, fld1(d, "From")); M->to = nd_car(s, fld1(d, "To"));
    if (M->from < 0 || M->to < 0) return nd_err(err, es, "Map %s: From/To names no declared Carrier%s", M->name, NULL);
    const Sx *b = fld(d, "Cases"); M->choice = 0;
    if (!b) { b = fld(d, "Choice"); M->choice = 1; }
    if (!b) return nd_err(err, es, "Map %s: needs (Cases ..) or (Choice ..)%s", M->name, NULL);
    const NdCar *F = &s->car[M->from], *T = &s->car[M->to];
    NdSet seen = 0;
    for (size_t i = 1; i < b->n; i++) {
        const Sx *c = b->items[i];
        if (c->kind != SX_LIST || c->n < 2 || (!M->choice && c->n != 2)) return nd_err(err, es, "Map %s: malformed case%s", M->name, NULL);
        int x = nd_el(F, nm_of(c->items[0]));
        if (x < 0) return nd_err(err, es, "Map %s: %s is not in its From carrier", M->name, nm_of(c->items[0]));
        if (seen & ((NdSet)1 << x)) return nd_err(err, es, "Map %s: %s has two cases", M->name, F->el[x]);
        seen |= (NdSet)1 << x;
        for (size_t k = 1; k < c->n; k++) {
            int y = nd_el(T, nm_of(c->items[k]));
            if (y < 0) return nd_err(err, es, "Map %s: %s is not in its To carrier", M->name, nm_of(c->items[k]));
            M->img[x] |= (NdSet)1 << y;
        }
    }
    NdSet all = F->n == 64 ? ~(NdSet)0 : (((NdSet)1 << F->n) - 1);
    if (seen != all) return nd_err(err, es, "Map %s: not total on its From carrier%s", M->name, NULL);
    s->nmap++; return 0;
}
static int nd_read_named(NdMod *s, const Sx *f, NdNamed *v, int *n, const char *mn, char *err, size_t es) {
    if (*n >= 8 || f->n != 3) return nd_err(err, es, "Machine %s: malformed (%s name map)", mn, nm_of(f->items[0]));
    snprintf(v[*n].name, sizeof v[*n].name, "%s", nm_of(f->items[1]) ? nm_of(f->items[1]) : "");
    v[*n].map = nd_map(s, nm_of(f->items[2]));
    if (v[*n].map < 0) return nd_err(err, es, "Machine %s: %s names no declared Map", mn, nm_of(f->items[2]));
    (*n)++; return 0;
}
static int nd_read(const Sx *src, NdMod *s, char *err, size_t es) {
    memset(s, 0, sizeof *s);
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (d->kind != SX_LIST || d->n < 2 || !nm_of(d->items[0])) continue;
        const char *h = d->items[0]->text, *dn = nm_of(d->items[1]);
        if (!strcmp(h, "Carrier")) {
            if (s->ncar >= ND_MAXN || !dn) return nd_err(err, es, "Carrier: malformed%s%s", NULL, NULL);
            NdCar *C = &s->car[s->ncar]; memset(C, 0, sizeof *C); snprintf(C->name, sizeof C->name, "%s", dn);
            const Sx *e = fld(d, "Enum");
            if (!e) return nd_err(err, es, "Carrier %s: needs (Enum ..)%s", dn, NULL);
            if (e->n - 1 > ND_MAXC) return nd_err(err, es, "Carrier %s: more than 64 elements%s", dn, NULL);
            for (size_t k = 1; k < e->n; k++) snprintf(C->el[C->n++], DC_MAX_NAME, "%s", e->items[k]->text ? e->items[k]->text : "");
            s->ncar++;
        } else if (!strcmp(h, "Map")) { if (!dn || nd_read_map(s, d, err, es)) return -1; }
        else if (!strcmp(h, "Machine")) {
            if (s->nmach >= ND_MAXN || !dn) return nd_err(err, es, "Machine: malformed%s%s", NULL, NULL);
            NdMach *M = &s->mach[s->nmach]; memset(M, 0, sizeof *M); snprintf(M->name, sizeof M->name, "%s", dn);
            M->states = nd_car(s, fld1(d, "States"));
            if (M->states < 0) return nd_err(err, es, "Machine %s: States names no declared Carrier%s", dn, NULL);
            for (size_t k = 2; k < d->n; k++) {
                const Sx *f = d->items[k];
                if (sx_head_is(f, "Observe")) { if (nd_read_named(s, f, M->obs, &M->nobs, dn, err, es)) return -1; }
                else if (sx_head_is(f, "Action")) { if (nd_read_named(s, f, M->act, &M->nact, dn, err, es)) return -1; }
                else if (sx_head_is(f, "Bag") && f->n == 2) { M->has_bag = 1; M->bag_multiset = nm_of(f->items[1]) && !strcmp(f->items[1]->text, "Multiset"); }
            }
            s->nmach++;
        } else if (!strcmp(h, "Scheduler")) {
            if (s->nsch >= 8 || !dn) return nd_err(err, es, "Scheduler: malformed%s%s", NULL, NULL);
            snprintf(s->sch[s->nsch].name, DC_MAX_NAME, "%s", dn);
            snprintf(s->sch[s->nsch].rule, DC_MAX_NAME, "%s", fld1(d, "Rule") ? fld1(d, "Rule") : "");
            s->nsch++;
        } else if (!strcmp(h, "Relation")) {
            if (s->nrel >= ND_MAXN || !dn) return nd_err(err, es, "Relation: malformed%s%s", NULL, NULL);
            int a = nd_car(s, fld1(d, "From")), b = nd_car(s, fld1(d, "To")), k = s->nrel;
            if (a < 0 || b < 0) return nd_err(err, es, "Relation %s: From/To names no declared Carrier%s", dn, NULL);
            snprintf(s->relname[k], DC_MAX_NAME, "%s", dn); s->relsrc[k] = a; s->reltgt[k] = b;
            memset(s->relp[k], 0, sizeof s->relp[k]);
            const Sx *pp = fld(d, "Pairs");
            if (!pp) return nd_err(err, es, "Relation %s: needs (Pairs ..)%s", dn, NULL);
            for (size_t j = 1; j < pp->n; j++) {
                const Sx *c = pp->items[j];
                int x = c->kind == SX_LIST && c->n == 2 ? nd_el(&s->car[a], nm_of(c->items[0])) : -1;
                int y = x >= 0 ? nd_el(&s->car[b], nm_of(c->items[1])) : -1;
                if (y < 0) return nd_err(err, es, "Relation %s: pair %s is not in From x To", dn, c->kind == SX_LIST && c->n ? nm_of(c->items[0]) : "?");
                s->relp[k][x] |= (NdSet)1 << y;
            }
            s->nrel++;
        } else if (!strcmp(h, "Simulation")) {
            if (s->nsim >= ND_MAXN || !dn) return nd_err(err, es, "Simulation: malformed%s%s", NULL, NULL);
            NdSim *S = &s->sim[s->nsim]; memset(S, 0, sizeof *S); snprintf(S->name, sizeof S->name, "%s", dn);
            {   /* review 2 F2: only lockstep matching is checked; Stutter and Order are declared by the beyond registry but not implemented */
                const Sx *mf = fld(d, "Matching"); const char *mt = fld1(d, "Matching");
                if (mf && (!mt || strcmp(mt, "Lockstep"))) snprintf(S->unsup, sizeof S->unsup, "(Matching %s) is declared but only Lockstep matching is checked", mt ? mt : "?");
                else if (fld(d, "Order")) snprintf(S->unsup, sizeof S->unsup, "an Order is declared but the simulation check does not read it");
            }
            S->src = nd_mach(s, fld1(d, "Source")); S->tgt = nd_mach(s, fld1(d, "Target"));
            if (S->src < 0 || S->tgt < 0) return nd_err(err, es, "Simulation %s: Source/Target names no declared Machine%s", dn, NULL);
            const char *rn = fld1(d, "Relation"); S->map = -1; S->pairs = -1;
            int cs = s->mach[S->src].states, ct = s->mach[S->tgt].states;
            for (int k = 0; rn && k < s->nrel; k++) if (!strcmp(s->relname[k], rn)) S->pairs = k;
            if (S->pairs >= 0) {
                if (s->relsrc[S->pairs] != cs || s->reltgt[S->pairs] != ct)
                    return nd_err(err, es, "Simulation %s: Relation %s does not relate Source states to Target states", dn, rn);
                memcpy(S->rel, s->relp[S->pairs], sizeof S->rel);
            } else if ((S->map = nd_map(s, rn)) >= 0) {   /* a Map used as a functional relation */
                const NdMap *R = &s->map[S->map];
                if (R->from != cs || R->to != ct) return nd_err(err, es, "Simulation %s: Map %s does not go from Source states to Target states", dn, rn);
                memcpy(S->rel, R->img, sizeof S->rel);
            } else return nd_err(err, es, "Simulation %s: Relation %s names no declared Relation or Map", dn, rn);
            s->nsim++;
        }
    }
    return 0;
}

/* ---- requests ---- */
static const Sx *ropt(const Sx *q, const char *h) { for (size_t i = 2; i < q->n; i++) if (sx_head_is(q->items[i], h) && q->items[i]->n >= 2) return q->items[i]; return NULL; }
static int nd_named(const NdNamed *v, int n, const char *a) { if (!a) return -1; for (int i = 0; i < n; i++) if (!strcmp(v[i].name, a)) return v[i].map; return -1; }
static NdSet nd_post(const NdMap *A, NdSet X) { NdSet Y = 0; for (int x = 0; x < ND_MAXC; x++) if ((X >> x) & 1) Y |= A->img[x]; return Y; }
static Sx *rsx(DcRat r) { return dc_form("Rat", dc_int((long)r.n), dc_int((long)r.d), NULL); }
static int g_nd_rep = 1;   /* 0: the envelope answers Unknown (no replayable evidence) */
static Sx *nd_env_k(DcModule *m, DcVerdict v, const Sx *q, const char *subjk, const char *subjn, Sx *val, Sx *ev, const char *why) {
    DcScope sc = { "M5-Nondeterministic", -1, "", NULL };
    Sx *subj = dc_form("Subject", dc_form(subjk, dc_sym(subjn), NULL), NULL);
    Sx *res = dc_envelope_scoped(m, v, g_nd_rep, dc_claim_of(q, "Literal"), subj, val, ev, why, &sc);
    Sx *au = res ? (Sx *)sx_find(res, "Assurance", 1) : NULL, *pp = au ? (Sx *)sx_find(au, "Policy", 1) : NULL;
    if (pp && pp->n == 2) { sx_free(pp->items[1]); pp->items[1] = dc_sym("M5-NondeterministicReplay"); }
    return res;
}
#define nd_env(m, v, q, n, val, ev, why) nd_env_k(m, v, q, "Machine", n, val, ev, why)
/* D01-D04: (Outcomes M (From s) (After (Do a..)) (Observe o)) and
 * (OutcomeProbability M (From s) (After (Do a..)) (Event (Shows o v)) (Scheduler S)) */
static Sx *nd_outcomes(DcModule *m, const NdMod *s, const Sx *q, int prob) {
    const char *hd = q->items[0]->text, *mn = q->n >= 2 ? nm_of(q->items[1]) : NULL;
    int mi = nd_mach(s, mn);
    if (mi < 0) return dc_invalid(m, "%s: names no declared Machine (%s)", hd, mn ? mn : "?");
    const NdMach *M = &s->mach[mi]; const NdCar *C = &s->car[M->states];
    const Sx *fr = ropt(q, "From"), *af = ropt(q, "After");
    int x0 = fr ? nd_el(C, nm_of(fr->items[1])) : -1;
    if (x0 < 0) return dc_invalid(m, "%s: (From s) names no state of %s", hd, mn);
    if (!af || !sx_head_is(af->items[1], "Do")) return dc_invalid(m, "%s: needs (After (Do action ..))", hd);
    const Sx *w = af->items[1]; int acts[64], na = 0;
    for (size_t k = 1; k < w->n && na < 64; k++) {
        int a = nd_named(M->act, M->nact, nm_of(w->items[k]));
        if (a < 0) return dc_invalid(m, "%s: %s is not an Action of %s", hd, nm_of(w->items[k]) ? nm_of(w->items[k]) : "?", mn);
        if (s->map[a].from != M->states || s->map[a].to != M->states) return dc_invalid(m, "%s: Action map %s is not States -> States", hd, s->map[a].name);
        acts[na++] = a;
    }
    Sx *word = dc_form("Word", NULL);
    for (int k = 0; k < na; k++) sx_push(word, dc_sym(w->items[k + 1]->text));
    if (!prob) {
        const Sx *ob = ropt(q, "Observe");
        int om = ob ? nd_named(M->obs, M->nobs, nm_of(ob->items[1])) : -1;
        if (om < 0) { sx_free(word); return dc_invalid(m, "%s: (Observe o) names no observer of %s", hd, mn); }
        NdSet X = (NdSet)1 << x0;
        for (int k = 0; k < na; k++) X = nd_post(&s->map[acts[k]], X);
        NdSet Y = nd_post(&s->map[om], X); const NdCar *T = &s->car[s->map[om].to];
        Sx *os = dc_form("OutcomeSet", NULL), *rs = dc_form("Reached", NULL);
        for (int y = 0; y < T->n; y++) if ((Y >> y) & 1) sx_push(os, dc_sym(T->el[y]));
        for (int x = 0; x < C->n; x++) if ((X >> x) & 1) sx_push(rs, dc_sym(C->el[x]));
        return nd_env(m, VERDICT_HOLDS, q, mn, dc_form("Value", os, NULL), dc_form("Evidence", word, rs, NULL), NULL);
    }
    /* negative gate: a host result bag used as a law needs a scheduler */
    const Sx *sp = ropt(q, "Scheduler");
    int si = sp ? nd_sch(s, nm_of(sp->items[1])) : -1;
    if (si < 0) { sx_free(word); return dc_invalid(m, "%s: a result bag is not a law without a declared (Scheduler ..)", hd); }
    if (strcmp(s->sch[si].rule, "Uniform")) { sx_free(word); return dc_unsupported(m, "%s: Scheduler rule %s", hd, s->sch[si].rule); }
    if (M->bag_multiset) { sx_free(word); return dc_unsupported(m, "%s: (Bag Multiset) under a Uniform scheduler is not implemented", hd); }
    const Sx *ev = ropt(q, "Event"), *e = ev ? ev->items[1] : NULL;
    int om = e && sx_head_is(e, "Shows") && e->n == 3 ? nd_named(M->obs, M->nobs, nm_of(e->items[1])) : -1;
    if (om < 0 || s->map[om].choice) { sx_free(word); return dc_invalid(m, "%s: needs (Event (Shows o v)) with o a functional observer of %s", hd, mn); }
    int v = nd_el(&s->car[s->map[om].to], nm_of(e->items[2]));
    if (v < 0) { sx_free(word); return dc_invalid(m, "%s: %s is not a value of observer %s", hd, nm_of(e->items[2]) ? nm_of(e->items[2]) : "?", nm_of(e->items[1])); }
    int ovf = 0; DcRat p[ND_MAXC], np[ND_MAXC], zero = dc_rat(0, 1, &ovf);
    for (int x = 0; x < ND_MAXC; x++) p[x] = zero;
    p[x0] = dc_rat(1, 1, &ovf);
    for (int k = 0; k < na; k++) {
        const NdMap *A = &s->map[acts[k]];
        for (int x = 0; x < ND_MAXC; x++) np[x] = zero;
        for (int x = 0; x < C->n; x++) {
            if (dc_rat_is_zero(p[x])) continue;
            DcRat share = dc_rat_div(p[x], dc_rat(popc(A->img[x]), 1, &ovf), &ovf);
            for (int y = 0; y < C->n; y++) if ((A->img[x] >> y) & 1) np[y] = dc_rat_add(np[y], share, &ovf);
        }
        memcpy(p, np, sizeof p);
    }
    DcRat tot = zero;
    for (int x = 0; x < C->n; x++) if (s->map[om].img[x] == ((NdSet)1 << v)) tot = dc_rat_add(tot, p[x], &ovf);
    if (ovf) { sx_free(word); return dc_unsupported(m, "%s: rational overflow (64-bit limit)", hd); }
    Sx *dist = dc_form("Distribution", NULL);
    for (int x = 0; x < C->n; x++) if (!dc_rat_is_zero(p[x])) sx_push(dist, dc_form(C->el[x], rsx(p[x]), NULL));
    return nd_env(m, VERDICT_HOLDS, q, mn, dc_form("Value", dc_form("Probability", rsx(tot), NULL), NULL),
                  dc_form("Evidence", word, dc_form("Scheduler", dc_sym(s->sch[si].name), dc_sym("Uniform"), NULL), dist, NULL), NULL);
}

/* ---- simulation: R is a simulation of Source by Target when related states agree on every
 * observer of Source (matched by name in Target, compared by value name) and every move
 * x -a-> x' of Source is matched by some y -a-> y' of Target with (x', y') in R. ---- */
typedef struct { int kind; int x, y, a, x2; char why[200]; } NdMiss;   /* kind 1: observer, 2: move */
static const char *nd_obsval(const NdMod *s, int map, int x) {   /* functional observer value name, NULL if not single */
    const NdMap *O = &s->map[map]; NdSet v = O->img[x];
    if (popc(v) != 1) return NULL;
    for (int k = 0; k < ND_MAXC; k++) if ((v >> k) & 1) return s->car[O->to].el[k];
    return NULL;
}
/* 0: holds, 1: fails (miss filled), -1: invalid (err filled) */
static int nd_simcheck(const NdMod *s, const NdSim *S, const NdSet *rel, NdMiss *ms, char *err, size_t es) {
    const NdMach *A = &s->mach[S->src], *B = &s->mach[S->tgt];
    int om[8], am[8];
    for (int i = 0; i < A->nobs; i++) {
        om[i] = nd_named(B->obs, B->nobs, A->obs[i].name);
        if (om[i] < 0) { snprintf(err, es, "observer %s of %s is not an observer of %s", A->obs[i].name, A->name, B->name); return -1; }
    }
    for (int i = 0; i < A->nact; i++) {
        am[i] = nd_named(B->act, B->nact, A->act[i].name);
        if (am[i] < 0) { snprintf(err, es, "action %s of %s is not an action of %s", A->act[i].name, A->name, B->name); return -1; }
    }
    const NdCar *CA = &s->car[A->states], *CB = &s->car[B->states];
    for (int x = 0; x < CA->n; x++) for (int y = 0; y < CB->n; y++) {
        if (!((rel[x] >> y) & 1)) continue;
        for (int i = 0; i < A->nobs; i++) {
            const char *va = nd_obsval(s, A->obs[i].map, x), *vb = nd_obsval(s, om[i], y);
            if (!va || !vb || strcmp(va, vb)) {
                ms->kind = 1; ms->x = x; ms->y = y; ms->a = i; ms->x2 = -1;
                snprintf(ms->why, sizeof ms->why, "observer %s: %s shows %s, %s shows %s", A->obs[i].name, CA->el[x], va ? va : "?", CB->el[y], vb ? vb : "?");
                return 1;
            }
        }
        for (int i = 0; i < A->nact; i++) {
            NdSet sx = s->map[A->act[i].map].img[x], sy = s->map[am[i]].img[y];
            for (int x2 = 0; x2 < CA->n; x2++) if ((sx >> x2) & 1) {
                int ok = 0;
                for (int y2 = 0; y2 < CB->n && !ok; y2++) if (((sy >> y2) & 1) && ((rel[x2] >> y2) & 1)) ok = 1;
                if (!ok) {
                    ms->kind = 2; ms->x = x; ms->y = y; ms->a = i; ms->x2 = x2;
                    snprintf(ms->why, sizeof ms->why, "move %s -%s-> %s has no matching move from %s", CA->el[x], A->act[i].name, CA->el[x2], CB->el[y]);
                    return 1;
                }
            }
        }
    }
    return 0;
}
static Sx *nd_misswit(const NdMod *s, const NdSim *S, const NdMiss *ms) {
    const NdMach *A = &s->mach[S->src], *B = &s->mach[S->tgt];
    const NdCar *CA = &s->car[A->states], *CB = &s->car[B->states];
    if (ms->kind == 1) return dc_form("Witness", dc_form("ObserverMismatch", dc_form("Pair", dc_sym(CA->el[ms->x]), dc_sym(CB->el[ms->y]), NULL),
                                                         dc_form("Observer", dc_sym(A->obs[ms->a].name), NULL), NULL), NULL);
    return dc_form("Witness", dc_form("UnmatchedMove", dc_form("Pair", dc_sym(CA->el[ms->x]), dc_sym(CB->el[ms->y]), NULL),
                                      dc_form("Action", dc_sym(A->act[ms->a].name), NULL), dc_form("Step", dc_sym(CA->el[ms->x2]), NULL), NULL), NULL);
}
static Sx *nd_pairs(const NdMod *s, const NdSim *S) {
    const NdCar *CA = &s->car[s->mach[S->src].states], *CB = &s->car[s->mach[S->tgt].states];
    Sx *l = dc_form("Pairs", NULL);
    for (int x = 0; x < CA->n; x++) for (int y = 0; y < CB->n; y++) if ((S->rel[x] >> y) & 1) sx_push(l, dc_form(CA->el[x], dc_sym(CB->el[y]), NULL));
    return l;
}
/* review 1 F1: the Simulation certificate (Table 1 row) carries, besides the pairs, one
 * matching move per related pair, action and source successor, so a replayer needs only
 * one membership check per move.  Call only after nd_simcheck returned 0. */
static Sx *nd_matches(const NdMod *s, const NdSim *S) {
    const NdMach *A = &s->mach[S->src], *B = &s->mach[S->tgt];
    const NdCar *CA = &s->car[A->states], *CB = &s->car[B->states];
    Sx *l = dc_form("Matches", NULL);
    for (int x = 0; x < CA->n; x++) for (int y = 0; y < CB->n; y++) {
        if (!((S->rel[x] >> y) & 1)) continue;
        for (int i = 0; i < A->nact; i++) {
            int bm = nd_named(B->act, B->nact, A->act[i].name); if (bm < 0) continue;   /* nd_named yields the map index */
            NdSet sx = s->map[A->act[i].map].img[x], sy = s->map[bm].img[y];
            for (int x2 = 0; x2 < CA->n; x2++) if ((sx >> x2) & 1)
                for (int y2 = 0; y2 < CB->n; y2++) if (((sy >> y2) & 1) && ((S->rel[x2] >> y2) & 1)) {
                    sx_push(l, dc_form("Match", dc_form("Pair", dc_sym(CA->el[x]), dc_sym(CB->el[y]), NULL), dc_form("Action", dc_sym(A->act[i].name), NULL),
                                       dc_form("Step", dc_sym(CA->el[x2]), NULL), dc_form("To", dc_sym(CB->el[y2]), NULL), NULL));
                    break;
                }
        }
    }
    return l;
}
static Sx *nd_simcert(const NdMod *s, const NdSim *S, NdSet init) {
    const NdCar *CA = &s->car[s->mach[S->src].states], *CB = &s->car[s->mach[S->tgt].states];
    Sx *c = dc_form("Certificate", dc_form("Kind", dc_sym("Simulation"), NULL), dc_form("Relation", dc_sym(S->name), NULL),
                    dc_form("Source", dc_sym(s->mach[S->src].name), NULL), dc_form("Target", dc_sym(s->mach[S->tgt].name), NULL), nd_pairs(s, S), nd_matches(s, S), NULL);
    if (!init) init = CA->n >= 64 ? ~(NdSet)0 : (((NdSet)1 << CA->n) - 1);   /* InitialStates AllDeclared */
    Sx *cov = dc_form("Coverage", NULL);   /* one related target per initial source state */
    for (int x = 0; x < CA->n; x++) if ((init >> x) & 1) {
        int y = -1; for (int k = 0; k < CB->n && y < 0; k++) if ((S->rel[x] >> k) & 1) y = k;
        if (y >= 0) sx_push(cov, dc_form("Covers", dc_sym(CA->el[x]), dc_sym(CB->el[y]), NULL));
    }
    sx_push(c, cov);
    return c;
}
/* review 1 F2: a budget is a work limit in a registered unit, never a horizon.
 * (Budget (PairExpansions k)) and the generic (Budget (Unit k)) count related pairs
 * examined; a bare k is read as PairExpansions.  Returns k >= 0; -1: not a budget
 * (e.g. (Steps k), a horizon form); -2: a registered unit this check does not count. */
static long nd_budget(const Sx *bu, const char **unit) {
    const Sx *v = bu->items[1]; const char *t = NULL; *unit = "PairExpansions";
    if (v->kind == SX_SYM) t = v->text;
    else if (v->kind == SX_LIST && v->n == 2 && v->items[0]->kind == SX_SYM && v->items[1]->kind == SX_SYM) {
        const char *u = v->items[0]->text; t = v->items[1]->text; *unit = u;
        if (strcmp(u, "PairExpansions") && strcmp(u, "Unit")) {
            static const char *reg[] = { "Probes", "Proposals", "Seconds", "Unrollings" };
            for (int i = 0; i < 4; i++) if (!strcmp(u, reg[i])) return -2;
            return -1;
        }
    }
    if (!t) return -1;
    char *e; long k = strtol(t, &e, 10);
    return (e == t || *e || k < 0) ? -1 : k;
}
/* H13, Y02: (CheckSimulation S [(Budget n)]) */
static Sx *nd_checksim_core(DcModule *m, const NdMod *s, const Sx *q) {
    const char *sn = q->n >= 2 ? nm_of(q->items[1]) : NULL; int si = nd_sim(s, sn); char err[256];
    if (si < 0) return dc_invalid(m, "CheckSimulation: names no declared Simulation (%s)", sn ? sn : "?");
    const NdSim *S = &s->sim[si]; NdMiss ms; memset(&ms, 0, sizeof ms);
    if (S->unsup[0]) return dc_unsupported(m, "CheckSimulation %s: %s", S->name, S->unsup);
    const Sx *bu = ropt(q, "Budget");
    if (bu) {   /* the budget bounds the related pairs examined */
        const char *bunit; long b = nd_budget(bu, &bunit); int np = 0;
        for (int x = 0; x < ND_MAXC; x++) np += popc(S->rel[x]);
        if (b == -2) return dc_unsupported(m, "CheckSimulation: budget unit %s is not counted by the simulation check (it counts PairExpansions)", bunit);
        if (b < 0) return dc_invalid(m, "CheckSimulation: (Budget %s k) needs a registered work unit (PairExpansions or Unit) and a natural k; a budget is never a horizon", bunit);
        if (np > b) {   /* budget exhausted: Unknown (no replayable evidence), never Checked */
            char w[160]; snprintf(w, sizeof w, "budget %ld is below the %d related pairs to examine", b, np);
            g_nd_rep = 0;
            Sx *res = nd_env_k(m, VERDICT_HOLDS, q, "Simulation", S->name, NULL, dc_form("Evidence", dc_form("Budget", dc_int(b), dc_int(np), NULL), NULL), w);
            g_nd_rep = 1; return res;
        }
    }
    int rc = nd_simcheck(s, S, S->rel, &ms, err, sizeof err);
    if (rc < 0) return dc_invalid(m, "CheckSimulation %s: %s", S->name, err);
    if (rc) return nd_env_k(m, VERDICT_FAILS, q, "Simulation", S->name, NULL, dc_form("Evidence", nd_misswit(s, S, &ms), NULL), ms.why);
    return nd_env_k(m, VERDICT_HOLDS, q, "Simulation", S->name, dc_form("Value", dc_sym("True"), NULL),
                    dc_form("Evidence", nd_simcert(s, S, 0), NULL), NULL);
}
/* ---- safety transfer along a simulation (H14, Y03, Y04): the three registered forms
 * (Shows o v), (EnterFrom X (Not Y)), (ReachWithin X k), each under Never. ---- */
typedef struct { int kind; NdSet X, Y; int k; const char *o, *v; } NdProp;   /* kind 1 Shows, 2 EnterFrom, 3 ReachWithin */
static int nd_bfs(const NdMod *s, const NdMach *M, NdSet init, const NdProp *P, int *par, int *pact, int *dep, int *bad, int *bact, int *bnxt) {
    const NdCar *C = &s->car[M->states]; int qu[ND_MAXC], h = 0, t = 0;
    for (int x = 0; x < C->n; x++) { par[x] = -1; pact[x] = -1; dep[x] = -1; if ((init >> x) & 1) { dep[x] = 0; qu[t++] = x; } }
    int om = P->kind == 1 ? nd_named(M->obs, M->nobs, P->o) : -1;
    *bact = -1; *bnxt = -1;
    while (h < t) {
        int x = qu[h++];
        if (P->kind == 1) { const char *v = om >= 0 ? nd_obsval(s, om, x) : NULL; if (v && !strcmp(v, P->v)) { *bad = x; return 1; } }
        else if (P->kind == 3) { if (((P->X >> x) & 1) && dep[x] <= P->k) { *bad = x; return 1; } }
        for (int a = 0; a < M->nact; a++) {
            NdSet sx = s->map[M->act[a].map].img[x];
            for (int y = 0; y < C->n; y++) if ((sx >> y) & 1) {
                if (P->kind == 2 && !((P->X >> x) & 1) && !((P->Y >> x) & 1) && ((P->X >> y) & 1)) { *bad = x; *bact = a; *bnxt = y; return 1; }
                if (dep[y] < 0) { dep[y] = dep[x] + 1; par[y] = x; pact[y] = a; qu[t++] = y; }
            }
        }
    }
    return 0;
}
/* states st[0..n-1] of the path to x (then the entering step), ac[i]: action index into st[i] (i >= 1) */
static int nd_trace(const int *par, const int *pact, int x, int ba, int bn, int *st, int *ac) {
    int tmp[ND_MAXC + 1], ta[ND_MAXC + 1], n = 0;
    for (int y = x; y >= 0 && n < ND_MAXC; y = par[y]) { tmp[n] = y; ta[n] = pact[y]; n++; }
    for (int i = 0; i < n; i++) { st[i] = tmp[n - 1 - i]; ac[i] = ta[n - 1 - i]; }
    if (ba >= 0) { st[n] = bn; ac[n] = ba; n++; }
    return n;
}
static Sx *nd_pathsx(const NdMod *s, const NdMach *M, const int *st, const int *ac, int n) {
    const NdCar *C = &s->car[M->states];
    Sx *p = dc_form("Path", dc_sym(C->el[st[0]]), NULL);
    for (int i = 1; i < n; i++) sx_push(p, dc_form("Step", dc_sym(M->act[ac[i]].name), dc_sym(C->el[st[i]]), NULL));
    return p;
}
static NdSet nd_pre(const NdSim *S, int nsrc, int y) { NdSet r = 0; for (int x = 0; x < nsrc; x++) if ((S->rel[x] >> y) & 1) r |= (NdSet)1 << x; return r; }
static NdSet nd_down(const NdSim *S, int nsrc, NdSet X) {   /* concrete states every image of which lies in X */
    NdSet r = 0; for (int x = 0; x < nsrc; x++) if (S->rel[x] && !(S->rel[x] & ~X)) r |= (NdSet)1 << x; return r;
}
static int nd_one(const NdCar *C, const Sx *x, NdSet *out) { int e = nd_el(C, nm_of(x)); if (e < 0) return -1; *out = (NdSet)1 << e; return 0; }
static void nd_bind(Sx *res, const NdMod *s, const NdSim *S, const Sx *init);
static Sx *nd_checksim(DcModule *m, const NdMod *s, const Sx *q) {
    Sx *r = nd_checksim_core(m, s, q);
    int si = nd_sim(s, q->n >= 2 ? nm_of(q->items[1]) : NULL);
    if (si >= 0 && r && sx_find(r, "Binding", 1)) nd_bind(r, s, &s->sim[si], NULL);
    return r;
}
static Sx *nd_safety_core(DcModule *m, const NdMod *s, const Sx *q) {
    const char *tn = q->n >= 2 ? nm_of(q->items[1]) : NULL; int ti = nd_mach(s, tn); char err[256];
    const Sx *nv = ropt(q, "Never");
    if (!nv) {
        static const char *const LIVE[] = { "Eventually", "Always", "Exists", "Reach", "Until", "Possibly", 0 };
        for (int k = 0; LIVE[k]; k++) if (ropt(q, LIVE[k])) return dc_unsupported(m, "CheckSafety: (%s ..) is a liveness or existential property; it is not transferred through a simulation", LIVE[k]);
        return dc_invalid(m, "CheckSafety: needs (Never property)");
    }
    if (ti < 0) return dc_invalid(m, "CheckSafety: names no declared Machine (%s)", tn ? tn : "?");
    const Sx *vi = ropt(q, "Via"); int si = vi ? nd_sim(s, nm_of(vi->items[1])) : -1;
    if (si < 0) return dc_invalid(m, "CheckSafety: (Via S) names no declared Simulation");
    const NdSim *S = &s->sim[si]; const NdMach *A = &s->mach[S->src], *B = &s->mach[S->tgt];
    if (S->unsup[0]) return dc_unsupported(m, "CheckSafety via %s: %s", S->name, S->unsup);
    if (S->tgt != ti) return dc_invalid(m, "CheckSafety: Simulation %s targets %s, not the request's target %s", S->name, B->name, tn);
    const NdCar *CA = &s->car[A->states], *CB = &s->car[B->states];
    const Sx *e = nv->items[1]; NdProp P; memset(&P, 0, sizeof P);
    if (sx_head_is(e, "Shows") && e->n == 3) {
        P.kind = 1; P.o = nm_of(e->items[1]); P.v = nm_of(e->items[2]);
        if (!P.o || !P.v || nd_named(B->obs, B->nobs, P.o) < 0 || nd_named(A->obs, A->nobs, P.o) < 0)
            return dc_invalid(m, "CheckSafety: (Shows o v) names no observer o shared by %s and %s", A->name, B->name);
    } else if (sx_head_is(e, "EnterFrom") && e->n == 3 && sx_head_is(e->items[2], "Not") && e->items[2]->n == 2) {
        P.kind = 2;
        if (nd_one(CB, e->items[1], &P.X) || nd_one(CB, e->items[2]->items[1], &P.Y)) return dc_invalid(m, "CheckSafety: EnterFrom names a state outside %s", CB->name);
    } else if (sx_head_is(e, "ReachWithin") && e->n == 3) {
        P.kind = 3; char *end = NULL;
        if (nd_one(CB, e->items[1], &P.X)) return dc_invalid(m, "CheckSafety: ReachWithin names a state outside %s", CB->name);
        P.k = e->items[2]->kind == SX_SYM ? (int)strtol(e->items[2]->text, &end, 10) : -1;
        if (P.k < 0 || !end || *end) return dc_invalid(m, "CheckSafety: (ReachWithin X k) needs a natural number k");
    } else {
        /* negative gate 2: liveness or existential properties are outside the universal fragment
         * that a simulation with initial coverage preserves: Unsupported, never transferred */
        static const char *const LIVE[] = { "Eventually", "Always", "Exists", "Reach", "Until", "Possibly", "Not", 0 };
        const char *eh = e->kind == SX_LIST && e->n ? nm_of(e->items[0]) : NULL;
        for (int k = 0; eh && LIVE[k]; k++) if (!strcmp(eh, LIVE[k]))
            return dc_unsupported(m, "CheckSafety: (Never (%s ..)) is a liveness or existential property; it is not transferred through a simulation", eh);
        return dc_unsupported(m, "CheckSafety: %s is not a registered safety form (Shows, EnterFrom, ReachWithin)", eh ? eh : "?");
    }
    const Sx *in = ropt(q, "Init"); NdSet I = 0;
    for (size_t k = 1; in && k < in->n; k++) { int x = nd_el(CA, nm_of(in->items[k])); if (x < 0) return dc_invalid(m, "CheckSafety: Init %s is not a state of %s", nm_of(in->items[k]) ? nm_of(in->items[k]) : "?", A->name); I |= (NdSet)1 << x; }
    if (!I) return dc_invalid(m, "CheckSafety: (Init s ..) names no state");
    const Sx *bu = ropt(q, "Budget");
    if (bu) {   /* review 1 F2: honour the budget; it bounds the related pairs examined, never a horizon */
        const char *bunit; long b = nd_budget(bu, &bunit); int np = 0;
        for (int x = 0; x < ND_MAXC; x++) np += popc(S->rel[x]);
        if (b == -2) return dc_unsupported(m, "CheckSafety: budget unit %s is not counted by the simulation check (it counts PairExpansions)", bunit);
        if (b < 0) return dc_invalid(m, "CheckSafety: (Budget %s k) needs a registered work unit (PairExpansions or Unit) and a natural k; a budget is never a horizon", bunit);
        if (np > b) {   /* budget exhausted: Unknown, never Checked */
            char w[160]; snprintf(w, sizeof w, "budget %ld is below the %d related pairs to examine", b, np);
            g_nd_rep = 0;
            Sx *r = nd_env(m, VERDICT_HOLDS, q, tn, NULL, dc_form("Evidence", dc_form("Budget", dc_int(b), dc_int(np), NULL), NULL), w);
            g_nd_rep = 1; return r;
        }
    }
    NdMiss ms; memset(&ms, 0, sizeof ms);
    int rc = nd_simcheck(s, S, S->rel, &ms, err, sizeof err);
    if (rc < 0) return dc_invalid(m, "CheckSafety via %s: %s", S->name, err);
    if (rc) { g_nd_rep = 0; Sx *r = nd_env(m, VERDICT_HOLDS, q, tn, NULL, dc_form("Evidence", nd_misswit(s, S, &ms), NULL), "the Via relation is not a simulation; nothing transfers"); g_nd_rep = 1; return r; }
    for (int x = 0; x < CA->n; x++) if (((I >> x) & 1) && !S->rel[x]) {   /* H14: initial coverage */
        char w[200]; snprintf(w, sizeof w, "initial state %s is outside the domain of %s; the simulation proves nothing (vacuous)", CA->el[x], S->name);
        g_nd_rep = 0;
        Sx *r = nd_env(m, VERDICT_HOLDS, q, tn, NULL, dc_form("Evidence", dc_form("Witness", dc_form("UncoveredInit", dc_sym(CA->el[x]), NULL), NULL), dc_form("Coverage", dc_sym("Vacuous"), NULL), NULL), w);
        g_nd_rep = 1; return r;
    }
    NdSet AI = 0; for (int x = 0; x < CA->n; x++) if ((I >> x) & 1) AI |= S->rel[x];
    int par[ND_MAXC], pact[ND_MAXC], dep[ND_MAXC], bad = -1, ba = -1, bn = -1;
    if (!nd_bfs(s, B, AI, &P, par, pact, dep, &bad, &ba, &bn)) {
        Sx *re = dc_form("Reachable", NULL);
        for (int y = 0; y < CB->n; y++) if (dep[y] >= 0) sx_push(re, dc_sym(CB->el[y]));
        return nd_env(m, VERDICT_HOLDS, q, tn, dc_form("Value", dc_sym("True"), NULL),
                      dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("SafetyTransfer"), NULL), dc_form("Via", dc_sym(S->name), NULL),
                                                  dc_form("InitCovered", dc_sym("True"), NULL), re, nd_simcert(s, S, I), NULL), NULL), NULL);
    }
    int ys[ND_MAXC + 1], as[ND_MAXC + 1], L = nd_trace(par, pact, bad, ba, bn, ys, as);
    Sx *acx = dc_form("AbstractCounterexample", nd_pathsx(s, B, ys, as, L), NULL);
    /* concrete check: the property pulled back along the relation, explored on the source */
    NdProp PC = P; PC.X = nd_down(S, CA->n, P.X); PC.Y = nd_down(S, CA->n, P.Y);
    int cpar[ND_MAXC], cpact[ND_MAXC], cdep[ND_MAXC], cb = -1, cba = -1, cbn = -1;
    if (nd_bfs(s, A, I, &PC, cpar, cpact, cdep, &cb, &cba, &cbn)) {
        int xs[ND_MAXC + 1], xa[ND_MAXC + 1], n = nd_trace(cpar, cpact, cb, cba, cbn, xs, xa);
        sx_free(acx);
        return nd_env(m, VERDICT_FAILS, q, tn, NULL, dc_form("Evidence", dc_form("Witness", dc_form("ConcreteCounterexample", nd_pathsx(s, A, xs, xa, n), NULL), NULL), NULL),
                      "a concrete run from Init violates the property");
    }
    /* spurious: find where the concrete runs leave the abstract path, and split that abstract state */
    Sx *ev = dc_form("Evidence", acx, dc_form("Spurious", dc_sym("True"), NULL), NULL);
    NdSet Cc = I & nd_pre(S, CA->n, ys[0]); int cut = -1, cam = -1;
    for (int i = 1; i < L; i++) {
        int ca = nd_named(A->act, A->nact, B->act[as[i]].name);
        NdSet nx = ca >= 0 ? nd_post(&s->map[ca], Cc) & nd_pre(S, CA->n, ys[i]) : 0;
        if (!nx) { cut = i; cam = ca; break; }
        Cc = nx;
    }
    if (cut > 0) {
        NdSet Pr = nd_pre(S, CA->n, ys[cut - 1]), tgt = nd_pre(S, CA->n, ys[cut]), good = 0;
        for (int x = 0; x < CA->n; x++) if (((Pr >> x) & 1) && cam >= 0 && (s->map[cam].img[x] & tgt)) good |= (NdSet)1 << x;
        Sx *g = dc_form("CanStep", NULL), *b = dc_form("CannotStep", NULL);
        for (int x = 0; x < CA->n; x++) if ((Pr >> x) & 1) sx_push((good >> x) & 1 ? g : b, dc_sym(CA->el[x]));
        sx_push(ev, dc_form("Refinement", dc_form("Split", dc_sym(CB->el[ys[cut - 1]]), NULL), dc_form("Action", dc_sym(B->act[as[cut]].name), NULL), g, b, NULL));
    }
    if (P.kind == 3) {   /* how far the pulled-back target set really is */
        NdProp PR = PC; PR.k = 1 << 20;
        if (nd_bfs(s, A, I, &PR, cpar, cpact, cdep, &cb, &cba, &cbn)) sx_push(ev, dc_form("ConcreteSteps", dc_int(cdep[cb]), NULL));
    }
    g_nd_rep = 0;
    Sx *r = nd_env(m, VERDICT_HOLDS, q, tn, NULL, ev, "the abstract counterexample is spurious; refinement splits an abstract state, so the declared abstraction proves nothing");
    g_nd_rep = 1; return r;
}

/* Y01: (InduceExact R) on (Representation R (Of M) (Encode e)): the quotient by e is exact when
 * states with one code have successor sets with one code set, for every action of M.  Otherwise
 * Refuted with the witness (x x' action code(x a) code(x' a)). */
/* review 1 F4: bind Source/Target to the simulation's machines and record the
 * requested initial states in the Scope instead of AllDeclared. */
static void nd_bind(Sx *res, const NdMod *s, const NdSim *S, const Sx *init) {
    if (!res || !S) return;
    dc_result_bind_models(res, s->mach[S->src].name, s->mach[S->tgt].name);
    if (!init) return;
    Sx *sc = (Sx *)sx_find(res, "Scope", 1), *is = sc ? (Sx *)sx_find(sc, "InitialStates", 1) : NULL;
    if (!is || is->n != 2 || init->n < 2) return;
    sx_free(is->items[1]); is->items[1] = sx_sym(init->items[1]->kind == SX_SYM ? init->items[1]->text : "?");
    for (size_t k = 2; k < init->n; k++) sx_push(is, sx_sym(init->items[k]->kind == SX_SYM ? init->items[k]->text : "?"));
}
static Sx *nd_safety(DcModule *m, const NdMod *s, const Sx *q) {
    Sx *r = nd_safety_core(m, s, q);
    const Sx *vi = ropt(q, "Via"); int si = vi ? nd_sim(s, nm_of(vi->items[1])) : -1;
    if (si >= 0 && r && sx_find(r, "Binding", 1)) nd_bind(r, s, &s->sim[si], ropt(q, "Init"));
    return r;
}
static Sx *nd_induce(DcModule *m, const NdMod *s, const Sx *q) {
    const char *rn = q->n >= 2 ? nm_of(q->items[1]) : NULL; const Sx *d = NULL;
    for (size_t i = 2; rn && m->source && i < m->source->n; i++) {
        const Sx *x = m->source->items[i];
        if (sx_head_is(x, "Representation") && x->n >= 2 && nm_of(x->items[1]) && !strcmp(x->items[1]->text, rn)) d = x;
    }
    if (!d) return dc_invalid(m, "InduceExact: names no declared Representation (%s)", rn ? rn : "?");
    int mi = nd_mach(s, fld1(d, "Of")), ei = nd_map(s, fld1(d, "Encode"));
    if (mi < 0 || ei < 0) return dc_invalid(m, "InduceExact %s: (Of M) or (Encode e) names nothing declared", rn);
    const NdMach *M = &s->mach[mi]; const NdMap *E = &s->map[ei];
    if (E->from != M->states || E->choice) return dc_invalid(m, "InduceExact %s: Encode %s is not a function on the states of %s", rn, E->name, M->name);
    const NdCar *C = &s->car[M->states], *K = &s->car[E->to];
    for (int x = 0; x < C->n; x++) for (int z = x + 1; z < C->n; z++) {
        if (E->img[x] != E->img[z]) continue;
        for (int a = 0; a < M->nact; a++) {
            const NdMap *A = &s->map[M->act[a].map];
            NdSet cx = nd_post(E, A->img[x]), cz = nd_post(E, A->img[z]);
            if (cx == cz) continue;
            Sx *vx = dc_form("Codes", NULL), *vz = dc_form("Codes", NULL);
            for (int k = 0; k < K->n; k++) { if ((cx >> k) & 1) sx_push(vx, dc_sym(K->el[k])); if ((cz >> k) & 1) sx_push(vz, dc_sym(K->el[k])); }
            char w[240]; snprintf(w, sizeof w, "%s and %s share a code but %s leads to different codes", C->el[x], C->el[z], M->act[a].name);
            Sx *wit = dc_form("Witness", dc_form("ExactnessFailure", dc_form("States", dc_sym(C->el[x]), dc_sym(C->el[z]), NULL),
                                                  dc_form("Action", dc_sym(M->act[a].name), NULL), vx, vz, NULL), NULL);
            return nd_env_k(m, VERDICT_FAILS, q, "Representation", rn, NULL, dc_form("Evidence", wit, NULL), w);
        }
    }
    return nd_env_k(m, VERDICT_HOLDS, q, "Representation", rn, dc_form("Value", dc_sym("True"), NULL),
                    dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("ExactQuotient"), NULL), dc_form("Encode", dc_sym(E->name), NULL), NULL), NULL), NULL);
}

/* ---- m5-rest: strong bisimulation on a nondeterministic machine (spec 1377-1379, 2550-2553).
 * Partition refinement from the observer partition (level 0: equal observer image sets; level l:
 * equal level l-1 block sets under every action). A pair first split at level l is told apart by
 * a Hennessy-Milner formula graph with shared subformulas (ModalTestWitness, spec 5058):
 * (Indicator o v) holds at x iff v is in o's image of x; (Not k); (And k..), empty = true;
 * (Diamond a k) holds at x iff some a-successor of x satisfies k. Node names are beyond registry. ---- */
#define ND_MAXF (3 * ND_MAXC * ND_MAXC)
typedef struct { const NdMod *s; const NdMach *M; int n, L; int blk[ND_MAXC + 1][ND_MAXC]; int memo[ND_MAXC][ND_MAXC];
                 Sx *body[ND_MAXF]; NdSet sat[ND_MAXF]; int nn, bad; } NdBis;
static NdSet nd_blkset(const int *blk, NdSet X, int n) { NdSet r = 0; for (int y = 0; y < n; y++) if ((X >> y) & 1) r |= (NdSet)1 << blk[y]; return r; }
static void nd_bis_refine(NdBis *B) {
    const NdMod *s = B->s; const NdMach *M = B->M; int n = B->n;
    for (int x = 0; x < n; x++) { B->blk[0][x] = x;
        for (int y = 0; y < x; y++) { int same = 1;
            for (int j = 0; j < M->nobs; j++) if (s->map[M->obs[j].map].img[x] != s->map[M->obs[j].map].img[y]) same = 0;
            if (same) { B->blk[0][x] = B->blk[0][y]; break; } } }
    for (int l = 1; l <= n; l++) {
        for (int x = 0; x < n; x++) { B->blk[l][x] = x;
            for (int y = 0; y < x; y++) { if (B->blk[l - 1][x] != B->blk[l - 1][y]) continue; int same = 1;
                for (int a = 0; a < M->nact && same; a++) { const NdMap *A = &s->map[M->act[a].map];
                    if (nd_blkset(B->blk[l - 1], A->img[x], n) != nd_blkset(B->blk[l - 1], A->img[y], n)) same = 0; }
                if (same) { B->blk[l][x] = B->blk[l][y]; break; } } }
        if (!memcmp(B->blk[l], B->blk[l - 1], sizeof B->blk[l])) { B->L = l - 1; return; }
    }
    B->L = n;
}
static int nd_fnode(NdBis *B, Sx *body, NdSet sat) {
    if (B->nn >= ND_MAXF) { B->bad = 1; sx_free(body); return 0; }
    B->body[B->nn] = body; B->sat[B->nn] = sat; return B->nn++;
}
static int nd_dist(NdBis *B, int x, int y, int depth) {
    if (B->memo[x][y] >= 0) return B->memo[x][y];
    if (depth > 2 * ND_MAXC + 4 || B->bad) { B->bad = 1; return 0; }
    const NdMod *s = B->s; const NdMach *M = B->M; int n = B->n, l = 0, k = -1;
    NdSet all = n >= 64 ? ~(NdSet)0 : (((NdSet)1 << n) - 1);
    while (l <= B->L && B->blk[l][x] == B->blk[l][y]) l++;
    if (l > B->L) { B->bad = 1; return 0; }   /* bisimilar: no formula exists */
    if (l == 0) {
        for (int j = 0; j < M->nobs && k < 0; j++) { const NdMap *O = &s->map[M->obs[j].map]; NdSet d = O->img[x] & ~O->img[y];
            if (!d) continue;
            int v = __builtin_ctzll(d); NdSet st = 0;
            for (int z = 0; z < n; z++) if ((O->img[z] >> v) & 1) st |= (NdSet)1 << z;
            k = nd_fnode(B, dc_form("Indicator", dc_sym(M->obs[j].name), dc_sym(s->car[O->to].el[v]), NULL), st); }
    } else {
        for (int a = 0; a < M->nact && k < 0; a++) { const NdMap *A = &s->map[M->act[a].map];
            for (int x2 = 0; x2 < n && k < 0; x2++) { if (!((A->img[x] >> x2) & 1)) continue; int ok = 1;
                for (int y2 = 0; y2 < n; y2++) if (((A->img[y] >> y2) & 1) && B->blk[l - 1][y2] == B->blk[l - 1][x2]) ok = 0;
                if (!ok) continue;
                Sx *conj = dc_form("And", NULL); NdSet cs = all;
                for (int y2 = 0; y2 < n; y2++) if ((A->img[y] >> y2) & 1) { int c = nd_dist(B, x2, y2, depth + 1); sx_push(conj, dc_int(c)); cs &= B->sat[c]; }
                int c = nd_fnode(B, conj, cs); NdSet ds = 0;
                for (int z = 0; z < n; z++) if (A->img[z] & B->sat[c]) ds |= (NdSet)1 << z;
                k = nd_fnode(B, dc_form("Diamond", dc_sym(M->act[a].name), dc_int(c), NULL), ds); } }
    }
    if (k < 0) { int c = nd_dist(B, y, x, depth + 1); k = nd_fnode(B, dc_form("Not", dc_int(c), NULL), all & ~B->sat[c]); }
    return B->memo[x][y] = k;
}
static Sx *nd_part(const NdBis *B, const NdCar *C, int *nb) {
    Sx *part = dc_form("Partition", NULL); *nb = 0;
    for (int b = 0; b < B->n; b++) { if (B->blk[B->L][b] != b) continue; Sx *bl = dc_form("Block", NULL);
        for (int x = 0; x < B->n; x++) if (B->blk[B->L][x] == b) sx_push(bl, dc_sym(C->el[x]));
        sx_push(part, bl); (*nb)++; }
    return part;
}
static const char *nd_bis_setup(NdBis *B, const NdMod *s, int mi) {
    static char why[200]; const NdMach *M = &s->mach[mi];
    memset(B, 0, sizeof *B); memset(B->memo, -1, sizeof B->memo);
    B->s = s; B->M = M; B->n = s->car[M->states].n;
    for (int a = 0; a < M->nact; a++) { const NdMap *A = &s->map[M->act[a].map];
        if (A->from != M->states || A->to != M->states) { snprintf(why, sizeof why, "Action map %s is not States -> States", A->name); return why; } }
    for (int j = 0; j < M->nobs; j++) if (s->map[M->obs[j].map].from != M->states) { snprintf(why, sizeof why, "observer map %s is not on States", s->map[M->obs[j].map].name); return why; }
    nd_bis_refine(B); return NULL;
}
/* (BehavioralTolerance M) -> the coarsest bisimulation; (CheckBehavioral R [(Discount 1)]
 * [(Horizon AllFiniteWords)] [(Within 0)]) on a Representation R: Holds iff every same-code pair is
 * bisimilar, else a ModalTestWitness for the first such pair. Other options: Unsupported. */
static Sx *nd_haus(DcModule *m, const NdMod *s, const Sx *q);
static Sx *nd_bisim(DcModule *m, const NdMod *s, const Sx *q, int chk) {
    const char *hd = q->items[0]->text, *a1 = q->n >= 2 ? nm_of(q->items[1]) : NULL, *e;
    static NdBis B; int nb = 0;
    if (!chk) {
        int mi = nd_mach(s, a1);
        if (mi < 0) return dc_invalid(m, "%s: names no declared Machine (%s)", hd, a1 ? a1 : "?");
        if (q->n > 2) return dc_unsupported(m, "%s: options are not implemented for Profile Nondeterministic", hd);
        if ((e = nd_bis_setup(&B, s, mi))) return dc_invalid(m, "%s %s: %s", hd, a1, e);
        Sx *part = nd_part(&B, &s->car[s->mach[mi].states], &nb);
        return nd_env(m, VERDICT_HOLDS, q, a1, dc_form("Value", dc_form("Bisimulation", part, dc_form("Classes", dc_int(nb), NULL), NULL), NULL),
                      dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("PartitionRefinement"), NULL), dc_form("Rounds", dc_int(B.L), NULL), NULL), NULL), NULL);
    }
    for (size_t i = 2; i < q->n; i++) { const Sx *o = q->items[i]; const char *oh = o->n ? nm_of(o->items[0]) : NULL; DcRat g;
        if (oh && !strcmp(oh, "Horizon") && o->n == 2 && nm_of(o->items[1]) && !strcmp(o->items[1]->text, "AllFiniteWords")) continue;
        if (oh && (!strcmp(oh, "Discount") || !strcmp(oh, "Within")) && o->n == 2 && !dc_sx_rat(o->items[1], &g)) {
            if (g.n == (strcmp(oh, "Discount") ? 0 : g.d)) continue;
            return nd_haus(m, s, q); }
        return nd_haus(m, s, q);
    }
    const Sx *d = NULL;
    for (size_t i = 2; a1 && m->source && i < m->source->n; i++) { const Sx *x = m->source->items[i];
        if (sx_head_is(x, "Representation") && x->n >= 2 && nm_of(x->items[1]) && !strcmp(x->items[1]->text, a1)) d = x; }
    if (!d) return dc_invalid(m, "%s: names no declared Representation (%s)", hd, a1 ? a1 : "?");
    int mi = nd_mach(s, fld1(d, "Of")), ei = nd_map(s, fld1(d, "Encode"));
    if (mi < 0 || ei < 0) return dc_invalid(m, "%s %s: (Of M) or (Encode e) names nothing declared", hd, a1);
    const NdMach *M = &s->mach[mi]; const NdMap *E = &s->map[ei]; const NdCar *C = &s->car[M->states];
    if (E->from != M->states || E->choice) return dc_invalid(m, "%s %s: Encode %s is not a function on the states of %s", hd, a1, E->name, M->name);
    if ((e = nd_bis_setup(&B, s, mi))) return dc_invalid(m, "%s %s: %s", hd, a1, e);
    for (int x = 0; x < C->n; x++) for (int z = x + 1; z < C->n; z++) {
        if (E->img[x] != E->img[z] || B.blk[B.L][x] == B.blk[B.L][z]) continue;
        int root = nd_dist(&B, x, z, 0);
        if (B.bad || !((B.sat[root] >> x) & 1) || ((B.sat[root] >> z) & 1)) {   /* self-check: refuse, never emit a wrong witness */
            for (int k = 0; k < B.nn; k++) sx_free(B.body[k]);
            return dc_unsupported(m, "%s %s: distinguishing formula construction failed its self-check", hd, a1); }
        Sx *fg = dc_form("Formula", dc_form("Root", dc_int(root), NULL), NULL);
        for (int k = 0; k < B.nn; k++) sx_push(fg, dc_form("Node", dc_int(k), B.body[k], NULL));
        char w[240]; snprintf(w, sizeof w, "%s and %s share a code but are not bisimilar", C->el[x], C->el[z]);
        Sx *wit = dc_form("Witness", dc_form("ModalTestWitness", dc_form("Pair", dc_sym(C->el[x]), dc_sym(C->el[z]), NULL), fg,
                                               dc_form("Left", dc_sym("True"), NULL), dc_form("Right", dc_sym("False"), NULL), NULL), NULL);
        return nd_env_k(m, VERDICT_FAILS, q, "Representation", a1, NULL, dc_form("Evidence", wit, NULL), w);
    }
    Sx *part = nd_part(&B, C, &nb);
    return nd_env_k(m, VERDICT_HOLDS, q, "Representation", a1, dc_form("Value", dc_sym("True"), NULL),
                    dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("Bisimulation"), NULL), dc_form("Encode", dc_sym(E->name), NULL), part, NULL), NULL), NULL);
}

/* ---- m5-rest: may-trace equivalence on a Representation (spec 1068-1073: for nondeterministic
 * machines only the crisp claim is defined, equal sets of possible observation traces under every
 * word; 2554-2556: PSPACE-complete, reported under a budget). Subset-pair exploration: a pair
 * (X, Z) holds the states each side may occupy before the next observation; observation vector y
 * filters both, action a takes post-images. A pair where exactly one filtered side is empty yields a
 * may-trace word (MayTraceWitness, name beyond registry). Exhausted budget or pair table: Unknown. ---- */
#define ND_MAXY 256
#define ND_TCAP 4096
typedef struct { NdSet x, z; int par, y, a, d; } NdTP;
static NdTP g_tp[ND_TCAP];
static int nd_obsvecs(const NdMod *s, const NdMach *M, int n, int vec[ND_MAXY][8], NdSet *mask) {
    int ny = 0;
    for (int x = 0; x < n; x++) {
        int cnt[8], el[8][64], idx[8] = {0}, empty = 0;
        for (int j = 0; j < M->nobs; j++) { NdSet I = s->map[M->obs[j].map].img[x]; cnt[j] = 0;
            for (int b = 0; b < 64; b++) if ((I >> b) & 1) el[j][cnt[j]++] = b;
            if (!cnt[j]) empty = 1; }
        if (empty) continue;
        for (;;) {
            int v[8] = {0}, y;
            for (int j = 0; j < M->nobs; j++) v[j] = el[j][idx[j]];
            for (y = 0; y < ny; y++) if (!memcmp(vec[y], v, sizeof(int) * (size_t)M->nobs)) break;
            if (y == ny) { if (ny >= ND_MAXY) return -1; memcpy(vec[ny], v, sizeof v); mask[ny++] = 0; }
            mask[y] |= (NdSet)1 << x;
            int j = 0;
            while (j < M->nobs && ++idx[j] == cnt[j]) idx[j++] = 0;
            if (j == M->nobs) break;
        }
    }
    return ny;
}
static int nd_tp_put(int *ht, int *np, NdSet X, NdSet Z, int par, int y, int a, int d) {
    uint64_t h = (X * 0x9E3779B97F4A7C15ULL) ^ ((Z + 0x632BE59BD9B4E019ULL) * 0xC2B2AE3D27D4EB4FULL);
    for (unsigned k = (unsigned)(h >> 50);; k = (k + 1) & 16383u) {
        if (ht[k] < 0) { if (*np >= ND_TCAP) return -1; NdTP t = { X, Z, par, y, a, d }; g_tp[*np] = t; ht[k] = (*np)++; return 1; }
        if (g_tp[ht[k]].x == X && g_tp[ht[k]].z == Z) return 0;
    }
}
static Sx *nd_shows(const NdMod *s, const NdMach *M, const int *v) {
    Sx *r = dc_form("Shows", NULL);
    for (int j = 0; j < M->nobs; j++) sx_push(r, dc_form(M->obs[j].name, dc_sym(s->car[s->map[M->obs[j].map].to].el[v[j]]), NULL));
    return r;
}
static Sx *nd_states(const char *h, const NdCar *C, NdSet X) {
    Sx *r = dc_form(h, NULL);
    for (int x = 0; x < C->n; x++) if ((X >> x) & 1) sx_push(r, dc_sym(C->el[x]));
    return r;
}
static Sx *nd_maytrace(DcModule *m, const NdMod *s, const Sx *q) {
    const char *hd = q->items[0]->text, *a1 = q->n >= 2 ? nm_of(q->items[1]) : NULL;
    if (!strcmp(hd, "MeasureTrace")) return dc_unsupported(m, "MeasureTrace: for nondeterministic machines only the crisp claim (CheckTrace, may-trace equivalence) is defined (spec 1072-1073)");
    long long budget = -1; int hor = -1;
    for (size_t i = 2; i < q->n; i++) { const Sx *o = q->items[i]; const char *oh = o->n ? nm_of(o->items[0]) : NULL;
        const Sx *v = oh && o->n == 2 ? o->items[1] : NULL; DcRat g;
        if (v && !strcmp(oh, "Horizon") && nm_of(v) && !strcmp(v->text, "AllFiniteWords")) continue;
        if (v && !strcmp(oh, "Horizon") && sx_head_is(v, "Steps") && v->n == 2 && !dc_sx_rat(v->items[1], &g) && g.d == 1 && g.n >= 0 && g.n <= 64) { hor = (int)g.n; continue; }
        if (v && !strcmp(oh, "Policies") && nm_of(v) && !strcmp(v->text, "Words")) continue;
        if (v && !strcmp(oh, "Within") && !dc_sx_rat(v, &g) && g.n == 0) continue;
        if (v && !strcmp(oh, "Budget") && sx_head_is(v, "PairExpansions") && v->n == 2 && !dc_sx_rat(v->items[1], &g) && g.d == 1 && g.n >= 0) { budget = g.n; continue; }
        return dc_unsupported(m, "%s: option %s is not implemented for Profile Nondeterministic (crisp may-trace only)", hd, oh ? oh : "?");
    }
    const Sx *d = NULL;
    for (size_t i = 2; a1 && m->source && i < m->source->n; i++) { const Sx *x = m->source->items[i];
        if (sx_head_is(x, "Representation") && x->n >= 2 && nm_of(x->items[1]) && !strcmp(x->items[1]->text, a1)) d = x; }
    if (!d) return dc_invalid(m, "%s: names no declared Representation (%s)", hd, a1 ? a1 : "?");
    int mi = nd_mach(s, fld1(d, "Of")), ei = nd_map(s, fld1(d, "Encode"));
    if (mi < 0 || ei < 0) return dc_invalid(m, "%s %s: (Of M) or (Encode e) names nothing declared", hd, a1);
    const NdMach *M = &s->mach[mi]; const NdMap *E = &s->map[ei]; const NdCar *C = &s->car[M->states];
    if (E->from != M->states || E->choice) return dc_invalid(m, "%s %s: Encode %s is not a function on the states of %s", hd, a1, E->name, M->name);
    for (int a = 0; a < M->nact; a++) { const NdMap *A = &s->map[M->act[a].map];
        if (A->from != M->states || A->to != M->states) return dc_invalid(m, "%s %s: Action map %s is not States -> States", hd, a1, A->name); }
    if (M->nobs > 8) return dc_unsupported(m, "%s %s: more than 8 observers", hd, a1);
    static int vec[ND_MAXY][8], ht[16384]; NdSet mk[ND_MAXY];
    int n = C->n, ny = nd_obsvecs(s, M, n, vec, mk), np = 0, hit = -1, hy = -1, over = 0; long long exp = 0;
    if (ny < 0) return dc_unsupported(m, "%s %s: more than %d distinct observation vectors", hd, a1, ND_MAXY);
    for (int k = 0; k < 16384; k++) ht[k] = -1;
    for (int x = 0; x < n && !over; x++) for (int z = x + 1; z < n && !over; z++)
        if (E->img[x] == E->img[z] && nd_tp_put(ht, &np, (NdSet)1 << x, (NdSet)1 << z, -1, -1, -1, 0) < 0) over = 2;
    for (int i = 0; i < np && hit < 0 && !over; i++) {
        if (budget >= 0 && exp >= budget) { over = 1; break; }
        exp++;
        for (int y = 0; y < ny && hit < 0 && !over; y++) {
            NdSet X = g_tp[i].x & mk[y], Z = g_tp[i].z & mk[y];
            if (!X && !Z) continue;
            if (!X || !Z) { hit = i; hy = y; break; }
            if (hor >= 0 && g_tp[i].d >= hor) continue;
            for (int a = 0; a < M->nact && !over; a++) { const NdMap *A = &s->map[M->act[a].map];
                NdSet X2 = nd_post(A, X), Z2 = nd_post(A, Z);
                if ((X2 || Z2) && nd_tp_put(ht, &np, X2, Z2, i, y, a, g_tp[i].d + 1) < 0) over = 2; }
        }
    }
    if (hit >= 0) {
        int chain[ND_TCAP], nc = 0;
        for (int c = hit; c >= 0; c = g_tp[c].par) chain[nc++] = c;
        const NdTP *s0 = &g_tp[chain[nc - 1]]; int x = __builtin_ctzll(s0->x), z = __builtin_ctzll(s0->z);
        Sx *word = dc_form("Word", NULL), *tr = dc_form("Trace", NULL);
        for (int k = nc - 2; k >= 0; k--) { const NdTP *t = &g_tp[chain[k]];
            sx_push(tr, nd_shows(s, M, vec[t->y])); sx_push(tr, dc_sym(M->act[t->a].name)); sx_push(word, dc_sym(M->act[t->a].name)); }
        sx_push(tr, nd_shows(s, M, vec[hy]));
        int lx = (g_tp[hit].x & mk[hy]) != 0;
        char w[240]; snprintf(w, sizeof w, "%s and %s share a code but only %s can show this observation trace", C->el[x], C->el[z], lx ? C->el[x] : C->el[z]);
        Sx *wit = dc_form("Witness", dc_form("MayTraceWitness", dc_form("Pair", dc_sym(C->el[x]), dc_sym(C->el[z]), NULL), word, tr,
                                             dc_form("Left", dc_sym(lx ? "True" : "False"), NULL), dc_form("Right", dc_sym(lx ? "False" : "True"), NULL), NULL), NULL);
        return nd_env_k(m, VERDICT_FAILS, q, "Representation", a1, NULL, dc_form("Evidence", wit, NULL), w);
    }
    if (over) {
        char w[240]; snprintf(w, sizeof w, over == 1 ? "may-trace exploration stopped at the budget of %lld pair expansions with no difference found" : "may-trace exploration stopped at this implementation's limit of %lld pairs with no difference found",
                              over == 1 ? budget : (long long)ND_TCAP);
        g_nd_rep = 0;
        Sx *r = nd_env_k(m, VERDICT_HOLDS, q, "Representation", a1, NULL, dc_form("Evidence", dc_form("Explored", dc_form("PairExpansions", dc_int(exp), NULL), dc_form("Pairs", dc_int(np), NULL), NULL), NULL), w);
        g_nd_rep = 1; return r;
    }
    Sx *ps = dc_form("Pairs", NULL);
    for (int i = 0; i < np; i++) sx_push(ps, dc_form("P", dc_int(g_tp[i].d), nd_states("Left", C, g_tp[i].x), nd_states("Right", C, g_tp[i].z), NULL));
    return nd_env_k(m, VERDICT_HOLDS, q, "Representation", a1, dc_form("Value", dc_sym("True"), NULL),
                    dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("MayTraceSubsetPairs"), NULL), dc_form("Horizon", hor >= 0 ? dc_form("Steps", dc_int(hor), NULL) : dc_sym("AllFiniteWords"), NULL), ps, NULL), NULL), NULL);
}

/* ---- m5-rest: discounted behavioral distance on a nondeterministic machine (spec 951 Hausdorff
 * lifting, Def 4.1, Def 4.9 tests with the gamma-max modality, Prop 4.10(1)(3)). With functional
 * observers d^g(x,y) = g^s, s the first refinement round that splits x and y (0 when never split);
 * through (Horizon (Steps h)) only rounds s <= h count. Lower certificate: a test phi with
 * phi(x) - phi(y) = g^s; nodes Indicator, Not, Min (empty = 1), Sub (max(0, phi - r)), Diamond a k g
 * (g times the max over a-successors, 0 when none). Upper certificate: kernel layers with, per pair and
 * action, a forward and a backward matching (Prop 4.10(3)); one side without successors needs K >= g.
 * Node and Kind names are beyond registry. (Budget (Unrollings k)) below the stabilizing round: Unknown. ---- */
typedef struct { NdBis *B; DcRat g, gp[ND_MAXC + 3], zero, one; int memo[ND_MAXC][ND_MAXC]; DcRat *V; int nn, bad, ovf; Sx *body[ND_MAXF]; } NdQt;
#define QV(T, k, z) ((T)->V[(size_t)(k) * ND_MAXC + (size_t)(z)])
static int nd_split(const NdBis *B, int x, int y) { int l = 0; while (l <= B->L && B->blk[l][x] == B->blk[l][y]) l++; return l; }
static DcRat nd_dval(const NdQt *T, int x, int y, int h) {   /* h < 0: the fixed point */
    int sl = nd_split(T->B, x, y);
    return (sl > T->B->L || (h >= 0 && sl > h)) ? T->zero : T->gp[sl];
}
static int nd_qnode(NdQt *T, Sx *body) {
    if (T->nn >= ND_MAXF) { T->bad = 1; sx_free(body); return -1; }
    T->body[T->nn] = body; return T->nn++;
}
static int nd_qt(NdQt *T, int x, int y, int depth) {
    NdBis *B = T->B; const NdMod *s = B->s; const NdMach *M = B->M; int n = B->n, k = -1;
    if (T->memo[x][y] >= 0) return T->memo[x][y];
    if (T->bad || depth > 2 * ND_MAXC + 4) { T->bad = 1; return -1; }
    int sl = nd_split(B, x, y);
    if (sl > B->L) { T->bad = 1; return -1; }
    if (sl == 0) {
        for (int j = 0; j < M->nobs && k < 0; j++) { const NdMap *O = &s->map[M->obs[j].map]; NdSet d = O->img[x] & ~O->img[y];
            if (!d) continue;
            int v = __builtin_ctzll(d);
            if ((k = nd_qnode(T, dc_form("Indicator", dc_sym(M->obs[j].name), dc_sym(s->car[O->to].el[v]), NULL))) < 0) return -1;
            for (int z = 0; z < n; z++) QV(T, k, z) = ((O->img[z] >> v) & 1) ? T->one : T->zero;
        }
    } else {
        for (int a = 0; a < M->nact && k < 0; a++) { const NdMap *A = &s->map[M->act[a].map];
            for (int x2 = 0; x2 < n && k < 0; x2++) {
                if (!((A->img[x] >> x2) & 1)) continue;
                int ok = 1;
                for (int y2 = 0; y2 < n; y2++) if (((A->img[y] >> y2) & 1) && B->blk[sl - 1][y2] == B->blk[sl - 1][x2]) ok = 0;
                if (!ok) continue;
                int ch[ND_MAXC], nc = 0;
                for (int y2 = 0; y2 < n; y2++) if ((A->img[y] >> y2) & 1) { if ((ch[nc++] = nd_qt(T, x2, y2, depth + 1)) < 0) return -1; }
                Sx *mn = dc_form("Min", NULL);
                for (int i = 0; i < nc; i++) sx_push(mn, dc_int(ch[i]));
                int c = nd_qnode(T, mn);
                if (c < 0) return -1;
                for (int z = 0; z < n; z++) { DcRat v = T->one; for (int i = 0; i < nc; i++) v = dc_rat_min(v, QV(T, ch[i], z)); QV(T, c, z) = v; }
                if ((k = nd_qnode(T, dc_form("Diamond", dc_sym(M->act[a].name), dc_int(c), rsx(T->g), NULL))) < 0) return -1;
                for (int z = 0; z < n; z++) { DcRat v = T->zero;
                    for (int z2 = 0; z2 < n; z2++) if ((A->img[z] >> z2) & 1) v = dc_rat_max(v, QV(T, c, z2));
                    QV(T, k, z) = dc_rat_mul(T->g, v, &T->ovf); }
            }
        }
    }
    if (k < 0) {   /* the difference is on y's side: Sub(Not psi_{y,x}, 1 - g^s) */
        int c = nd_qt(T, y, x, depth + 1);
        if (c < 0) return -1;
        int nt = nd_qnode(T, dc_form("Not", dc_int(c), NULL));
        if (nt < 0) return -1;
        for (int z = 0; z < n; z++) QV(T, nt, z) = dc_rat_sub(T->one, QV(T, c, z), &T->ovf);
        DcRat r = dc_rat_sub(T->one, T->gp[sl], &T->ovf);
        if ((k = nd_qnode(T, dc_form("Sub", dc_int(nt), rsx(r), NULL))) < 0) return -1;
        for (int z = 0; z < n; z++) { DcRat v = dc_rat_sub(QV(T, nt, z), r, &T->ovf); QV(T, k, z) = dc_rat_cmp(v, T->zero) > 0 ? v : T->zero; }
    }
    return T->memo[x][y] = k;
}
static Sx *nd_layer(NdQt *T, int l, int h) {   /* kernel at horizon l (h < 0: fixed point), matchings into layer l-1 (or itself) */
    NdBis *B = T->B; const NdMod *s = B->s; const NdMach *M = B->M; const NdCar *C = &s->car[M->states]; int n = B->n;
    int hl = h < 0 ? -1 : l, hp = h < 0 ? -1 : l - 1;
    Sx *K = dc_form("Kernel", NULL), *Mt = dc_form("Matchings", NULL);
    for (int x = 0; x < n; x++) for (int y = x + 1; y < n; y++) {
        DcRat v = nd_dval(T, x, y, hl);
        if (!dc_rat_is_zero(v)) sx_push(K, dc_form("P", dc_sym(C->el[x]), dc_sym(C->el[y]), rsx(v), NULL));
        if ((h >= 0 && l == 0) || dc_rat_cmp(v, T->one) >= 0) continue;
        for (int a = 0; a < M->nact; a++) { const NdMap *A = &s->map[M->act[a].map];
            if (!A->img[x] || !A->img[y]) continue;
            Sx *f = dc_form("Fwd", NULL), *b = dc_form("Bwd", NULL);
            for (int x2 = 0; x2 < n; x2++) if ((A->img[x] >> x2) & 1) { int by = -1;
                for (int y2 = 0; y2 < n; y2++) if (((A->img[y] >> y2) & 1) && (by < 0 || dc_rat_cmp(nd_dval(T, x2, y2, hp), nd_dval(T, x2, by, hp)) < 0)) by = y2;
                sx_push(f, dc_form(C->el[x2], dc_sym(C->el[by]), NULL)); }
            for (int y2 = 0; y2 < n; y2++) if ((A->img[y] >> y2) & 1) { int bx = -1;
                for (int x2 = 0; x2 < n; x2++) if (((A->img[x] >> x2) & 1) && (bx < 0 || dc_rat_cmp(nd_dval(T, x2, y2, hp), nd_dval(T, bx, y2, hp)) < 0)) bx = x2;
                sx_push(b, dc_form(C->el[y2], dc_sym(C->el[bx]), NULL)); }
            sx_push(Mt, dc_form("Match", dc_sym(C->el[x]), dc_sym(C->el[y]), dc_sym(M->act[a].name), f, b, NULL));
        }
    }
    return dc_form("Layer", dc_int(l), K, Mt, NULL);
}
static Sx *nd_haus(DcModule *m, const NdMod *s, const Sx *q) {
    const char *hd = q->items[0]->text, *a1 = q->n >= 2 ? nm_of(q->items[1]) : NULL, *e;
    int chk = !strcmp(hd, "CheckBehavioral"), hor = -1, ovf = 0; long long bud = -1;
    DcRat g = dc_rat(1, 1, &ovf), b = dc_rat(0, 1, &ovf);
    for (size_t i = 2; i < q->n; i++) { const Sx *o = q->items[i]; const char *oh = o->n ? nm_of(o->items[0]) : NULL;
        const Sx *v = oh && o->n == 2 ? o->items[1] : NULL; DcRat t;
        if (v && !strcmp(oh, "Discount")) {
            if (dc_sx_rat(v, &g) || g.n < 0 || g.n > g.d) return dc_invalid(m, "%s: expected (Discount g) with 0 <= g <= 1", hd);
            continue; }
        if (v && !strcmp(oh, "Horizon") && nm_of(v) && !strcmp(v->text, "AllFiniteWords")) continue;
        if (v && !strcmp(oh, "Horizon")) {
            if (!sx_head_is(v, "Steps") || v->n != 2 || dc_sx_rat(v->items[1], &t) || t.d != 1 || t.n < 0 || t.n > 64)
                return dc_invalid(m, "%s: expected (Horizon (Steps h)) with 0 <= h <= 64", hd);
            hor = (int)t.n; continue; }
        if (v && !strcmp(oh, "Within") && chk) {
            if (dc_sx_rat(v, &b) || b.n < 0) return dc_invalid(m, "%s: expected (Within b) with b >= 0", hd);
            continue; }
        if (v && !strcmp(oh, "Precision") && !chk) {
            if (dc_sx_rat(v, &t) || t.n < 0) return dc_invalid(m, "%s: expected (Precision r) with r >= 0", hd);
            continue; }
        if (v && !strcmp(oh, "Budget") && sx_head_is(v, "Unrollings") && v->n == 2 && !dc_sx_rat(v->items[1], &t) && t.d == 1 && t.n >= 0) { bud = t.n; continue; }
        return dc_unsupported(m, "%s: option %s is not implemented for Profile Nondeterministic", hd, oh ? oh : "?");
    }
    const Sx *d = NULL;
    for (size_t i = 2; a1 && m->source && i < m->source->n; i++) { const Sx *x = m->source->items[i];
        if (sx_head_is(x, "Representation") && x->n >= 2 && nm_of(x->items[1]) && !strcmp(x->items[1]->text, a1)) d = x; }
    if (!d) return dc_invalid(m, "%s: names no declared Representation (%s)", hd, a1 ? a1 : "?");
    int mi = nd_mach(s, fld1(d, "Of")), ei = nd_map(s, fld1(d, "Encode"));
    if (mi < 0 || ei < 0) return dc_invalid(m, "%s %s: (Of M) or (Encode e) names nothing declared", hd, a1);
    const NdMach *M = &s->mach[mi]; const NdMap *E = &s->map[ei]; const NdCar *C = &s->car[M->states];
    if (E->from != M->states || E->choice) return dc_invalid(m, "%s %s: Encode %s is not a function on the states of %s", hd, a1, E->name, M->name);
    for (int j = 0; j < M->nobs; j++) if (s->map[M->obs[j].map].choice)
        return dc_unsupported(m, "%s %s: observer %s is set-valued (Choice); the quantitative distance needs functional observers", hd, a1, M->obs[j].name);
    static NdBis B; static NdQt T;
    if ((e = nd_bis_setup(&B, s, mi))) return dc_invalid(m, "%s %s: %s", hd, a1, e);
    memset(&T, 0, sizeof T); memset(T.memo, -1, sizeof T.memo);
    static DcRat *Vbuf; if (!Vbuf) Vbuf = malloc(sizeof(DcRat) * (size_t)ND_MAXF * ND_MAXC);
    if (!Vbuf) return dc_unsupported(m, "%s: out of memory", hd);
    T.V = Vbuf; T.B = &B; T.g = g; T.zero = dc_rat(0, 1, &ovf); T.one = dc_rat(1, 1, &ovf); T.gp[0] = T.one;
    for (int k = 1; k <= B.L + 2 && k < ND_MAXC + 3; k++) T.gp[k] = dc_rat_mul(T.gp[k - 1], g, &T.ovf);
    if (ovf || T.ovf) return dc_unsupported(m, "%s %s: rational overflow (64-bit limit) in the powers of the discount", hd, a1);
    int n = C->n, known = bud < 0 || bud >= B.L || (hor >= 0 && hor <= bud);
    int eh = known ? hor : (hor >= 0 && hor < bud ? hor : (int)bud);   /* rounds whose splits are counted */
    DcRat lo = T.zero; int wx = -1, wy = -1, open = 0;
    for (int x = 0; x < n; x++) for (int y = x + 1; y < n; y++) {
        if (E->img[x] != E->img[y]) continue;
        DcRat v = nd_dval(&T, x, y, eh);
        if (dc_rat_cmp(v, lo) > 0) { lo = v; wx = x; wy = y; }
        if (!known && nd_split(&B, x, y) > bud) open = 1;
    }
    Sx *wit = NULL;
    if (wx >= 0) {
        int root = nd_qt(&T, wx, wy, 0);
        if (root < 0 || T.bad || T.ovf || dc_rat_cmp(dc_rat_sub(QV(&T, root, wx), QV(&T, root, wy), &T.ovf), lo) || T.ovf) {
            for (int k = 0; k < T.nn; k++) sx_free(T.body[k]);
            return dc_unsupported(m, "%s %s: the lower-certificate test failed its self-check", hd, a1); }
        Sx *fg = dc_form("Formula", dc_form("Root", dc_int(root), NULL), NULL);
        for (int k = 0; k < T.nn; k++) sx_push(fg, dc_form("Node", dc_int(k), T.body[k], NULL));
        wit = dc_form("ModalTestWitness", dc_form("Pair", dc_sym(C->el[wx]), dc_sym(C->el[wy]), NULL), fg,
                      dc_form("Left", rsx(QV(&T, root, wx)), NULL), dc_form("Right", rsx(QV(&T, root, wy)), NULL), NULL);
    }
    Sx *hz = hor >= 0 ? dc_form("Steps", dc_int(hor), NULL) : dc_sym("AllFiniteWords");
    if (!known) {
        DcRat up = open ? dc_rat_max(lo, T.gp[bud + 1]) : lo;
        if (chk && dc_rat_cmp(lo, b) > 0) {
            Sx *val = dc_form("Value", dc_form("WithinBound", dc_sym("False"), NULL), dc_form("BehavioralInterval", dc_form("Lower", rsx(lo), NULL), dc_form("Upper", rsx(up), NULL), NULL), NULL);
            sx_free(hz);
            return nd_env_k(m, VERDICT_FAILS, q, "Representation", a1, val, dc_form("Evidence", dc_form("Witness", wit, NULL), NULL), "the lower-certificate test already exceeds the Within bound");
        }
        if (wit) sx_free(wit);
        char w[200]; snprintf(w, sizeof w, "refinement stopped at the budget of %lld unrollings before it stabilized", bud);
        Sx *val = dc_form("Value", dc_form("BehavioralInterval", dc_form("Lower", rsx(lo), NULL), dc_form("Upper", rsx(up), NULL), NULL), dc_form("Discount", rsx(g), NULL), dc_form("Horizon", hz, NULL), NULL);
        g_nd_rep = 0;
        Sx *r = nd_env_k(m, VERDICT_HOLDS, q, "Representation", a1, val, dc_form("Evidence", dc_form("Explored", dc_form("Unrollings", dc_int((int)bud), NULL), NULL), NULL), w);
        g_nd_rep = 1; return r;
    }
    Sx *cert = dc_form("Certificate", dc_form("Kind", dc_sym(hor < 0 ? "HausdorffPrefixpoint" : "HausdorffLayers"), NULL), dc_form("Discount", rsx(g), NULL), dc_form("Horizon", hz, NULL), NULL);
    if (hor < 0) sx_push(cert, nd_layer(&T, 0, -1));
    else for (int l = 0; l <= hor; l++) sx_push(cert, nd_layer(&T, l, hor));
    int holds = !chk || dc_rat_cmp(lo, b) <= 0;
    Sx *val = dc_form("Value", dc_form("BehavioralDefect", rsx(lo), NULL), dc_form("Discount", rsx(g), NULL), NULL);
    if (chk) sx_push(val, dc_form("WithinBound", dc_sym(holds ? "True" : "False"), NULL));
    Sx *ev = dc_form("Evidence", NULL);
    if (chk && !holds) { sx_free(cert); sx_push(ev, dc_form("Witness", wit, NULL)); }
    else { sx_push(ev, cert); if (wit) sx_push(ev, dc_form("Test", wit, NULL)); }
    return nd_env_k(m, holds ? VERDICT_HOLDS : VERDICT_FAILS, q, "Representation", a1, val, ev, NULL);
}

Sx *dc_req_nondet(DcRun *r, const Sx *q, const char *head, int slot) {
    DcModule *m = r->m; static NdMod S; char err[256]; (void)slot;
    if (nd_read(m->source, &S, err, sizeof err)) return dc_invalid(m, "nondeterministic module: %s", err);
    if (!strcmp(head, "Outcomes")) return nd_outcomes(m, &S, q, 0);
    if (!strcmp(head, "OutcomeProbability")) return nd_outcomes(m, &S, q, 1);
    if (!strcmp(head, "CheckSimulation")) return nd_checksim(m, &S, q);
    if (!strcmp(head, "CheckSafety")) return nd_safety(m, &S, q);
    if (!strcmp(head, "InduceExact")) return nd_induce(m, &S, q);
    if (!strcmp(head, "BehavioralTolerance")) return nd_bisim(m, &S, q, 0);
    if (!strcmp(head, "CheckBehavioral")) return nd_bisim(m, &S, q, 1);
    if (!strcmp(head, "MeasureBehavioral")) return nd_haus(m, &S, q);
    if (!strcmp(head, "CheckTrace") || !strcmp(head, "MeasureTrace")) return nd_maytrace(m, &S, q);
    return dc_unsupported(m, "request %s: not yet implemented for Profile Nondeterministic (M5 in progress)", head);
}
