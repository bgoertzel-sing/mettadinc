(DC.Module CmpSmoke
  (Profile Stochastic)
  (Use Estimates)
  (Stream Lives (Source "../../../../docs/e0/docs/06_wmtm_worked_example/validation_bundle/streams/lives_gate.json")
    (Digest "sha256:5eb1f54bf60f047de30f1cdfa4516dcefc3a789df5bac4763cdebe14aaaca801")
    (Population "lives") (Selection "all") (Policy "v1")))
!(dc.run CmpSmoke (CompareRates (On Lives) (First "window_bad") (Second "event_bad") (Equals 1) (Level (Rat 1 100))))
