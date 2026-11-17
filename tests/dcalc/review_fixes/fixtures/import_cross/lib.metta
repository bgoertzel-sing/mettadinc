;; Review 1 F1 (cross-file): Lib declares a duplicate-row Cases map; importers must be refused too.
(DC.Module Lib
  (Profile Crisp)
  (Carrier Case (Of Symbol) (Enum Absent Neither Support Oppose Both))
  (Map bias (From Case) (To Int)
    (Cases (Absent 0) (Absent 5) (Neither 0) (Support 1) (Oppose -1) (Both 0)))
  (Map stay (From Case) (To Case) (Cases (Absent Absent) (Neither Neither) (Support Support) (Oppose Oppose) (Both Both))))
