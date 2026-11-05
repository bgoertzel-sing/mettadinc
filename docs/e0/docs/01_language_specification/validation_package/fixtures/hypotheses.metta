;; Counterexamples behind theorem hypotheses: observer equality, restriction,
;; horizon indexing, staged quotients, descent converse, literal congruence of
;; code fibers, witness length, surjectivity and simulation scope.
;; Specification, Sections 3-5 and 8.
;; @excerpt observer-equality
(DC.Module ObserverEquality
  (Profile Graded)
  (Carrier Two   (Of Symbol) (Enum a b))
  (Carrier Color (Of Symbol) (Enum red blue))
  (Carrier One   (Of Symbol) (Enum c))
  (Map color    (From Two) (To Color) (Cases (a red) (b blue)))
  (Map stay     (From Two) (To Two)   (Cases (a a) (b b)))
  (Map constant (From Two) (To One)   (Cases (a c) (b c)))
  (Tolerance Blind (On Color) (Trivial))
  (Tolerance Sharp (On Color) (Discrete))
  (Machine BlindView (States Two) (Observe color color (Values Blind)) (Action stay stay))
  (Machine SharpView (States Two) (Observe color color (Values Sharp)) (Action stay stay))
  (Representation BlindConstant (Of BlindView) (Encode constant))
  (Representation SharpConstant (Of SharpView) (Encode constant))
  (Carrier OnlyA (Of Symbol) (Reach SharpView (From a)))
  (Machine SharpViewA (States OnlyA) (Observe color color (Values Sharp)) (Action stay stay))
  (Representation SharpConstantA (Of SharpViewA) (Encode constant)))
;; @end
;; @excerpt observer-equality-requests
!(dc.run ObserverEquality (MeasureNow BlindConstant))
!(dc.run ObserverEquality (InduceExact BlindConstant))
!(dc.run ObserverEquality (CheckNow SharpConstant))
!(dc.run ObserverEquality (CheckNow SharpConstantA))
;; @end

;; @excerpt staged-horizon
(DC.Module Staged
  (Profile Crisp)
  (Carrier Four (Of Nat) (Enum 0 1 2 3))
  (Carrier Bit  (Of Nat) (Enum 0 1))
  (Carrier Block3 (Of Nat) (Enum 0 1 2))
  (Map last  (From Four) (To Bit)    (Table (0 0) (1 0) (2 0) (3 1)))
  (Map climb (From Four) (To Four)   (Table (0 1) (1 2) (2 3) (3 3)))
  (Map stage (From Four) (To Block3) (Table (0 0) (1 0) (2 1) (3 2)))
  (Machine Ladder (States Four) (Observe last last) (Action climb climb))
  (Representation Merge01 (Of Ladder) (Encode stage)))
!(dc.run Staged (CheckBehavioral Merge01 (Horizon (Steps 0))))
!(dc.run Staged (CheckBehavioral Merge01 (Horizon (Steps 1))))
!(dc.run Staged (CheckBehavioral Merge01 (Horizon (Steps 2))))
!(dc.run Staged (InduceExact Merge01))
;; @end

;; @excerpt descent-converse
(DC.Module DescentConverse
  (Profile Crisp)
  (Carrier Three (Of Nat) (Enum 0 1 2))
  (Carrier Unit  (Of Nat) (Enum 0))
  (Carrier Bit   (Of Nat) (Enum 0 1))
  (Map none  (From Three) (To Unit) (Table (0 0) (1 0) (2 0)))
  (Map hop   (From Three) (To Three) (Table (0 0) (1 2) (2 2)))
  (Map split (From Three) (To Bit) (Table (0 0) (1 0) (2 1)))
  (Machine M (States Three) (Observe none none) (Action hop hop))
  (Representation Q (Of M) (Encode split)))
!(dc.run DescentConverse (CheckBehavioral Q))
!(dc.run DescentConverse (CheckUpdates Q))
;; @end

