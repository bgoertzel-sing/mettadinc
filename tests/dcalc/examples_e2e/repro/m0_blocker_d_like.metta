;; Remaining M0 blocker (d): (Machine X (States S) (Like Y)).
;; D1 -> Unsupported (blocker); D1C control (the same machine written out) -> Checked.
(DC.Module D1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M0 (States A) (Observe id id) (Action id id))
  (Machine M (States A) (Like M0))
  (Representation R (Of M) (Encode id)))
!(dc.run D1 (CheckNow R))
(DC.Module D1C
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M0 (States A) (Observe id id) (Action id id))
  (Machine M (States A) (Observe id id) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run D1C (CheckNow R))
