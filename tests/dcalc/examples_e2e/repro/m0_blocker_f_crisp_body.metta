;; M0 blocker (f), found by t-2026-11-23-mettadinc-m0-bool-observe: a (Body ($x) e) map in a Crisp module.
;; doc04 AnchorMigration's lesion and TaskResume's checkpoint-with-reads are Body maps; both are also declared with a
;; type form (blocker b), which hides this one.  F1 was Unsupported (Body was lowered only in Graded FiniteSets or
;; Contracts modules); since t-2026-11-24-mettadinc-m0-body-maps F1 -> Checked, Blocks (p) (q), byte-for-byte as its
;; control F1C (the same map as Cases), which is unchanged (gate: tests/dcalc/m0_body_maps).
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
