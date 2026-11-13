;; m6-graded: a graded kernel hive (spec Def 10.1 l.2821: c_ij in [0, 1]).  Lukasiewicz composition (l.288-289, l.736-742).
;; M1-M2 Near (degree 1/4 off-diagonal), M2-M3 Blur (3/4 on the diagonal), M3-M1 Weak (1/4 on the diagonal):
;; c_13(0,0) = 1/4 < c_12(0,0) (x) c_23(0,0) = max(0, 1 + 3/4 - 1) = 3/4, so the hive is not coherent.
(DC.Module GradedTriangle
  (Profile Graded)
  (Use Hives)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Tolerance Sharp (On Bit) (Discrete))
  (Measure UniformBit (On Bit) (Uniform))
  (CrossKernel Near (Left Bit) (Right Bit) (Entries (0 0 1) (0 1 (Rat 1 4)) (1 0 (Rat 1 4)) (1 1 1)))
  (CrossKernel Blur (Left Bit) (Right Bit) (Entries (0 0 (Rat 3 4)) (0 1 0) (1 0 0) (1 1 (Rat 3 4))))
  (CrossKernel Weak (Left Bit) (Right Bit) (Entries (0 0 (Rat 1 4)) (0 1 0) (1 0 0) (1 1 (Rat 1 4))))
  (KernelHive Tri
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Near Measured)
    (Correspondence M2 M3 Blur Measured)
    (Correspondence M3 M1 Weak Measured)
    (Weights (M1 (Rat 1 3)) (M2 (Rat 1 3)) (M3 (Rat 1 3)))))
!(dc.run GradedTriangle (CheckKernelCoherence Tri))
!(dc.run GradedTriangle (Holonomy Tri (Cycle M1 M2 M3)))
!(dc.run GradedTriangle (ConsensusCost Tri))
!(dc.run GradedTriangle (LeastCoherentRefinement Tri))
!(dc.run GradedTriangle (Associator Tri M1 M2 M3))
