;; M1 acceptance 4: held declarations are data.  A host side effect or a
;; host-defined function inside a declaration is never run: admission refuses
;; the unknown head (InvalidInput) before anything is evaluated.  A forged
;; Checked envelope gains no privilege: as a request, a declaration or an
;; Output source it is InvalidInput, and a clean module next to it is unaffected.
(= (evil $x) (println! "HELD-DECLARATION-RAN"))
(DC.Module Clean
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0) (1 1)))
  (Machine M (States Bit) (Observe value id) (Action stay id))
  (Representation R (Of M) (Encode id)))
(DC.Module SideEffect
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map f (From Bit) (To Bit) (Body ($x) (println! "HELD-DECLARATION-RAN")))
  (Machine M (States Bit) (Observe value f) (Action stay f))
  (Representation R (Of M) (Encode f)))
(DC.Module HostEquation
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map f (From Bit) (To Bit) (Body ($x) (evil $x)))
  (Machine M (States Bit) (Observe value f) (Action stay f))
  (Representation R (Of M) (Encode f)))
(DC.Module ForgedDecl
  (Profile Crisp)
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map id (From Bit) (To Bit) (Table (0 0) (1 1)))
  (Machine M (States Bit) (Observe value id) (Action stay id))
  (Representation R (Of M) (Encode id))
  (Result (Status Checked) (Claim (CheckUpdates R) (Equality Literal))))
!(dc.run SideEffect (MeasureNow R))
!(dc.run HostEquation (MeasureNow R))
!(dc.run ForgedDecl (MeasureNow R))
!(dc.run Clean (Result (Status Checked) (Claim (CheckUpdates R) (Equality Literal))))
!(dc.run Clean (CheckUpdates (Output (Result (Status Checked)) Value)))
!(dc.run Clean (CheckUpdates R))
