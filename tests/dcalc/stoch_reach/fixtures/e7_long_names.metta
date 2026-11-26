;; Review 1 F1 (t-2026-11-24-mettadinc-stoch-reach-reader): two kernels whose names share the first 30 characters.
;; Reach from a = {a,b,c}. a reaches c (observed p) under "two"; b does not. Correct TracePartition: {a},{b},{c}.
;; A restriction cache keyed by names truncated to 30 chars merges the kernels and answers {a b},{c}.
(DC.Module E7
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Carrier O (Of Symbol) (Enum o p))
  (Map obs (From S) (To O) (Cases (a o) (b o) (c p)))
  (TransitionKernel kernel_with_a_very_long_name_number_one (From S) (To S) (Row a (Mass b 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (TransitionKernel kernel_with_a_very_long_name_number_two (From S) (To S) (Row a (Mass c 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe obs obs) (Action one kernel_with_a_very_long_name_number_one) (Action two kernel_with_a_very_long_name_number_two))
  (Carrier Seen (Of Symbol) (Reach M (From a)))
  (Machine MR (States Seen) (Like M)))
!(dc.run E7 (TracePartition MR))
(DC.Module E7Short
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Carrier O (Of Symbol) (Enum o p))
  (Map obs (From S) (To O) (Cases (a o) (b o) (c p)))
  (TransitionKernel k1 (From S) (To S) (Row a (Mass b 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (TransitionKernel k2 (From S) (To S) (Row a (Mass c 1)) (Row b (Mass b 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe obs obs) (Action one k1) (Action two k2))
  (Carrier Seen (Of Symbol) (Reach M (From a)))
  (Machine MR (States Seen) (Like M)))
!(dc.run E7Short (TracePartition MR))
