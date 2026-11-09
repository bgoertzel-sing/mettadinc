;; Review 4 F3: Add overflow is an admission error, not a wrapped value.
(DC.Module OverflowAdd
  (Profile Crisp)
  (Carrier One (Of Nat) (Enum 0))
  (Carrier Wrapped (Of Int) (Enum -9223372036854775808))
  (Map broken (From One) (To Wrapped) (Cases ($x (Add 9223372036854775807 1))))
  (Map id (From One) (To One) (Table (0 0)))
  (Machine M (States One) (Observe number broken))
  (Representation R (Of M) (Encode id)))
!(dc.run OverflowAdd (MeasureNow R))
