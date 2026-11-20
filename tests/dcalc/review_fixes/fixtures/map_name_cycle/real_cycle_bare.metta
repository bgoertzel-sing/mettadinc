;; real map-call cycle through a bare Map name that is not an Enum element: f applies g, g's value is the bare map f
(DC.Module CycB
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map f (From Press) (To Press) (Body ($x) (g $x)))
  (Map g (From Press) (To Press) (Cases ($p f)))
  (Machine M (States Press) (Observe f f) (Action push g)))

!(dc.run CycB (MinimizeForQueries M))
