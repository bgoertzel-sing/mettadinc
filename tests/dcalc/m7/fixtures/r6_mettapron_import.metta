(DC.Module KImport
  (Profile Crisp)
  (Carrier X (Of Nat) (Enum 0 1))
  (TransitionKernel Step (From X) (To X) (Import MeTTaProN step-model))
  (Map stay (From X) (To X) (Cases (0 0) (1 1)))
  (Machine M (States X) (Action stay stay)))
!(dc.run KImport (CheckNow M))
