;; M7 negative gate 5c: Require names a Derive that is not an invariance derivation (Decided); the separation must not be Checked.
;; Arithmetic observer discovery over F7.  Specification, Sections 11 and 13.5.
;; @excerpt arithmetic
(DC.Module ArithmeticProbes
  (Profile Crisp)
  (Use Discovery)
  (Record MarkedPair (T3 (Matrix F7 4 4)) (T5 (Matrix F7 4 4)))
  (Const KA MarkedPair
    (MarkedPair (T3 (Matrix4 (6 0 0 0) (0 6 0 0) (0 0 6 0) (4 0 0 6)))
                (T5 (Matrix4 (0 0 0 0) (4 0 0 0) (5 0 0 0) (0 0 5 0)))))
  (Const KB MarkedPair
    (MarkedPair (T3 (Matrix4 (6 0 0 0) (0 6 0 0) (0 0 6 0) (3 0 0 6)))
                (T5 (Matrix4 (0 0 0 0) (4 0 0 0) (5 0 0 0) (0 0 5 0)))))
  (Carrier Candidates (Of MarkedPair) (Enum KA KB))
  (Map jordan-summary (From Candidates) (To (Tuple (Tuple Nat Nat Nat) (Tuple Nat Nat Nat)))
    (Body ($k) (Tuple (PowerRanks (Sub (Get $k T3) (Scale 6 I4)) 3) (PowerRanks (Get $k T5) 3))))
  (Map probe-1 (From Candidates) (To Nat)
    (Body ($k) (Rank (Sub (Sub (Get $k T3) (Scale 6 I4)) (Scale 1 (Square (Get $k T5)))))))
  (Map hold (From Candidates) (To Candidates) (Cases (KA KA) (KB KB)))
  (Machine Structures (States Candidates) (Observe jordan jordan-summary) (Action hold hold))
  (Machine Enriched (States Candidates) (Observe jordan jordan-summary) (Observe probe-1 probe-1)
    (Action hold hold))
  (Representation JordanOnly (Of Enriched) (Encode jordan-summary))
  (ObserverFamily JointRankProbes (On MarkedPair) (Returns Rank4)
    (Generate (For $b (Elements F7))
      (Expr (Lambda (($k MarkedPair))
        (Rank (Sub (Sub (Get $k T3) (Scale 6 I4)) (Scale $b (Square (Get $k T5)))))))))
  (Derive Invariance (CheckObserverInvariance JointRankProbes
    (Under (SimultaneousConjugacy (Fields T3 T5) (Over F7))) (Method StructuralMatrixRules)))
  (Derive Separation (SeekSeparator (Pair KA KB) (Family JointRankProbes)
    (Require (Output Decided Derivation)) (Order GeneratedOrder) (Budget (Probes 7))))
  (ObserverSource ModuleIso (Procedure SimultaneousConjugacy) (On MarkedPair))
  (Derive Decided (DecideEquivalence ModuleIso (Pair KA KB))))
;; @end
!(dc.run ArithmeticProbes (MinimizeForQueries Structures))
!(dc.run ArithmeticProbes Separation)
!(dc.run ArithmeticProbes (CheckNow JordanOnly))
!(dc.run ArithmeticProbes Decided)
