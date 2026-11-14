;; M7 step 1: nested completion, (CompleteHive (Output D Hive)); replayers must resolve both levels.
;; ChainDone: ChainHive completed (M3-M1 filled Equal along the measured path) -> coherence Holds.
;; SplitDone: SplitHive completed; M3 has no measured path to M1 or M2 (NoPath), so those entries stay
;; Unmeasured (never 0) and a claim reading them answers Unknown.
(DC.Module CompleteNestFx
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
  (Derive ChainDone (CompleteHive ChainHive))
  (Derive SplitDone (CompleteHive SplitHive))
  (Derive ChainTwice (CompleteHive (Output ChainDone Hive)))
  (Derive SplitTwice (CompleteHive (Output SplitDone Hive))))
!(dc.run CompleteNestFx (CheckKernelCoherence (Output ChainTwice Hive)))
!(dc.run CompleteNestFx (CheckKernelCoherence (Output SplitTwice Hive)))
!(dc.run CompleteNestFx (CompleteHive (Output ChainDone Hive)))
