;; M6 review-2 F1 (negative test 4): an Unmeasured correspondence is not zero-filled.
;; M1-M2 and M2-M3 Equal (measured), M3-M1 Unmeasured: coherence depends on the completion -> Unknown, never Refuted.
(DC.Module Neg4Unmeasured
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
    (Correspondence M3 M1 Opposite Unmeasured)
    (Weights (M1 (Rat 1 3)) (M2 (Rat 1 3)) (M3 (Rat 1 3)))))
!(dc.run Neg4Unmeasured (CheckKernelCoherence Triangle))
