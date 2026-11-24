(DC.Module L
  (Profile Stochastic)
  (Carrier Z (Of Symbol) (Enum z)))
(DC.Module R
  (Profile Stochastic)
  (Use Linear)
  (Import L (Only Z))
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum o p))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass b 1)))
  (Map obs (From S) (To O) (Table (a o) (b p)))
  (Machine M (States S) (Observe obs obs) (Action go K))
  (Derive LM (MinimalLinear M)))
!(dc.run R LM)
