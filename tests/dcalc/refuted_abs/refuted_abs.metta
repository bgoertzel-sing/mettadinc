;; Review 2 finding 2: a CheckAbstractionMap that must come back Refuted with a
;; CommutationWitness that replays.  Src flips on t, Tgt does not; the identity
;; map therefore fails the action square at every state.
(DC.Module RefAbs
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id-bit (From Bit) (To Bit) (Table (0 0) (1 1)))
  (Map flip   (From Bit) (To Bit) (Table (0 1) (1 0)))
  (Machine Src (States Bit) (Observe a id-bit) (Action t flip))
  (Machine Tgt (States Bit) (Observe a id-bit) (Action t id-bit))
  (AbstractionMap Bad (Source Src) (Target Tgt) (Map id-bit)))
!(dc.run RefAbs (CheckAbstractionMap Bad))
