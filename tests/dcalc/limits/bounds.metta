;; Review 4 F3: Within must be a finite non-negative number.
(DC.Module Bounds
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0) (1 1)))
  (Machine M (States Bit) (Observe value id) (Action stay id))
  (Representation R (Of M) (Encode id)))
!(dc.run Bounds (CheckUpdates R (Within nan)))
!(dc.run Bounds (CheckUpdates R (Within inf)))
!(dc.run Bounds (CheckUpdates R (Within -inf)))
!(dc.run Bounds (CheckUpdates R (Within 1e999)))
!(dc.run Bounds (CheckUpdates R (Within -1)))
!(dc.run Bounds (CheckUpdates R (Within 0)))
;; Hex bounds: not a registry rat01, so M1 admission answers InvalidInput.
!(dc.run Bounds (CheckUpdates R (Within 0x0)))
!(dc.run Bounds (CheckUpdates R (Within 0x1p-1074)))
