;; Minimal reproduction (doc 04 ClaimArbitration, memory_goals.metta:594/638): a Map named like an Enum element
;; that its own body returns. admit.c sym_atoms (l.776) collects every symbol that names a Map, so the element
;; 'deadline' inside Map 'deadline' is read as a self-call -> "map-call cycle deadline -> deadline" (InvalidInput).
(DC.Module P
  (Profile Crisp)
  (Carrier Press (Of Symbol) (Enum calm deadline))
  (Map show (From Press) (To Press) (Body ($x) $x))
  (Map deadline (From Press) (To Press) (Body ($x) deadline))
  (Machine M (States Press) (Observe show show) (Action push deadline))
  (BlockPartition Part (On Press)
    (Block All (Body ($x) True) calm)
    (Successor push All All)))

!(dc.run P (CheckBlockPartition Part (Of M)))
