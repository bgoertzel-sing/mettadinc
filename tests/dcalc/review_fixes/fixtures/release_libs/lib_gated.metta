;; t-2026-11-20-mettadinc-release-libs: library file using PROPOSED NatArith; importing it cross-file must not widen release admission.
(DC.Module LibGated
  (Profile Crisp)
  (Use NatArith)
  (Carrier S (Of Symbol) (Enum A B C D E))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map obs (From S) (To Bit) (Cases (A 0) (B 0) (C 1) (D 1) (E 0)))
  (Map step (From S) (To S) (Cases (A C) (B D) (C C) (D D) (E E))))
