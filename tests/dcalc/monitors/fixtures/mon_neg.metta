(DC.Module MonNeg
  (Profile Stochastic)
  (Use Decisions Laws Families Monitors)
  (Carrier One  (Of Symbol) (Enum one))
  (Monitor Nowhere (Context Missing) (Null (Coin (Rat 1 4))) (Alternative (Coin (Rat 1 2))) (Columns (observation "x")))
  (Stream Hot (Source "streams/hot.json") (Digest "sha256:329ae55366ee77dcb37a2f661572ec64be8664c469dad27b391375cd1f5fa221") (Provenance "fixture: eight ones")))
!(dc.run MonNeg (CheckMonitor Nowhere))
