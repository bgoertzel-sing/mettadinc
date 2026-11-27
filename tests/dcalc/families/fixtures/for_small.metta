;; t-2026-11-26-mettadinc-families-gates-2 item 1: a small For fixture for the for_drops_last_element mutant (replaces
;; the ex2 run in the mutant gate, which peaked at about 4.2 GB RSS).  Ix = i0 i1 i2, (idx i) = bit index 0 1 2.
;; FS: Machine M has one Action per element, (set $i) for $i in Ix, set.i sets bit (idx i); MR is M on the words
;; reachable from 0.  Bit2Low claims bit 2 stays 0 under every action.
;;   HEAD: For gives set.i0 set.i1 set.i2; set.i2 reaches word 4 from 0: Refuted, witness word 4.
;;   A For that drops the last element gives set.i0 set.i1 only; bit 2 is never set and the answer is not Refuted.
;; FT (control, last element not involved): Bit1Low claims bit 1 stays 0; set.i1 reaches word 2: Refuted, witness
;;   word 2 on HEAD and under the mutant (so the gate also shows the mutant still elaborates the module).
(DC.Module FS
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 3)) (All))
  (Carrier Ix (Of Symbol) (Enum i0 i1 i2))
  (Map idx (From Ix) (To Nat) (Table (i0 0) (i1 1) (i2 2)))
  (Map setb (Parameters ($i Ix)) (From Word) (To Word) (Body ($x) (SetBit $x (idx $i) 1)))
  (Map read2 (From Word) (To Bit) (Body ($x) (BitAt $x 2)))
  (Machine M (States Word) (Observe x2 read2) (Action (set $i) (setb $i) (For $i Ix)))
  (Carrier FromZero (Of (BitVector 3)) (Reach M (From 0)))
  (Machine MR (States FromZero) (Observe x2 read2) (ActionsOf M))
  (BlockPartition Bit2Low (On FromZero)
    (Block B0 (Body ($x) (Eq (BitAt $x 2) 0)) 0)
    (Successor Any B0 B0)))
!(dc.run FS (CheckBlockPartition Bit2Low (Of MR)))
(DC.Module FT
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 3)) (All))
  (Carrier Ix (Of Symbol) (Enum i0 i1 i2))
  (Map idx (From Ix) (To Nat) (Table (i0 0) (i1 1) (i2 2)))
  (Map setb (Parameters ($i Ix)) (From Word) (To Word) (Body ($x) (SetBit $x (idx $i) 1)))
  (Map read1 (From Word) (To Bit) (Body ($x) (BitAt $x 1)))
  (Machine M (States Word) (Observe x1 read1) (Action (set $i) (setb $i) (For $i Ix)))
  (Carrier FromZero (Of (BitVector 3)) (Reach M (From 0)))
  (Machine MR (States FromZero) (Observe x1 read1) (ActionsOf M))
  (BlockPartition Bit1Low (On FromZero)
    (Block B0 (Body ($x) (Eq (BitAt $x 1) 0)) 0)
    (Successor Any B0 B0)))
!(dc.run FT (CheckBlockPartition Bit1Low (Of MR)))
