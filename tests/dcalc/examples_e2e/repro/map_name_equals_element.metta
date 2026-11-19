;; Minimal reproduction (doc 04 ClaimArbitration, memory_goals.metta:594/638): a map named like an enumeration
;; element (deadline) whose body returns that element. Admission (admit.c:967) reads the element as a call to
;; the map and reports "map-call cycle deadline -> deadline".
(DC.Module R
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map deadline (From Press) (To Press) (Cases ($p deadline)))
  (Map obs (From Press) (To Press) (Cases ($p $p)))
  (Machine M (States Press) (Observe obs obs) (Action deadline deadline)))

!(dc.run R (MinimizeForQueries M))
