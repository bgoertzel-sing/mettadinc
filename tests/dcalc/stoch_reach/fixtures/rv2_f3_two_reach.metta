;; Review 2: one map f as an Action on machines over two Reach carriers of the same parent
;; (Seen1 = {a b}, Seen2 = {c}); f maps each carrier into itself, so both are valid.
(DC.Module RV2F3
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum a b c))
  (Map f (From S) (To S) (Cases (a b) (b a) (c c)))
  (TransitionKernel K (From S) (To S) (Row a (Mass b 1)) (Row b (Mass a 1)) (Row c (Mass c 1)))
  (Machine M (States S) (Observe f f) (Action go K))
  (Carrier Seen1 (Of Symbol) (Reach M (From a)))
  (Carrier Seen2 (Of Symbol) (Reach M (From c)))
  (Machine MS1 (States Seen1) (Observe f f) (Action go f))
  (Machine MS2 (States Seen2) (Observe f f) (Action go f)))
!(dc.run RV2F3 (TracePartition MS1))
!(dc.run RV2F3 (TracePartition MS2))
