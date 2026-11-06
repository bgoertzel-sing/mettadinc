;; Example 1: compacting an agent's belief memory.
;; Four modules: the memory as first designed (floor-halving decay), the memory with
;; the repaired decay rule, six beliefs in parallel, and an evidence-receipt ledger
;; with forks and merges.  Forms marked PROPOSED are not in the current registry;
;; the example registry patch (ex1_registry_patch.json) adds them.

;; @excerpt belief-memory
(DC.Module BeliefMemory
  (Profile Graded)
  (Use NatArith)                                    ; PROPOSED library: Le, Min, Quot
  (Carrier Count  (Of Nat) (Enum 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15))
  (Carrier Belief (Of (Tuple Nat Nat)) (Product Count Count))
  (Carrier Status (Of Symbol) (Enum Believed Disbelieved Uncertain))

  ;; what the memory reports
  (Map strength (From Belief) (To Rational01)
    (Cases ((Tuple $p $n) (If (Eq (Add $p $n) 0) (Rat 1 2) (Div $p (Add $p $n))))))
  (Map confidence (From Belief) (To Rational01)
    (Cases ((Tuple $p $n) (Div (Add $p $n) (Add (Add $p $n) 4)))))
  (Map status (From Belief) (To Status)
    (Cases ((Tuple $p $n)
      (If (And (Le 4 (Add $p $n)) (Le (Mul 2 $n) $p)) Believed
        (If (And (Le 4 (Add $p $n)) (Le (Mul 2 $p) $n)) Disbelieved Uncertain)))))

  ;; how it changes: evidence saturates at 15, decay halves and rounds down
  (Map add-pos (From Belief) (To Belief) (Cases ((Tuple $p $n) (Tuple (Min (Add $p 1) 15) $n))))
  (Map add-neg (From Belief) (To Belief) (Cases ((Tuple $p $n) (Tuple $p (Min (Add $n 1) 15)))))
  (Map halve   (From Belief) (To Belief) (Cases ((Tuple $p $n) (Tuple (Quot $p 2) (Quot $n 2)))))

  (Tolerance Dist01 (On Rational01) (OneMinusAbsoluteDifference))
  (Machine Decide (States Belief)                   ; the action-selection interface
    (Observe status status)
    (Action pos add-pos) (Action neg add-neg) (Action decay halve))
  (Machine Report (States Belief)                   ; the reasoning interface
    (Observe strength strength (Values Dist01))
    (Observe confidence confidence (Values Dist01))
    (Action pos add-pos) (Action neg add-neg) (Action decay halve))

  ;; candidate encodings: grid indices of the rounded truth value, count buckets, caps
  (Map tv-grid-20 (From Belief) (To (Tuple Nat Nat))
    (Cases ((Tuple $p $n)
      (Tuple (If (Eq (Add $p $n) 0) 10 (Quot (Add (Mul 40 $p) (Add $p $n)) (Mul 2 (Add $p $n))))
             (Quot (Add (Mul 41 (Add $p $n)) 4) (Add (Mul 2 (Add $p $n)) 8))))))
  (Map tv-grid-10 (From Belief) (To (Tuple Nat Nat))
    (Cases ((Tuple $p $n)
      (Tuple (If (Eq (Add $p $n) 0) 5 (Quot (Add (Mul 20 $p) (Add $p $n)) (Mul 2 (Add $p $n))))
             (Quot (Add (Mul 21 (Add $p $n)) 4) (Add (Mul 2 (Add $p $n)) 8))))))
  (Map tv-grid-10-7 (From Belief) (To (Tuple Nat Nat))
    (Cases ((Tuple $p $n)
      (Tuple (If (Eq (Add $p $n) 0) 5 (Quot (Add (Mul 20 $p) (Add $p $n)) (Mul 2 (Add $p $n))))
             (Quot (Add (Mul 15 (Add $p $n)) 4) (Add (Mul 2 (Add $p $n)) 8))))))
  (Map bucket7 (From Count) (To Nat)
    (Table (0 0) (1 1) (2 2) (3 3) (4 4) (5 4) (6 5) (7 5) (8 5) (9 5)
           (10 6) (11 6) (12 6) (13 6) (14 6) (15 6)))
  (Map buckets7 (From Belief) (To (Tuple Nat Nat))
    (Cases ((Tuple $p $n) (Tuple (bucket7 $p) (bucket7 $n)))))
  (Map cap7 (From Belief) (To (Tuple Nat Nat))
    (Cases ((Tuple $p $n) (Tuple (Min $p 7) (Min $n 7)))))

  (Representation StatusOnly  (Of Decide) (Encode status))
  (Representation RoundedTV20 (Of Report) (Encode tv-grid-20))
  (Representation RoundedTV10 (Of Report) (Encode tv-grid-10))
  (Representation Grid10x7    (Of Report) (Encode tv-grid-10-7))
  (Representation Buckets7    (Of Report) (Encode buckets7))
  (Representation Capped7     (Of Report) (Encode cap7))
  (Measure Uniform (On Belief) (Uniform))

  (Derive DecisionQuotient (MinimizeForQueries Decide (Under Uniform)))
  (Derive StatusRepair (Refine StatusOnly (Preserve Encoding) (Until Stable) (Under Uniform)))
  (Derive Staged2 (Refine StatusOnly (Preserve Encoding) (Until (Steps 2))))      ; PROPOSED Until form
  (Derive Staged2Machine (InduceExact (Output Staged2 Representation)))
  (Derive FewestAtFifth
    (WeakestWithin Report (Within (Rat 1 5)) (Kind Behavioral) (Under Uniform)
                   (Objective Codes) (Search Exhaustive)))                       ; PROPOSED Objective
  (Derive FewestAtHalf
    (WeakestWithin Report (Within (Rat 1 2)) (Kind Behavioral) (Under Uniform)
                   (Objective Codes) (Search Exhaustive))))
