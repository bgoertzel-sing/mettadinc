;; t-2026-11-26-mettadinc-families-gates-2 item 2: exact verdicts for the ForAll / Exists unfolding (families.c,
;; term_list: the Or / And of the instances).  Ix = i0 i1 i2, (idx i) = bit index 0 1 2.  One action, set2, sets bit 2;
;; MR is the machine on the words reachable from 0, i.e. {0, 4}.  Only the LAST element of Ix (i2) sees bit 2.  QE and QA
;; observe bit 1, which is 0 on both words, so the Constancy obligation holds and the block body alone decides.
;; QE (Exists body): Quiet = (Not (Exists $i Ix (Eq (BitAt $x (idx $i)) 1))), "no bit is set".
;;   HEAD: word 4 has bit 2 set, so Exists is true there: Refuted, witness word 4.
;;   An unfolding that drops the last element tests bits 0 and 1 only; word 4 stays Quiet: Checked, not Refuted.
;; QA (ForAll body): Good = (ForAll $i Ix (Eq (BitAt $x (idx $i)) 0)), "every bit is clear".
;;   HEAD: word 4 fails it at i2: Refuted, witness word 4.  Dropping i2: word 4 is Good: Checked, not Refuted.
;; QF (first-element control): Good = (ForAll $i Ix (Eq (BitAt $x (idx $i)) 0)) with the action setting bit 0 instead;
;;   Refuted, witness word 1 on HEAD and under the drop-last mutant (the mutant still elaborates ForAll).
(DC.Module QE
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 3)) (All))
  (Carrier Ix (Of Symbol) (Enum i0 i1 i2))
  (Map idx (From Ix) (To Nat) (Table (i0 0) (i1 1) (i2 2)))
  (Map set2 (From Word) (To Word) (Body ($x) (SetBit $x 2 1)))
  (Map read1 (From Word) (To Bit) (Body ($x) (BitAt $x 1)))
  (Machine M (States Word) (Observe x1 read1) (Action act set2))
  (Carrier FromZero (Of (BitVector 3)) (Reach M (From 0)))
  (Machine MR (States FromZero) (Observe x1 read1) (Action act set2))
  (BlockPartition Quiet (On FromZero)
    (Block B0 (Body ($x) (Not (Exists $i Ix (Eq (BitAt $x (idx $i)) 1)))) 0)
    (Successor Any B0 B0)))
!(dc.run QE (CheckBlockPartition Quiet (Of MR)))
(DC.Module QA
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 3)) (All))
  (Carrier Ix (Of Symbol) (Enum i0 i1 i2))
  (Map idx (From Ix) (To Nat) (Table (i0 0) (i1 1) (i2 2)))
  (Map set2 (From Word) (To Word) (Body ($x) (SetBit $x 2 1)))
  (Map read1 (From Word) (To Bit) (Body ($x) (BitAt $x 1)))
  (Machine M (States Word) (Observe x1 read1) (Action act set2))
  (Carrier FromZero (Of (BitVector 3)) (Reach M (From 0)))
  (Machine MR (States FromZero) (Observe x1 read1) (Action act set2))
  (BlockPartition Good (On FromZero)
    (Block B0 (Body ($x) (ForAll $i Ix (Eq (BitAt $x (idx $i)) 0))) 0)
    (Successor Any B0 B0)))
!(dc.run QA (CheckBlockPartition Good (Of MR)))
(DC.Module QF
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 3)) (All))
  (Carrier Ix (Of Symbol) (Enum i0 i1 i2))
  (Map idx (From Ix) (To Nat) (Table (i0 0) (i1 1) (i2 2)))
  (Map set0 (From Word) (To Word) (Body ($x) (SetBit $x 0 1)))
  (Map read0 (From Word) (To Bit) (Body ($x) (BitAt $x 0)))
  (Machine M (States Word) (Observe x0 read0) (Action act set0))
  (Carrier FromZero (Of (BitVector 3)) (Reach M (From 0)))
  (Machine MR (States FromZero) (Observe x0 read0) (Action act set0))
  (BlockPartition Good (On FromZero)
    (Block B0 (Body ($x) (ForAll $i Ix (Eq (BitAt $x (idx $i)) 0))) 0)
    (Successor Any B0 B0)))
!(dc.run QF (CheckBlockPartition Good (Of MR)))
