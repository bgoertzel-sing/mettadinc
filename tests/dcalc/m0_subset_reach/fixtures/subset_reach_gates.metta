;; Gates for t-2026-11-20-mettadinc-m0-subset-reach: Subset and Reach carriers in the Crisp M0 lowering.
;; Subset: spec 5.3 (txt l.1774) "(Subset C p) restricts a carrier by an admitted predicate"; grammar l.1718.
;; Reach:  spec 5.3 "Reachability scopes" (txt l.1810) "the forward closure of the initial set under the actions of M"; grammar l.1719.
;; Hand answers (run_m0_subset_reach.py checks them):
;;  S2  B = {x in {p,q,r} | keep x = True} = {p,q}; enc p->k1, q->k2 injective on B -> CheckNow Checked.
;;  S2C same machine on all of A: enc p = enc r = k1 but obs p = o1, obs r = o2 -> Refuted, witness (p r).
;;      S2C is the control: a lowering that kept r (wrong state set) would answer Refuted for S2 too.
;;  T2  Reach M0 From p, step p->q, q->p, r->r: {p} -> {p,q} -> fixed point {p,q}; same answer as S2 (Checked).
;;  SX  keep has no case for r -> InvalidInput.   SY  action go sends p to r, outside B -> InvalidInput.
(DC.Module S2
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r))
  (Carrier K (Of Symbol) (Enum k1 k2))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map keep (From A) (To Bool) (Cases (p True) (q True) (r False)))
  (Carrier B (Of Symbol) (Subset A keep))
  (Map enc (From A) (To K) (Cases (p k1) (q k2) (r k1)))
  (Map obs (From A) (To O) (Cases (p o1) (q o2) (r o2)))
  (Map stay (From A) (To A) (Cases ($a $a)))
  (Machine M (States B) (Observe obs obs) (Action stay stay))
  (Representation R (Of M) (Encode enc)))
!(dc.run S2 (CheckNow R))
(DC.Module S2C
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r))
  (Carrier K (Of Symbol) (Enum k1 k2))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map enc (From A) (To K) (Cases (p k1) (q k2) (r k1)))
  (Map obs (From A) (To O) (Cases (p o1) (q o2) (r o2)))
  (Map stay (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe obs obs) (Action stay stay))
  (Representation R (Of M) (Encode enc)))
!(dc.run S2C (CheckNow R))
(DC.Module T2
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r))
  (Carrier K (Of Symbol) (Enum k1 k2))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map enc (From A) (To K) (Cases (p k1) (q k2) (r k1)))
  (Map obs (From A) (To O) (Cases (p o1) (q o2) (r o2)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r r)))
  (Machine M0 (States A) (Observe obs obs) (Action step step))
  (Carrier C (Of Symbol) (Reach M0 (From p)))
  (Machine M (States C) (Observe obs obs) (Action step step))
  (Representation R (Of M) (Encode enc)))
!(dc.run T2 (CheckNow R))
(DC.Module SX
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r))
  (Map keep (From A) (To Bool) (Cases (p True) (q True)))
  (Carrier B (Of Symbol) (Subset A keep))
  (Map stay (From A) (To A) (Cases ($a $a)))
  (Machine M (States B) (Observe stay stay) (Action stay stay))
  (Representation R (Of M) (Encode stay)))
!(dc.run SX (CheckNow R))
(DC.Module SY
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r))
  (Map keep (From A) (To Bool) (Cases (p True) (q True) (r False)))
  (Carrier B (Of Symbol) (Subset A keep))
  (Map go (From A) (To A) (Cases (p r) (q q) (r r)))
  (Machine M (States B) (Observe go go) (Action go go))
  (Representation R (Of M) (Encode go)))
!(dc.run SY (CheckNow R))
