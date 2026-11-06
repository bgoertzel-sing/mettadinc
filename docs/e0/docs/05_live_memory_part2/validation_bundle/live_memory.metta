;; Live memory and goals in MeTTaDinC: the modules of Part II of the implementation guide,
;; 4 November 2026.  Each module is the live counterpart of a pattern of Part I, on real
;; time, real confidence and unbounded sets of sources instead of finite models.
;; Forms marked PROPOSED need registry patches.  From ls_registry_patch.json: the
;; libraries RationalArith, BoundedSets, Statistics and Estimates, the Statistic, Store
;; and Keyed declarations, the Matching field of Simulation, the CheckStatistic,
;; EstimateRate and CompareRates requests, and For clauses over carriers that are not
;; enumerated.  From earlier patches: NatArith and Meet (Example 1); Families, Like,
;; ActionsOf, Invariant and Unrollings (Example 2); Laws, Monitors, Monitor, Stream,
;; CheckMonitor and Detect (Example 4); the Pairs field of Implementation (Part I).
;; The lines ";; @excerpt <name>" and ";; @end" delimit the excerpts printed in the guide.

;; ============================================================ 1. open items in real time
;; @excerpt live-open-items
(DC.Module LiveOpenItems
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use RationalArith Families Statistics)              ; PROPOSED libraries
  (Carrier Rat  (Of Rational) (All))
  (Carrier Flag (Of Bool) (Enum False True))
  (Map nonnegative (From Rational) (To Bool) (Body ($x) (Le 0 $x)))
  (Carrier Days (Of Rational) (Subset Rat nonnegative))
  ;; an item: (age in days, closed, days since the closing reply)
  (Carrier Raw  (Of (Tuple Rational Bool Rational)) (Product Days Flag Days))
  (Map well-formed (From (Tuple Rational Bool Rational)) (To Bool)
    (Cases ((Tuple $a $c $e) (Le $e $a))))
  (Carrier Item (Of (Tuple Rational Bool Rational)) (Subset Raw well-formed))

  ;; how an item changes, and what its users ask
  (Map wait (Parameters ($d Days)) (From Item) (To Item)
    (Cases ((Tuple $a $c $e) (Tuple (Add $a $d) $c (Add $e $d)))))
  (Map on-reply (From Item) (To Item)
    (Cases ((Tuple $a $c $e) (Tuple $a True (If $c $e 0)))))
  (Map suggest (From Item) (To Bool) (Cases ((Tuple $a $c $e) (And (Not $c) (Le $a 7)))))
  (Map open    (From Item) (To Bool) (Cases ((Tuple $a $c $e) (Not $c))))
  (Machine ItemTime (States Item) (Observe suggest suggest) (Observe open open)
    (Action (wait $d) (wait $d) (For $d Days))       ; PROPOSED For over Days
    (Action reply on-reply))
  (Machine EngineTime (States Item) (Observe suggest suggest) (ActionsOf ItemTime))

  ;; the event statistic: the age and whether the item is closed
  (Map event-stat (From Item) (To (Tuple Rational Bool))
    (Cases ((Tuple $a $c $e) (Tuple $a $c))))
  (Map event-wait (Parameters ($d Days)) (From (Tuple Rational Bool))
    (To (Tuple Rational Bool)) (Cases ((Tuple $a $c) (Tuple (Add $a $d) $c))))
  (Map event-reply (From (Tuple Rational Bool)) (To (Tuple Rational Bool))
    (Cases ((Tuple $a $c) (Tuple $a True))))
  (Map event-suggest (From (Tuple Rational Bool)) (To Bool)
    (Cases ((Tuple $a $c) (And (Not $c) (Le $a 7)))))
  (Map event-open (From (Tuple Rational Bool)) (To Bool) (Cases ((Tuple $a $c) (Not $c))))
  (Statistic EventStat (Of ItemTime) (Encode event-stat)          ; PROPOSED Statistic
    (Step (wait $d) (event-wait $d) (For $d Days)) (Step reply event-reply)
    (Read suggest event-suggest) (Read open event-open))

  ;; the coarsest statistic for both users: closed, or the age of an open item saturated
  ;; at seven days (the flag is true once the age is past seven days)
  (Map joint-stat (From Item) (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $a $c $e)
      (Tuple $c (And (Not $c) (Lt 7 $a)) (If (And (Not $c) (Le $a 7)) $a 0)))))
  (Map joint-wait (Parameters ($d Days)) (From (Tuple Bool Bool Rational))
    (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $c $t $v)
      (Tuple $c (And (Not $c) (Or $t (Lt 7 (Add $v $d))))
             (If (And (Not $c) (Not (Or $t (Lt 7 (Add $v $d))))) (Add $v $d) 0)))))
  (Map joint-reply (From (Tuple Bool Bool Rational)) (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $c $t $v) (Tuple True False 0))))
  (Map joint-suggest (From (Tuple Bool Bool Rational)) (To Bool)
    (Cases ((Tuple $c $t $v) (And (Not $c) (Not $t)))))
  (Map joint-open (From (Tuple Bool Bool Rational)) (To Bool)
    (Cases ((Tuple $c $t $v) (Not $c))))
  (Statistic JointStat (Of ItemTime) (Encode joint-stat)
    (Step (wait $d) (joint-wait $d) (For $d Days)) (Step reply joint-reply)
    (Read suggest joint-suggest) (Read open joint-open))

  ;; the coarsest statistic for the engine alone: dead (closed or past seven days), or
  ;; the age of a live item
  (Map engine-stat (From Item) (To (Tuple Bool Rational))
    (Cases ((Tuple $a $c $e) (Tuple (Or $c (Lt 7 $a)) (If (Or $c (Lt 7 $a)) 0 $a)))))
  (Map engine-wait (Parameters ($d Days)) (From (Tuple Bool Rational))
    (To (Tuple Bool Rational))
    (Cases ((Tuple $x $v)
      (Tuple (Or $x (Lt 7 (Add $v $d))) (If (Or $x (Lt 7 (Add $v $d))) 0 (Add $v $d))))))
  (Map engine-reply (From (Tuple Bool Rational)) (To (Tuple Bool Rational))
    (Cases ((Tuple $x $v) (Tuple True 0))))
  (Map engine-suggest (From (Tuple Bool Rational)) (To Bool)
    (Cases ((Tuple $x $v) (Not $x))))
  (Statistic EngineStat (Of EngineTime) (Encode engine-stat)
    (Step (wait $d) (engine-wait $d) (For $d Days)) (Step reply engine-reply)
    (Read suggest engine-suggest))

  ;; what a two-day recall window shows: the age, and whether a reply is visible
  (Map window-view (From Item) (To (Tuple Rational Bool))
    (Cases ((Tuple $a $c $e) (Tuple $a (And $c (Le $e 2))))))
  (Representation WindowView (Of EngineTime) (Encode window-view))

  ;; the store: finitely many items under identifiers; waiting moves every item at once
  (Carrier ItemId (Of Symbol) (All))
  (Store Items (Keys ItemId) (Of ItemTime) (Global wait))         ; PROPOSED Store
  (Keyed EventIndex (Of Items) (Item EventStat))                  ; PROPOSED Keyed
  (Keyed JointIndex (Of Items) (Item JointStat))
  ;; the engine's coarsest statistic indexes a view of the items, bound to suggest only
  (Keyed EngineIndex (Of Items) (Item EngineStat) (View EngineTime))   ; PROPOSED View
  ;; negative fixture: EngineStat is not a statistic of the store's item machine
  (Keyed EngineAsItems (Of Items) (Item EngineStat)))
