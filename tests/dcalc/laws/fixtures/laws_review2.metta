;; Laws review-2 gate: a computed Point value evaluates (F1); a map call in a Point, or an admitted Families/NatArith form
;; in a law leaf, is Unsupported with its reason (F1, F2); a bare (Expect L) case body is InvalidInput with a sub-reason (F4).
(DC.Module QPadd
  (Profile Stochastic)
  (Use Decisions)
  (Use Laws)
  
  (Carrier S (Of Symbol) (Enum A))
  (Carrier Act (Of Symbol) (Enum K))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map pr (From S) (To Bit) (Cases (A 0)))
  (Map rl (From (Product S Act)) (To (Law Bit)) (Cases ((Tuple A K) (Point (Add 0 1)))))
  (Measure Pa (On S) (Masses (A 1)))
  (DecisionModel M (States S) (Actions Act) (RewardLaw rl) (Prior Pa)))
!(dc.run QPadd (AverageModel M (Under Pa)))

(DC.Module QPif
  (Profile Stochastic)
  (Use Decisions)
  (Use Laws)
  
  (Carrier S (Of Symbol) (Enum A))
  (Carrier Act (Of Symbol) (Enum K))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map pr (From S) (To Bit) (Cases (A 0)))
  (Map rl (From (Product S Act)) (To (Law Bit)) (Cases ((Tuple A K) (Point (If (Eq 1 1) 1 0)))))
  (Measure Pa (On S) (Masses (A 1)))
  (DecisionModel M (States S) (Actions Act) (RewardLaw rl) (Prior Pa)))
!(dc.run QPif (AverageModel M (Under Pa)))

(DC.Module QPmap
  (Profile Stochastic)
  (Use Decisions)
  (Use Laws)
  
  (Carrier S (Of Symbol) (Enum A))
  (Carrier Act (Of Symbol) (Enum K))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map pr (From S) (To Bit) (Cases (A 0)))
  (Map rl (From (Product S Act)) (To (Law Bit)) (Cases ((Tuple A K) (Point (pr A)))))
  (Measure Pa (On S) (Masses (A 1)))
  (DecisionModel M (States S) (Actions Act) (RewardLaw rl) (Prior Pa)))
!(dc.run QPmap (AverageModel M (Under Pa)))

(DC.Module QFsw
  (Profile Stochastic)
  (Use Decisions)
  (Use Laws)
  (Use Families)
  (Carrier S (Of Symbol) (Enum A))
  (Carrier Act (Of Symbol) (Enum K))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map pr (From S) (To Bit) (Cases (A 0)))
  (Map rl (From (Product S Act)) (To (Law Bit)) (Cases ((Tuple A K) (Image $b (Switch $b (0 1) (1 0)) (Coin (Rat 1 2))))))
  (Measure Pa (On S) (Masses (A 1)))
  (DecisionModel M (States S) (Actions Act) (RewardLaw rl) (Prior Pa)))
!(dc.run QFsw (AverageModel M (Under Pa)))

(DC.Module QNquot
  (Profile Stochastic)
  (Use Decisions)
  (Use Laws)
  (Use NatArith)
  (Carrier S (Of Symbol) (Enum A))
  (Carrier Act (Of Symbol) (Enum K))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map pr (From S) (To Bit) (Cases (A 0)))
  (Map rl (From (Product S Act)) (To (Law Bit)) (Cases ((Tuple A K) (Image $b (Quot $b 2) (Coin (Rat 1 2))))))
  (Measure Pa (On S) (Masses (A 1)))
  (DecisionModel M (States S) (Actions Act) (RewardLaw rl) (Prior Pa)))
!(dc.run QNquot (AverageModel M (Under Pa)))

(DC.Module QEexp
  (Profile Stochastic)
  (Use Decisions)
  (Use Laws)
  
  (Carrier S (Of Symbol) (Enum A))
  (Carrier Act (Of Symbol) (Enum K))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map pr (From S) (To Bit) (Cases (A 0)))
  (Map rl (From (Product S Act)) (To (Law Bit)) (Cases ((Tuple A K) (Expect (Coin (Rat 1 2))))))
  (Measure Pa (On S) (Masses (A 1)))
  (DecisionModel M (States S) (Actions Act) (RewardLaw rl) (Prior Pa)))
!(dc.run QEexp (AverageModel M (Under Pa)))

