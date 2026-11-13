;; M6-rest: LeastCoherentRefinement through the general exact linear program (spec Sec. 10.4, Example 10.5).
;; UnequalTriangle: the parity triangle with unequal weights (cycle edges of unequal weight).
;; PathHive: M3-M1 kernel is zero, so each identification component is a path (not a clique, not a cycle).
(DC.Module LcrLp
  (Profile Graded)
  (Use Hives)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Tolerance Sharp (On Bit) (Discrete))
  (Measure UniformBit (On Bit) (Uniform))
  (CrossKernel Equal    (Left Bit) (Right Bit) (Entries (0 0 1) (0 1 0) (1 0 0) (1 1 1)))
  (CrossKernel Opposite (Left Bit) (Right Bit) (Entries (0 0 0) (0 1 1) (1 0 1) (1 1 0)))
  (CrossKernel Zero     (Left Bit) (Right Bit) (Entries (0 0 0) (0 1 0) (1 0 0) (1 1 0)))
  (KernelHive UnequalTriangle
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured)
    (Correspondence M2 M3 Equal Measured)
    (Correspondence M3 M1 Opposite Measured)
    (Weights (M1 (Rat 1 2)) (M2 (Rat 1 4)) (M3 (Rat 1 4))))
  (KernelHive PathHive
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured)
    (Correspondence M2 M3 Equal Measured)
    (Correspondence M3 M1 Zero Measured)
    (Weights (M1 (Rat 1 3)) (M2 (Rat 1 3)) (M3 (Rat 1 3)))))
!(dc.run LcrLp (LeastCoherentRefinement UnequalTriangle))
!(dc.run LcrLp (LeastCoherentRefinement PathHive))
!(dc.run LcrLp (ConsensusCost PathHive))
