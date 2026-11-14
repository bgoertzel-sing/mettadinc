/* M7 (opt-in, beyond the first release): availability requests on a (Use Hyperseed) module
 * (docs/e0/MILESTONES.md M7, claims W01-W02).  Map codomains such as PBit, Int or a declared
 * Sum type are outside the M0 fragment, so model.c skips them; this file reads the Carrier,
 * Map, Machine and Representation declarations from m->source.  Values are compared as ground
 * terms (structural equality).  CheckNow DefaultZero answers Refuted with every pair of states
 * that share a code but differ on some observation (names sorted, as in the manifest oracle). */
#include "ops_internal.h"
#include "ops_run.h"
#include "model.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define M7_MAXS 64
static const Sx *m7_decl(const DcModule *m, const char *head, const char *name) {
    const Sx *f = m->source;
    for (size_t i = 2; f && i < f->n; i++) {
        const Sx *d = f->items[i];
        if (sx_head_is(d, head) && d->n >= 2 && sx_is_sym(d->items[1], name)) return d;
    }
    return NULL;
}
static const Sx *m7_field(const Sx *d, const char *head) {
    for (size_t i = 2; d && i < d->n; i++) if (sx_head_is(d->items[i], head)) return d->items[i];
    return NULL;
}
static const Sx *m7_case(const Sx *map, const char *elem) {
    const Sx *cs = m7_field(map, "Cases");
    for (size_t i = 1; cs && i < cs->n; i++) {
        const Sx *c = cs->items[i];
        if (c->kind == SX_LIST && c->n == 2 && sx_is_sym(c->items[0], elem)) return c->items[1];
    }
    return NULL;
}
typedef struct { const char *a, *b; } M7Pair;
static int m7_cmp(const void *x, const void *y) {
    const M7Pair *p = x, *q = y; int k = strcmp(p->a, q->a);
    return k ? k : strcmp(p->b, q->b);
}
static Sx *m7_unsup(const DcModule *m, const DcScope *sc, Sx *claim, const char *why) {
    return dc_envelope_scoped(m, VERDICT_UNSUPPORTED, 0, claim, NULL, NULL, NULL, why, sc);
}


/* M7 (Use Neural): (CompareDistinctions Old New (Under PairLaw)).  Masses under the pair law mu x mu, diagonal
 * included (spec 7.x trap): MassR = P[enc_R(x) != enc_R(y)]; Creation = P[new differs, old agrees]; Erasure =
 * P[old differs, new agrees]; Turnover = Creation + Erasure.  Only the uniform law is admitted (DcMeas). */
