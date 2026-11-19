;; D-con-clip (t-2026-11-18-mettadinc-m4m6-differential): minimal input.
;; One audited point x = 0; ideal f(x) = 0, actual f-hat(x) = 2. Requested grade (L, eta) = (0, 1).
;; Spec l.686-694: the OneMinusAbsoluteDifference tolerance is beta = max(0, 1 - |p - p'|), and the value
;; distance is 1 - beta = min(1, |p - p'|). So d(f-hat(0), f(0)) = 1 <= 0 * 0 + 1: the contract holds.
;; Oracle (spec): Checked, Grade 0 1.  dcalc (ops_contracts.c ct_dist uses unclipped |p - q| = 2): see report.
(DC.Module DConClip
  (Profile Graded)
  (Use Contracts)
  (Carrier X (Of Rational) (Enum 0))
  (Map f (From X) (To Rational) (Body ($x) (Add (Mul 0 $x) 0)))
  (Map f-hat (From X) (To Rational) (Body ($x) (Add (Mul 0 $x) 2)))
  (Tolerance Gap (On Rational) (OneMinusAbsoluteDifference))
  (Implementation First (Ideal f) (Actual f-hat) (Audit X) (InputDistance Gap) (OutputDistance Gap))
  (Derive C1 (CheckImplementation First (Grade 0 1))))
!(dc.run DConClip C1)
