;; Eight-state calibration.  Specification, Section 6.1.
;; @excerpt eight-state-module
(DC.Module EightState
  (Profile Crisp)
  (Carrier Bit   (Of Nat) (Enum 0 1))
  (Carrier State (Of (Tuple Nat Nat Nat)) (Product Bit Bit Bit))
  (Carrier Pair  (Of (Tuple Nat Nat)) (Product Bit Bit))
  (Map read-a  (From State) (To Bit)   (Cases ((Tuple $a $b $c) $a)))
  (Map swap-ab (From State) (To State) (Cases ((Tuple $a $b $c) (Tuple $b $a $c))))
  (Map keep-ab (From State) (To Pair)  (Cases ((Tuple $a $b $c) (Tuple $a $b))))
  (Machine Concrete (States State) (Observe a read-a) (Action swap swap-ab))
  (Representation KeepA  (Of Concrete) (Encode read-a))
  (Representation KeepAB (Of Concrete) (Encode keep-ab))
  (Measure Uniform (On State) (Uniform))
  (Derive Repair (Refine KeepA (Preserve Encoding) (Until Stable) (Under Uniform)))
  (Derive AB (InduceExact KeepAB))

  (Carrier Code (Of Nat) (Enum 0 1 2 3))
  (Map code-a    (From Code) (To Bit)  (Table (0 0) (1 0) (2 1) (3 1)))
  (Map code-swap (From Code) (To Code) (Table (0 0) (1 1) (2 2) (3 3)))
  (Map pair-code (From Pair) (To Code) (Cases ((Tuple $a $b) (Add (Mul 2 $a) $b))))
  (Machine Codes (States Code) (Observe a code-a) (Action swap code-swap))
  (AbstractionMap ABToCodes
    (Source (Output AB Machine)) (Target Codes) (Map pair-code))
  (Derive SecondChecked (CheckAbstractionMap ABToCodes))
  (Derive Composed
    (Then (Output AB AbstractionMap) (Output SecondChecked Value))))
;; @end
;; @excerpt eight-state-requests
!(dc.run EightState (Defects KeepA))
!(dc.run EightState (CheckUpdates KeepA))
!(dc.run EightState (CheckBehavioral KeepA))
!(dc.run EightState (CheckBehavioral KeepA (Horizon (Steps 0))))
!(dc.run EightState (InduceExact KeepA))
!(dc.run EightState Repair)
!(dc.run EightState (SamePartition (Output Repair Representation) KeepAB))
!(dc.run EightState AB)
!(dc.run EightState Composed)
;; @end