static Sx *m7_rsym(int64_t num, int64_t den) {
    int ovf = 0; char b[48]; DcRat r = dc_rat(num, den, &ovf); dc_rat_str(r, b, sizeof b); return dc_sym(b);
}
static Sx *m7_compare(DcRun *r, const Sx *q) {
    DcModule *m = r->m;
    DcScope sc = {"M7-Neural", -1, "", NULL};
    Sx *claim = dc_claim_of(q, "Literal");
    if (q->n != 4 || q->items[1]->kind != SX_SYM || q->items[2]->kind != SX_SYM || !sx_head_is(q->items[3], "Under")
        || q->items[3]->n != 2 || q->items[3]->items[1]->kind != SX_SYM)
        return dc_invalid(m, "CompareDistinctions: expected (CompareDistinctions Old New (Under PairLaw))");
    int ro = dc_find_repr(m, q->items[1]->text), rn = dc_find_repr(m, q->items[2]->text);
    if (ro < 0 || rn < 0) return m7_unsup(m, &sc, claim, "CompareDistinctions: both representations must be admitted");
    int so = m->mach[m->rep[ro].machine].states, sn = m->mach[m->rep[rn].machine].states;
    if (so != sn) return m7_unsup(m, &sc, claim, "CompareDistinctions: representations of different state carriers");
    const Sx *pl = m7_decl(m, "PairLaw", q->items[3]->items[1]->text);
    const Sx *ind = m7_field(pl, "Independent"), *dg = m7_field(pl, "Diagonal");
    if (!pl || !ind || ind->n != 3 || ind->items[1]->kind != SX_SYM || !sx_equal(ind->items[1], ind->items[2])
        || !dg || dg->n != 2 || !sx_is_sym(dg->items[1], "Included"))
        return m7_unsup(m, &sc, claim, "CompareDistinctions: M7 admits (PairLaw P (Independent M M) (Diagonal Included)) only");
    int mi = dc_find_meas(m, ind->items[1]->text);
    if (mi < 0 || !m->meas[mi].uniform || m->meas[mi].on != so)
        return m7_unsup(m, &sc, claim, "CompareDistinctions: the pair law's measure must be uniform on the state carrier");
    int64_t n = (int64_t)m->car[so].n; const int *eo = m->map[m->rep[ro].encode].table, *en = m->map[m->rep[rn].encode].table;
    if (n <= 0 || n > 4096) return m7_unsup(m, &sc, claim, "CompareDistinctions: state carrier empty or larger than 4096");
    int64_t mo = 0, mn = 0, cr = 0, er = 0;
    for (int64_t x = 0; x < n; x++) for (int64_t y = 0; y < n; y++) {
        int dO = eo[x] != eo[y], dN = en[x] != en[y];
        mo += dO; mn += dN; cr += dN && !dO; er += dO && !dN;
    }
    int ok = (mn - mo == cr - er);   /* replay identity: MassNew - MassOld = Creation - Erasure */
    int64_t d = n * n;
    Sx *val = dc_form("DistinctionComparison", dc_form("MassOld", m7_rsym(mo, d), NULL), dc_form("MassNew", m7_rsym(mn, d), NULL),
        dc_form("Creation", m7_rsym(cr, d), NULL), dc_form("Erasure", m7_rsym(er, d), NULL),
        dc_form("Turnover", m7_rsym(cr + er, d), NULL), NULL);
    Sx *ev = dc_form("Evidence", dc_form("PairCounts", dc_form("Pairs", m7_rsym(d, 1), NULL), dc_form("OldDiffer", m7_rsym(mo, 1), NULL),
        dc_form("NewDiffer", m7_rsym(mn, 1), NULL), dc_form("Created", m7_rsym(cr, 1), NULL), dc_form("Erased", m7_rsym(er, 1), NULL), NULL), NULL);
    Sx *subj = dc_form("Subject", dc_form("Representation", dc_sym(q->items[1]->text), NULL),
                       dc_form("Representation", dc_sym(q->items[2]->text), NULL), NULL);
    return dc_envelope_scoped(m, VERDICT_HOLDS, ok, claim, subj, dc_form("Value", val, NULL), ev, NULL, &sc);
}

/* M7 (Use Neural): (AuditIntervention (Systems S...) (Intervention (SetReport v)) (Task map) (Under M) (Metric Accuracy)).
 * Each (ReportSystem S (Input C) (ReportType T) (Encoder e) (Readout r)) answers readout((Tuple x z)) with z = e(x)
 * (Baseline) or z = v (Intervened); accuracy = P_M[answer = task(x)] under the uniform law M on C.  Readout bodies
 * are read from the source: (Body ($v) expr), expr = variable | literal | (GetTuple expr k) | (map expr) with map
 * an admitted Map applied by its table. */
