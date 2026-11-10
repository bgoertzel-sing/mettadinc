;; OQ3 claimless test module (M2): MinimizeForQueries (Thm 4.2(3), Def 4.11 splitting tree).
;; Hand derivation: o = A 0, B 0, C 1, D 1, E 0; step A->C, B->D, C->C, D->D, E->E.
;; K_O = {A,B,E}{C,D}. Under step: A,B go to {C,D}, E stays in {A,B,E} -> split E off.
;; Stable: {A,B}{C,D}{E}. Trace words: A,B give 0,1,1..., E gives 0,0,...; C,D give 1,1,...
(DC.Module MinPairs
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum A B C D E))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map obs (From S) (To Bit) (Cases (A 0) (B 0) (C 1) (D 1) (E 0)))
  (Map step (From S) (To S) (Cases (A C) (B D) (C C) (D D) (E E)))
  (Machine M (States S) (Observe o obs) (Action step step)))
!(dc.run MinPairs (MinimizeForQueries M))
