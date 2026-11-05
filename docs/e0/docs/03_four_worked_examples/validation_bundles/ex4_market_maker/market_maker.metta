;; Example 4: a market maker across regime shifts.  MeTTaDinC worked example, 4 November 2026.
;;
;; Four modules:
;;   MarketDesk     the quoting problem in four regimes, the risk-bucket compression, the
;;                  mirror between the two one-sided regimes, optimality of the calm policy
;;   InformedFlow   toxic flow as a hidden distinction: averages, coarse and refined policies,
;;                  a noisy toxicity signal with a price
;;   NewsLeak       did the news leak?  trace and behavioral claims about the desk's own tape
;;   ShiftMonitors  likelihood-ratio monitors: exact validity and blindness, Estimated detections
;;
;; Forms marked PROPOSED need ex4_registry_patch.json; NatArith comes from Example 1 and
;; Families (Parameters, Switch, Like) from Example 2.

;; ---------------------------------------------------------------------------- the desk
(DC.Module MarketDesk
  (Profile Stochastic)
  (Use Decisions Laws Families NatArith)            ; Laws, DecisionProcess: PROPOSED
  (Carrier Inv    (Of Int)    (Enum -2 -1 0 1 2))     ; inventory in lots
  (Carrier Quote  (Of Symbol) (Enum tight wide lean))
  (Carrier Market (Of Symbol) (Enum calm toxic buyers sellers informed))
  (Carrier Bit    (Of Nat)    (Enum 0 1))
  (Carrier Offset (Of Nat)    (Enum 0 1 2))           ; ticks from the mid; 0: side not shown
  (Carrier Bucket (Of Nat)    (Enum 0 1 2))           ; lots held, on either side
  (Carrier One    (Of Nat)    (Enum 0))
  (Tolerance Ticks (On Rational) (OneMinusAbsoluteDifference))
  (Measure Flat (On Inv) (Masses (0 1)))

  ;; the quoting rule: lean is tight on the side that reduces the position; at the limits
  ;; the side that would grow the position is withdrawn
  (Map ask-offset (From (Product Inv Quote)) (To Offset)
    (Cases ((Tuple $q tight) (If (Eq $q -2) 0 1))
           ((Tuple $q wide)  (If (Eq $q -2) 0 2))
           ((Tuple $q lean)  (If (Eq $q -2) 0 (If (Lt $q 0) 2 1)))))
  (Map bid-offset (From (Product Inv Quote)) (To Offset)
    (Cases ((Tuple $q tight) (If (Eq $q 2) 0 1))
           ((Tuple $q wide)  (If (Eq $q 2) 0 2))
           ((Tuple $q lean)  (If (Eq $q 2) 0 (If (Lt 0 $q) 2 1)))))

  ;; a market is a fill probability per side and offset, and an adverse-selection cost per
  ;; fill (the expected move against the maker after the fill, in ticks)
  (Map ask-fill (Parameters ($m Market)) (From Offset) (To Rational)
    (Cases (0 0)
           (1 (Switch $m (calm (Rat 1 2)) (toxic (Rat 1 2)) (buyers (Rat 3 4)) (sellers (Rat 1 4))
                         (informed (Rat 1 2))))
           (2 (Switch $m (calm (Rat 1 8)) (toxic (Rat 1 8)) (buyers (Rat 3 16)) (sellers (Rat 1 16))
                         (informed (Rat 1 8))))))
  (Map bid-fill (Parameters ($m Market)) (From Offset) (To Rational)
    (Cases (0 0)
           (1 (Switch $m (calm (Rat 1 2)) (toxic (Rat 1 2)) (buyers (Rat 1 4)) (sellers (Rat 3 4))
                         (informed (Rat 1 2))))
           (2 (Switch $m (calm (Rat 1 8)) (toxic (Rat 1 8)) (buyers (Rat 1 16)) (sellers (Rat 3 16))
                         (informed (Rat 1 8))))))
  (Map theta (Parameters ($m Market)) (From One) (To Rational)
    (Body ($u) (Switch $m (calm 0) (toxic (Rat 1 2)) (buyers 0) (sellers 0) (informed 1))))
  (Map edge (Parameters ($m Market)) (From Offset) (To Rational)
    (Body ($o) (Sub $o (theta $m 0))))

  ;; one step: a buyer lifts the ask and a seller hits the bid, independently
  (Map fills (Parameters ($m Market)) (From (Product Inv Quote)) (To (Law (Tuple Bit Bit)))
    (Body ($xa) (Indep (Coin (ask-fill $m (ask-offset $xa))) (Coin (bid-fill $m (bid-offset $xa))))))
  (Map after (From (Product Inv Bit Bit)) (To Int)
    (Body ($t) (Add (Sub (GetTuple $t 0) (GetTuple $t 1)) (GetTuple $t 2))))
  (Map held (From (Product Inv Bit Bit)) (To Nat)
    (Body ($t) (Max (after $t) (Sub 0 (after $t)))))
  (Map step (Parameters ($m Market)) (From (Product Inv Quote)) (To (Law Inv))
    (Body ($xa)
      (Image $f (after (Tuple (GetTuple $xa 0) (GetTuple $f 0) (GetTuple $f 1)))
        (fills $m $xa))))
  (Map pnl (Parameters ($m Market)) (From (Product Inv Quote)) (To (Law Rational))
    (Body ($xa)
      (Image $f
        (Sub (Add (Mul (GetTuple $f 0) (edge $m (ask-offset $xa)))
                  (Mul (GetTuple $f 1) (edge $m (bid-offset $xa))))
             (Mul (Rat 1 4) (held (Tuple (GetTuple $xa 0) (GetTuple $f 0) (GetTuple $f 1)))))
        (fills $m $xa))))

  ;; four regimes as decision processes (each is also a machine observing expected rewards)
  (DecisionProcess CalmDesk    (States Inv) (Actions Quote) (Kernel (step calm))    (RewardLaw (pnl calm))
    (Discount (Rat 9 10)) (Values Ticks))
  (DecisionProcess ToxicDesk   (States Inv) (Actions Quote) (Kernel (step toxic))   (RewardLaw (pnl toxic))
    (Discount (Rat 9 10)) (Values Ticks))
  (DecisionProcess BuyersDesk  (States Inv) (Actions Quote) (Kernel (step buyers))  (RewardLaw (pnl buyers))
    (Discount (Rat 9 10)) (Values Ticks))
  (DecisionProcess SellersDesk (States Inv) (Actions Quote) (Kernel (step sellers)) (RewardLaw (pnl sellers))
    (Discount (Rat 9 10)) (Values Ticks))

  ;; the risk-bucket compression and the mirror
  (Map bucket (From Inv) (To Bucket) (Body ($q) (Max $q (Sub 0 $q))))
  (Map mirror (From Inv) (To Inv) (Body ($q) (Sub 0 $q)))
  (Representation Risk       (Of CalmDesk)   (Encode bucket))
  (Representation RiskToxic  (Of ToxicDesk)  (Encode bucket))
  (Representation RiskBuyers (Of BuyersDesk) (Encode bucket))
  (AbstractionMap CalmMirror (Source CalmDesk)   (Target CalmDesk)    (Map mirror))
  (AbstractionMap Flip       (Source BuyersDesk) (Target SellersDesk) (Map mirror))

  ;; policies the desk has on file
  (Map calm-policy    (From Inv) (To Quote) (Table (-2 tight) (-1 lean)  (0 tight) (1 lean)  (2 tight)))
  (Map sellers-policy (From Inv) (To Quote) (Table (-2 tight) (-1 tight) (0 tight) (1 lean)  (2 tight)))

  (Derive CalmQuotient (InduceExact Risk))
  (Derive FlipChecked  (CheckAbstractionMap Flip)))