;; @end

;; @excerpt live-open-items-requests
!(dc.run LiveOpenItems (CheckStatistic EventStat (Method Symbolic)))
!(dc.run LiveOpenItems (CheckStatistic JointStat (Method Symbolic)))
!(dc.run LiveOpenItems (CheckStatistic EngineStat (Method Symbolic)))
!(dc.run LiveOpenItems (CheckNow WindowView))
!(dc.run LiveOpenItems (CheckUpdates WindowView))
!(dc.run LiveOpenItems (CheckStatistic EventIndex (Method Lift)))
!(dc.run LiveOpenItems (CheckStatistic JointIndex (Method Lift)))
!(dc.run LiveOpenItems (CheckStatistic EngineIndex (Method Lift)))
!(dc.run LiveOpenItems (CheckStatistic EngineAsItems (Method Lift)))   ; InvalidInput
;; @end

;; ======================================================== 3. evidence from many sources
;; @excerpt live-evidence
(DC.Module LiveEvidence
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use NatArith Families BoundedSets Statistics)       ; PROPOSED BoundedSets
  (Carrier Source (Of Symbol) (All))                   ; an unbounded set of identifiers
  (Carrier Seen   (Of (FiniteSet Symbol)) (All))
  ;; the distinct supporting and the distinct contradicting sources seen so far
  (Carrier Evidence (Of (Tuple (FiniteSet Symbol) (FiniteSet Symbol)))
    (Product Seen Seen))
  (Map plus (Parameters ($s Source)) (From Evidence) (To Evidence)
    (Cases ((Tuple $p $m) (Tuple (Insert $s $p) $m))))
  (Map minus (Parameters ($s Source)) (From Evidence) (To Evidence)
    (Cases ((Tuple $p $m) (Tuple $p (Insert $s $m)))))
  (Map join (From (Tuple (Tuple (FiniteSet Symbol) (FiniteSet Symbol))
                         (Tuple (FiniteSet Symbol) (FiniteSet Symbol))))
    (To Evidence)
    (Cases ((Tuple (Tuple $p $m) (Tuple $q $n)) (Tuple (Union $p $q) (Union $m $n)))))
  (Map contra (From Evidence) (To Bool) (Cases ((Tuple $p $m) (Le 1 (Size $m)))))
  (Map eff    (From Evidence) (To Nat)  (Cases ((Tuple $p $m) (Min 2 (Size $p)))))
  (Map regen  (From Evidence) (To Bool) (Cases ((Tuple $p $m) (Le 2 (Size $m)))))
  (Machine EvidenceStream (States Evidence)
    (Observe contra contra) (Observe eff eff) (Observe regen regen)
    (Action (plus $s) (plus $s) (For $s Source))
    (Action (minus $s) (minus $s) (For $s Source))
    (Merge join join))

  ;; D_2 for each polarity: the set while it has at most one member, Many afterwards
  (Map d2-stat (From Evidence) (To (Tuple (Capped Symbol) (Capped Symbol)))
    (Cases ((Tuple $p $m) (Tuple (Cap 2 $p) (Cap 2 $m)))))
  (Map d2-plus (Parameters ($s Source)) (From (Tuple (Capped Symbol) (Capped Symbol)))
    (To (Tuple (Capped Symbol) (Capped Symbol)))
    (Cases ((Tuple $p $m) (Tuple (CapInsert 2 $s $p) $m))))
  (Map d2-minus (Parameters ($s Source)) (From (Tuple (Capped Symbol) (Capped Symbol)))
    (To (Tuple (Capped Symbol) (Capped Symbol)))
    (Cases ((Tuple $p $m) (Tuple $p (CapInsert 2 $s $m)))))
  (Map d2-join (From (Tuple (Tuple (Capped Symbol) (Capped Symbol))
                            (Tuple (Capped Symbol) (Capped Symbol))))
    (To (Tuple (Capped Symbol) (Capped Symbol)))
    (Cases ((Tuple (Tuple $p $m) (Tuple $q $n))
      (Tuple (CapUnion 2 $p $q) (CapUnion 2 $m $n)))))
  (Map d2-contra (From (Tuple (Capped Symbol) (Capped Symbol))) (To Bool)
    (Cases ((Tuple $p $m) (Le 1 (CapSize 2 $m)))))
  (Map d2-eff (From (Tuple (Capped Symbol) (Capped Symbol))) (To Nat)
    (Cases ((Tuple $p $m) (CapSize 2 $p))))
  (Map d2-regen (From (Tuple (Capped Symbol) (Capped Symbol))) (To Bool)
    (Cases ((Tuple $p $m) (Le 2 (CapSize 2 $m)))))
  (Statistic FirstOrMore (Of EvidenceStream) (Encode d2-stat)
    (Step (plus $s) (d2-plus $s) (For $s Source))
    (Step (minus $s) (d2-minus $s) (For $s Source))
    (MergeStep join d2-join)
    (Read contra d2-contra) (Read eff d2-eff) (Read regen d2-regen)))
