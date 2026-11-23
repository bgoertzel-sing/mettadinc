;; M0 blocker (f), found by t-2026-11-23-mettadinc-m0-bool-observe: a (Body ($x) e) map in a Crisp module.
;; doc04 AnchorMigration's lesion and TaskResume's checkpoint-with-reads are Body maps; both are also declared with a
;; type form (blocker b), which hides this one.  F1 -> Unsupported (Body is lowered only in Graded FiniteSets or
;; Contracts modules); F1C control (the same map as Cases) -> Checked.
(DC.Module F1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map reset (From A) (To A) (Body ($x) p))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe id id) (Action reset reset))
  (Representation R (Of M) (Encode id)))
!(dc.run F1 (CheckNow R))
(DC.Module F1C
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map reset (From A) (To A) (Cases ($a p)))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe id id) (Action reset reset))
  (Representation R (Of M) (Encode id)))
!(dc.run F1C (CheckNow R))
