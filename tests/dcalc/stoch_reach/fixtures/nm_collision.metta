;; t-2026-11-26-mettadinc-stoch-reach-followups case 1: a structured-image Map f gets a synthetic value carrier;
;; a user Carrier named f# must not be shadowed by it. NC (user carrier f#) must answer as NCR (same module, the
;; user carrier renamed h): g separates a, b, c -> Checked, 3 classes.
(DC.Module NC
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Map f (From S) (To (Tuple Int)) (Cases (a (Tuple 1)) (b (Tuple 1)) (c (Tuple 2))))
  (Carrier f# (Of Symbol) (Enum p q r))
  (Map g (From S) (To f#) (Cases (a p) (b q) (c r)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass a 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe o g) (Action go K)))
(DC.Module NCR
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Map f (From S) (To (Tuple Int)) (Cases (a (Tuple 1)) (b (Tuple 1)) (c (Tuple 2))))
  (Carrier h (Of Symbol) (Enum p q r))
  (Map g (From S) (To h) (Cases (a p) (b q) (c r)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass a 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe o g) (Action go K)))
!(dc.run NC (TracePartition M))
!(dc.run NCR (TracePartition M))