;; @end

;; @excerpt live-evidence-requests
!(dc.run LiveEvidence (CheckStatistic FirstOrMore (Method Symbolic)))
;; @end

;; ============================================================ 5. goals on real ages
;; @excerpt live-goals
(DC.Module LiveGoals
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use RationalArith Families Statistics)
  (Carrier Rat  (Of Rational) (All))
  (Carrier Flag (Of Bool) (Enum False True))
  (Carrier Who  (Of Symbol) (Enum ben andy))
  (Map nonnegative (From Rational) (To Bool) (Body ($x) (Le 0 $x)))
  (Carrier Days (Of Rational) (Subset Rat nonnegative))
  ;; a record: (open, age in days, addressee)
  (Carrier Record (Of (Tuple Bool Rational Symbol)) (Product Flag Days Who))
  (Map wait (Parameters ($d Days)) (From Record) (To Record)
    (Cases ((Tuple $o $a $w) (Tuple $o (Add $a $d) $w))))
  (Map close (From Record) (To Record) (Cases ((Tuple $o $a $w) (Tuple False $a $w))))

  ;; the nag goal and three proposed changes, each an observer on the record
  (Map nag (From Record) (To Bool) (Cases ((Tuple $o $a $w) (And $o (Le $a 2)))))
  (Map nag-days-left (From Record) (To (Tuple Bool Rational))
    (Cases ((Tuple $o $a $w) (Tuple (And $o (Le $a 2)) (If $o (Max 0 (Sub 2 $a)) 0)))))
  (Map nag-ben-first (From Record) (To (Tuple Bool Bool))
    (Cases ((Tuple $o $a $w) (Tuple (And $o (Le $a 2)) (And $o (Le $a 2) (Eq $w ben))))))
  (Map nag-cap3 (From Record) (To Bool) (Cases ((Tuple $o $a $w) (And $o (Le $a 3)))))
  (Machine Nag (States Record) (Observe nag nag)
    (Action (wait $d) (wait $d) (For $d Days)) (Action close close))
  (Machine DaysGoal     (States Record) (Observe days nag-days-left) (ActionsOf Nag))
  (Machine BenFirstGoal (States Record) (Observe first nag-ben-first) (ActionsOf Nag))
  (Machine Cap3Goal     (States Record) (Observe nag3 nag-cap3)       (ActionsOf Nag))
  (Machine BothNags (States Record) (Observe nag nag) (Observe nag3 nag-cap3)
    (ActionsOf Nag))
  (Representation DaysLeft       (Of Nag)          (Encode nag-days-left))
  (Representation BenFirst       (Of Nag)          (Encode nag-ben-first))
  (Representation Cap3           (Of Nag)          (Encode nag-cap3))
  (Representation NagForDays     (Of DaysGoal)     (Encode nag))
  (Representation NagForBenFirst (Of BenFirstGoal) (Encode nag))
  (Representation NagForCap3     (Of Cap3Goal)     (Encode nag))

  ;; the age saturated at two days, with the open flag: the coarsest statistic of the nag
  ;; goal that keeps the flag (the goal alone could merge closed records with open records
  ;; past two days, as EngineStat of LiveOpenItems does)
  (Map sat2 (From Record) (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $a $w)
      (Tuple $o (And $o (Lt 2 $a)) (If (And $o (Le $a 2)) $a 0)))))
  (Map sat2-wait (Parameters ($d Days)) (From (Tuple Bool Bool Rational))
    (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $t $v)
      (Tuple $o (And $o (Or $t (Lt 2 (Add $v $d))))
             (If (And $o (Not (Or $t (Lt 2 (Add $v $d))))) (Add $v $d) 0)))))
  (Map sat-close (From (Tuple Bool Bool Rational)) (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $t $v) (Tuple False False 0))))
  (Map sat-live (From (Tuple Bool Bool Rational)) (To Bool)
    (Cases ((Tuple $o $t $v) (And $o (Not $t)))))
  (Statistic SaturateAtTwo (Of Nag) (Encode sat2)
    (Step (wait $d) (sat2-wait $d) (For $d Days)) (Step close sat-close)
    (Read nag sat-live))
  (Representation TwoForBoth (Of BothNags) (Encode sat2))

  ;; with the three-day goal added, the statistic must saturate at three days
  (Map sat3 (From Record) (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $a $w)
      (Tuple $o (And $o (Lt 3 $a)) (If (And $o (Le $a 3)) $a 0)))))
  (Map sat3-wait (Parameters ($d Days)) (From (Tuple Bool Bool Rational))
    (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $t $v)
      (Tuple $o (And $o (Or $t (Lt 3 (Add $v $d))))
             (If (And $o (Not (Or $t (Lt 3 (Add $v $d))))) (Add $v $d) 0)))))
  (Map sat3-nag (From (Tuple Bool Bool Rational)) (To Bool)
    (Cases ((Tuple $o $t $v) (And $o (Not $t) (Le $v 2)))))
  (Statistic SaturateAtThree (Of BothNags) (Encode sat3)
    (Step (wait $d) (sat3-wait $d) (For $d Days)) (Step close sat-close)
    (Read nag sat3-nag) (Read nag3 sat-live))

  ;; a schema migration: store whether the follow-up window has expired and the days left
  (Map to-deadline (From Record) (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $a $w) (Tuple $o (Lt 2 $a) (If (Lt 2 $a) 0 (Sub 2 $a))))))
  (Map deadline-wait (Parameters ($d Days)) (From (Tuple Bool Bool Rational))
    (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $x $l)
      (Tuple $o (Or $x (Lt (Sub $l $d) 0))
             (If (Or $x (Lt (Sub $l $d) 0)) 0 (Sub $l $d))))))
  (Map deadline-close (From (Tuple Bool Bool Rational)) (To (Tuple Bool Bool Rational))
    (Cases ((Tuple $o $x $l) (Tuple False $x $l))))
  (Map deadline-nag (From (Tuple Bool Bool Rational)) (To Bool)
    (Cases ((Tuple $o $x $l) (And $o (Not $x)))))
  (Statistic Deadline (Of Nag) (Encode to-deadline)
    (Step (wait $d) (deadline-wait $d) (For $d Days)) (Step close deadline-close)
    (Read nag deadline-nag)))
