;; map-name-cycle (review 1): Choice rows: Map deadline named like an Enum element, rows are data, not a self-call
(DC.Module R
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map deadline (From Press) (To Press) (Choice (calm deadline) (deadline calm deadline)))
  (Map obs (From Press) (To Press) (Cases ($p $p)))
  (Machine M (States Press) (Observe obs obs) (Action deadline deadline)))

!(dc.run R (MinimizeForQueries M))