static Sx *m7_ev(const DcModule *m, const Sx *b, const char *var, const Sx *val) {
    if (b->kind == SX_SYM) return sx_copy(!strcmp(b->text, var) ? val : b);
    if (b->kind != SX_LIST || b->n == 0 || b->items[0]->kind != SX_SYM) return NULL;
    if (sx_head_is(b, "GetTuple") && b->n == 3 && b->items[2]->kind == SX_SYM) {
        Sx *x = m7_ev(m, b->items[1], var, val); long k = atol(b->items[2]->text); Sx *res = NULL;
        if (x && sx_head_is(x, "Tuple") && k >= 0 && (size_t)k + 1 < x->n) res = sx_copy(x->items[k + 1]);
        if (x) sx_free(x);
        return res;
    }
    if (b->n == 2) {
        int mi = dc_find_map(m, b->items[0]->text); if (mi < 0 || !m->map[mi].table) return NULL;
        Sx *x = m7_ev(m, b->items[1], var, val); if (!x) return NULL;
        int ci = dc_carrier_index(&m->car[m->map[mi].from], x); sx_free(x);
        if (ci < 0) return NULL;
        return sx_copy(m->car[m->map[mi].to].elems[m->map[mi].table[ci]]);
    }
    return NULL;
}
/* request fields start at index 1 (declaration fields start at 2, after the name) */
static const Sx *m7_qfield(const Sx *q, const char *head) {
    for (size_t i = 1; q && i < q->n; i++) if (sx_head_is(q->items[i], head)) return q->items[i];
    return NULL;
}
static Sx *m7_audit(DcRun *r, const Sx *q) {
    DcModule *m = r->m;
    DcScope sc = {"M7-Neural", -1, "", NULL};
    Sx *claim = dc_claim_of(q, "Literal");
    const Sx *sy = m7_qfield(q, "Systems"), *iv = m7_qfield(q, "Intervention"), *tk = m7_qfield(q, "Task"),
             *un = m7_qfield(q, "Under"), *me = m7_qfield(q, "Metric");
    if (!sy || sy->n < 2 || !iv || iv->n != 2 || !tk || tk->n != 2 || !un || un->n != 2 || !me || me->n != 2)
        return dc_invalid(m, "AuditIntervention: Systems, Intervention, Task, Under and Metric are required");
    if (!sx_is_sym(me->items[1], "Accuracy")) return m7_unsup(m, &sc, claim, "AuditIntervention: M7 admits (Metric Accuracy) only");
    const Sx *sr = iv->items[1];
    if (!sx_head_is(sr, "SetReport") || sr->n != 2) return m7_unsup(m, &sc, claim, "AuditIntervention: M7 admits (Intervention (SetReport v)) only");
    int ti = tk->items[1]->kind == SX_SYM ? dc_find_map(m, tk->items[1]->text) : -1;
    int mi = un->items[1]->kind == SX_SYM ? dc_find_meas(m, un->items[1]->text) : -1;
    if (ti < 0 || mi < 0 || !m->meas[mi].uniform || m->map[ti].from != m->meas[mi].on)
        return m7_unsup(m, &sc, claim, "AuditIntervention: Task must be an admitted map on the uniform law's carrier");
    const DcCarrier *C = &m->car[m->meas[mi].on]; int64_t n = (int64_t)C->n;
    Sx *tab = dc_form("Table", NULL), *ev = dc_form("Counts", NULL); int ok = 1;
    for (size_t s = 1; s < sy->n; s++) {
        const Sx *rs = sy->items[s]->kind == SX_SYM ? m7_decl(m, "ReportSystem", sy->items[s]->text) : NULL;
        const Sx *ef = m7_field(rs, "Encoder"), *rf = m7_field(rs, "Readout");
        int ei = ef && ef->n == 2 && ef->items[1]->kind == SX_SYM ? dc_find_map(m, ef->items[1]->text) : -1;
        const Sx *rd = rf && rf->n == 2 && rf->items[1]->kind == SX_SYM ? m7_decl(m, "Map", rf->items[1]->text) : NULL;
        const Sx *bd = m7_field(rd, "Body");
        if (!rs || ei < 0 || m->map[ei].from != m->meas[mi].on || !bd || bd->n != 3 || bd->items[1]->kind != SX_LIST
            || bd->items[1]->n != 1 || bd->items[1]->items[0]->kind != SX_SYM) {
            sx_free(tab); sx_free(ev);
            return m7_unsup(m, &sc, claim, "AuditIntervention: each system needs a declared ReportSystem with an admitted Encoder and a (Body ($v) expr) Readout");
        }
        const char *var = bd->items[1]->items[0]->text; int64_t hit[2] = {0, 0};
        for (int64_t x = 0; x < n; x++) {
            const Sx *want = m->car[m->map[ti].to].elems[m->map[ti].table[x]];
            for (int k = 0; k < 2; k++) {
                const Sx *z = k ? sr->items[1] : m->car[m->map[ei].to].elems[m->map[ei].table[x]];
                Sx *arg = dc_form("Tuple", sx_copy(C->elems[x]), sx_copy(z), NULL);
                Sx *ans = m7_ev(m, bd->items[2], var, arg); sx_free(arg);
                if (!ans) ok = 0; else { hit[k] += sx_equal(ans, want); sx_free(ans); }
            }
        }
        sx_push(tab, dc_form("Row", dc_sym(sy->items[s]->text), dc_form("Baseline", m7_rsym(hit[0], n), NULL),
                             dc_form("Intervened", m7_rsym(hit[1], n), NULL), NULL));
        sx_push(ev, dc_form("System", dc_sym(sy->items[s]->text), dc_form("Inputs", m7_rsym(n, 1), NULL),
                            dc_form("CorrectBaseline", m7_rsym(hit[0], 1), NULL), dc_form("CorrectIntervened", m7_rsym(hit[1], 1), NULL), NULL));
    }
    if (!ok) { sx_free(tab); sx_free(ev); return m7_unsup(m, &sc, claim, "AuditIntervention: a readout body did not evaluate on some input"); }
    Sx *subj = dc_form("Subject", sx_copy(sy), NULL);
    return dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, subj, dc_form("Value", dc_form("MetricTable", tab, NULL), NULL),
                              dc_form("Evidence", ev, NULL), NULL, &sc);
}

