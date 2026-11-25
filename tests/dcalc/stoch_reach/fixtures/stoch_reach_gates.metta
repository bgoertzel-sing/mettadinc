;; Gates for t-2026-11-24-mettadinc-stoch-reach-reader: (Reach M (From s+)) carriers in the stochastic reader.
;; Spec 5.3 l.1810-1812: the forward closure of the starts under the actions of M; a stochastic action
;; moves x to every y it gives mass > 0.
(DC.Module Z
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Carrier O (Of Symbol) (Enum o p))
  (Map obs (From S) (To O) (Cases (a o) (b o) (c p)))
  ;; a listed zero-mass outcome is NOT a successor: Reach from a must be {a,b}, not {a,b,c}
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1) (Mass c 0)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (TransitionKernel K2 (From S) (To S) (Row a (Mass c 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe obs obs) (Action go K))
  (Carrier Seen (Of Symbol) (Reach M (From a)))
  (Machine MZ (States Seen) (Like M))
  (Derive LZ (MinimalLinear MZ)))
!(dc.run Z LZ)
