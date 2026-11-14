;; Parity-triangle kernel hive.  Specification, Section 10.4.
;; @excerpt parity-triangle
(DC.Module ParityTriangle
  (Profile Graded)
  (Use Hives)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Tolerance Sharp (On Bit) (Discrete))
  (Measure UniformBit (On Bit) (Uniform))
  (CrossKernel Equal    (Left Bit) (Right Bit) (Entries (0 0 1) (0 1 0) (1 0 0) (1 1 1)))
  (CrossKernel Opposite (Left Bit) (Right Bit) (Entries (0 0 0) (0 1 1) (1 0 1) (1 1 0)))
  (KernelHive Triangle
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured)
    (Correspondence M2 M3 Equal Measured)
    (Correspondence M3 M1 Equal    Measured)
    (Weights (M1 (Rat 1 3)) (M2 (Rat 1 3)) (M3 (Rat 1 3)))))
;; @end
!(dc.run ParityTriangle (CheckKernelCoherence Triangle))
!(dc.run ParityTriangle (Holonomy Triangle (Cycle M1 M2 M3)))
!(dc.run ParityTriangle (ConsensusCost Triangle))
!(dc.run ParityTriangle (LeastCoherentRefinement Triangle))
