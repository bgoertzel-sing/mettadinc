;; Remaining M0 blocker (a) for doc04 AnchorMigration/TaskResume: a (To Bool) map used as an Observe port.
;; A1 -> Unsupported (blocker); A1C control (same, observing into an Enum carrier) -> Checked.
(DC.Module A1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map live (From A) (To Bool) (Cases (p True) (q False)))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run A1 (CheckNow R))
(DC.Module A1C
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map live (From A) (To O) (Cases (p o1) (q o2)))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run A1C (CheckNow R))