;; @end

;; @excerpt belief-memory-requests
!(dc.run BeliefMemory DecisionQuotient)
!(dc.run BeliefMemory StatusRepair)
!(dc.run BeliefMemory (CheckUpdates StatusOnly))
!(dc.run BeliefMemory (CheckBehavioral StatusOnly (Horizon (Steps 0))))
!(dc.run BeliefMemory (CheckBehavioral StatusOnly (Horizon (Steps 1))))
!(dc.run BeliefMemory Staged2)
!(dc.run BeliefMemory Staged2Machine)
!(dc.run BeliefMemory (Defects RoundedTV20))
!(dc.run BeliefMemory (MeasureBehavioral RoundedTV20 (Horizon (Steps 1))))
!(dc.run BeliefMemory (MeasureBehavioral RoundedTV20 (Horizon (Steps 2))))
!(dc.run BeliefMemory (MeasureBehavioral RoundedTV20 (Horizon (Steps 3))))
!(dc.run BeliefMemory (MeasureBehavioral RoundedTV20 (Horizon (Steps 6))))
!(dc.run BeliefMemory (MeasureBehavioral RoundedTV20 (Discount (Rat 9 10))))
!(dc.run BeliefMemory (CheckBehavioral RoundedTV20 (Within (Rat 1 5))))
!(dc.run BeliefMemory (CheckBehavioral RoundedTV20 (Within (Rat 1 2))))
!(dc.run BeliefMemory (CheckBehavioral RoundedTV20 (Within (Rat 1 5)) (Horizon (Steps 1))))
!(dc.run BeliefMemory (Defects RoundedTV10))
!(dc.run BeliefMemory (Defects Buckets7))
!(dc.run BeliefMemory (Defects Capped7))
!(dc.run BeliefMemory FewestAtFifth)
!(dc.run BeliefMemory FewestAtHalf)
;; @end

