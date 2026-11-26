;; Review 2: same two machines as rv2_f1_reach_first.metta, parent-carrier machine declared first.
(DC.Module RV2F2
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Map f (From S) (To S) (Cases (a b) (b a) (c c)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass a 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe f f) (Action go K))
  (Machine MC (States S) (Observe f f) (Action go f))
  (Carrier Seen (Of Symbol) (Reach M (From a)))
  (Machine MS (States Seen) (Observe f f) (Action go f)))
!(dc.run RV2F2 (TracePartition MS))
!(dc.run RV2F2 (TracePartition MC))
