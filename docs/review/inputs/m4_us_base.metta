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
