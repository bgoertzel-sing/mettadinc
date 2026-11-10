;; OQ3 claimless test module (M2): Then (arrow composition).
;; Module body copied from fixtures/eight_state.metta (Spec 6.1) so the test is self-contained.
;; Hand-derived: AB = InduceExact KeepAB is a quotient Concrete -> AB machine (keep-ab is onto);
;; ABToCodes: pair-code (a,b) -> 2a+b is a bijection Pair -> Code that commutes with swap and a,
;; so the checked map is a surjective quotient and Then gives a Quotient arrow Concrete -> Codes.
(DC.Module ThenEight
  (Profile Crisp)
  (Carrier Bit   (Of Nat) (Enum 0 1))
  (Carrier State (Of (Tuple Nat Nat Nat)) (Product Bit Bit Bit))
  (Carrier Pair  (Of (Tuple Nat Nat)) (Product Bit Bit))
  (Map read-a  (From State) (To Bit)   (Cases ((Tuple $a $b $c) $a)))
  (Map swap-ab (From State) (To State) (Cases ((Tuple $a $b $c) (Tuple $b $a $c))))
  (Map keep-ab (From State) (To Pair)  (Cases ((Tuple $a $b $c) (Tuple $a $b))))
  (Machine Concrete (States State) (Observe a read-a) (Action swap swap-ab))
  (Representation KeepA  (Of Concrete) (Encode read-a))
  (Representation KeepAB (Of Concrete) (Encode keep-ab))
  (Measure Uniform (On State) (Uniform))
  (Derive Repair (Refine KeepA (Preserve Encoding) (Until Stable) (Under Uniform)))
  (Derive AB (InduceExact KeepAB))

  (Carrier Code (Of Nat) (Enum 0 1 2 3))
  (Map code-a    (From Code) (To Bit)  (Table (0 0) (1 0) (2 1) (3 1)))
  (Map code-swap (From Code) (To Code) (Table (0 0) (1 2) (2 1) (3 3)))
  (Map pair-code (From Pair) (To Code) (Cases ((Tuple $a $b) (Add (Mul 2 $a) $b))))
  (Machine Codes (States Code) (Observe a code-a) (Action swap code-swap))
  (AbstractionMap ABToCodes
    (Source (Output AB Machine)) (Target Codes) (Map pair-code))
  (Derive SecondChecked (CheckAbstractionMap ABToCodes))
  (Derive Composed
    (Then (Output AB AbstractionMap) (Output SecondChecked Value))))
!(dc.run ThenEight SecondChecked)
!(dc.run ThenEight Composed)
