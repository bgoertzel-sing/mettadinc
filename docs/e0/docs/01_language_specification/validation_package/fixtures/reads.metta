;; Shared and fresh reads of one nondeterministic choice.  Specification, Section 8.1.
;; @excerpt reads
(DC.Module Reads
  (Profile Nondeterministic)
  (Use Simulation)
  (Carrier Run (Of Symbol) (Enum Start R00 R01 R10 R11))
  (Carrier Truth (Of Symbol) (Enum Agree Differ Pending))
  (Map agree (From Run) (To Truth)
    (Cases (Start Pending) (R00 Agree) (R01 Differ) (R10 Differ) (R11 Agree)))
  (Map shared-read (From Run) (To Run)
    (Choice (Start R00 R11) (R00 R00) (R01 R01) (R10 R10) (R11 R11)))
  (Map fresh-read (From Run) (To Run)
    (Choice (Start R00 R01 R10 R11) (R00 R00) (R01 R01) (R10 R10) (R11 R11)))
  (Machine Shared (States Run) (Observe agree agree) (Action read shared-read) (Bag Set))
  (Machine Fresh  (States Run) (Observe agree agree) (Action read fresh-read) (Bag Set))
  (Scheduler Fair (Rule Uniform)))
;; @end
!(dc.run Reads (Outcomes Shared (From Start) (After (Do read)) (Observe agree)))
!(dc.run Reads (Outcomes Fresh (From Start) (After (Do read)) (Observe agree)))
!(dc.run Reads (OutcomeProbability Shared (From Start) (After (Do read)) (Event (Shows agree Agree)) (Scheduler Fair)))
!(dc.run Reads (OutcomeProbability Fresh (From Start) (After (Do read)) (Event (Shows agree Agree)) (Scheduler Fair)))
