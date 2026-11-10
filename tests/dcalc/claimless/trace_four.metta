;; OQ3 claimless test module (M2): MeasureTrace / CheckTrace (Def 4.4(4), deterministic, discrete value tolerances).
;; Hand derivation: only code-equal pair is (A,B). Horizon 1: A gives 0,0 and B gives 0,0 -> defect 0.
;; Horizon 2: A gives 0,0,0 and B gives 0,0,1 -> defect 1 (word step step). Unbounded: 1. Discount is refused.
;; code A,B -> 0, C -> 1, D -> 2: only code-equal pair is (A,B), first separated at horizon 2.
(DC.Module TraceFour
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum A B C D))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Carrier Code (Of Nat) (Enum 0 1 2))
  (Map obs (From S) (To Bit) (Cases (A 0) (B 0) (C 0) (D 1)))
  (Map step (From S) (To S) (Cases (A B) (B C) (C D) (D D)))
  (Map code (From S) (To Code) (Cases (A 0) (B 0) (C 1) (D 2)))
  (Machine M (States S) (Observe o obs) (Action step step))
  (Representation Q (Of M) (Encode code)))
!(dc.run TraceFour (MeasureTrace Q (Horizon (Steps 1))))
!(dc.run TraceFour (MeasureTrace Q (Horizon (Steps 2))))
!(dc.run TraceFour (CheckTrace Q (Horizon (Steps 1))))
!(dc.run TraceFour (CheckTrace Q (Policies ObservationBased)))
!(dc.run TraceFour (MeasureTrace Q (Discount (Rat 1 2))))
