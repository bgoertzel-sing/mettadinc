;; Control for map_name_element_clash.metta: same module with the Map renamed to-deadline; no map-call cycle.
(DC.Module P
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map show (From Press) (To Press) (Body ($x) $x))
  (Map to-deadline (From Press) (To Press) (Body ($x) deadline))
  (Machine M (States Press) (Observe show show) (Action push to-deadline))
  (BlockPartition Part (On Press)
    (Block All (Body ($x) True) calm)
    (Successor push All All)))

!(dc.run P (CheckBlockPartition Part (Of M)))