;; @end

;; @excerpt live-goals-requests
!(dc.run LiveGoals (CheckNow DaysLeft))
!(dc.run LiveGoals (CheckNow NagForDays))
!(dc.run LiveGoals (CheckNow BenFirst))
!(dc.run LiveGoals (CheckNow NagForBenFirst))
!(dc.run LiveGoals (CheckNow Cap3))
!(dc.run LiveGoals (CheckNow NagForCap3))
!(dc.run LiveGoals (CheckStatistic SaturateAtTwo (Method Symbolic)))
!(dc.run LiveGoals (CheckNow TwoForBoth))
!(dc.run LiveGoals (CheckStatistic SaturateAtThree (Method Symbolic)))
!(dc.run LiveGoals (CheckStatistic Deadline (Method Symbolic)))
;; @end

;; ======================================================== 6. arbitration on real values
;; @excerpt live-arbitration
(DC.Module LiveArbitration
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use RationalArith Families Simulation)
  (Import ClaimArbitration (Only Weighted NormFirst))  ; the finite model of Part I
  (Carrier Rat  (Of Rational) (All))
  (Carrier Flag (Of Bool) (Enum False True))
  (Map unit (From Rational) (To Bool) (Body ($x) (And (Le 0 $x) (Le $x 1))))
  (Carrier Unit (Of Rational) (Subset Rat unit))
  ;; (confidence, independently checked, consolidated, deadline pressure)
  (Carrier Claim (Of (Tuple Rational Bool Bool Rational)) (Product Unit Flag Flag Unit))
  (Const live-start Claim (Tuple 0 False False 0))
  (Map evidence (Parameters ($l Unit)) (From Claim) (To Claim)
    (Cases ((Tuple $c $k $d $p) (Tuple (Add $c (Mul $l (Sub 1 $c))) $k $d $p))))
  (Map pressure (Parameters ($l Unit)) (From Claim) (To Claim)
    (Cases ((Tuple $c $k $d $p) (Tuple $c $k $d (Min 1 (Add $p $l))))))

  ;; the goals read the real values through two thresholds
  (Map confident (From Rational) (To Bool) (Body ($c) (Le (Rat 4 5) $c)))
  (Map pressing  (From Rational) (To Bool) (Body ($p) (Le (Rat 1 2) $p)))
  (Map throughput (From Claim) (To Symbol)
    (Cases ((Tuple $c $k $d $p)
      (If $d none (If (Or (confident $c) (pressing $p)) consolidate none)))))
  (Map verify-first (From Claim) (To Symbol)
    (Cases ((Tuple $c $k $d $p)
      (If $d none (If (Not $k) verify (If (confident $c) consolidate hold))))))
  (Map forbidden (From (Tuple (Tuple Rational Bool Bool Rational) Symbol)) (To Bool)
    (Cases ((Tuple (Tuple $c $k $d $p) $m) (And (Eq $m consolidate) (Not $k)))))
  (Map weighted (From Claim) (To Symbol)
    (Body ($x) (If (Not (Eq (throughput $x) none)) (throughput $x)
                 (If (Not (Eq (verify-first $x) none)) (verify-first $x) hold))))
  (Map permitted (From (Tuple (Tuple Rational Bool Bool Rational) Symbol)) (To Bool)
    (Cases ((Tuple $x $m) (And (Not (Eq $m none)) (Not (forbidden (Tuple $x $m)))))))
  (Map norm-first (From Claim) (To Symbol)
    (Body ($x) (If (permitted (Tuple $x (throughput $x))) (throughput $x)
                 (If (permitted (Tuple $x (verify-first $x))) (verify-first $x) hold))))
  (Map apply-move (From (Tuple (Tuple Rational Bool Bool Rational) Symbol)) (To Claim)
    (Cases ((Tuple (Tuple $c $k $d $p) $m)
      (Tuple $c (Or $k (Eq $m verify)) (Or $d (Eq $m consolidate)) $p))))
  (Map act-weighted   (From Claim) (To Claim)
    (Body ($x) (apply-move (Tuple $x (weighted $x)))))
  (Map act-norm-first (From Claim) (To Claim)
    (Body ($x) (apply-move (Tuple $x (norm-first $x)))))
  (Map unlawful-weighted   (From Claim) (To Bool)
    (Body ($x) (forbidden (Tuple $x (weighted $x)))))
  (Map unlawful-norm-first (From Claim) (To Bool)
    (Body ($x) (forbidden (Tuple $x (norm-first $x)))))
  (Machine RealWeighted (States Claim) (Observe unlawful unlawful-weighted)
    (Action (evidence $l) (evidence $l) (For $l Unit))
    (Action (deadline $l) (pressure $l) (For $l Unit))
    (Action act act-weighted))
  (Machine RealNormFirst (States Claim) (Observe unlawful unlawful-norm-first)
    (Action (evidence $l) (evidence $l) (For $l Unit))
    (Action (deadline $l) (pressure $l) (For $l Unit))
    (Action act act-norm-first))

  ;; the class map onto Part I's claims, and the two simulations up to stuttering
  (Map classes (From Claim) (To (Tuple Symbol Bool Bool Symbol))
    (Cases ((Tuple $c $k $d $p)
      (Tuple (If (confident $c) high low) $k $d (If (pressing $p) deadline calm)))))
  (Simulation StutterWeighted (Source RealWeighted) (Target Weighted)
    (Relation classes) (Matching Stutter))                        ; PROPOSED Matching
  (Simulation StutterNormFirst (Source RealNormFirst) (Target NormFirst)
    (Relation classes) (Matching Stutter)))
