;; t-2026-11-24-mettadinc-m0-gap-g: near misses of the (To Bool) Observe map with a type-form From.
;; Each module differs from repro g's G1 (tests/dcalc/examples_e2e/repro/m0_blocker_g_bool_typeform_from.metta) in one
;; respect; the expected answers and the reason for each are in ../README.md.
;; NT1: To names an undeclared symbol, not the builtin Bool.
(DC.Module NT1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Truth) (Cases ((Tuple $a $b) (Eq $a $b))))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NT1 (CheckNow R))
;; NF1: From names an undeclared carrier, not a type form.
(DC.Module NF1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From BB) (To Bool) (Cases ((Tuple $a $b) (Eq $a $b))))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NF1 (CheckNow R))
;; NF2: From is a type form, but not the element type of the states it is used on.
(DC.Module NF2
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol Symbol)) (To Bool) (Cases ((Tuple $a $b $c) (Eq $a $b))))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NF2 (CheckNow R))
;; NW1: a value that is not True or False.
(DC.Module NW1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple $a $b) $a)))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NW1 (CheckNow R))
;; NW2: no value on one state (not total on the states).
(DC.Module NW2
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple p p) True) ((Tuple p q) False) ((Tuple q p) False)))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NW2 (CheckNow R))
;; NW3: two cases match one state (overlap).
(DC.Module NW3
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple p $b) True) ((Tuple $a $b) False)))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NW3 (CheckNow R))
;; NG1: the same map in a Graded module.
(DC.Module NG1
  (Profile Graded)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple $a $b) (Eq $a $b))))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NG1 (CheckNow R))
;; NA1: the map used as an Action, not an Observe port.
(DC.Module NA1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple $a $b) (Eq $a $b))))
  (Machine M (States AA) (Observe me id) (Action live live))
  (Representation R (Of M) (Encode id)))
!(dc.run NA1 (CheckNow R))
;; NE1: the map is an Observe port and also the Encode map (a code in Bool).
(DC.Module NE1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple $a $b) (Eq $a $b))))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode live)))
!(dc.run NE1 (CheckNow R))
;; NU1: a Body outside the Body fragment (Eq in a Body; Body maps keep Tuple/Add/Mul).
(DC.Module NU1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Body ($x) (Eq $x (Tuple p p))))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NU1 (CheckNow R))
;; NU2: a Cases body with an operator outside the Crisp fragment (Xor; admitted only in a Neural module).
(DC.Module NU2
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From AA) (To AA) (Cases ($x $x)))
  (Map live (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple $a $b) (Xor (Eq $a p) (Eq $b p)))))
  (Machine M (States AA) (Observe live live) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NU2 (CheckNow R))
