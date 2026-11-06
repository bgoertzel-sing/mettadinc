;; Example 3: sharing navigation skills between robots whose cameras see the bay in
;; different frames.  Three modules: the progress task, the docking task, and a bay with
;; an extra pallet.  Forms marked PROPOSED need ex3_registry_patch.json (and NatArith from
;; ex1_registry_patch.json).

;; @excerpt skill-share
(DC.Module SkillShare
  (Profile Crisp)
  (Use Transfers Hives NatArith)
  (Carrier Coord  (Of Nat) (Enum 0 1 2 3 4))
  (Carrier Grid   (Of (Tuple Nat Nat)) (Product Coord Coord))
  (Carrier Dir    (Of Symbol) (Enum up right down left))
  (Carrier Reward (Of Rational) (Enum 0 (Rat 1 2) 1))

  ;; the dihedral group of the square, on cells (row from the top, column from the left)
  ;; and on image directions; r90 is a clockwise quarter turn on the screen
  (Map r90-cell  (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple $c (Sub 4 $r)))))
  (Map r270-cell (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple (Sub 4 $c) $r))))
  (Map mv-cell   (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple $r (Sub 4 $c)))))   ; mirror left-right
  (Map mh-cell   (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple (Sub 4 $r) $c))))   ; mirror up-down
  (Map md-cell   (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple $c $r))))           ; transpose
  (Map ma-cell   (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple (Sub 4 $c) (Sub 4 $r)))))
  (Map r180-cell (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple (Sub 4 $r) (Sub 4 $c)))))
  (Map same-cell (From Grid) (To Grid) (Cases ((Tuple $r $c) (Tuple $r $c))))
  (Map r90-dir   (From Dir) (To Dir) (Cases (up right) (right down) (down left) (left up)))
  (Map r270-dir  (From Dir) (To Dir) (Cases (up left) (right up) (down right) (left down)))
  (Map mv-dir    (From Dir) (To Dir) (Cases (up up) (right left) (down down) (left right)))
  (Map mh-dir    (From Dir) (To Dir) (Cases (up down) (right right) (down up) (left left)))
  (Map md-dir    (From Dir) (To Dir) (Cases (up left) (right down) (down right) (left up)))
  (Map ma-dir    (From Dir) (To Dir) (Cases (up right) (right up) (down left) (left down)))
  (Map r180-dir  (From Dir) (To Dir) (Cases (up down) (right left) (down up) (left right)))
  (Map same-dir  (From Dir) (To Dir) (Cases (up up) (right right) (down down) (left left)))

  ;; the bay: goal at the centre, pillars at rows 1 and 3 of the outer columns
  (Map pillar (From Grid) (To Bool)
    (Cases ((Tuple $r $c) (And (Or (Eq $r 1) (Eq $r 3)) (Or (Eq $c 0) (Eq $c 4))))))
  (Map dist (From Grid) (To Nat)
    (Cases ((Tuple $r $c) (Add (If (Le $r 2) (Sub 2 $r) (Sub $r 2)) (If (Le $c 2) (Sub 2 $c) (Sub $c 2))))))
  (Map step (From (Product Grid Dir)) (To Grid)       ; blocked moves stay put
    (Cases
      ((Tuple (Tuple $r $c) up)
        (If (Eq $r 0) (Tuple $r $c)
          (If (pillar (Tuple (Sub $r 1) $c)) (Tuple $r $c) (Tuple (Sub $r 1) $c))))
      ((Tuple (Tuple $r $c) down)
        (If (Eq $r 4) (Tuple $r $c)
          (If (pillar (Tuple (Add $r 1) $c)) (Tuple $r $c) (Tuple (Add $r 1) $c))))
      ((Tuple (Tuple $r $c) left)
        (If (Eq $c 0) (Tuple $r $c)
          (If (pillar (Tuple $r (Sub $c 1))) (Tuple $r $c) (Tuple $r (Sub $c 1)))))
      ((Tuple (Tuple $r $c) right)
        (If (Eq $c 4) (Tuple $r $c)
          (If (pillar (Tuple $r (Add $c 1))) (Tuple $r $c) (Tuple $r (Add $c 1)))))))
  (Map progress (From (Product Grid Dir)) (To Reward)  ; 1 closer, 1/2 no change, 0 farther
    (Body ($xm)
      (If (Lt (dist (step $xm)) (dist (GetTuple $xm 0))) 1
        (If (Eq (dist (step $xm)) (dist (GetTuple $xm 0))) (Rat 1 2) 0))))

  ;; three robots: A's camera is aligned with the bay, B's is turned a quarter turn
  ;; clockwise, C's sees the bay transposed; each commands moves in its own image frame
  (Map free-A (From Grid) (To Bool) (Body ($y) (Not (pillar $y))))
  (Map free-B (From Grid) (To Bool) (Body ($y) (Not (pillar (r270-cell $y)))))
  (Map free-C (From Grid) (To Bool) (Body ($y) (Not (pillar (md-cell $y)))))
  (Carrier FreeA (Of (Tuple Nat Nat)) (Subset Grid free-A))
  (Carrier FreeB (Of (Tuple Nat Nat)) (Subset Grid free-B))
  (Carrier FreeC (Of (Tuple Nat Nat)) (Subset Grid free-C))
  (Map respond-A (From (Product FreeA Dir)) (To Reward) (Body ($ym) (progress $ym)))
  (Map respond-B (From (Product FreeB Dir)) (To Reward)
    (Body ($ym) (progress (Tuple (r270-cell (GetTuple $ym 0)) (r270-dir (GetTuple $ym 1))))))
  (Map respond-C (From (Product FreeC Dir)) (To Reward)
    (Body ($ym) (progress (Tuple (md-cell (GetTuple $ym 0)) (md-dir (GetTuple $ym 1))))))
  (MethodSystem A (States FreeA) (Methods Dir) (Response respond-A))
  (MethodSystem B (States FreeB) (Methods Dir) (Response respond-B))
  (MethodSystem C (States FreeC) (Methods Dir) (Response respond-C))

  ;; the library: AB and BC from camera calibration, CA learned by matching recorded
  ;; responses; a pullback maps target cells to source cells, a pushforward source commands
  ;; to target commands
  (Transfer AB      (Source A) (Target B) (StatePullback r270-cell) (MethodPushforward r90-dir))
  (Transfer BC      (Source B) (Target C) (StatePullback mv-cell)   (MethodPushforward mv-dir))
  (Transfer CA      (Source C) (Target A) (StatePullback r90-cell)  (MethodPushforward r270-dir))
  (Transfer CAcal   (Source C) (Target A) (StatePullback md-cell)   (MethodPushforward md-dir))
  (Transfer NaiveAB (Source A) (Target B) (StatePullback r270-cell) (MethodPushforward same-dir))
  ;; every exact C-to-A transfer among the eight frame changes (pullback, pushforward)
  (Derive CandidatesCA
    (FindTransfers C A                                                                  ; PROPOSED
      (Candidates (same-cell same-dir) (r90-cell r270-dir) (r180-cell r180-dir) (r270-cell r90-dir)
                  (mv-cell mv-dir) (mh-cell mh-dir) (md-cell md-dir) (ma-cell ma-dir))))
  (Derive ABchecked (CheckTransfer AB))
  (Derive BCchecked (CheckTransfer BC))
  (Derive CAchecked (CheckTransfer CA))
  (Derive RoundTrip (ComposeTransfers (Output ABchecked Transfer) (Output BCchecked Transfer)
                                      (Output CAchecked Transfer)))

  ;; response symmetries, each in its robot's own frame
  (Symmetry FlipUD-A (Of A) (States mh-cell) (Methods mh-dir))
  (Symmetry FlipLR-A (Of A) (States mv-cell) (Methods mv-dir))
  (Symmetry FlipUD-B (Of B) (States mh-cell) (Methods mh-dir))
  (Symmetry FlipLR-B (Of B) (States mv-cell) (Methods mv-dir))
  (Symmetry FlipUD-C (Of C) (States mh-cell) (Methods mh-dir))
  (Symmetry FlipLR-C (Of C) (States mv-cell) (Methods mv-dir))
  (TransferHive Strict (Member A) (Member B) (Member C)
    (Edge AB) (Edge BC) (Edge CA) (Cycle A B C))
  (TransferHive FullGauge (Member A) (Member B) (Member C)
    (Edge AB) (Edge BC) (Edge CA) (Cycle A B C)
    (Gauge A FlipUD-A FlipLR-A) (Gauge B FlipUD-B FlipLR-B) (Gauge C FlipUD-C FlipLR-C))
  (TransferHive Copied (Member A) (Member B) (Member C)
    (Edge AB) (Edge BC) (Edge CA) (Cycle A B C)
    (Gauge A FlipUD-A) (Gauge B FlipUD-B) (Gauge C FlipUD-C))
  (TransferHive Transported (Member A) (Member B) (Member C)
    (Edge AB) (Edge BC) (Edge CA) (Cycle A B C)
    (Gauge A FlipUD-A) (Gauge B FlipLR-B) (Gauge C FlipLR-C))
  (TransferHive FromBase (Member A) (Member B) (Member C)                             ; PROPOSED
    (Edge AB) (Edge BC) (Edge CA) (Cycle A B C) (GaugeFrom A FlipUD-A))
  (Derive Unsaturated (KernelOf Strict))
  (Derive SaturatedFull (KernelOf FullGauge (Saturate Gauge)))
  (Derive SaturatedCopied (KernelOf Copied (Saturate Gauge)))
  (Derive SaturatedTransported (KernelOf Transported (Saturate Gauge)))

  ;; a skill: the greedy move, ties broken by command order (as a frozen table)
  (Map greedy-A (From FreeA) (To Dir)
    (Table ((Tuple 0 0) right) ((Tuple 0 1) right) ((Tuple 0 2) down) ((Tuple 0 3) down) ((Tuple 0 4) left)
           ((Tuple 1 1) right) ((Tuple 1 2) down) ((Tuple 1 3) down)
           ((Tuple 2 0) right) ((Tuple 2 1) right) ((Tuple 2 2) up) ((Tuple 2 3) left) ((Tuple 2 4) left)
           ((Tuple 3 1) up) ((Tuple 3 2) up) ((Tuple 3 3) up)
           ((Tuple 4 0) right) ((Tuple 4 1) up) ((Tuple 4 2) up) ((Tuple 4 3) up) ((Tuple 4 4) left)))
  (Derive SkillRoundTrip (TransportSkill (Output RoundTrip Transfer) greedy-A))        ; PROPOSED
  ;; a skill whose rewards are not mirror-symmetric: always move up
  (Map always-up (From FreeA) (To Dir) (Body ($x) up))
  (Derive UpRoundTrip (TransportSkill (Output RoundTrip Transfer) always-up)))
