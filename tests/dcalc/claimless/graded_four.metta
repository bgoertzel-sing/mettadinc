;; OQ3 claimless test module (M2): PathClosure, Bracket, Delta, Threshold.
;; Expected values hand-derived: Lukasiewicz closure raises A-C to max(0,4/5+7/10-1)=1/2,
;; B-D to 1/5, A-D stays 0; mean of T over 16 pairs = 8/16 = 1/2; after closure 47/80.
(DC.Module GradedFour
  (Profile Graded)
  (Use GradedKernels)
  (Carrier Point (Of Symbol) (Enum A B C D))
  (Tolerance T (On Point)
    (SymmetricTable (Diagonal 1)
      (A B (Rat 4 5)) (B C (Rat 7 10)) (C D (Rat 1 2))
      (A C (Rat 0 1)) (A D (Rat 0 1)) (B D (Rat 0 1))))
  (Measure Uniform (On Point) (Uniform))
  (PairLaw UU (Independent Uniform Uniform) (Diagonal Included))
  (Derive Closed (PathClosure T (Algebra Lukasiewicz01)))
  (Derive Before (Bracket T (Under UU)))
  (Derive After  (Bracket (Output Closed Kernel) (Under UU)))
  (Derive Increase (Delta (From (Output Before Value)) (To (Output After Value))))
  (Derive Thresholded (Threshold (Output Closed Kernel) (AtLeast (Rat 1 2)))))
!(dc.run GradedFour Closed)
!(dc.run GradedFour Before)
!(dc.run GradedFour After)
!(dc.run GradedFour Increase)
!(dc.run GradedFour Thresholded)
