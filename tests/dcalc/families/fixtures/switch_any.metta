;; Review 1 finding 4 (t-2026-11-24-mettadinc-families): Switch with an Any arm.  pick a sets bit 0 (its own arm);
;; pick b has no arm of its own and takes the Any arm, which sets bit 1.  Both expected answers are Refuted, so the
;; fixture decides without the proof backend.
;; SwA runs pick a from word 0 and claims bit 0 stays 0: the a arm reaches word 1, Refuted with witness word 1.
;;   An elaborator that always prefers the Any arm reaches only word 2, so bit 0 stays 0 and the answer is not Refuted.
;; SwB runs pick b from word 0 and claims bit 1 stays 0: the Any arm reaches word 2, Refuted with witness word 2.
;;   An elaborator that takes the first arm reaches word 1 (not Refuted); one that ignores Any cannot elaborate pick b.
(DC.Module SwA
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 3)) (All))
  (Carrier K (Of Symbol) (Enum a b))
  (Map pick (Parameters ($k K)) (From Word) (To Word)
    (Body ($x) (Switch $k (a (SetBit $x 0 1)) (Any (SetBit $x 1 1)))))
  (Map doa  (From Word) (To Word) (Body ($x) (pick a $x)))
  (Map read0 (From Word) (To Bit) (Body ($x) (BitAt $x 0)))
  (Machine M (States Word) (Observe x0 read0) (Action act doa))
  (Carrier FromZero (Of (BitVector 3)) (Reach M (From 0)))
  (Machine MR (States FromZero) (Observe x0 read0) (Action act doa))
  (BlockPartition Bit0Low (On FromZero)
    (Block B0 (Body ($x) (Eq (BitAt $x 0) 0)) 0)
    (Successor act B0 B0)))
!(dc.run SwA (CheckBlockPartition Bit0Low (Of MR)))
(DC.Module SwB
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 3)) (All))
  (Carrier K (Of Symbol) (Enum a b))
  (Map pick (Parameters ($k K)) (From Word) (To Word)
    (Body ($x) (Switch $k (a (SetBit $x 0 1)) (Any (SetBit $x 1 1)))))
  (Map dob  (From Word) (To Word) (Body ($x) (pick b $x)))
  (Map read1 (From Word) (To Bit) (Body ($x) (BitAt $x 1)))
  (Machine M (States Word) (Observe x1 read1) (Action act dob))
  (Carrier FromZero (Of (BitVector 3)) (Reach M (From 0)))
  (Machine MR (States FromZero) (Observe x1 read1) (Action act dob))
  (BlockPartition Bit1Low (On FromZero)
    (Block B0 (Body ($x) (Eq (BitAt $x 1) 0)) 0)
    (Successor act B0 B0)))
!(dc.run SwB (CheckBlockPartition Bit1Low (Of MR)))