;; @end

;; @excerpt skill-share-requests
!(dc.run SkillShare ABchecked)
!(dc.run SkillShare BCchecked)
!(dc.run SkillShare CAchecked)
!(dc.run SkillShare (CheckTransfer CAcal))
!(dc.run SkillShare CandidatesCA)
!(dc.run SkillShare (CheckTransfer NaiveAB))
!(dc.run SkillShare (CheckValuePullback NaiveAB))
!(dc.run SkillShare RoundTrip)
!(dc.run SkillShare (CheckTransferHive Strict))
!(dc.run SkillShare (CheckTransferHive FullGauge))
!(dc.run SkillShare (CheckTransferHive Copied))
!(dc.run SkillShare (CheckTransferHive Transported))
!(dc.run SkillShare (CheckTransferHive FromBase))
!(dc.run SkillShare (CheckKernelCoherence (Output Unsaturated Hive)))
!(dc.run SkillShare (Holonomy (Output Unsaturated Hive) (Cycle A B C)))
!(dc.run SkillShare (ConsensusCost (Output Unsaturated Hive)))
!(dc.run SkillShare (CheckKernelCoherence (Output SaturatedFull Hive)))
!(dc.run SkillShare (CheckKernelCoherence (Output SaturatedCopied Hive)))
!(dc.run SkillShare (CheckKernelCoherence (Output SaturatedTransported Hive)))
!(dc.run SkillShare SkillRoundTrip)
!(dc.run SkillShare UpRoundTrip)
;; @end

