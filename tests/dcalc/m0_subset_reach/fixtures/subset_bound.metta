;; Bound: the Subset parent is a 65x65 = 4225-element Product, past the 4096 Enum/Product bound -> Unsupported
;; (the same answer as the plain Product control PB).
(DC.Module SB
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum e0 e1 e2 e3 e4 e5 e6 e7 e8 e9 e10 e11 e12 e13 e14 e15 e16 e17 e18 e19 e20 e21 e22 e23 e24 e25 e26 e27 e28 e29 e30 e31 e32 e33 e34 e35 e36 e37 e38 e39 e40 e41 e42 e43 e44 e45 e46 e47 e48 e49 e50 e51 e52 e53 e54 e55 e56 e57 e58 e59 e60 e61 e62 e63 e64))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map keep (From (Tuple Symbol Symbol)) (To Bool) (Cases ((Tuple $a $b) True)))
  (Carrier B (Of (Tuple Symbol Symbol)) (Subset AA keep))
  (Map stay (From B) (To B) (Cases ($x $x)))
  (Machine M (States B) (Observe stay stay) (Action stay stay))
  (Representation R (Of M) (Encode stay)))
!(dc.run SB (CheckNow R))
(DC.Module PB
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum e0 e1 e2 e3 e4 e5 e6 e7 e8 e9 e10 e11 e12 e13 e14 e15 e16 e17 e18 e19 e20 e21 e22 e23 e24 e25 e26 e27 e28 e29 e30 e31 e32 e33 e34 e35 e36 e37 e38 e39 e40 e41 e42 e43 e44 e45 e46 e47 e48 e49 e50 e51 e52 e53 e54 e55 e56 e57 e58 e59 e60 e61 e62 e63 e64))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map stay (From AA) (To AA) (Cases ($x $x)))
  (Machine M (States AA) (Observe stay stay) (Action stay stay))
  (Representation R (Of M) (Encode stay)))
!(dc.run PB (CheckNow R))
