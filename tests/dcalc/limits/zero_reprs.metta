;; Review-fixes review 1 F2: a module with zero representations; a request naming one is refused.
(DC.Module NoReprs
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0) (1 1)))
  (Machine M (States Bit) (Observe value id)))
!(dc.run NoReprs (MeasureNow R0))