;; @excerpt skill-share-dock
(DC.Module SkillShareDock
  (Profile Crisp)
  (Use Transfers Hives NatArith)
  (Import SkillShare
    (Only Grid Dir Reward FreeA FreeB FreeC r90-cell r270-cell mv-cell mh-cell md-cell
          r90-dir r270-dir mv-dir mh-dir md-dir step progress))
  ;; the charger faces north: arriving at the goal from any other side earns 1/2
  (Map docking (From (Product Grid Dir)) (To Reward)
    (Body ($xm)
      (If (And (Eq (step $xm) (Tuple 2 2))
               (And (Not (Eq (GetTuple $xm 0) (Tuple 2 2))) (Not (Eq (GetTuple $xm 1) down))))
          (Rat 1 2)
          (progress $xm))))
  (Map dock-A (From (Product FreeA Dir)) (To Reward) (Body ($ym) (docking $ym)))
  (Map dock-B (From (Product FreeB Dir)) (To Reward)
    (Body ($ym) (docking (Tuple (r270-cell (GetTuple $ym 0)) (r270-dir (GetTuple $ym 1))))))
  (Map dock-C (From (Product FreeC Dir)) (To Reward)
    (Body ($ym) (docking (Tuple (md-cell (GetTuple $ym 0)) (md-dir (GetTuple $ym 1))))))
  (MethodSystem A (States FreeA) (Methods Dir) (Response dock-A))
  (MethodSystem B (States FreeB) (Methods Dir) (Response dock-B))
  (MethodSystem C (States FreeC) (Methods Dir) (Response dock-C))
  (Transfer AB    (Source A) (Target B) (StatePullback r270-cell) (MethodPushforward r90-dir))
  (Transfer BC    (Source B) (Target C) (StatePullback mv-cell)   (MethodPushforward mv-dir))
  (Transfer CAold (Source C) (Target A) (StatePullback r90-cell)  (MethodPushforward r270-dir))
  (Transfer CAnew (Source C) (Target A) (StatePullback r270-cell) (MethodPushforward r90-dir))
  (Symmetry FlipUD-A (Of A) (States mh-cell) (Methods mh-dir))
  (Symmetry FlipLR-A (Of A) (States mv-cell) (Methods mv-dir))
  (Symmetry FlipUD-B (Of B) (States mh-cell) (Methods mh-dir))
  (Symmetry FlipLR-B (Of B) (States mv-cell) (Methods mv-dir))
  (Symmetry FlipUD-C (Of C) (States mh-cell) (Methods mh-dir))
  (Symmetry FlipLR-C (Of C) (States mv-cell) (Methods mv-dir))
  (TransferHive StaleGauge (Member A) (Member B) (Member C)
    (Edge AB) (Edge BC) (Edge CAnew) (Cycle A B C)
    (Gauge A FlipUD-A FlipLR-A) (Gauge B FlipUD-B FlipLR-B) (Gauge C FlipUD-C FlipLR-C))
  (TransferHive OldLibrary (Member A) (Member B) (Member C)
    (Edge AB) (Edge BC) (Edge CAold) (Cycle A B C)
    (Gauge A FlipLR-A) (Gauge B FlipUD-B) (Gauge C FlipUD-C))
  (TransferHive Docking (Member A) (Member B) (Member C)
    (Edge AB) (Edge BC) (Edge CAnew) (Cycle A B C)
    (Gauge A FlipLR-A) (Gauge B FlipUD-B) (Gauge C FlipUD-C))
  (Derive DockSaturated (KernelOf Docking (Saturate Gauge))))
