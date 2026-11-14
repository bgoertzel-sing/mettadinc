;; M7 gate 6e (review 1 finding 4): a (Masses ..) measure on a 3-bit carrier that lists all 8 points
;; but gives four of them mass 0 has no full support; ClockRates must refuse it as InvalidInput, not Unsupported.
(DC.Module Gate6e
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Discovery)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Carrier W3 (Of (BitVector 3)) (All))
  (Map r0 (From W3) (To Bit) (Body ($x) (BitAt $x 0)))
  (Map sw (From W3) (To W3) (Body ($x) (SwapBits $x 0 1)))
  (Machine M3 (States W3) (Observe x0 r0) (Action swap sw))
  (Measure HalfZero (On W3) (Masses (0 (Rat 1 4)) (1 (Rat 1 4)) (2 (Rat 1 4)) (3 (Rat 1 4)) (4 (Rat 0 1)) (5 (Rat 0 1)) (6 (Rat 0 1)) (7 (Rat 0 1))))
  (Derive G (ClockRates M3 (Under HalfZero) (Library Coordinates) (Kind Mean))))
!(dc.run Gate6e G)
