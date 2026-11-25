;; Negative: Reach start z is not a state of the parent carrier S -> InvalidInput.
;; Spec l.1719 allows carrier-expr (Reach machine (From element+)); stoch.c:52 accepts only (Enum ...).
(DC.Module R
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Carrier O (Of Symbol) (Enum o p))
  (Map obs (From S) (To O) (Cases (a o) (b o) (c p)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe obs obs) (Action go K))
  (Carrier Seen (Of Symbol) (Reach M (From z)))
  (Machine MS (States Seen) (Like M))
  (Derive LM (MinimalLinear M))
  (Derive LS (MinimalLinear MS)))

!(dc.run R LM)
!(dc.run R LS)
