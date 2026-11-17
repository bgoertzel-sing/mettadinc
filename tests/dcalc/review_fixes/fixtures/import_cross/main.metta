;; Review 1 F1 (cross-file): run as dcalc main.metta lib.metta
(DC.Module Availability
  (Profile Crisp)
  (Use Hyperseed)
  (Import Lib (Only Case bias stay))
  (Type Report (Sum Missing (Observed PBit)))
  (Map report (From Case) (To Report)
    (Cases (Absent Missing) (Neither (Observed (PBit 0 0))) (Support (Observed (PBit 1 0)))
           (Oppose (Observed (PBit 0 1))) (Both (Observed (PBit 1 1)))))
  (Machine Reports (States Case) (Observe report report) (Action stay stay))
  (Representation Bias (Of Reports) (Encode bias)))
!(dc.run Availability (CheckNow Bias))
