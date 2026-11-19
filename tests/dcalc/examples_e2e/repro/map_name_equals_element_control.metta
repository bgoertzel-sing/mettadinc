;; Control for map_name_equals_element.metta: the same module with the map renamed to-deadline; passes admission.
(DC.Module R
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map to-deadline (From Press) (To Press) (Cases ($p deadline)))
  (Map obs (From Press) (To Press) (Cases ($p $p)))
  (Machine M (States Press) (Observe obs obs) (Action deadline to-deadline)))

!(dc.run R (MinimizeForQueries M))
