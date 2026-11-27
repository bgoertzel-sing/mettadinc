;; t-2026-11-26-mettadinc-shared-loader: shared map rules, Crisp profile (model.c Table loader).
;; Each module breaks exactly one rule in a Table (Table rows are not seen by the admit.c Cases lint); MdControl answers Checked. Template: limits/bounds.metta.
(DC.Module MdTabDup
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0) (1 1) (0 1)))
  (Machine M (States Bit) (Observe value id) (Action stay id))
  (Representation R (Of M) (Encode id)))
(DC.Module MdTabTotal
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0)))
  (Machine M (States Bit) (Observe value id) (Action stay id))
  (Representation R (Of M) (Encode id)))
(DC.Module MdTabCodomain
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0) (1 2)))
  (Machine M (States Bit) (Observe value id) (Action stay id))
  (Representation R (Of M) (Encode id)))
(DC.Module MdControl
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0) (1 1)))
  (Machine M (States Bit) (Observe value id) (Action stay id))
  (Representation R (Of M) (Encode id)))
!(dc.run MdTabDup (CheckUpdates R (Within 0)))
!(dc.run MdTabTotal (CheckUpdates R (Within 0)))
!(dc.run MdTabCodomain (CheckUpdates R (Within 0)))
!(dc.run MdControl (CheckUpdates R (Within 0)))