/* M7 (Use Hyperseed), spec 12.6: description systems.  (Literal X) costs X; (Tokens t...) costs Tokens*n;
 * (Repeat X k) costs X + Operator + Count and decodes to X repeated k times (decoder Expand only).
 * FindCheapestDescription certifies the minimum cost among the declared descriptions that decode to the
 * target (never a search over a larger grammar); CheckPatternWitness checks decode == target and cost < baseline. */
#define M7_TOK 512
typedef struct { long wt, wo, wc; } M7Cost;
static int m7_decode(const Sx *d, const M7Cost *w, const char **out, int *n, long *cost, int depth) {
    if (depth > 8 || d->kind != SX_LIST || d->n == 0) return 0;
    if (sx_head_is(d, "Tokens")) {
        for (size_t i = 1; i < d->n; i++) { if (d->items[i]->kind != SX_SYM || *n >= M7_TOK) return 0; out[(*n)++] = d->items[i]->text; }
        *cost += w->wt * (long)(d->n - 1); return 1;
    }
    if (sx_head_is(d, "Literal") && d->n == 2) return m7_decode(d->items[1], w, out, n, cost, depth + 1);
    if (sx_head_is(d, "Repeat") && d->n == 3 && d->items[2]->kind == SX_SYM) {
        long k = atol(d->items[2]->text); int s = *n;
        if (k < 1 || k > M7_TOK || !m7_decode(d->items[1], w, out, n, cost, depth + 1)) return 0;
        int len = *n - s;
        for (long r = 1; r < k; r++) for (int i = 0; i < len; i++) { if (*n >= M7_TOK) return 0; out[(*n)++] = out[s + i]; }
        *cost += w->wo + w->wc; return 1;
    }
    return 0;
}
static int m7_target(const Sx *tg, const char **out, int *n) {
    if (!tg || tg->n != 2 || !sx_head_is(tg->items[1], "Tokens")) return 0;
    M7Cost z = {0, 0, 0}; long c = 0; *n = 0; return m7_decode(tg->items[1], &z, out, n, &c, 0);
}
static const Sx *m7_desc(const Sx *sys, const char *name) {
    for (size_t i = 2; i < sys->n; i++) {
        const Sx *d = sys->items[i];
        if (sx_head_is(d, "Description") && d->n == 3 && sx_is_sym(d->items[1], name)) return d;
    }
    return NULL;
}
static int m7_sys(const Sx *sys, M7Cost *w, const char **why) {
    const Sx *dec = m7_field(sys, "Decoder"), *co = m7_field(sys, "Cost");
    if (!dec || dec->n != 2 || !sx_is_sym(dec->items[1], "Expand")) { *why = "DescriptionSystem: M7 admits (Decoder Expand) only"; return 0; }
    w->wt = w->wo = w->wc = -1;
    for (size_t i = 1; co && i < co->n; i++) {
        const Sx *f = co->items[i];
        if (f->kind != SX_LIST || f->n != 2 || f->items[1]->kind != SX_SYM) continue;
        long v = atol(f->items[1]->text);
        if (sx_head_is(f, "Tokens")) w->wt = v; else if (sx_head_is(f, "Operator")) w->wo = v; else if (sx_head_is(f, "Count")) w->wc = v;
    }
    if (w->wt < 0 || w->wo < 0 || w->wc < 0) { *why = "DescriptionSystem: (Cost (Tokens n) (Operator n) (Count n)) with natural weights is required"; return 0; }
    return 1;
}
static Sx *m7_pattern(DcRun *r, const Sx *q, const char *h) {
    DcModule *m = r->m;
    DcScope sc = {"M7-Patterns", -1, "", NULL};
    Sx *claim = dc_claim_of(q, "Literal");
    const char *why = NULL; M7Cost w; const char *tg[M7_TOK]; int nt = 0;
    const Sx *sys = NULL, *target = NULL, *wd = NULL;
    if (!strcmp(h, "FindCheapestDescription")) {
        if (q->n != 3 || q->items[1]->kind != SX_SYM || !sx_head_is(q->items[2], "Target"))
            return dc_invalid(m, "FindCheapestDescription: expected (FindCheapestDescription System (Target (Tokens ...)))");
        sys = m7_decl(m, "DescriptionSystem", q->items[1]->text); target = q->items[2];
    } else {
        if (q->n != 2 || q->items[1]->kind != SX_SYM) return dc_invalid(m, "CheckPatternWitness: expected (CheckPatternWitness W)");
        wd = m7_decl(m, "PatternWitness", q->items[1]->text);
        const Sx *sf = m7_field(wd, "System");
        if (!wd || !sf || sf->n != 2 || sf->items[1]->kind != SX_SYM) return dc_invalid(m, "CheckPatternWitness: no declared PatternWitness with a System");
        sys = m7_decl(m, "DescriptionSystem", sf->items[1]->text); target = m7_field(wd, "Target");
    }
    if (!sys) return dc_invalid(m, "%s: no declared DescriptionSystem", h);
    if (!m7_sys(sys, &w, &why)) return m7_unsup(m, &sc, claim, why);
    if (!m7_target(target, tg, &nt)) return m7_unsup(m, &sc, claim, "pattern request: the target must be (Target (Tokens t...))");
    const Sx *bl = m7_field(sys, "Baseline");
    const Sx *bd = bl && bl->n == 2 && bl->items[1]->kind == SX_SYM ? m7_desc(sys, bl->items[1]->text) : NULL;
    if (!bd) return m7_unsup(m, &sc, claim, "DescriptionSystem: (Baseline D) must name a declared Description");
    Sx *cands = dc_form("Candidates", NULL);
    const char *best = NULL; long bc = 0, basec = -1; int okall = 1;
    for (size_t i = 2; i < sys->n; i++) {
        const Sx *d = sys->items[i];
        if (!sx_head_is(d, "Description")) continue;
        if (d->n != 3 || d->items[1]->kind != SX_SYM) { okall = 0; continue; }
        const char *out[M7_TOK]; int n = 0; long c = 0;
        int ok = m7_decode(d->items[2], &w, out, &n, &c, 0);
        int dec = ok && n == nt; for (int k = 0; dec && k < n; k++) dec = !strcmp(out[k], tg[k]);
        if (!ok) okall = 0;
        if (d == bd) basec = ok ? c : -1;
        sx_push(cands, dc_form("Candidate", dc_sym(d->items[1]->text), dc_form("Cost", m7_rsym(ok ? c : 0, 1), NULL),
                               dc_form("Decodes", dc_sym(dec ? "True" : "False"), NULL), NULL));
        if (dec && (!best || c < bc)) { best = d->items[1]->text; bc = c; }
    }
    if (!okall) { sx_free(cands); return m7_unsup(m, &sc, claim, "DescriptionSystem: a description is outside (Literal|Tokens|Repeat) under Expand"); }
    if (!strcmp(h, "FindCheapestDescription")) {
        if (!best) { sx_free(cands); return m7_unsup(m, &sc, claim, "FindCheapestDescription: no declared description decodes to the target"); }
        Sx *val = dc_form("DescriptionResult", dc_form("Description", dc_sym(best), NULL), dc_form("Cost", m7_rsym(bc, 1), NULL),
                          dc_form("Optimality", dc_sym("Checked"), NULL), NULL);
        return dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, dc_form("Subject", dc_form("DescriptionSystem", dc_sym(sys->items[1]->text), NULL), NULL),
                                  dc_form("Value", val, NULL), dc_form("Evidence", dc_form("Certificate", cands, NULL), NULL), NULL, &sc);
    }
    const Sx *df = m7_field(wd, "Description");
    const Sx *wdesc = df && df->n == 2 && df->items[1]->kind == SX_SYM ? m7_desc(sys, df->items[1]->text) : NULL;
    if (!wdesc) { sx_free(cands); return dc_invalid(m, "CheckPatternWitness: the witness Description is not declared in its system"); }
    const char *out[M7_TOK]; int n = 0; long c = 0;
    m7_decode(wdesc->items[2], &w, out, &n, &c, 0);
    int dec = n == nt; for (int k = 0; dec && k < n; k++) dec = !strcmp(out[k], tg[k]);
    int holds = dec && c < basec;
    Sx *cert = dc_form("Certificate", dc_form("Decodes", dc_sym(dec ? "True" : "False"), NULL), dc_form("Cost", m7_rsym(c, 1), NULL),
                       dc_form("BaselineCost", m7_rsym(basec, 1), NULL), dc_form("Gain", m7_rsym(basec - c, 1), NULL), NULL);
    sx_free(cands);
    return dc_envelope_scoped(m, holds ? VERDICT_HOLDS : VERDICT_FAILS, 1, claim,
        dc_form("Subject", dc_form("PatternWitness", dc_sym(q->items[1]->text), NULL), NULL),
        dc_form("Value", dc_form("Verdict", sx_copy(cert), NULL), NULL), dc_form("Evidence", cert, NULL), NULL, &sc);
}
/* Returns NULL when the request is not an M7 availability request (the caller falls through). */
Sx *dc_req_m7(DcRun *r, const Sx *q, const char *h) {
    DcModule *m = r->m;
    if (m->hyperseed && (!strcmp(h, "FindCheapestDescription") || !strcmp(h, "CheckPatternWitness"))) return m7_pattern(r, q, h);
    if (m->neural && !strcmp(h, "CompareDistinctions")) return m7_compare(r, q);
    if (m->neural && !strcmp(h, "AuditIntervention")) return m7_audit(r, q);
    if (!m->hyperseed || strcmp(h, "CheckNow") || q->n != 2 || q->items[1]->kind != SX_SYM) return NULL;
    const Sx *rep = m7_decl(m, "Representation", q->items[1]->text);
    if (!rep) return NULL;
    DcScope sc = {"M7-Availability", -1, "", NULL};
    Sx *claim = dc_claim_of(q, "Literal");
    const Sx *of = m7_field(rep, "Of"), *en = m7_field(rep, "Encode");
    if (!of || of->n != 2 || !en || en->n != 2 || of->items[1]->kind != SX_SYM || en->items[1]->kind != SX_SYM)
        return m7_unsup(m, &sc, claim, "CheckNow: M7 reads (Representation R (Of M) (Encode map)) only");
    const Sx *mach = m7_decl(m, "Machine", of->items[1]->text);
    const Sx *st = m7_field(mach, "States");
    const Sx *car = st && st->n == 2 && st->items[1]->kind == SX_SYM ? m7_decl(m, "Carrier", st->items[1]->text) : NULL;
    const Sx *enm = m7_field(car, "Enum");
    const Sx *code = m7_decl(m, "Map", en->items[1]->text);
    if (!enm || enm->n < 2 || enm->n - 1 > M7_MAXS || !code)
        return m7_unsup(m, &sc, claim, "CheckNow: M7 needs an enumerated state carrier (<= 64) and a declared Encode map");
    size_t n = enm->n - 1;
    const char *nm[M7_MAXS];
    for (size_t i = 0; i < n; i++) {
        if (enm->items[i + 1]->kind != SX_SYM) return m7_unsup(m, &sc, claim, "CheckNow: M7 state carrier elements must be symbols");
        nm[i] = enm->items[i + 1]->text;
        if (!m7_case(code, nm[i])) return m7_unsup(m, &sc, claim, "CheckNow: Encode map has no case for some state");
    }
    /* observations: (Observe label map ...) pairs */
    const Sx *obsm[16]; const char *obsl[16]; size_t no = 0;
    for (size_t i = 2; i < mach->n; i++) {
        const Sx *o = mach->items[i];
        if (!sx_head_is(o, "Observe")) continue;
        for (size_t k = 1; k + 1 < o->n; k += 2) {
            const Sx *mp = o->items[k + 1]->kind == SX_SYM ? m7_decl(m, "Map", o->items[k + 1]->text) : NULL;
            if (!mp || no >= 16) return m7_unsup(m, &sc, claim, "CheckNow: M7 observation maps must be declared Maps (<= 16)");
            for (size_t s = 0; s < n; s++) if (!m7_case(mp, nm[s])) return m7_unsup(m, &sc, claim, "CheckNow: an observation map has no case for some state");
            obsl[no] = o->items[k]->kind == SX_SYM ? o->items[k]->text : "?"; obsm[no++] = mp;
        }
    }
    if (!no) return m7_unsup(m, &sc, claim, "CheckNow: machine declares no observation");
    M7Pair *pr = calloc(n * n / 2 + 1, sizeof *pr); size_t np = 0;
    Sx *wit = dc_form("MergedPairs", NULL);
    for (size_t i = 0; i < n; i++) for (size_t j = i + 1; j < n; j++) {
        if (!sx_equal(m7_case(code, nm[i]), m7_case(code, nm[j]))) continue;
        size_t k = 0; while (k < no && sx_equal(m7_case(obsm[k], nm[i]), m7_case(obsm[k], nm[j]))) k++;
        if (k == no) continue;
        int sw = strcmp(nm[i], nm[j]) > 0;
        pr[np].a = sw ? nm[j] : nm[i]; pr[np].b = sw ? nm[i] : nm[j]; np++;
        sx_push(wit, dc_form("Merge", dc_form("Pair", dc_sym(nm[i]), dc_sym(nm[j]), NULL),
            dc_form("Code", sx_copy(m7_case(code, nm[i])), NULL),
            dc_form("Observe", dc_sym(obsl[k]), sx_copy(m7_case(obsm[k], nm[i])), sx_copy(m7_case(obsm[k], nm[j])), NULL), NULL));
    }
    qsort(pr, np, sizeof *pr, m7_cmp);
    Sx *val = dc_form("MergedPairs", NULL);
    for (size_t i = 0; i < np; i++) sx_push(val, dc_form("Pair", dc_sym(pr[i].a), dc_sym(pr[i].b), NULL));
    free(pr);
    /* replay: every listed merge re-checked from the declarations (same code, some observation differs) */
    int rep_ok = 1;
    for (size_t i = 1; i < wit->n; i++) {
        const Sx *w = wit->items[i], *p = w->items[1], *cd = w->items[2], *ob = w->items[3];
        const char *a = p->items[1]->text, *b = p->items[2]->text; const Sx *mo = NULL;
        for (size_t k = 0; k < no; k++) if (!strcmp(obsl[k], ob->items[1]->text)) mo = obsm[k];
        if (!sx_equal(m7_case(code, a), cd->items[1]) || !sx_equal(m7_case(code, b), cd->items[1]) || !mo
            || sx_equal(m7_case(mo, a), m7_case(mo, b))) rep_ok = 0;
    }
    Sx *subj = dc_form("Subject", dc_form("Representation", dc_sym(q->items[1]->text), NULL),
                       dc_form("Machine", dc_sym(of->items[1]->text), NULL), NULL);
    return dc_envelope_scoped(m, np ? VERDICT_FAILS : VERDICT_HOLDS, rep_ok, claim, subj,
        dc_form("Value", val, NULL), dc_form("Evidence", dc_form("Witness", wit, NULL), NULL), NULL, &sc);
}