;; calm: the risk buckets are an exact quotient, and the optimum lives on them
!(dc.run MarketDesk CalmQuotient)
!(dc.run MarketDesk (CheckAbstractionMap CalmMirror))
!(dc.run MarketDesk (OptimizePolicy CalmDesk (Under Flat)))
!(dc.run MarketDesk (OptimizePolicy CalmDesk (Through Risk) (Under Flat)))
;; toxic flow: every value moves, no decision does
!(dc.run MarketDesk (InduceExact RiskToxic))
!(dc.run MarketDesk (CheckOptimal ToxicDesk (Policy calm-policy)))
!(dc.run MarketDesk (EvaluatePolicy ToxicDesk (Policy calm-policy) (Under Flat)))
;; one-sided flow: the compression breaks, and so does the policy
!(dc.run MarketDesk (InduceExact RiskBuyers))
!(dc.run MarketDesk (CheckUpdates RiskBuyers))
!(dc.run MarketDesk (MeasureBehavioral RiskBuyers (Discount (Rat 9 10))))
!(dc.run MarketDesk (CheckOptimal BuyersDesk (Policy calm-policy)))
!(dc.run MarketDesk (OptimizePolicy BuyersDesk (Under Flat)))
!(dc.run MarketDesk (OptimizePolicy BuyersDesk (Through RiskBuyers) (Under Flat)))
;; the broken symmetry survives as a transfer between the two one-sided markets
!(dc.run MarketDesk FlipChecked)
!(dc.run MarketDesk (PullbackPolicy Flip (Policy sellers-policy)))