;; @excerpt literal-congruence
(DC.Module LiteralCongruence
  (Profile Crisp)
  (Carrier Three (Of Nat) (Enum 0 1 2))
  (Carrier Unit  (Of Nat) (Enum 0))
  (Carrier Bit   (Of Nat) (Enum 0 1))
  (Map none  (From Three) (To Unit) (Table (0 0) (1 0) (2 0)))
  (Map hop   (From Three) (To Three) (Table (0 0) (1 2) (2 2)))
  (Map split (From Three) (To Bit) (Table (0 0) (1 0) (2 1)))
  (Tolerance AllCodes (On Bit) (Trivial))
  (Machine M (States Three) (Observe none none) (Action hop hop))
  (Representation Blurred (Of M) (Encode split) (Codes AllCodes)))
!(dc.run LiteralCongruence (MeasureNow Blurred))
!(dc.run LiteralCongruence (CheckUpdates Blurred))
!(dc.run LiteralCongruence (InduceExact Blurred))
;; @end

;; @excerpt chain-bound
(DC.Module ChainBound
  (Profile Crisp)
  (Carrier Six (Of Nat) (Enum 0 1 2 3 4 5))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map marked (From Six) (To Bit)  (Table (0 0) (1 0) (2 0) (3 0) (4 0) (5 1)))
  (Map next   (From Six) (To Six)  (Table (0 1) (1 2) (2 3) (3 4) (4 5) (5 5)))
  (Map join01 (From Six) (To Six)  (Table (0 0) (1 0) (2 2) (3 3) (4 4) (5 5)))
  (Machine Chain (States Six) (Observe marked marked) (Action next next))
  (Representation Join01 (Of Chain) (Encode join01)))
!(dc.run ChainBound (CheckBehavioral Join01))
;; @end

;; @excerpt surjectivity
(DC.Module Surjectivity
  (Profile Crisp)
  (Carrier One (Of Symbol) (Enum s))
  (Carrier Two (Of Symbol) (Enum z0 z1))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map zero  (From One) (To Bit) (Cases (s 0)))
  (Map hold  (From One) (To One) (Cases (s s)))
  (Map which (From Two) (To Bit) (Cases (z0 0) (z1 1)))
  (Map keep  (From Two) (To Two) (Cases (z0 z0) (z1 z1)))
  (Map to-z0 (From One) (To Two) (Cases (s z0)))
  (Machine Single (States One) (Observe bit zero) (Action step hold))
  (Machine Pair2  (States Two) (Observe bit which) (Action step keep))
  (AbstractionMap Embed (Source Single) (Target Pair2) (Map to-z0)))
!(dc.run Surjectivity (CheckAbstractionMap Embed))
;; @end

;; @excerpt simulation-scope
(DC.Module SimulationScope
  (Profile Nondeterministic)
  (Use Simulation)
  (Carrier CState (Of Symbol) (Enum c0 c1))
  (Carrier AState (Of Symbol) (Enum s0))
  (Carrier Flag   (Of Symbol) (Enum Bad Good))
  (Map flag   (From CState) (To Flag) (Cases (c0 Bad) (c1 Good)))
  (Map cstep  (From CState) (To CState) (Cases (c0 c1) (c1 c1)))
  (Map aflag  (From AState) (To Flag) (Cases (s0 Good)))
  (Map astep  (From AState) (To AState) (Choice (s0 s0)))
  (Machine Concrete (States CState) (Observe flag flag) (Action go cstep))
  (Machine Abstract (States AState) (Observe flag aflag) (Action go astep) (Bag Set))
  (Relation EmptyRelation (From CState) (To AState) (Pairs))
  (Simulation Empty (Source Concrete) (Target Abstract) (Relation EmptyRelation)))
!(dc.run SimulationScope (CheckSimulation Empty))
!(dc.run SimulationScope (CheckSafety Abstract (Never (Shows flag Bad)) (Via Empty) (Init c0)))
;; @end
