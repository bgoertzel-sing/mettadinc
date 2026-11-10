;; OQ3 claimless test module (M2): Refine (discrete start, 0 rounds), WeakestWithin, InduceApprox.
;; Hand-derived: obs P,Q,R distinct -> P0 discrete, Rounds 0, ledger 1/3 -> 1/3.
;; Behavioral distances P-Q 1/10, Q-R 1/5, P-R 3/10; all 5 partitions (Bell(3)) searched.
;; Within 1/10 -> {P,Q}{R}, weakness (4+1)/9 = 5/9; within 3/10 -> one block, weakness 1.
;; InduceApprox with pick P->Q: classes {P,Q}->Q, {R}->R; step keeps 0->0, 1->1.
(DC.Module WeakThree
  (Profile Graded)
  (Carrier S (Of Symbol) (Enum P Q R))
  (Map obs (From S) (To Rational01)
    (Cases (P (Rat 1 2)) (Q (Rat 3 5)) (R (Rat 4 5))))
  (Map coarse (From S) (To Rational01)
    (Cases (P (Rat 0 1)) (Q (Rat 1 1)) (R (Rat 1 1))))
  (Map step (From S) (To S) (Cases (P Q) (Q Q) (R R)))
  (Map pick (From S) (To S) (Cases (P Q) (Q Q) (R R)))
  (Tolerance Dist (On Rational01) (OneMinusAbsoluteDifference))
  (Machine M (States S)
    (Observe obs obs (Values Dist))
    (Action step step))
  (Representation Coarse (Of M) (Encode coarse) (Codes Dist))
  (Measure Uniform (On S) (Uniform))
  (Derive Split (Refine Coarse (Preserve Encoding) (Until Stable) (Under Uniform)))
  (Derive Tight (WeakestWithin M (Within (Rat 1 10)) (Kind Behavioral) (Discount 1) (Under Uniform) (Search Exhaustive)))
  (Derive Loose (WeakestWithin M (Within (Rat 3 10)) (Kind Behavioral) (Discount 1) (Under Uniform) (Search Exhaustive)))
  (Derive TightMachine (InduceApprox (Output Tight Representation) (Representatives (Choose pick)))))
!(dc.run WeakThree Split)
!(dc.run WeakThree Tight)
!(dc.run WeakThree Loose)
!(dc.run WeakThree TightMachine)