;; ---------------------------------------------------------------------------- informed flow
(DC.Module InformedFlow
  (Profile Stochastic)
  (Use Decisions Laws Families NatArith)
  (Import MarketDesk (Only Inv Quote Market Bit Ticks step pnl ToxicDesk))
  (Carrier Flow    (Of Symbol) (Enum noise informed))
  (Carrier Book    (Of (Tuple Int Symbol)) (Product Inv Flow))
  (Carrier Reading (Of Symbol) (Enum says-noise says-informed))
  (Measure Half     (On Flow) (Masses (noise (Rat 1 2)) (informed (Rat 1 2))))
  (Measure FlatHalf (On Book) (Masses ((Tuple 0 noise) (Rat 1 2)) ((Tuple 0 informed) (Rat 1 2))))

  ;; each step is informed with probability 1/2, independently of everything else: an
  ;; informed fill is followed by a one-tick move against the maker; fills are as in calm
  (Map visible (From Book) (To Inv) (Body ($x) (GetTuple $x 0)))
  (Map flow-of (From Book) (To Flow) (Body ($x) (GetTuple $x 1)))
  (Map visible-move (From (Product Book Quote)) (To (Product Inv Quote))
    (Body ($xa) (Tuple (visible (GetTuple $xa 0)) (GetTuple $xa 1))))
  (Map split-step (From (Product Book Quote)) (To (Law Book))
    (Body ($xa) (Indep (step calm (visible-move $xa)) (LawOf Half))))
  (Map split-pnl (From (Product Book Quote)) (To (Law Rational))
    (Body ($xa) (If (Eq (flow-of (GetTuple $xa 0)) informed)
                    (pnl informed (visible-move $xa))
                    (pnl calm (visible-move $xa)))))
  (DecisionProcess Split (States Book) (Actions Quote) (Kernel split-step) (RewardLaw split-pnl)
    (Discount (Rat 9 10)) (Values Ticks))
  (Representation Coarse (Of Split) (Encode visible))

  ;; a toxicity signal that is wrong one time in ten and costs 1/20 tick per step
  (TransitionKernel FlowSignal (From Flow) (To Reading)
    (Row noise    (Mass says-noise (Rat 9 10)) (Mass says-informed (Rat 1 10)))
    (Row informed (Mass says-noise (Rat 1 10)) (Mass says-informed (Rat 9 10))))
  (ObservationMethod Signal (Channel FlowSignal) (Cost (Rat 1 20))))

