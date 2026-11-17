/* M7 (opt-in, beyond the first release), claim Z01: keyed snapshot carriers.
 * (Profile ... (Carriers Snapshot)) modules declare (Snapshot S (Space s) (Digest "sha256:<64 hex>") (Revision n)),
 * carriers (Carrier C (Of T) (Query S pattern (Key $k))) and maps (Map f (From C) (To D) (Query S pattern (Key $k) (Value $v))).
 * The content is never materialized here.  CheckNow R is decided symbolically: it holds for every snapshot content when
 * every observation of the machine is the Encode map's own query (the code IS the observation) and every action is the
 * identity body (Body ($x) $x).  Otherwise the request is Unsupported (content would be needed).  The digest is
 * syntax-checked and recorded as an assumption; functional-map admission of the content is an assumption too. */
#include "ops_internal.h"
#include "ops_run.h"
#include "model.h"
#include <ctype.h>
#include <stdio.h>
#include <string.h>

static const Sx *z_decl(const DcModule *m, const char *head, const char *name) {
    const Sx *f = m->source;
    for (size_t i = 2; f && i < f->n; i++) {
        const Sx *d = f->items[i];
        if (sx_head_is(d, head) && d->n >= 2 && sx_is_sym(d->items[1], name)) return d;
    }
    return NULL;
}
static const Sx *z_field(const Sx *d, size_t from, const char *head) {
    for (size_t i = from; d && i < d->n; i++) if (sx_head_is(d->items[i], head)) return d->items[i];
    return NULL;
}
/* (Query S pattern (Key $k) [(Value $v)]) */
static int z_query(const Sx *q, int want_value) {
    if (!q || q->n < 4 || q->items[1]->kind != SX_SYM || q->items[2]->kind != SX_LIST) return 0;
    const Sx *k = z_field(q, 3, "Key"), *v = z_field(q, 3, "Value");
    if (!k || k->n != 2 || k->items[1]->kind != SX_SYM || k->items[1]->text[0] != '$') return 0;
    if (want_value && (!v || v->n != 2 || v->items[1]->kind != SX_SYM || v->items[1]->text[0] != '$')) return 0;
    return 1;
}
static int z_digest_ok(const Sx *d) {
    if (!d || d->n != 2 || d->items[1]->kind != SX_STR) return 0;
    const char *s = d->items[1]->text;
    if (strncmp(s, "sha256:", 7) || strlen(s) != 71) return 0;
    for (int i = 7; i < 71; i++) if (!isxdigit((unsigned char)s[i]) || isupper((unsigned char)s[i])) return 0;
    return 1;
}
static int z_identity(const Sx *mp) {
    const Sx *b = z_field(mp, 2, "Body");
    return b && b->n == 3 && b->items[1]->kind == SX_LIST && b->items[1]->n == 1 && b->items[1]->items[0]->kind == SX_SYM
        && sx_equal(b->items[1]->items[0], b->items[2]);
}
static Sx *z_unsup(const DcModule *m, const DcScope *sc, Sx *claim, const char *why) {
    return dc_envelope_scoped(m, VERDICT_UNSUPPORTED, 0, claim, NULL, NULL, NULL, why, sc);
}

