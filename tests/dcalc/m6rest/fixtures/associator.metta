;; M6-rest: (Associator Hive Mi Mj Mk) (request shape ours; definition spec Def 10.1 l.2827: [i,j,k] = c_ik - c_ij o c_jk).
;; Parity: the parity triangle of Example 10.5 -> nonzero associator (direct Opposite vs composite Equal).
;; Coherent: three Equal correspondences -> zero associator.  Partial: M3-M1 Unmeasured -> Unsupported.
(DC.Module AssocFx
  (Profile Graded)
  (Use Hives)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Tolerance Sharp (On Bit) (Discrete))
  (Measure UniformBit (On Bit) (Uniform))
  (CrossKernel Equal    (Left Bit) (Right Bit) (Entries (0 0 1) (0 1 0) (1 0 0) (1 1 1)))
  (CrossKernel Opposite (Left Bit) (Right Bit) (Entries (0 0 0) (0 1 1) (1 0 1) (1 1 0)))
  (KernelHive Parity
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured) (Correspondence M2 M3 Equal Measured) (Correspondence M3 M1 Opposite Measured))
  (KernelHive Coherent
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured) (Correspondence M2 M3 Equal Measured) (Correspondence M3 M1 Equal Measured))
  (KernelHive Partial
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured) (Correspondence M2 M3 Equal Measured) (Correspondence M3 M1 Equal Unmeasured)))
!(dc.run AssocFx (Associator Parity M1 M2 M3))
!(dc.run AssocFx (Associator Coherent M1 M2 M3))
!(dc.run AssocFx (Associator Partial M1 M2 M3))
!(dc.run AssocFx (Associator Parity M1 M1 M3))
!(dc.run AssocFx (Associator Parity M1 M2 M9))