!(dc.run InformedFlow (CheckEqual (AverageModel Split (Through Coarse) (Under Half)) ToxicDesk (Compare Means)))
!(dc.run InformedFlow (CheckEqual (AverageModel Split (Through Coarse) (Under Half)) ToxicDesk))
!(dc.run InformedFlow (InduceExact Coarse))
!(dc.run InformedFlow (OptimizePolicy Split (Through Coarse) (Under FlatHalf)))
!(dc.run InformedFlow (OptimizePolicy Split (Under FlatHalf)))
!(dc.run InformedFlow (EvaluatePolicy Split (With Signal) (Through Coarse) (Under FlatHalf)))

;; ---------------------------------------------------------------------------- did the news leak?
(DC.Module NewsLeak
  (Profile Stochastic)
  (Use Linear)                                          ; the Like field: PROPOSED with Example 2
  (Carrier Tape   (Of Symbol)
    (Enum leak embargo knows-up knows-down pending moved-up moved-down picked-up picked-down))
  (Carrier Report (Of Symbol) (Enum quiet up down hit-up hit-down))
  (Map report (From Tape) (To Report)
    (Cases (leak quiet) (embargo quiet) (knows-up quiet) (knows-down quiet) (pending quiet)
           (moved-up up) (moved-down down) (picked-up hit-up) (picked-down hit-down)))
  ;; leak: an informed trader already knows the direction; embargo: nobody does yet.
  ;; The informed trader picks off a tight quote just before the move and leaves a wide one.
  (TransitionKernel QuoteTight (From Tape) (To Tape)
    (Row leak (Mass knows-up (Rat 1 2)) (Mass knows-down (Rat 1 2)))
    (Row embargo (Mass pending 1))
    (Row knows-up (Mass picked-up 1))
    (Row knows-down (Mass picked-down 1))
    (Row pending (Mass moved-up (Rat 1 2)) (Mass moved-down (Rat 1 2)))
    (Row moved-up (Mass moved-up 1)) (Row moved-down (Mass moved-down 1))
    (Row picked-up (Mass picked-up 1)) (Row picked-down (Mass picked-down 1)))
  (TransitionKernel QuoteWide (From Tape) (To Tape)
    (Row leak (Mass knows-up (Rat 1 2)) (Mass knows-down (Rat 1 2)))
    (Row embargo (Mass pending 1))
    (Row knows-up (Mass moved-up 1))
    (Row knows-down (Mass moved-down 1))
    (Row pending (Mass moved-up (Rat 1 2)) (Mass moved-down (Rat 1 2)))
    (Row moved-up (Mass moved-up 1)) (Row moved-down (Mass moved-down 1))
    (Row picked-up (Mass picked-up 1)) (Row picked-down (Mass picked-down 1)))
  (Machine Desk     (States Tape) (Observe report report) (Action tight QuoteTight) (Action wide QuoteWide))
  (Machine WideDesk (States Tape) (Observe report report) (Action wide QuoteWide))
  (Carrier Seen (Of Symbol) (Reach WideDesk (From leak embargo)))
  (Machine WideSeen (States Seen) (Like WideDesk))        ; the desk that only ever quotes wide
  (Map merge-leak (From Tape) (To Tape)
    (Cases (leak leak) (embargo leak) (knows-up knows-up) (knows-down knows-down) (pending pending)
           (moved-up moved-up) (moved-down moved-down) (picked-up picked-up) (picked-down picked-down)))
  (Map merge-leak-seen (From Seen) (To Seen)
    (Cases (leak leak) (embargo leak) (knows-up knows-up) (knows-down knows-down) (pending pending)
           (moved-up moved-up) (moved-down moved-down)))
  (Representation MergeLeak     (Of Desk)     (Encode merge-leak))
  (Representation MergeLeakWide (Of WideSeen) (Encode merge-leak-seen))
  (Derive WideLinear (MinimalLinear WideSeen))
  (Derive DeskLinear (MinimalLinear Desk))
  (Derive WideTraceClasses (TracePartition WideSeen)))