;; @end

;; @excerpt skill-share-dock-requests
!(dc.run SkillShareDock (CheckTransfer CAold))
!(dc.run SkillShareDock (CheckTransfer CAold (Metric ExpectedReward) (Within (Rat 1 2))))
!(dc.run SkillShareDock (CheckTransfer CAnew))
!(dc.run SkillShareDock (CheckTransferHive StaleGauge))
!(dc.run SkillShareDock (CheckTransferHive OldLibrary))
!(dc.run SkillShareDock (CheckTransferHive Docking))
!(dc.run SkillShareDock (CheckKernelCoherence (Output DockSaturated Hive)))
;; @end

;; @excerpt pallet-bay
(DC.Module PalletBay
  (Profile Crisp)
  (Use Transfers NatArith)
  (Import SkillShare
    (Only Grid Dir Reward FreeA FreeB pillar dist md-cell md-dir mv-cell mv-dir r270-cell r90-dir
          A B AB ABchecked))
  ;; C's bay has a pallet on the north side of the goal's column (world cell (0,2))
  (Map blocked (From Grid) (To Bool) (Body ($y) (Or (pillar $y) (Eq $y (Tuple 0 2)))))
  (Map step-p (From (Product Grid Dir)) (To Grid)
    (Cases
      ((Tuple (Tuple $r $c) up)
        (If (Eq $r 0) (Tuple $r $c)
          (If (blocked (Tuple (Sub $r 1) $c)) (Tuple $r $c) (Tuple (Sub $r 1) $c))))
      ((Tuple (Tuple $r $c) down)
        (If (Eq $r 4) (Tuple $r $c)
          (If (blocked (Tuple (Add $r 1) $c)) (Tuple $r $c) (Tuple (Add $r 1) $c))))
      ((Tuple (Tuple $r $c) left)
        (If (Eq $c 0) (Tuple $r $c)
          (If (blocked (Tuple $r (Sub $c 1))) (Tuple $r $c) (Tuple $r (Sub $c 1)))))
      ((Tuple (Tuple $r $c) right)
        (If (Eq $c 4) (Tuple $r $c)
          (If (blocked (Tuple $r (Add $c 1))) (Tuple $r $c) (Tuple $r (Add $c 1)))))))
  (Map progress-p (From (Product Grid Dir)) (To Reward)
    (Body ($xm)
      (If (Lt (dist (step-p $xm)) (dist (GetTuple $xm 0))) 1
        (If (Eq (dist (step-p $xm)) (dist (GetTuple $xm 0))) (Rat 1 2) 0))))
  (Map free-Cp (From Grid) (To Bool) (Body ($y) (Not (blocked (md-cell $y)))))
  (Carrier FreeCp (Of (Tuple Nat Nat)) (Subset Grid free-Cp))
  (Map respond-Cp (From (Product FreeCp Dir)) (To Reward)
    (Body ($ym) (progress-p (Tuple (md-cell (GetTuple $ym 0)) (md-dir (GetTuple $ym 1))))))
  (MethodSystem Cp (States FreeCp) (Methods Dir) (Response respond-Cp))
  (Transfer ACp (Source A) (Target Cp) (StatePullback md-cell) (MethodPushforward md-dir))
  (Transfer BCp (Source B) (Target Cp) (StatePullback mv-cell) (MethodPushforward mv-dir))
  (Derive BCpChecked (CheckTransfer BCp (Metric ExpectedReward) (Within (Rat 1 2))))
  (Derive AtoCp (ComposeTransfers (Output ABchecked Transfer) (Output BCpChecked Transfer))))
;; @end

;; @excerpt pallet-bay-requests
!(dc.run PalletBay (CheckTransfer ACp))
!(dc.run PalletBay (CheckTransfer ACp (Metric ExpectedReward) (Within (Rat 1 2))))
!(dc.run PalletBay (CheckTransfer ACp (Metric ExpectedReward) (Within (Rat 1 4))))
!(dc.run PalletBay AtoCp)
;; @end
