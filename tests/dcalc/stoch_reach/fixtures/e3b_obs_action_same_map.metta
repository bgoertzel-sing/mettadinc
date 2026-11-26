;; Review 1 F2 (t-2026-11-24-mettadinc-stoch-reach-reader): one parent map used both as the Observe port and as an
;; Action of a machine on a Reach carrier, with no parent kernel of that name. MS lists Observe first, MS2 lists Action
;; first; both are valid and must get the same answer (the restriction cache must key on the role as well).
(DC.Module E3B
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Map f (From S) (To S) (Cases (a b) (b b) (c c)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe f f) (Action go K))
  (Carrier Seen (Of Symbol) (Reach M (From a)))
  (Machine MS (States Seen) (Observe f f) (Action step f))
  (Machine MS2 (States Seen) (Action step f) (Observe f f)))
!(dc.run E3B (TracePartition MS))
!(dc.run E3B (TracePartition MS2))