;; @end

;; @excerpt live-arbitration-requests
!(dc.run LiveArbitration (CheckSimulation StutterWeighted))
!(dc.run LiveArbitration (CheckSimulation StutterNormFirst))
!(dc.run LiveArbitration
   (CheckSafety NormFirst (Never (Shows unlawful True)) (Via StutterNormFirst)
                (Init live-start)))
!(dc.run LiveArbitration
   (CheckSafety Weighted (Never (Shows unlawful True)) (Via StutterWeighted)
                (Init live-start)))
;; negative fixture: StutterWeighted relates RealWeighted to Weighted, so the safety of
;; NormFirst says nothing about RealWeighted (InvalidInput)
!(dc.run LiveArbitration
   (CheckSafety NormFirst (Never (Shows unlawful True)) (Via StutterWeighted)
                (Init live-start)))
;; @end

;; ============================================================ 7. MetaMo on real values
;; @excerpt live-motivation
(DC.Module LiveMotivation
  (Profile (Dynamics Deterministic) (Values Lukasiewicz) (Carriers Symbolic))
  (Use RationalArith NatArith Families Contracts)
  (Carrier Rat (Of Rational) (All))
  (Map unit   (From Rational) (To Bool) (Body ($x) (And (Le 0 $x) (Le $x 1))))
  (Map weight (From Rational) (To Bool) (Body ($x) (And (Le (Rat 1 4) $x) (Le $x 1))))
  (Map bit    (From Rational) (To Bool) (Body ($x) (Or (Eq $x 0) (Eq $x 1))))
  (Carrier Unit   (Of Rational) (Subset Rat unit))
  (Carrier Weight (Of Rational) (Subset Rat weight))
  (Carrier Bit    (Of Rational) (Subset Rat bit))
  (Carrier Variant (Of Symbol) (Enum plain floor))
  ;; (individuation, exploration, arousal, securing, novelty, risk)
  (Carrier Motive (Of (Tuple Rational Rational Rational Rational Rational Rational))
    (Product Weight Unit Unit Unit Bit Bit))
  (Const start Motive (Tuple (Rat 3 4) (Rat 1 2) (Rat 1 2) (Rat 1 2) 0 0))

  ;; appraisal updates the modulators; decision updates the goal weights
  (Map appraise (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho)
      (Tuple $gi $g1 (Div (Add $nu $g1) 2) (Div (Add $rho $gi) 2) $nu $rho))))
  (Map clip (From Rational) (To Rational) (Body ($v) (Max 0 (Min 1 $v))))
  (Map decide (Parameters ($v Variant)) (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho)
      (Tuple
        (If (And (Le (Rat 3 4) $a) (Le (Rat 3 4) $g1))
            (Switch $v
              (plain (Max (Rat 1 4) (Sub $gi (Rat 1 4))))
              (floor (Max (If (Le (Rat 1 2) $gi) (Rat 1 2) (Rat 1 4))
                          (Sub $gi (Rat 1 4)))))
            (If (Le (Rat 3 4) $c) (Min 1 (Add $gi (Rat 1 4))) $gi))
        (clip (Add $g1 (Div (Sub $a $c) 2)))
        $a $c $nu $rho))))
  (Map cycle-plain   (From Motive) (To Motive) (Body ($x) (decide plain (appraise $x))))
  (Map cycle-floor   (From Motive) (To Motive) (Body ($x) (decide floor (appraise $x))))
  (Map swapped-floor (From Motive) (To Motive) (Body ($x) (appraise (decide floor $x))))
  (Map set-stimulus (Parameters ($n Bit) ($r Bit)) (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Tuple $gi $g1 $a $c $n $r))))
  (Map gi-of (From Motive) (To Rational) (Cases ((Tuple $gi $g1 $a $c $nu $rho) $gi)))
  (Map below (From Motive) (To Bool) (Body ($x) (Lt (gi-of $x) (Rat 1 2))))
  (Map safe-region (From Motive) (To Bool) (Body ($x) (Le (Rat 1 2) (gi-of $x))))

  ;; the safe region: individuation at least one half, from the start, under any stimuli
  (Machine PlainMotive (States Motive) (Observe below below) (Action cycle cycle-plain)
    (Action (stimulus $n $r) (set-stimulus $n $r) (For $n Bit) (For $r Bit)))
  (Machine FloorMotive (States Motive) (Observe below below) (Action cycle cycle-floor)
    (Action (stimulus $n $r) (set-stimulus $n $r) (For $n Bit) (For $r Bit)))
  (Carrier ReachPlain (Of (Tuple Rational Rational Rational Rational Rational Rational))
    (Reach PlainMotive (From start)))
  (Carrier ReachFloor (Of (Tuple Rational Rational Rational Rational Rational Rational))
    (Reach FloorMotive (From start)))
  (Machine PlainWatch (States ReachPlain) (Like PlainMotive))
  (Machine FloorWatch (States ReachFloor) (Like FloorMotive))
  (BlockPartition SafePlain (On ReachPlain)
    (Block Safe (Body ($x) (Not (below $x))) start) (Successor Any Safe Safe)
    (Invariant safe-region))
  (BlockPartition SafeFloor (On ReachFloor)
    (Block Safe (Body ($x) (Not (below $x))) start) (Successor Any Safe Safe)
    (Invariant safe-region))

  ;; appraisal and decision in either order, compared on the goal weights of one state
  (Map gi-real  (From Motive) (To Rational01) (Cases ((Tuple $i $g $a $c $n $r) $i)))
  (Map g1-real  (From Motive) (To Rational01) (Cases ((Tuple $i $g $a $c $n $r) $g)))
  (Map a-real   (From Motive) (To Rational01) (Cases ((Tuple $i $g $a $c $n $r) $a)))
  (Map c-real   (From Motive) (To Rational01) (Cases ((Tuple $i $g $a $c $n $r) $c)))
  (Map nu-real  (From Motive) (To Rational01) (Cases ((Tuple $i $g $a $c $n $r) $n)))
  (Map rho-real (From Motive) (To Rational01) (Cases ((Tuple $i $g $a $c $n $r) $r)))
  (Tolerance Dist01 (On Rational01) (OneMinusAbsoluteDifference))
  (Tolerance Sup (On Motive)
    (Meet (Pullback gi-real Dist01) (Pullback g1-real Dist01) (Pullback a-real Dist01)
          (Pullback c-real Dist01) (Pullback nu-real Dist01) (Pullback rho-real Dist01)))
  (Tolerance GoalSup (On Motive)
    (Meet (Pullback gi-real Dist01) (Pullback g1-real Dist01)))
  (Map same-state
    (From (Tuple (Tuple Rational Rational Rational Rational Rational Rational)
                 (Tuple Rational Rational Rational Rational Rational Rational)))
    (To Bool) (Body ($pq) (Eq (GetTuple $pq 0) (GetTuple $pq 1))))
  (Implementation OrderSwapGoals (Ideal cycle-floor) (Actual swapped-floor)
    (Audit Motive) (InputDistance Sup) (OutputDistance GoalSup) (Pairs same-state))
  ;; on settled states, where appraisal changes nothing, the two orders agree
  (Map settled (From Motive) (To Bool) (Body ($x) (Eq (appraise $x) $x)))
  (Carrier Settled (Of (Tuple Rational Rational Rational Rational Rational Rational))
    (Subset Motive settled))
  (Implementation OrderSwapSettled (Ideal cycle-floor) (Actual swapped-floor)
    (Audit Settled) (InputDistance Sup) (OutputDistance GoalSup) (Pairs same-state)))
