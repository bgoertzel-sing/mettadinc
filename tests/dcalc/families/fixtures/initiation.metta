;; Review 1 (t-2026-11-24-mettadinc-families): the start word 1 lies outside the Invariant (x0 = 0), which is
;; inductive under every action, and the only block covers exactly the Invariant.  The budget truncates the
;; reach scope, so the induction path runs.  Initiation fails, so induction must not certify the scope; the start
;; word itself is uncovered, so the answer is Refuted (Coverage at the start word).  Without the Initiation check
;; the induction would wrongly certify I and answer Checked.
(DC.Module InitOut
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors)
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Word (Of (BitVector 5)) (All))
  (Map read0  (From Word) (To Bit)  (Body ($x) (BitAt $x 0)))
  (Map clear0 (From Word) (To Word) (Body ($x) (SetBit $x 0 0)))
  (Map set1   (From Word) (To Word) (Body ($x) (SetBit $x 1 1)))
  (Map rot    (From Word) (To Word) (Body ($x) (RotateRange $x 1 4)))
  (Map lowzero (From Word) (To Bit) (Body ($x) (Not (BitAt $x 0))))
  (Machine OneMachine (States Word) (Observe x0 read0) (Action clear clear0) (Action set set1) (Action rot rot))
  (Carrier FromOne (Of (BitVector 5)) (Reach OneMachine (From 1)))
  (Machine OneReach (States FromOne) (Observe x0 read0) (Action clear clear0) (Action set set1) (Action rot rot))
  (BlockPartition Low (On FromOne)
    (Block B0 (Body ($x) (Eq (BitAt $x 0) 0)) 0)
    (Successor clear B0 B0) (Successor set B0 B0) (Successor rot B0 B0)
    (Invariant lowzero)))
!(dc.run InitOut (CheckBlockPartition Low (Of OneReach) (Budget (Unrollings 1))))
!(dc.run InitOut (CheckBlockPartition Low (Of OneReach)))