!(dc.run NewsLeak (CheckTrace MergeLeakWide (Policies ObservationBased)))
!(dc.run NewsLeak (CheckBehavioral MergeLeakWide))
!(dc.run NewsLeak (MeasureBehavioral MergeLeakWide (Discount (Rat 9 10))))
!(dc.run NewsLeak WideTraceClasses)
!(dc.run NewsLeak WideLinear)
!(dc.run NewsLeak (CheckTrace MergeLeak))
!(dc.run NewsLeak (CheckBehavioral MergeLeak))
!(dc.run NewsLeak DeskLinear)

;; ---------------------------------------------------------------------------- monitors
(DC.Module ShiftMonitors
  (Profile Stochastic)
  (Use Decisions Laws Families Monitors)                ; Monitors: PROPOSED
  (Import MarketDesk (Only Inv Quote Market One theta fills))
  (Carrier Markout (Of Symbol) (Enum adverse favorable))
  (Carrier Posted  (Of (Tuple Int Symbol)) (Product Inv Quote))     ; the quote standing at a step
  ;; after a fill the mid moves one tick against the maker with probability (1 + theta)/2
  (Map markout (Parameters ($m Market)) (From One) (To (Law Markout))
    (Body ($u) (Image $b (If (Eq $b 1) adverse favorable) (Coin (Div (Add 1 (theta $m $u)) 2)))))
  (Monitor Markouts       (Context One) (Null (markout calm)) (Alternative (markout toxic))
    (Columns (observation (each "markouts"))))
  (Monitor MarkoutsBuyers (Context One) (Null (markout calm)) (Alternative (markout buyers))
    (Columns (observation (each "markouts"))))
  (Monitor Fills      (Context Posted) (Null (fills calm)) (Alternative (fills buyers))
    (Columns (context "q" "quote") (observation "ask" "bid")))
  (Monitor FillsToxic (Context Posted) (Null (fills calm)) (Alternative (fills toxic))
    (Columns (context "q" "quote") (observation "ask" "bid")))
  (Stream ToxicTape  (Source "streams/toxic_seed1.json")  (Digest "sha256:ddbb604841be3c26ae4b5af8ab260f0a7aa995bd2a0963c994b58fee71257d00")
    (Provenance "simulated: informed flow on half the steps, calm policy, 4000 steps, seed 1"))
  (Stream BuyersTape (Source "streams/buyers_seed1.json") (Digest "sha256:7f3ca6594cc85c5cfc3833861eb12a27c7136ab01fc4ef3e3151797632254cc0")
    (Provenance "simulated: one-sided buying, calm policy, 4000 steps, seed 1"))
  (Stream CalmTape   (Source "streams/calm_seed1.json")   (Digest "sha256:075bbc19f30524d642a07b57de44daf1618b043cc273e0f49357ee6b1e1af3ab")
    (Provenance "simulated: calm market, calm policy, 4000 steps, seed 1")))

!(dc.run ShiftMonitors (CheckMonitor Markouts))
!(dc.run ShiftMonitors (CheckMonitor Fills))
!(dc.run ShiftMonitors (CheckMonitor FillsToxic))
!(dc.run ShiftMonitors (CheckMonitor MarkoutsBuyers))
!(dc.run ShiftMonitors (Detect Markouts Fills (On ToxicTape)  (Level (Rat 1 100))))
!(dc.run ShiftMonitors (Detect Markouts Fills (On BuyersTape) (Level (Rat 1 100))))
!(dc.run ShiftMonitors (Detect Markouts Fills (On CalmTape)   (Level (Rat 1 100))))
