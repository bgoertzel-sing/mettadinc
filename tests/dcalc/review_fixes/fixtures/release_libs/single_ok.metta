;; t-2026-11-20-mettadinc-release-libs: single-file control for main_ok.metta + lib_ok.metta.
(DC.Module LibCar
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum A B C D E))
  (Carrier Bit (Of Nat) (Enum 0 1)))
(DC.Module UsesLibCar
  (Profile Crisp)
  (Import LibCar (Only S Bit))
  (Map obs (From S) (To Bit) (Cases (A 0) (B 0) (C 1) (D 1) (E 0)))
  (Map step (From S) (To S) (Cases (A C) (B D) (C C) (D D) (E E)))
  (Machine M (States S) (Observe o obs) (Action step step)))
!(dc.run UsesLibCar (MinimizeForQueries M))
