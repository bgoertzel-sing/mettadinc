;; Remaining blocker for doc04 TaskResume ResumeMemory: (Derive X (MinimizeForQueries M)).
;; E1: MinimizeForQueries on a plain Enum machine with literal Cases (no a-d blocker present).
(DC.Module E1
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q r))
  (Carrier O (Of Symbol) (Enum o1 o2))
  (Map ob (From A) (To O) (Cases (p o1) (q o1) (r o2)))
  (Map step (From A) (To A) (Cases (p q) (q p) (r r)))
  (Machine M (States A) (Observe ob ob) (Action step step))
  (Derive Mem (MinimizeForQueries M)))
!(dc.run E1 Mem)
