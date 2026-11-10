;; OQ3 claimless test module (M2): BehavioralTolerance (Def 4.1, Thm 4.2, Prop 4.10), deterministic.
;; Hand derivation on A->B->C->D->D with o = 0,0,0,1: first separating step k gives d = g^k.
;; g=1/2 unbounded: d(x,D)=1, d(A,C)=d(B,C)=1/2, d(A,B)=1/4. Horizon 1, g=1: d(A,B)=0, all other pairs 1. g=1, unbounded: every distinct pair 1.
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
!(dc.run TraceFour (BehavioralTolerance M (Discount (Rat 1 2))))
!(dc.run TraceFour (BehavioralTolerance M (Horizon (Steps 1))))
!(dc.run TraceFour (BehavioralTolerance M))
