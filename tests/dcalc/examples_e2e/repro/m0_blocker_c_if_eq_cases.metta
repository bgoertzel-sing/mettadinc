;; Remaining M0 blocker (c): If/Eq (also And/Or/Not) inside Cases bodies.
;; C1 -> Unsupported (blocker); C1C control (same function written as literal Cases) -> Checked.
(DC.Module C1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Map ob (From A) (To A) (Cases ($a (If (Eq $a p) p q))))
  (Machine M (States A) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run C1 (CheckNow R))
(DC.Module C1C
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Map ob (From A) (To A) (Cases (p p) (q q)))
  (Machine M (States A) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run C1C (CheckNow R))
