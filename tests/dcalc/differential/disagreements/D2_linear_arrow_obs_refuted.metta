;; D2 minimal: one-state machines with different reports, arrow L = [[1]] (row sums to 1).
;; Spec Def 3.8: valid (L eta' = eta); R_a = 0; S_0 = 1, S_1 = -1 -> grade (lambda 1, rho 1), Checked.
(DC.Module D2Min
  (Profile Stochastic)
  (Use Linear)
  (Carrier Report (Of Nat) (Enum 0 1))
  (Carrier SA (Of Symbol) (Enum A0))
  (Map repA (From SA) (To Report) (Cases (A0 0)))
  (TransitionKernel KAa (From SA) (To SA) (Row A0 (Mass A0 1)))
  (Machine MA (States SA) (Observe report repA) (Action a KAa))
  (Carrier SB (Of Symbol) (Enum B0))
  (Map repB (From SB) (To Report) (Cases (B0 1)))
  (TransitionKernel KBa (From SB) (To SB) (Row B0 (Mass B0 1)))
  (Machine MB (States SB) (Observe report repB) (Action a KBa))
  (LinearArrow L (Source MA) (Target MB) (Kind Positive) (Matrix (Rows (A0 (B0 1)))))
  (Derive LChecked (CheckLinearArrow L)))
!(dc.run D2Min LChecked)
