;; Body maps that use a form still outside the M0 fragment answer Unsupported, the reason naming the form
;; (t-2026-11-24-mettadinc-m0-body-maps).
;; BU1: If/Eq in a Body (doc04's Cases bodies use these; gap c).
(DC.Module BU1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map flip (From A) (To A) (Body ($x) (If (Eq $x p) q p)))
  (Map id   (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe id id) (Action flip flip))
  (Representation R (Of M) (Encode id)))
!(dc.run BU1 (CheckNow R))
;; BU2: GetTuple in a type-form Body.
(DC.Module BU2
  (Profile Crisp)
  (Carrier Atom (Of Symbol) (Enum present absent))
  (Carrier Link (Of Symbol) (Enum old none))
  (Carrier All  (Of (Tuple Symbol Symbol)) (Product Atom Link))
  (Map link (From (Tuple Symbol Symbol)) (To (Tuple Symbol)) (Body ($x) (Tuple (GetTuple $x 1))))
  (Map stay (From All) (To All) (Cases ($s $s)))
  (Machine M (States All) (Observe link link) (Action stay stay))
  (Representation R (Of M) (Encode link)))
!(dc.run BU2 (CheckNow R))
;; BU3: Sub (not among the M0 body operators) inside Add; the reason names Sub, the outermost such operator.
(DC.Module BU3
  (Profile Crisp)
  (Carrier N (Of Int) (Enum 0 1))
  (Carrier P (Of Int) (Enum 0 -1))
  (Map dec (From N) (To P) (Body ($n) (Add (Sub 0 $n) 0)))
  (Map id  (From N) (To N) (Cases ($n $n)))
  (Machine M (States N) (Observe id id) (Action id id))
  (Representation R (Of M) (Encode dec)))
!(dc.run BU3 (CheckNow R))
