;; M7 negative gate 1: an unavailable report (Missing) must never be silently read as neither (PBit 0 0).
;; default-zero is declared To PBit but its Absent case returns Missing; the request must be refused as stated (not Checked, not Unsupported).
(DC.Module Gate1Missing
  (Profile Crisp)
  (Use Hyperseed)
  (Type Report (Sum Missing (Observed PBit)))
  (Carrier Case (Of Symbol) (Enum Absent Neither Support Oppose Both))
  (Map report (From Case) (To Report)
    (Cases (Absent Missing) (Neither (Observed (PBit 0 0))) (Support (Observed (PBit 1 0)))
           (Oppose (Observed (PBit 0 1))) (Both (Observed (PBit 1 1)))))
  (Map default-zero (From Case) (To PBit)
    (Cases (Absent Missing) (Neither (PBit 0 0)) (Support (PBit 1 0)) (Oppose (PBit 0 1)) (Both (PBit 1 1))))
  (Map bias (From Case) (To Int)
    (Cases (Absent 0) (Neither 0) (Support 1) (Oppose -1) (Both 0)))
  (Map stay (From Case) (To Case) (Cases (Absent Absent) (Neither Neither) (Support Support) (Oppose Oppose) (Both Both)))
  (Machine Reports (States Case) (Observe report report) (Action stay stay))
  (Representation DefaultZero (Of Reports) (Encode default-zero))
  (Representation Bias (Of Reports) (Encode bias)))
!(dc.run Gate1Missing (CheckNow DefaultZero))
