;; D4 minimal (t-2026-11-18-mettadinc-m4m6-differential): OneMinusAbsoluteDifference distance not clipped at 1.
;; Audit X = {0, 2}, f = f-hat = identity, requested grade (L 0, eta 1).
;; Spec l.686-694: distance = 1 - max(0, 1 - |p - q|) = min(1, |p - q|). Worst pair d(f-hat 0, f 2) = 1 <= 0*1 + 1.
;; Oracle (spec): Checked, Grade 0 1.  Unclipped |p - q| = 2 would give Refuted.
(DC.Module D4Min
  (Profile Graded)
  (Use Contracts)
  (Carrier X (Of Rational) (Enum 0 2))
  (Map f (From X) (To Rational) (Body ($x) (Add (Mul 1 $x) 0)))
  (Map f-hat (From X) (To Rational) (Body ($x) (Add (Mul 1 $x) 0)))
  (Tolerance Gap (On Rational) (OneMinusAbsoluteDifference))
  (Implementation First (Ideal f) (Actual f-hat) (Audit X) (InputDistance Gap) (OutputDistance Gap))
  (Derive C1 (CheckImplementation First (Grade 0 1))))
!(dc.run D4Min C1)
