;; Remaining M0 blocker (g), found by t-2026-11-23-mettadinc-m0-cases-logic: a (To Bool) map used as an Observe port
;; and declared with a type-form From (doc04 AnchorMigration live-old/live-new).  Neither the Bool Observe lowering (a,
;; From must name a carrier) nor the type-form lowering (b, To must be a carrier or a type form, not the builtin Bool)
;; takes it.  G1 -> Unsupported ("Observe live: Map live: field From"); G1C control (From AA) -> Checked.
(DC.Module G1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple p p) True) ((Tuple p q) False) ((Tuple q p) False) ((Tuple q q) True)))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run G1 (CheckNow R))
(DC.Module G1C
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From AA) (To Bool) (Cases ((Tuple p p) True) ((Tuple p q) False) ((Tuple q p) False) ((Tuple q q) True)))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run G1C (CheckNow R))
