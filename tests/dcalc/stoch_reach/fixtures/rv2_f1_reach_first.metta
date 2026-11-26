;; Review 2 (t-2026-11-24-mettadinc-stoch-reach-reader): a deterministic Map used as an Action (V03 0/1 kernel)
;; on a Reach-carrier machine, then the same map as an Action on the parent carrier. Must give the same answers
;; as rv2_f2_parent_first.metta (declaration order must not matter); the V03 kernel is keyed by (map, carrier).
(DC.Module RV2F1
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Map f (From S) (To S) (Cases (a b) (b a) (c c)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass a 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe f f) (Action go K))
  (Carrier Seen (Of Symbol) (Reach M (From a)))
  (Machine MS (States Seen) (Observe f f) (Action go f))
  (Machine MC (States S) (Observe f f) (Action go f)))
!(dc.run RV2F1 (TracePartition MS))
!(dc.run RV2F1 (TracePartition MC))
