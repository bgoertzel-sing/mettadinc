;; Negative: a machine on a Reach carrier whose action (K2, not an action of M) sends mass outside it -> InvalidInput.
(DC.Module X
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Carrier O (Of Symbol) (Enum o p))
  (Map obs (From S) (To O) (Cases (a o) (b o) (c p)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (TransitionKernel K2 (From S) (To S) (Row a (Mass c 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe obs obs) (Action go K))
  (Carrier Seen (Of Symbol) (Reach M (From a)))
  (Machine MX (States Seen) (Observe obs obs) (Action jump K2))
  (Derive LX (MinimalLinear MX)))
!(dc.run X LX)
