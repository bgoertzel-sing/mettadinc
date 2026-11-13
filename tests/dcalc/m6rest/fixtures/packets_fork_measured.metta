;; m6-rest review-2 F1: the spec fixture receipt_packets.metta (validation_package/fixtures) with a Fork in PacketMerges.
;; MergeMemory is declared in HyperseedMemory and imported by name (Only ... MergeMemory); the Fork names it.
;; Shared Measured: P12/P13 must match the spec fixture byte for byte.
;; Evidence-packet memory.  Specification, Sections 4 and 12.4.
;; @excerpt packets-module
(DC.Module HyperseedMemory
  (Profile Graded)
  (Use FiniteSets)                ; supplies ReceiptUnion on packet symbols
  (Carrier Packet (Of Symbol) (Enum Empty UOnly VOnly Both))
  (Map posterior (From Packet) (To Rational01)
    (Cases (Empty (Rat 1 2)) (UOnly (Rat 3 4)) (VOnly (Rat 3 4)) (Both (Rat 9 10))))
  (Map add-u (From Packet) (To Packet)
    (Cases (Empty UOnly) (UOnly UOnly) (VOnly Both) (Both Both)))
  (Map add-v (From Packet) (To Packet)
    (Cases (Empty VOnly) (UOnly Both) (VOnly VOnly) (Both Both)))
  (Tolerance PosteriorDistance (On Rational01) (OneMinusAbsoluteDifference))
  (Machine Memory (States Packet)
    (Observe posterior posterior (Values PosteriorDistance))
    (Action add-u add-u) (Action add-v add-v))
  (Representation PosteriorOnly (Of Memory) (Encode posterior)
    (Codes PosteriorDistance))
  (Measure Uniform (On Packet) (Uniform))
  (Derive Repair (Refine PosteriorOnly (Preserve Encoding) (Until Stable) (Under Uniform)))
  (Derive TwoClass
    (WeakestWithin Memory (Within (Rat 3 20)) (Kind Behavioral) (Discount 1)
                   (Under Uniform) (Search Exhaustive)))
  (Map pick-both (From Packet) (To Packet)
    (Cases (Empty Empty) (UOnly Both) (VOnly Both) (Both Both)))
  (Derive TwoClassMachine
    (InduceApprox (Output TwoClass Representation) (Representatives (Choose pick-both))))
;; @end
;; @excerpt packets-merge
  (Map union-packets (From (Product Packet Packet)) (To Packet)
    (Body ($pair) (ReceiptUnion (GetTuple $pair 0) (GetTuple $pair 1))))
  (Machine MergeMemory (States Packet)       ; the merge is its only operation
    (Observe posterior posterior) (Merge union union-packets))
  (Representation PosteriorCodes (Of MergeMemory) (Encode posterior))
  (Derive MergeRepair (Refine PosteriorCodes (Preserve Encoding) (Until Stable))))
;; @end
;; @excerpt packets-independent-merge
(DC.Module PacketMerges
  (Profile Graded)
  (Use FiniteSets Contracts)
  (Import HyperseedMemory (Only Packet posterior union-packets PosteriorDistance MergeMemory))
  (Map posterior-of-union (From (Product Packet Packet)) (To Rational01)
    (Body ($pair) (posterior (union-packets $pair))))
  (Map odds-merge (From (Product Packet Packet)) (To Rational01)
    (Body ($pair)
      (Div (Mul (posterior (GetTuple $pair 0)) (posterior (GetTuple $pair 1)))
           (Add (Mul (posterior (GetTuple $pair 0)) (posterior (GetTuple $pair 1)))
                (Mul (Sub 1 (posterior (GetTuple $pair 0))) (Sub 1 (posterior (GetTuple $pair 1))))))))
  (Carrier PacketPair (Of (Tuple Symbol Symbol)) (Product Packet Packet))
  (Tolerance SamePair (On PacketPair) (Discrete))
  (Fork Copies (Of MergeMemory) (Merge union) (Shared Measured))
  (Implementation IndependentMerge (Ideal posterior-of-union) (Actual odds-merge)
    (Audit PacketPair) (InputDistance SamePair) (OutputDistance PosteriorDistance) (Over Copies)))
;; @end
;; @excerpt packets-requests
!(dc.run HyperseedMemory (CheckNow PosteriorOnly))
!(dc.run HyperseedMemory (CheckBehavioral PosteriorOnly))
!(dc.run HyperseedMemory (Defects PosteriorOnly))
!(dc.run HyperseedMemory (MeasureBehavioral PosteriorOnly (Discount (Rat 9 10))))
!(dc.run HyperseedMemory (CheckBehavioral PosteriorOnly (Within (Rat 3 20))))
!(dc.run HyperseedMemory (CheckBehavioral PosteriorOnly (Within (Rat 1 10))))
!(dc.run HyperseedMemory Repair)
!(dc.run HyperseedMemory TwoClass)
!(dc.run HyperseedMemory TwoClassMachine)
!(dc.run HyperseedMemory (CheckUpdates PosteriorCodes))
!(dc.run HyperseedMemory MergeRepair)
!(dc.run PacketMerges (CheckImplementation IndependentMerge (Grade 1 (Rat 3 20))))
!(dc.run PacketMerges (CheckImplementation IndependentMerge (Grade 1 (Rat 1 10))))
;; @end
