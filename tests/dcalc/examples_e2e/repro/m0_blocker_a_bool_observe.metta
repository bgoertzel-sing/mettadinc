;; M0 blocker (a) for doc04 AnchorMigration/TaskResume: a (To Bool) map used as an Observe port.
;; Lowered by t-2026-11-23-mettadinc-m0-bool-observe: A1 -> Checked (Encode id is injective, so every code class is one
;; state and live factors through it; spec Prop 4.5).  A1C control (same, observing into an Enum carrier) -> Checked.
;; Regression gate: tests/dcalc/m0_bool_observe/run_m0_bool_observe.py (it was Unsupported "outside the M0 fragment").
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
