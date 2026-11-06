;; Affine implementation contracts.  Specification, Section 9.3.
;; @excerpt affine
(DC.Module AffineContracts
  (Profile Graded)
  (Use Contracts)
  (Carrier X (Of Rational) (Enum 0 1))
  (Carrier Y (Of Rational) (Enum 0 2 (Rat 1 10) (Rat 21 10)))
  (Map f     (From X) (To Rational) (Body ($x) (Mul 2 $x)))
  (Map f-hat (From X) (To Rational) (Body ($x) (Add (Mul 2 $x) (Rat 1 10))))
  (Map g     (From Y) (To Rational) (Body ($y) (Mul 3 $y)))
  (Map g-hat (From Y) (To Rational) (Body ($y) (Add (Mul 3 $y) (Rat 1 5))))
  (Map gf     (From X) (To Rational) (Body ($x) (g (f $x))))
  (Map gf-hat (From X) (To Rational) (Body ($x) (g-hat (f-hat $x))))
  (Tolerance Gap (On Rational) (OneMinusAbsoluteDifference))
  (Implementation First   (Ideal f)  (Actual f-hat)  (Audit X) (InputDistance Gap) (OutputDistance Gap))
  (Implementation Second  (Ideal g)  (Actual g-hat)  (Audit Y) (InputDistance Gap) (OutputDistance Gap))
  (Implementation Direct  (Ideal gf) (Actual gf-hat) (Audit X) (InputDistance Gap) (OutputDistance Gap))
  (Derive FirstChecked  (CheckImplementation First  (Grade 2 (Rat 1 10))))
  (Derive SecondChecked (CheckImplementation Second (Grade 3 (Rat 1 5))))
  (Derive Composite (ThenContracts (Output FirstChecked Value) (Output SecondChecked Value))))
;; @end
!(dc.run AffineContracts Composite)
!(dc.run AffineContracts (CheckImplementation Direct (Grade 6 (Rat 1 2))))
!(dc.run AffineContracts (CheckImplementation Direct (Grade 6 (Rat 3 10))))