;; @end

;; @excerpt live-motivation-requests
!(dc.run LiveMotivation
   (CheckBlockPartition SafePlain (Of PlainWatch) (Budget (Unrollings 8))))
!(dc.run LiveMotivation (CheckBlockPartition SafeFloor (Of FloorWatch)))
!(dc.run LiveMotivation (CheckImplementation OrderSwapGoals (Grade 1 (Rat 9 10))))
!(dc.run LiveMotivation (CheckImplementation OrderSwapGoals (Grade 1 (Rat 4 5))))
!(dc.run LiveMotivation (CheckImplementation OrderSwapSettled (Grade 1 0)))
;; @end

;; ==================================================== 2 and 8. receipts and monitors
;; @excerpt live-receipts
(DC.Module LiveReceipts
  (Profile Stochastic)
  (Use Decisions Laws Families Monitors Estimates)     ; PROPOSED Estimates
  (Stream ContextReceipts (Source "streams/context_receipts_seed2.json")
    (Digest "sha256:71b78af0105a000962267564e4ecf181ff696b2d227523e37b7dfd3011491019")
    (Provenance "simulated: 2,000 snapshots of 60 items, budget 1,500 tokens, seed 2")
    (Population "context blocks built for the simulated workload")
    (Selection "one row per snapshot, written when its block is built")
    (Policy "the budgeted block builder of Pattern 2, simulation p2_live, seed 2"))
  (Stream LiveSuggestions (Source "streams/stale_alt_seed1.json")
    (Digest "sha256:f0d4be8461a2904e728f7b0a8ad895385ccd56f340ec854d729936aaf6a48763")
    (Provenance "simulated: stale with probability 1/5, 400 suggestions, seed 1")
    (Population "suggestions of Part I's alternative engine")
    (Selection "one row per suggestion, written when it is made")
    (Policy "Part I's alternative engine, simulated, seed 1"))
  (Stream TenPercent (Source "streams/stale_ten_seed1.json")
    (Digest "sha256:d1c692b4962de6113c041d046f012d93348fb1779dcbfa99d94f713356608dcc")
    (Provenance "simulated: stale with probability 1/10, 2,000 suggestions, seed 1")
    (Population "suggestions of a simulated engine")
    (Selection "one row per suggestion, written when it is made")
    (Policy "a simulated engine, stale with probability 1/10, seed 1"))
  ;; three alternatives for the stale-suggestion monitor; the accepted rate is 1/20
  (Carrier One  (Of Symbol) (Enum one))
  (Carrier Rate (Of Symbol) (Enum accepted tenth fifth twofifths))
  (Map stale-rate (From Rate) (To Rational01)
    (Table (accepted (Rat 1 20)) (tenth (Rat 1 10)) (fifth (Rat 1 5))
           (twofifths (Rat 2 5))))
  (Map stale (Parameters ($r Rate)) (From One) (To (Law Nat))
    (Body ($u) (Coin (stale-rate $r))))
  (Monitor StaleTenth (Context One) (Null (stale accepted)) (Alternative (stale tenth))
    (Columns (observation "stale")))
  (Monitor StaleFifth (Context One) (Null (stale accepted)) (Alternative (stale fifth))
    (Columns (observation "stale")))
  (Monitor StaleTwoFifths (Context One) (Null (stale accepted))
    (Alternative (stale twofifths)) (Columns (observation "stale"))))
;; @end

;; @excerpt live-receipts-requests
!(dc.run LiveReceipts
   (EstimateRate (On ContextReceipts) (Column "relevance_A") (Equals 0)
                 (Level (Rat 1 100))))
!(dc.run LiveReceipts
   (EstimateRate (On ContextReceipts) (Column "consumer_A") (Equals 0)
                 (Level (Rat 1 100))))
!(dc.run LiveReceipts
   (CompareRates (On ContextReceipts) (First "relevance_A") (Second "consumer_A")
                 (Equals 0) (Level (Rat 1 100))))
!(dc.run LiveReceipts
   (EstimateRate (On LiveSuggestions) (Column "stale") (Equals 1) (Level (Rat 1 100))))
!(dc.run LiveReceipts (CheckMonitor StaleFifth))
!(dc.run LiveReceipts (Detect StaleFifth (On TenPercent) (Level (Rat 1 100))))
!(dc.run LiveReceipts
   (Detect StaleTenth StaleFifth StaleTwoFifths (On TenPercent) (Level (Rat 1 100))
           (Combine Mixture)))
;; @end
