; M1 acceptance 4 (CeTTa lane): a host equation with a side effect is defined
; here; the module source and the request are data, so it must never run.
(= (evil $x) (println! "HELD-DECLARATION-RAN"))
!(import! &self dcalc)
!(dcalc:run "(DC.Module H (Profile Crisp) (Carrier Bit (Of Nat) (Enum 0 1)) (Map f (From Bit) (To Bit) (Body ($x) (evil $x))) (Machine M (States Bit) (Observe value f) (Action stay f)) (Representation R (Of M) (Encode f)))" H (MeasureNow R))
!(dcalc:run "(DC.Module C (Profile Crisp) (Carrier Bit (Of Nat) (Enum 0 1)) (Map id (From Bit) (To Bit) (Table (0 0) (1 1))) (Machine M (States Bit) (Observe value id) (Action stay id)) (Representation R (Of M) (Encode id)))" C (CheckUpdates (Within (evil 0))))
!(dcalc:run "(DC.Module C (Profile Crisp) (Carrier Bit (Of Nat) (Enum 0 1)) (Map id (From Bit) (To Bit) (Table (0 0) (1 1))) (Machine M (States Bit) (Observe value id) (Action stay id)) (Representation R (Of M) (Encode id)))" C (Result (Status Checked) (Claim (CheckUpdates R) (Equality Literal))))
!(dcalc:run "(DC.Module C (Profile Crisp) (Carrier Bit (Of Nat) (Enum 0 1)) (Map id (From Bit) (To Bit) (Table (0 0) (1 1))) (Machine M (States Bit) (Observe value id) (Action stay id)) (Representation R (Of M) (Encode id)))" C (CheckUpdates R))
