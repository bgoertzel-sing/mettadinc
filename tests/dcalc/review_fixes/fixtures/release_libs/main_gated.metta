;; t-2026-11-20-mettadinc-release-libs: run as dcalc main_gated.metta lib_gated.metta; must stay Unsupported (NatArith) in release mode.
(DC.Module UsesLibGated
  (Profile Crisp)
  (Import LibGated (Only S Bit obs step))
  (Machine M (States S) (Observe o obs) (Action step step)))
!(dc.run UsesLibGated (MinimizeForQueries M))