/* one pass of the symbolic check; cert may be NULL (replay pass) */
static const char *z_check(const DcModule *m, const char *rn, Sx *cert) {
    const Sx *rep = z_decl(m, "Representation", rn);
    const Sx *of = z_field(rep, 2, "Of"), *en = z_field(rep, 2, "Encode");
    if (!rep || !of || of->n != 2 || !en || en->n != 2 || of->items[1]->kind != SX_SYM || en->items[1]->kind != SX_SYM)
        return "CheckNow: (Representation R (Of M) (Encode f)) is required";
    const Sx *mach = z_decl(m, "Machine", of->items[1]->text), *st = z_field(mach, 2, "States");
    if (!mach || !st || st->n != 2 || st->items[1]->kind != SX_SYM) return "CheckNow: the machine and its (States C) must be declared";
    const Sx *car = z_decl(m, "Carrier", st->items[1]->text), *cq = z_field(car, 2, "Query");
    if (!z_query(cq, 0)) return "CheckNow: the state carrier must be a keyed snapshot carrier (Query S pattern (Key $k))";
    const Sx *snap = z_decl(m, "Snapshot", cq->items[1]->text), *dg = z_field(snap, 2, "Digest"), *rv = z_field(snap, 2, "Revision");
    if (!snap || !z_field(snap, 2, "Space")) return "CheckNow: the carrier's Snapshot (with Space) is not declared";
    if (!z_digest_ok(dg)) return "CheckNow: the Snapshot digest must be \"sha256:<64 lowercase hex>\" (checked before any materialization)";
    const Sx *em = z_decl(m, "Map", en->items[1]->text), *eq = z_field(em, 2, "Query"), *ef = z_field(em, 2, "From");
    if (!em || !z_query(eq, 1) || !ef || ef->n != 2 || !sx_equal(ef->items[1], st->items[1]))
        return "CheckNow: the Encode map must be a keyed snapshot map from the state carrier";
    if (!sx_equal(eq->items[1], cq->items[1]) || !sx_equal(eq->items[2], cq->items[2]) || !sx_equal(z_field(eq, 3, "Key"), z_field(cq, 3, "Key")))
        return "CheckNow: the Encode map must query the carrier's snapshot, pattern and key";
    if (cert) {
        sx_push(cert, dc_form("Snapshot", sx_copy(snap->items[1]), sx_copy(dg), rv ? sx_copy(rv) : dc_form("Revision", dc_sym("None"), NULL), NULL));
        sx_push(cert, dc_form("Assumptions", dc_form("DigestCheckedBeforeMaterialization", NULL),
                              dc_form("FunctionalMap", sx_copy(en->items[1]), NULL), NULL));
    }
    int nobs = 0;
    for (size_t i = 2; i < mach->n; i++) {
        const Sx *o = mach->items[i];
        int obs = sx_head_is(o, "Observe"), act = sx_head_is(o, "Action");
        if (!obs && !act) continue;
        for (size_t k = 1; k + 1 < o->n; k += 2) {
            const Sx *mp = o->items[k + 1]->kind == SX_SYM ? z_decl(m, "Map", o->items[k + 1]->text) : NULL;
            if (!mp) return "CheckNow: observation and action maps must be declared Maps";
            if (obs) {
                const Sx *oq = z_field(mp, 2, "Query");
                if (!sx_equal(mp->items[1], en->items[1]) && !(oq && sx_equal(oq, eq)))
                    return "CheckNow: an observation is not the Encode query; deciding it needs the snapshot content";
                nobs++;
                if (cert) sx_push(cert, dc_form("CodeIsObservation", sx_copy(o->items[k]), sx_copy(o->items[k + 1]), NULL));
            } else {
                if (!z_identity(mp)) return "CheckNow: an action is not the identity body; deciding it needs the snapshot content";
                if (cert) sx_push(cert, dc_form("IdentityAction", sx_copy(o->items[k]), sx_copy(o->items[k + 1]), NULL));
            }
        }
    }
    if (!nobs) return "CheckNow: the machine declares no observation";
    return NULL;
}

/* NULL = not a snapshot request (caller falls through). */
Sx *dc_req_m7_snapshot(DcRun *r, const Sx *q, const char *h) {
    DcModule *m = r->m;
    DcScope sc = {"M7-Snapshot", -1, "", NULL};
    Sx *claim = dc_claim_of(q, "Literal");
    if (strcmp(h, "CheckNow") || q->n != 2 || q->items[1]->kind != SX_SYM)
        return z_unsup(m, &sc, claim, "snapshot carriers: M7 decides (CheckNow R) only");
    Sx *cert = dc_form("Certificate", dc_form("Kind", dc_sym("SymbolicSnapshot"), NULL), NULL);
    const char *why = z_check(m, q->items[1]->text, cert);
    if (why) { sx_free(cert); return z_unsup(m, &sc, claim, why); }
    int replayed = z_check(m, q->items[1]->text, NULL) == NULL;
    const Sx *rep = z_decl(m, "Representation", q->items[1]->text);
    Sx *subj = dc_form("Subject", dc_form("Representation", dc_sym(q->items[1]->text), NULL),
                       dc_form("Machine", sx_copy(z_field(rep, 2, "Of")->items[1]), NULL), NULL);
    return dc_envelope_scoped(m, VERDICT_HOLDS, replayed, claim, subj,
        dc_form("Value", dc_form("SymbolicCheck", dc_form("Holds", dc_sym("ForAllContent"), NULL), NULL), NULL),
        dc_form("Evidence", cert, NULL), NULL, &sc);
}
