;; Reach start z is not a state of M0 -> InvalidInput (spec 5.3: the initial set must be states of M).
(DC.Module TB
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map step (From A) (To A) (Cases (p q) (q p)))
  (Machine M0 (States A) (Observe step step) (Action step step))
  (Carrier C (Of Symbol) (Reach M0 (From z)))
  (Machine M (States C) (Observe step step) (Action step step))
  (Representation R (Of M) (Encode step)))
!(dc.run TB (CheckNow R))
