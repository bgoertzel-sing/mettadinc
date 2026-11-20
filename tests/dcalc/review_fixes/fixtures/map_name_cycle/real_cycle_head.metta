;; real map-call cycle through applications: f calls g, g calls f (must stay rejected)
(DC.Module Cyc
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map f (From Press) (To Press) (Body ($x) (g $x)))
  (Map g (From Press) (To Press) (Body ($x) (f $x)))
  (Machine M (States Press) (Observe f f) (Action push g)))

!(dc.run Cyc (MinimizeForQueries M))