;; @excerpt gentle-memory
(DC.Module GentleMemory
  (Profile Graded)
  (Use NatArith)
  (Import BeliefMemory
    (Only Count Belief Status strength confidence status add-pos add-neg Dist01
          tv-grid-20 tv-grid-10 tv-grid-10-7 bucket7 buckets7 cap7))
  ;; decay only above eight observations, rounding up: small counts are never erased
  (Map halve-gentle (From Belief) (To Belief)
    (Cases ((Tuple $p $n)
      (If (Le 8 (Add $p $n)) (Tuple (Quot (Add $p 1) 2) (Quot (Add $n 1) 2)) (Tuple $p $n)))))
  (Machine Decide (States Belief) (Observe status status)
    (Action pos add-pos) (Action neg add-neg) (Action decay halve-gentle))
  (Machine Report (States Belief)
    (Observe strength strength (Values Dist01))
    (Observe confidence confidence (Values Dist01))
    (Action pos add-pos) (Action neg add-neg) (Action decay halve-gentle))
  (Representation StatusOnly  (Of Decide) (Encode status))
  (Representation RoundedTV20 (Of Report) (Encode tv-grid-20))
  (Representation RoundedTV10 (Of Report) (Encode tv-grid-10))
  (Representation Grid10x7    (Of Report) (Encode tv-grid-10-7))
  (Representation Buckets7    (Of Report) (Encode buckets7))
  (Representation Capped7     (Of Report) (Encode cap7))
  (Measure Uniform (On Belief) (Uniform))

  (Derive DecisionQuotient (MinimizeForQueries Decide (Under Uniform)))
  (EncodingFamily CountBuckets (Of Report)                                  ; PROPOSED
    (Generator (IntervalProduct Count Count (Tied True))))
  (EncodingFamily TVGrids (Of Report)
    (Generator (RoundedGrid (strength 1 40) (confidence 1 40))))
  (Derive BestBuckets
    (WeakestWithin Report (Within (Rat 1 5)) (Under Uniform) (Objective Codes)
                   (Family CountBuckets) (Search Exhaustive)))
  (Derive BestGrid
    (WeakestWithin Report (Within (Rat 1 5)) (Under Uniform) (Objective Codes)
                   (Family TVGrids) (Search Exhaustive)))
  (Derive Fewest
    (WeakestWithin Report (Within (Rat 1 5)) (Under Uniform) (Objective Codes)
                   (Search Exhaustive)))
  (Derive WeakestGreedy
    (WeakestWithin Report (Within (Rat 1 5)) (Under Uniform) (Search Greedy)))
  (Derive FewestDiscounted
    (WeakestWithin Report (Within (Rat 1 10)) (Discount (Rat 9 10)) (Under Uniform)
                   (Objective Codes) (Search Exhaustive)))
  (Derive FewestCenters
    (WeakestWithin Report (Within (Rat 1 5)) (Kind Radius) (Under Uniform)
                   (Objective Codes) (Search Exhaustive)))                       ; PROPOSED Kind
  (Derive ColdStoreCenters
    (InduceApprox (Output FewestCenters Representation)
                  (Representatives (Choose (Output FewestCenters Representatives)))))
  (Derive ColdStore     (InduceApprox RoundedTV20))
  (Derive ColdStoreGrid (InduceApprox Grid10x7))
  (Derive ColdStoreBest (InduceApprox (Output Fewest Representation))))
;; @end

;; @excerpt gentle-memory-requests
!(dc.run GentleMemory DecisionQuotient)
!(dc.run GentleMemory (Defects RoundedTV20))
!(dc.run GentleMemory (MeasureBehavioral RoundedTV20 (Horizon (Steps 1))))
!(dc.run GentleMemory (MeasureBehavioral RoundedTV20 (Horizon (Steps 4))))
!(dc.run GentleMemory (MeasureBehavioral RoundedTV20 (Horizon (Steps 5))))
!(dc.run GentleMemory (MeasureBehavioral RoundedTV20 (Discount (Rat 9 10))))
!(dc.run GentleMemory (CheckBehavioral RoundedTV20 (Within (Rat 1 5))))
!(dc.run GentleMemory (CheckBehavioral RoundedTV20 (Within (Rat 3 20))))
!(dc.run GentleMemory (CheckBehavioral Grid10x7 (Within (Rat 1 5))))
!(dc.run GentleMemory (Defects RoundedTV10))
!(dc.run GentleMemory (Defects Buckets7))
!(dc.run GentleMemory (Defects Capped7))
!(dc.run GentleMemory BestBuckets)
!(dc.run GentleMemory BestGrid)
!(dc.run GentleMemory Fewest)
!(dc.run GentleMemory WeakestGreedy)
!(dc.run GentleMemory FewestDiscounted)
!(dc.run GentleMemory ColdStore)
!(dc.run GentleMemory ColdStoreGrid)
!(dc.run GentleMemory (InduceApprox RoundedTV20 (Horizon (Steps 4))))
!(dc.run GentleMemory ColdStoreBest)
!(dc.run GentleMemory FewestCenters)
!(dc.run GentleMemory ColdStoreCenters)
;; @end

