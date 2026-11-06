;; Graded kernels: closure, brackets and thresholds.  Specification, Section 9.1.
;; @excerpt graded-closure
(DC.Module GradedClosure
  (Profile Graded)
  (Use GradedKernels)
  (Carrier Point (Of Symbol) (Enum A B C))
  (Tolerance Alpha (On Point)
    (SymmetricTable (Diagonal 1)
      (A B (Rat 9 10)) (B C (Rat 9 10)) (A C (Rat 1 10))))
  (Measure Uniform (On Point) (Uniform))
  (PairLaw UU (Independent Uniform Uniform) (Diagonal Included))
  (Derive Closed (PathClosure Alpha (Algebra Lukasiewicz01)))
  (Derive Before (Bracket Alpha (Under UU)))
  (Derive After  (Bracket (Output Closed Kernel) (Under UU)))
  (Derive Increase (Delta (From (Output Before Value)) (To (Output After Value))))
  (Derive Thresholded (Threshold (Output Closed Kernel) (AtLeast (Rat 9 10)))))
;; @end
!(dc.run GradedClosure Increase)
!(dc.run GradedClosure (CheckTransitive (Output Thresholded Relation) (Algebra Boolean)))
!(dc.run GradedClosure (CheckTransitive (Output Closed Kernel)))
!(dc.run GradedClosure (CheckTransitive Alpha))
