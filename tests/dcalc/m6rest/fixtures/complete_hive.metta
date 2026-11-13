;; M6-rest: CompleteHive (spec Sec. 10.4 l.2896-2906; hive decision 2: our reading, crisp kernels).
;; ChainHive: M1-M2 and M2-M3 measured Equal, M3-M1 Unmeasured -> filled Equal along the path (forest completion).
;; SplitHive: only M1-M2 measured; M3 has no measured path -> NoPath rows, entries stay 0 (marked, not silent).
;; ParityFull: fully measured parity triangle; closure would change a measured 0 -> Unsupported (not Lipschitz/round-trip).
(DC.Module CompleteFx
  (Profile Graded)
  (Use Hives)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Tolerance Sharp (On Bit) (Discrete))
  (Measure UniformBit (On Bit) (Uniform))
  (CrossKernel Equal    (Left Bit) (Right Bit) (Entries (0 0 1) (0 1 0) (1 0 0) (1 1 1)))
  (CrossKernel Opposite (Left Bit) (Right Bit) (Entries (0 0 0) (0 1 1) (1 0 1) (1 1 0)))
  (KernelHive ChainHive
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured)
    (Correspondence M2 M3 Opposite Measured)
    (Correspondence M3 M1 Equal Unmeasured))
  (KernelHive SplitHive
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured))
  (KernelHive ParityFull
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Equal Measured)
    (Correspondence M2 M3 Equal Measured)
    (Correspondence M3 M1 Opposite Measured)))
!(dc.run CompleteFx (CompleteHive ChainHive))
!(dc.run CompleteFx (CompleteHive SplitHive))
!(dc.run CompleteFx (CompleteHive ParityFull))
!(dc.run CompleteFx (ConsensusCost ChainHive))
