;; Where witnesses and certificates of one kind stop: an observation-based policy
;; separates two states more than any fixed word, and a behavioral distance that
;; no finite test attains.  Both modules are stochastic, so the first release must
;; answer each request below with Unsupported.  Specification, Sections 4 and 7.
;; @excerpt adaptive-probe
(DC.Module AdaptiveProbe
  (Profile Stochastic)
  (Carrier S (Of Symbol) (Enum x x2 r1 r2 s1 s2 A B C))
  (Carrier Report (Of Nat) (Enum 0 1 2 3 4 5))
  (Map report (From S) (To Report)
    (Cases (x 0) (x2 0) (r1 1) (r2 2) (s1 1) (s2 2) (A 3) (B 4) (C 5)))
  (TransitionKernel StepA (From S) (To S)
    (Row x (Mass r1 (Rat 1 2)) (Mass r2 (Rat 1 2)))
    (Row x2 (Mass s1 (Rat 1 2)) (Mass s2 (Rat 1 2)))
    (Row r1 (Mass r1 1)) (Row r2 (Mass r2 1)) (Row s1 (Mass s1 1)) (Row s2 (Mass s2 1))
    (Row A (Mass A 1)) (Row B (Mass B 1)) (Row C (Mass C 1)))
  (TransitionKernel StepB (From S) (To S)
    (Row x (Mass x 1)) (Row x2 (Mass x2 1))
    (Row r1 (Mass A 1)) (Row s1 (Mass B 1)) (Row r2 (Mass C 1)) (Row s2 (Mass C 1))
    (Row A (Mass A 1)) (Row B (Mass B 1)) (Row C (Mass C 1)))
  (TransitionKernel StepC (From S) (To S)
    (Row x (Mass x 1)) (Row x2 (Mass x2 1))
    (Row r2 (Mass A 1)) (Row s2 (Mass B 1)) (Row r1 (Mass C 1)) (Row s1 (Mass C 1))
    (Row A (Mass A 1)) (Row B (Mass B 1)) (Row C (Mass C 1)))
  (Machine Probe (States S) (Observe report report)
    (Action a StepA) (Action b StepB) (Action c StepC))
  (Map merge-x (From S) (To S)
    (Cases (x x) (x2 x) (r1 r1) (r2 r2) (s1 s1) (s2 s2) (A A) (B B) (C C)))
  (Representation MergeX (Of Probe) (Encode merge-x)))
;; @end
;; @excerpt adaptive-probe-requests
!(dc.run AdaptiveProbe (MeasureTrace MergeX (Horizon (Steps 2))))
!(dc.run AdaptiveProbe (CheckTrace MergeX (Horizon (Steps 2)) (Within (Rat 3 4))))
!(dc.run AdaptiveProbe (CheckTrace MergeX (Horizon (Steps 2)) (Policies ObservationBased)
                                          (Within (Rat 3 4))))
!(dc.run AdaptiveProbe (MeasureTrace MergeX (Horizon (Steps 2)) (Policies ObservationBased)))
;; @end

;; @excerpt unattained-supremum
(DC.Module UnattainedSupremum
  (Profile Stochastic)
  (Carrier S (Of Symbol) (Enum x y p))
  (Carrier Report (Of Nat) (Enum 0 1))
  (Map report (From S) (To Report) (Cases (x 0) (y 0) (p 1)))
  (TransitionKernel Step (From S) (To S)
    (Row x (Mass x (Rat 1 2)) (Mass p (Rat 1 2)))
    (Row y (Mass y 1))
    (Row p (Mass p 1)))
  (Machine Leak (States S) (Observe report report) (Action step Step))
  (Map join-xy (From S) (To S) (Cases (x x) (y x) (p p)))
  (Representation JoinXY (Of Leak) (Encode join-xy)))
;; @end
;; @excerpt unattained-supremum-requests
!(dc.run UnattainedSupremum (MeasureBehavioral JoinXY))
!(dc.run UnattainedSupremum (MeasureBehavioral JoinXY (Horizon (Steps 3))))
!(dc.run UnattainedSupremum (CheckBehavioral JoinXY (Within (Rat 99 100))))
!(dc.run UnattainedSupremum (MeasureBehavioral JoinXY (Discount (Rat 1 2))))
;; @end