;; @excerpt agent-memory
(DC.Module AgentMemory
  (Profile Graded)
  (Use NatArith Parallel)                           ; PROPOSED library
  (Import GentleMemory (Only Report Grid10x7 Fewest))
  (ParallelMachine Beliefs6 (Component Report) (Copies 6) (Synchronize decay))
  (ProductRepresentation Grid6 (Of Beliefs6) (Component Grid10x7) (Copies 6))
  (ProductRepresentation Fewest6 (Of Beliefs6) (Component (Output Fewest Representation)) (Copies 6)))
;; @end
;; @excerpt agent-memory-requests
!(dc.run AgentMemory (CheckBehavioral Grid6 (Within (Rat 1 5))))
!(dc.run AgentMemory (CheckBehavioral Fewest6 (Within (Rat 1 5))))
!(dc.run AgentMemory (MeasureBehavioral Grid6 (Discount (Rat 9 10))))
;; @end

;; @excerpt receipt-ledger
(DC.Module ReceiptLedger
  (Profile Graded)
  (Use BitVectors Contracts NatArith)
  ;; bit i records receipt i: u1 u2 u3 u4 support the proposition, v1 v2 oppose it
  (Carrier Receipts (Of (BitVector 6)) (All))
  (Carrier Upto8 (Of Nat) (Enum 0 1 2 3 4 5 6 7 8))
  (Carrier Upto4 (Of Nat) (Enum 0 1 2 3 4))
  (Carrier Tally (Of (Tuple Nat Nat)) (Product Upto8 Upto4))
  (Map counts (From Receipts) (To Tally)
    (Body ($r) (Tuple (PopCount (Slice $r 0 3)) (PopCount (Slice $r 4 5)))))   ; PROPOSED PopCount
  (Map tally-strength (From Tally) (To Rational01)
    (Cases ((Tuple $p $n) (If (Eq (Add $p $n) 0) (Rat 1 2) (Div $p (Add $p $n))))))
  (Map tally-confidence (From Tally) (To Rational01)
    (Cases ((Tuple $p $n) (Div (Add $p $n) (Add (Add $p $n) 4)))))
  (Map ledger-strength   (From Receipts) (To Rational01) (Body ($r) (tally-strength (counts $r))))
  (Map ledger-confidence (From Receipts) (To Rational01) (Body ($r) (tally-confidence (counts $r))))
  (Map hear-u1 (From Receipts) (To Receipts) (Body ($r) (SetBit $r 0 1)))
  (Map hear-u2 (From Receipts) (To Receipts) (Body ($r) (SetBit $r 1 1)))
  (Map hear-u3 (From Receipts) (To Receipts) (Body ($r) (SetBit $r 2 1)))
  (Map hear-u4 (From Receipts) (To Receipts) (Body ($r) (SetBit $r 3 1)))
  (Map hear-v1 (From Receipts) (To Receipts) (Body ($r) (SetBit $r 4 1)))
  (Map hear-v2 (From Receipts) (To Receipts) (Body ($r) (SetBit $r 5 1)))
  (Map union (From (Product Receipts Receipts)) (To Receipts)
    (Body ($pair) (BitOr (GetTuple $pair 0) (GetTuple $pair 1))))               ; PROPOSED BitOr
  (Tolerance Dist01 (On Rational01) (OneMinusAbsoluteDifference))
  (Machine Ledger (States Receipts)
    (Observe strength ledger-strength (Values Dist01))
    (Observe confidence ledger-confidence (Values Dist01))
    (Action hear-u1 hear-u1) (Action hear-u2 hear-u2) (Action hear-u3 hear-u3)
    (Action hear-u4 hear-u4) (Action hear-v1 hear-v1) (Action hear-v2 hear-v2)
    (Merge merge union))
  (Representation Counts (Of Ledger) (Encode counts))

  ;; merging two forks that kept only counts
  (Carrier ForkPair (Of (Tuple (BitVector 6) (BitVector 6))) (Product Receipts Receipts))
  (Map merged-tally (From ForkPair) (To Tally) (Body ($pair) (counts (union $pair))))
  (Map add-tallies (From ForkPair) (To Tally)
    (Body ($pair) (Tuple (Add (GetTuple (counts (GetTuple $pair 0)) 0) (GetTuple (counts (GetTuple $pair 1)) 0))
                         (Add (GetTuple (counts (GetTuple $pair 0)) 1) (GetTuple (counts (GetTuple $pair 1)) 1)))))
  (Map max-tallies (From ForkPair) (To Tally)
    (Body ($pair) (Tuple (Max (GetTuple (counts (GetTuple $pair 0)) 0) (GetTuple (counts (GetTuple $pair 1)) 0))
                         (Max (GetTuple (counts (GetTuple $pair 0)) 1) (GetTuple (counts (GetTuple $pair 1)) 1)))))
  (Tolerance SameInput (On ForkPair) (Discrete))
  (Tolerance TallyDistance (On Tally)
    (Meet (Pullback tally-strength Dist01) (Pullback tally-confidence Dist01)))   ; PROPOSED Meet
  (Implementation AddMerge (Ideal merged-tally) (Actual add-tallies)
    (Audit ForkPair) (InputDistance SameInput) (OutputDistance TallyDistance))
  (Implementation MaxMerge (Ideal merged-tally) (Actual max-tallies)
    (Audit ForkPair) (InputDistance SameInput) (OutputDistance TallyDistance))

  ;; three-way merge from the fork base: exact only when the forks heard different receipts
  (Carrier Triple (Of (Tuple (BitVector 6) (BitVector 6) (BitVector 6))) (Product Receipts Receipts Receipts))
  (Map based (From Triple) (To Bool)
    (Body ($t) (And (Eq (BitAnd (GetTuple $t 0) (GetTuple $t 1)) (GetTuple $t 0))
                    (Eq (BitAnd (GetTuple $t 0) (GetTuple $t 2)) (GetTuple $t 0)))))
  (Carrier Forks (Of (Tuple (BitVector 6) (BitVector 6) (BitVector 6))) (Subset Triple based))
  (Map fresh-news (From Forks) (To Bool)
    (Body ($t) (IsZero (BitAnd (BitXor (GetTuple $t 1) (GetTuple $t 0))
                               (BitXor (GetTuple $t 2) (GetTuple $t 0))))))
  (Carrier CleanForks (Of (Tuple (BitVector 6) (BitVector 6) (BitVector 6))) (Subset Forks fresh-news))
  (Map fork-union (From Forks) (To Tally)
    (Body ($t) (counts (BitOr (GetTuple $t 1) (GetTuple $t 2)))))
  (Map three-way (From Forks) (To Tally)
    (Body ($t) (Tuple (Sub (Add (GetTuple (counts (GetTuple $t 1)) 0) (GetTuple (counts (GetTuple $t 2)) 0))
                           (GetTuple (counts (GetTuple $t 0)) 0))
                      (Sub (Add (GetTuple (counts (GetTuple $t 1)) 1) (GetTuple (counts (GetTuple $t 2)) 1))
                           (GetTuple (counts (GetTuple $t 0)) 1)))))
  (Tolerance SameTriple (On Forks) (Discrete))
  (Implementation ThreeWay (Ideal fork-union) (Actual three-way)
    (Audit Forks) (InputDistance SameTriple) (OutputDistance TallyDistance))
  (Implementation ThreeWayClean (Ideal fork-union) (Actual three-way)
    (Audit CleanForks) (InputDistance SameTriple) (OutputDistance TallyDistance))

  ;; compaction below a fork horizon: u1 and u2 are older than the oldest open fork, so only
  ;; their number is kept; the identities of u3, u4, v1 and v2 are kept
  (Carrier Upto2 (Of Nat) (Enum 0 1 2))
  (Carrier Recent (Of (BitVector 4)) (All))
  (Carrier Compact (Of (Tuple Nat (BitVector 4))) (Product Upto2 Recent))
  (Map compact (From Receipts) (To Compact)
    (Body ($r) (Tuple (PopCount (Slice $r 0 1)) (Slice $r 2 5))))
  (Representation Compacted (Of Ledger) (Encode compact))   ; every hear action still allowed
  ;; the delivery protocol after compaction: u1 and u2 are never delivered again (a delivery
  ;; watermark at u2 that drops redeliveries), and forks are opened from the compacted state, so
  ;; a merge adds only newer receipts; the machine has exactly the operations the protocol allows
  (Machine SettledLedger (States Receipts)
    (Observe strength ledger-strength (Values Dist01))
    (Observe confidence ledger-confidence (Values Dist01))
    (Action hear-u3 hear-u3) (Action hear-u4 hear-u4)
    (Action hear-v1 hear-v1) (Action hear-v2 hear-v2))
  (Representation CompactedSettled (Of SettledLedger) (Encode compact))
  ;; merging two forks from their compacted codes: the old count of the first, the union of the
  ;; newer identities; exact only for forks that share the compacted part
  (Map compact-merge (From ForkPair) (To Tally)
    (Body ($pair)
      (Tuple (Add (PopCount (Slice (GetTuple $pair 0) 0 1))
                  (PopCount (BitOr (Slice (GetTuple $pair 0) 2 3) (Slice (GetTuple $pair 1) 2 3))))
             (PopCount (BitOr (Slice (GetTuple $pair 0) 4 5) (Slice (GetTuple $pair 1) 4 5))))))
  (Map same-old (From ForkPair) (To Bool)
    (Body ($pair) (Eq (Slice (GetTuple $pair 0) 0 1) (Slice (GetTuple $pair 1) 0 1))))
  (Carrier SettledForks (Of (Tuple (BitVector 6) (BitVector 6))) (Subset ForkPair same-old))
  (Tolerance SameSettled (On SettledForks) (Discrete))
  (Implementation CompactMerge (Ideal merged-tally) (Actual compact-merge)
    (Audit ForkPair) (InputDistance SameInput) (OutputDistance TallyDistance))
  (Implementation CompactMergeSettled (Ideal merged-tally) (Actual compact-merge)
    (Audit SettledForks) (InputDistance SameSettled) (OutputDistance TallyDistance)))
