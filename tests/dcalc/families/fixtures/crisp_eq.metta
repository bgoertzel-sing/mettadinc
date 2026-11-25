;; Finding 1 (review 1): a Crisp enumerated module with (Use Families); Eq of two enumeration constants must fold to True/False, not 0/1.
(DC.Module CE1
  (Profile Crisp)
  (Use Families)
  (Carrier Lvl (Of Symbol) (Enum low high))
  (Map same (From Lvl) (To Bool) (Cases (low (Eq low low)) (high (Eq high low))))
  (Map id (From Lvl) (To Lvl) (Cases ($a $a)))
  (Machine M (States Lvl) (Observe same same) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run CE1 (CheckNow R))
(DC.Module CE0
  (Profile Crisp)
  (Carrier Lvl (Of Symbol) (Enum low high))
  (Map same (From Lvl) (To Bool) (Cases (low (Eq low low)) (high (Eq high low))))
  (Map id (From Lvl) (To Lvl) (Cases ($a $a)))
  (Machine M (States Lvl) (Observe same same) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run CE0 (CheckNow R))
