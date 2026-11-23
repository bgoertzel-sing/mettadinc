;; t-2026-11-20-mettadinc-release-libs: run as dcalc main_ok.metta lib_ok.metta. Release mode must resolve the cross-file
;; import and give exactly the answer of the single-file control single_ok.metta.
(DC.Module UsesLibCar
  (Profile Crisp)
  (Import LibCar (Only S Bit))
  (Map obs (From S) (To Bit) (Cases (A 0) (B 0) (C 1) (D 1) (E 0)))
  (Map step (From S) (To S) (Cases (A C) (B D) (C C) (D D) (E E)))
  (Machine M (States S) (Observe o obs) (Action step step)))
!(dc.run UsesLibCar (MinimizeForQueries M))
