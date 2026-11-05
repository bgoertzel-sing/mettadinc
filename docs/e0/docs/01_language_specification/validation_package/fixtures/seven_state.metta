;; Seven-state chain: behavioral, trace and linear answers differ.
;; Mandatory for every implementation that claims a stochastic request; the first
;; release must answer each request below with Unsupported.  Specification, Section 7.
;; @excerpt seven-state-module
(DC.Module SevenState
  (Profile Stochastic)
  (Use Linear)
  (Carrier S (Of Symbol) (Enum x y u v w p q))
  (Carrier Report (Of Nat) (Enum 0 1 2))
  (Map report (From S) (To Report)
    (Cases (x 0) (y 0) (u 0) (v 0) (w 0) (p 1) (q 2)))
  (TransitionKernel Step (From S) (To S)
    (Row x (Mass u (Rat 1 2)) (Mass v (Rat 1 2)))
    (Row y (Mass w 1))
    (Row u (Mass p 1))
    (Row v (Mass q 1))
    (Row w (Mass p (Rat 1 2)) (Mass q (Rat 1 2)))
    (Row p (Mass p 1))
    (Row q (Mass q 1)))
  (Machine Chain (States S) (Observe report report) (Action step Step))
  (Map merge-xy (From S) (To S)
    (Cases (x x) (y x) (u u) (v v) (w w) (p p) (q q)))
  (Representation MergeXY (Of Chain) (Encode merge-xy))
  (Derive Bisimulation (MinimizeForQueries Chain))
  (Derive TraceClasses (TracePartition Chain))
  (Derive Behavioral   (CheckBehavioral MergeXY))
  (Derive Trace        (CheckTrace MergeXY))
  (Derive Linear       (MinimalLinear Chain))
;; @end
;; @excerpt seven-state-positive
  (Carrier S5 (Of Symbol) (Enum X5 U5 V5 P5 Q5))
  (Map report5 (From S5) (To Report) (Cases (X5 0) (U5 0) (V5 0) (P5 1) (Q5 2)))
  (TransitionKernel Step5 (From S5) (To S5)
    (Row X5 (Mass U5 (Rat 1 2)) (Mass V5 (Rat 1 2)))
    (Row U5 (Mass P5 1)) (Row V5 (Mass Q5 1)) (Row P5 (Mass P5 1)) (Row Q5 (Mass Q5 1)))
  (Machine Chain5 (States S5) (Observe report report5) (Action step Step5))
  (LinearArrow Lpos (Source Chain) (Target Chain5) (Kind Positive)
    (Matrix (Rows (x (X5 1)) (y (X5 1)) (u (U5 1)) (v (V5 1))
                  (w (U5 (Rat 1 2)) (V5 (Rat 1 2))) (p (P5 1)) (q (Q5 1)))))
  (Derive LposChecked (CheckLinearArrow Lpos))
  (Derive Positive (PositiveRealization Chain (Candidate Lpos))))
;; @end
;; @excerpt seven-state-requests
!(dc.run SevenState Bisimulation)
!(dc.run SevenState TraceClasses)
!(dc.run SevenState Behavioral)
!(dc.run SevenState (MeasureBehavioral MergeXY (Discount (Rat 9 10))))
!(dc.run SevenState Trace)
!(dc.run SevenState Linear)
!(dc.run SevenState Positive)
;; @end
