;; M7 step 1: nested CompleteHive over (Output D Hive) operands (completion is idempotent: ChainTwice = ChainDone).
(DC.Module NestedCompleteFx
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
!(dc.run NestedCompleteFx (CheckKernelCoherence (Output ChainTwice Hive)))
!(dc.run NestedCompleteFx (CheckKernelCoherence (Output SplitTwice Hive)))
