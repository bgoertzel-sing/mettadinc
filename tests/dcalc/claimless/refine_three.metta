;; OQ3 claimless test module (M2): Refine with one splitting round.
;; Hand-derived: flat code, obs {P,Q}{R} -> P0 = (P Q)(R), ledger before (4+1)/9 = 5/9.
;; step P->R, Q->Q separates P from Q in round 1 -> discrete, after 1/3.
(DC.Module RefineThree
  (Profile Graded)
  (Carrier S (Of Symbol) (Enum P Q R))
  (Map obs (From S) (To Rational01)
    (Cases (P (Rat 1 2)) (Q (Rat 1 2)) (R (Rat 4 5))))
  (Map flat (From S) (To Rational01)
    (Cases (P (Rat 0 1)) (Q (Rat 0 1)) (R (Rat 0 1))))
  (Map step (From S) (To S) (Cases (P R) (Q Q) (R R)))
  (Tolerance Dist (On Rational01) (OneMinusAbsoluteDifference))
  (Machine M (States S)
    (Observe obs obs (Values Dist))
    (Action step step))
  (Representation Flat (Of M) (Encode flat) (Codes Dist))
  (Measure Uniform (On S) (Uniform))
  (Derive Split (Refine Flat (Preserve Encoding) (Until Stable) (Under Uniform))))
!(dc.run RefineThree Split)
