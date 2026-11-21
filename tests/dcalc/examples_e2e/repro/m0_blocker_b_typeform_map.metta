;; Remaining M0 blocker (b): a map declared with a type, (From (Tuple Symbol Symbol)), instead of a carrier name.
;; B1 -> Unsupported (blocker); B1C control (From AB)/(To AB) -> Checked.
(DC.Module B1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Carrier B (Of Symbol) (Enum r s))
  (Carrier AB (Of (Tuple Symbol Symbol)) (Product A B))
  (Map id (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Cases ((Tuple $a $b) (Tuple $a $b))))
  (Machine M (States AB) (Observe id id) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run B1 (CheckNow R))
(DC.Module B1C
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Carrier B (Of Symbol) (Enum r s))
  (Carrier AB (Of (Tuple Symbol Symbol)) (Product A B))
  (Map id (From AB) (To AB) (Cases ((Tuple $a $b) (Tuple $a $b))))
  (Machine M (States AB) (Observe id id) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run B1C (CheckNow R))
