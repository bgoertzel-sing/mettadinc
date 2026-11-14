;; m6-graded: CompleteHive on graded kernel hives (Lukasiewicz path closure, spec l.736-742, l.2665-2683).
;; GradedChain: M1-M2 Half (1/2 on the diagonal), M2-M3 Blur (3/4 on the diagonal), M3-M1 Unmeasured.
;; Closure c_13(x, x) = 1/2 (x) 3/4 = 1/4, off-diagonal 0; cost = 4 ordered fills * (1/6)^2 * 1/4 = 1/36.
(DC.Module GradedChain
  (Profile Graded)
  (Use Hives)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Tolerance Sharp (On Bit) (Discrete))
  (Measure UniformBit (On Bit) (Uniform))
  (CrossKernel Half (Left Bit) (Right Bit) (Entries (0 0 (Rat 1 2)) (0 1 0) (1 0 0) (1 1 (Rat 1 2))))
  (CrossKernel Blur (Left Bit) (Right Bit) (Entries (0 0 (Rat 3 4)) (0 1 0) (1 0 0) (1 1 (Rat 3 4))))
  (KernelHive Chain
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Half Measured)
    (Correspondence M2 M3 Blur Measured)
    (Correspondence M3 M1 Blur Unmeasured)
    (Weights (M1 (Rat 1 3)) (M2 (Rat 1 3)) (M3 (Rat 1 3)))))
;; GradedBroken: M1-M2 Near puts 1/4 off the diagonal, so the measured M1(0)-M1(1) = 0 is below its closure 1/4.
(DC.Module GradedBroken
  (Profile Graded)
  (Use Hives)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Tolerance Sharp (On Bit) (Discrete))
  (Measure UniformBit (On Bit) (Uniform))
  (CrossKernel Near (Left Bit) (Right Bit) (Entries (0 0 1) (0 1 (Rat 1 4)) (1 0 (Rat 1 4)) (1 1 1)))
  (CrossKernel Blur (Left Bit) (Right Bit) (Entries (0 0 (Rat 3 4)) (0 1 0) (1 0 0) (1 1 (Rat 3 4))))
  (KernelHive Broken
    (Member M1 Bit Sharp UniformBit) (Member M2 Bit Sharp UniformBit) (Member M3 Bit Sharp UniformBit)
    (Correspondence M1 M2 Near Measured)
    (Correspondence M2 M3 Blur Measured)
    (Correspondence M3 M1 Blur Unmeasured)))
!(dc.run GradedChain (CompleteHive Chain))
!(dc.run GradedChain (CheckKernelCoherence Chain))
!(dc.run GradedChain (ConsensusCost Chain))
!(dc.run GradedBroken (CompleteHive Broken))
