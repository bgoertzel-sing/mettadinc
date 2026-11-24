;; Gates for t-2026-11-23-mettadinc-m0-bool-observe: a (To Bool) map used as an Observe port in the Crisp M0 lowering.
;; Spec: Def 3.1/3.2 (txt l.676-700): each query label has a value type Y_j with crisp equality unless declared
;;  otherwise and o_j : X -> Y_j is total; registry libraries.Core: builtin type Bool, constants True and False;
;;  5.4 (l.1851-1857): every input matches exactly one case, outputs stay in the declared type.
;; So (Observe live live) with (Map live (From A) (To Bool) ...) is the query live : A -> {False, True} under
;; literal equality, the same machine as observing into an Enum carrier {yes, no} (BOE is that control).
;;
;; Machine (BO, BOE): states p q r s t; live p,r,t = True, q,s = False; step p<->q, r<->s, t->t.
;; Hand answers (run_m0_bool_observe.py checks them):
;;  R1 e1: {p,r}->k1 {q,s}->k2 {t}->k3.  CheckNow: each code class has one live value -> Checked.
;;         CheckUpdates: k1 steps to {q,s}=k2, k2 steps to {p,r}=k1, k3 to k3 -> Checked.  CheckBehavioral -> Checked.
;;  R2 e2: {p,q}->k1 {r,s}->k2 {t}->k3.  CheckNow: p,q share k1, live p = True, live q = False -> Refuted, witness (p q).
;;  R3 e3: {p,r,t}->k1 {q,s}->k2.  CheckNow: k1 all True, k2 all False -> Checked.
;;         CheckUpdates: p,t share k1 but step p = q (k2), step t = t (k1) -> Refuted.
;;         CheckBehavioral: live traces p: T F T F ..., t: T T T ... differ after one step -> Refuted.
;;  Min (MinimizeForQueries M): behavioural classes {p,r} {q,s} {t} -> 3 classes.
;;  A lowering that ignored the Bool observation (constant) would answer R2 CheckNow Checked; one that kept
;;  it as an unknown map would answer Unsupported.  BOE must give the same statuses as BO on every request.
;;  BT: same machine on the scope (Reach M0 From t) = {t}: R2 CheckNow -> Checked (one state).
;; Negative and limit cases:
;;  BX live gives maybe on q, an undeclared name -> InvalidInput (spec 5.2: an atom must name a constant of the type).
;;  BX2 live gives yes (an element of carrier O, a declared name) on q -> InvalidInput: the value is outside Bool.
;;  BY live has no case for q -> InvalidInput (not total).   BW overlapping cases -> InvalidInput.
;;  BZ the Bool map starts at another carrier -> InvalidInput (does not start at the state carrier).
;;  BU1 a Representation encoding into Bool -> Unsupported, reason names the form (only Observe is lowered).
;;  BU2 a Bool Observe map whose case body uses an operator outside the M0 Cases fragment (Xor outside a Neural
;;      module) -> Unsupported.  (It used Eq until t-2026-11-23-mettadinc-m0-cases-logic lowered If/Eq/And/Or/Not;
;;      the Eq version is m0_cases_logic LG5, Refuted.)
;;  BU3 the same Bool Observe map in a Graded module -> Unsupported (only Crisp is lowered here).
(DC.Module BO
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) (q False) (r True) (s False) (t True)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1))
  (Representation R2 (Of M) (Encode e2))
  (Representation R3 (Of M) (Encode e3))
  (Derive Min (MinimizeForQueries M)))
!(dc.run BO (CheckNow R1))
!(dc.run BO (CheckUpdates R1))
!(dc.run BO (CheckBehavioral R1))
!(dc.run BO (CheckNow R2))
!(dc.run BO (CheckNow R3))
!(dc.run BO (CheckUpdates R3))
!(dc.run BO (CheckBehavioral R3))
!(dc.run BO Min)
(DC.Module BOE
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To O) (Cases (p yes) (q no) (r yes) (s no) (t yes)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1))
  (Representation R2 (Of M) (Encode e2))
  (Representation R3 (Of M) (Encode e3))
  (Derive Min (MinimizeForQueries M)))
!(dc.run BOE (CheckNow R1))
!(dc.run BOE (CheckUpdates R1))
!(dc.run BOE (CheckBehavioral R1))
!(dc.run BOE (CheckNow R2))
!(dc.run BOE (CheckNow R3))
!(dc.run BOE (CheckUpdates R3))
!(dc.run BOE (CheckBehavioral R3))
!(dc.run BOE Min)
(DC.Module BT
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) (q False) (r True) (s False) (t True)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M0 (States A) (Observe live live) (Action step step))
  (Carrier C (Of Symbol) (Reach M0 (From t)))
  (Machine M (States C) (Observe live live) (Action step step))
  (Representation R2 (Of M) (Encode e2)))
!(dc.run BT (CheckNow R2))
(DC.Module BX
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) (q maybe) (r True) (s False) (t True)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1)))
!(dc.run BX (CheckNow R1))
(DC.Module BX2
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) (q yes) (r True) (s False) (t True)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1)))
!(dc.run BX2 (CheckNow R1))
(DC.Module BY
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) (r True) (s False) (t True)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1)))
!(dc.run BY (CheckNow R1))
(DC.Module BW
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) ($a False)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1)))
!(dc.run BW (CheckNow R1))
(DC.Module BZ
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier B (Of Symbol) (Enum u v))
  (Map live (From B) (To Bool) (Cases (u True) (v False)))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run BZ (CheckNow R))
(DC.Module BU1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) (q False) (r True) (s False) (t True)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation RB (Of M) (Encode live)))
!(dc.run BU1 (CheckNow RB))
(DC.Module BU2
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases ($a (Xor $a q))))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1)))
!(dc.run BU2 (CheckNow R1))
(DC.Module BU3
  (Profile Graded)
  (Carrier A (Of Symbol) (Enum p q r s t))
  (Carrier K (Of Symbol) (Enum k1 k2 k3))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map live (From A) (To Bool) (Cases (p True) (q False) (r True) (s False) (t True)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r s) (s r) (t t)))
  (Map e1 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k3)))
  (Map e2 (From A) (To K) (Cases (p k1) (q k1) (r k2) (s k2) (t k3)))
  (Map e3 (From A) (To K) (Cases (p k1) (q k2) (r k1) (s k2) (t k1)))
  (Machine M (States A) (Observe live live) (Action step step))
  (Representation R1 (Of M) (Encode e1)))
!(dc.run BU3 (CheckNow R1))
