;; map-name-cycle (review 1): control for choice_clash: Map renamed, same rows
(DC.Module R
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map to-deadline (From Press) (To Press) (Choice (calm deadline) (deadline calm deadline)))
  (Map obs (From Press) (To Press) (Cases ($p $p)))
  (Machine M (States Press) (Observe obs obs) (Action deadline to-deadline)))

!(dc.run R (MinimizeForQueries M))