;; @end

;; @excerpt receipt-ledger-requests
!(dc.run ReceiptLedger (CheckNow Counts))
!(dc.run ReceiptLedger (CheckUpdates Counts))
!(dc.run ReceiptLedger (MeasureBehavioral Counts))
!(dc.run ReceiptLedger (CheckImplementation AddMerge (Grade 1 (Rat 6 35))))
!(dc.run ReceiptLedger (CheckImplementation AddMerge (Grade 1 (Rat 1 6))))
!(dc.run ReceiptLedger (CheckImplementation MaxMerge (Grade 1 (Rat 1 6))))
!(dc.run ReceiptLedger (CheckImplementation ThreeWay (Grade 1 0)))
!(dc.run ReceiptLedger (CheckImplementation ThreeWayClean (Grade 1 0)))
!(dc.run ReceiptLedger (CheckUpdates Compacted))                        ; Refuted without the protocol
!(dc.run ReceiptLedger (CheckBehavioral Compacted (Within (Rat 1 10))))
!(dc.run ReceiptLedger (CheckUpdates CompactedSettled))                 ; Checked under the protocol
!(dc.run ReceiptLedger (MeasureBehavioral CompactedSettled))
!(dc.run ReceiptLedger (CheckImplementation CompactMerge (Grade 1 0)))
!(dc.run ReceiptLedger (CheckImplementation CompactMergeSettled (Grade 1 0)))
;; @end
