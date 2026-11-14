;; M7 review 1 finding 7 (m7_expand Only): FortyBits is imported with (Only Word ZeroMachine); the importer uses
;; read0/swap01, which are declared in FortyBits but not listed in Only. Expected: InvalidInput "undeclared name read0".
;; Forty-bit symbolic fixtures, the adversarial zero-tail candidate and a
;; reachability scope.  Specification, Sections 5.3 and 6.2.
;; @excerpt forty-bits-module
(DC.Module FortyBits
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 40)) (All))
  (Map read0  (From Word) (To Bit)  (Body ($x) (BitAt $x 0)))
  (Map swap01 (From Word) (To Word) (Body ($x) (SwapBits $x 0 1)))
  (Map rotate (From Word) (To Word) (Body ($x) (RotateRange $x 2 39)))
  (Map inject-parity (From Word) (To Word)
    (Body ($x) (SetBit $x 1 (Xor (BitAt $x 1) (Parity (Slice $x 2 39))))))
  (Map inject-zero (From Word) (To Word)
    (Body ($x) (SetBit $x 1 (Xor (BitAt $x 1) (IsZero (Slice $x 2 39))))))
  (Machine ParityMachine (States Word) (Observe x0 read0)
    (Action swap swap01) (Action rotate rotate) (Action inject inject-parity))
  (Machine ZeroMachine (States Word) (Observe x0 read0)
    (Action swap swap01) (Action rotate rotate) (Action inject inject-zero))
  (Representation KeepX0 (Of ZeroMachine) (Encode read0))
  (Derive ParityQuotient (MinimizeForQueries ParityMachine))
  (Derive ZeroQuotient   (MinimizeForQueries ZeroMachine))
;; @end
;; @excerpt forty-bits-adversarial
  (BlockPartition ZeroTailOnly (On Word)
    (Block Z00 (Body ($x) (And (Eq (BitAt $x 0) 0) (And (Eq (BitAt $x 1) 0) (IsZero (Slice $x 2 39))))) 0)
    (Block Z10 (Body ($x) (And (Eq (BitAt $x 0) 1) (And (Eq (BitAt $x 1) 0) (IsZero (Slice $x 2 39))))) 1)
    (Block Z01 (Body ($x) (And (Eq (BitAt $x 0) 0) (And (Eq (BitAt $x 1) 1) (IsZero (Slice $x 2 39))))) 2)
    (Block Z11 (Body ($x) (And (Eq (BitAt $x 0) 1) (And (Eq (BitAt $x 1) 1) (IsZero (Slice $x 2 39))))) 3)
    (Successor swap Z00 Z00) (Successor swap Z10 Z01) (Successor swap Z01 Z10) (Successor swap Z11 Z11)
    (Successor rotate Z00 Z00) (Successor rotate Z10 Z10) (Successor rotate Z01 Z01) (Successor rotate Z11 Z11)
    (Successor inject Z00 Z01) (Successor inject Z01 Z00) (Successor inject Z10 Z11) (Successor inject Z11 Z10))
  (Derive WholeCarrier (CheckBlockPartition ZeroTailOnly (Of ZeroMachine)))

  (Carrier FromZero (Of (BitVector 40)) (Reach ZeroMachine (From 0)))
  (Machine ZeroReach (States FromZero) (Observe x0 read0)
    (Action swap swap01) (Action rotate rotate) (Action inject inject-zero))
  (BlockPartition ZeroTailReach (On FromZero)
    (Block Z00 (Body ($x) (And (Eq (BitAt $x 0) 0) (Eq (BitAt $x 1) 0))) 0)
    (Block Z10 (Body ($x) (And (Eq (BitAt $x 0) 1) (Eq (BitAt $x 1) 0))) 1)
    (Block Z01 (Body ($x) (And (Eq (BitAt $x 0) 0) (Eq (BitAt $x 1) 1))) 2)
    (Block Z11 (Body ($x) (And (Eq (BitAt $x 0) 1) (Eq (BitAt $x 1) 1))) 3)
    (Successor swap Z00 Z00) (Successor swap Z10 Z01) (Successor swap Z01 Z10) (Successor swap Z11 Z11)
    (Successor rotate Z00 Z00) (Successor rotate Z10 Z10) (Successor rotate Z01 Z01) (Successor rotate Z11 Z11)
    (Successor inject Z00 Z01) (Successor inject Z01 Z00) (Successor inject Z10 Z11) (Successor inject Z11 Z10))
  (Derive OnReach (CheckBlockPartition ZeroTailReach (Of ZeroReach)))
;; @end
  )
;; @excerpt forty-bits-requests
!(dc.run FortyBits (CheckNow KeepX0))
!(dc.run FortyBits (CheckBehavioral KeepX0))
!(dc.run FortyBits ZeroQuotient)
!(dc.run FortyBits ParityQuotient)
!(dc.run FortyBits WholeCarrier)
!(dc.run FortyBits OnReach)
;; @end

;; Relevance screens on the same machines (Discovery library, not in the first release).
;; @excerpt forty-bits-screens
;; R7 probe: name outside the Only list must not be visible to the importer
(DC.Module OnlyProbe
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Discovery)
  (Import FortyBits (Only Word ZeroMachine))
  (Machine Leak (States Word) (Observe x0 read0) (Action swap swap01))
  (Measure UniformWords (On Word) (Uniform))
  (Derive G (ClockRates Leak (Under UniformWords) (Library Coordinates) (Kind Mean))))
!(dc.run OnlyProbe G)
