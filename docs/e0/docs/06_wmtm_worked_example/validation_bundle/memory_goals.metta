;; Omega memory and goals in MeTTaDinC: the modules of the implementation guide,
;; 4 November 2026.  One module per pattern.
;; Forms marked PROPOSED need registry patches: NatArith (Example 1); Families, Like,
;; ActionsOf and Successor Any (Example 2); Laws and Monitors (Example 4); the Pairs
;; field, the Consumer declaration with its Accepts clause and Decode field, and the
;; CheckInterpretation request of this guide (mg_registry_patch.json).
;; The lines ";; @excerpt <name>" and ";; @end" delimit the excerpts printed in the guide.

;; ============================================================ 1. open items
;; @excerpt open-items
(DC.Module OpenItems
  (Profile Crisp)
  (Use NatArith Families)                              ; PROPOSED libraries
  (Carrier Age   (Of Nat) (Enum 0 1 2 3 4 5 6 7 8))      ; 8: more than seven days
  (Carrier Reply (Of Symbol) (Enum none d0 d1 d2 d3))    ; days since the reply; d3: 3+
  (Carrier Item  (Of (Tuple Nat Symbol)) (Product Age Reply))
  (Carrier Seen  (Of Symbol) (Enum open closed dropped)) ; as a record design shows it
  (Const start Item (Tuple 0 none))

  ;; how an item changes
  (Map later (From Reply) (To Reply) (Table (none none) (d0 d1) (d1 d2) (d2 d3) (d3 d3)))
  (Map tick (From Item) (To Item)
    (Cases ((Tuple $a $r) (Tuple (Min (Add $a 1) 8) (later $r)))))
  (Map on-reply (From Item) (To Item)
    (Cases ((Tuple $a $r) (Tuple $a (If (Eq $r none) d0 $r)))))

  ;; what its users ask
  (Map suggest (From Item) (To Bool) (Cases ((Tuple $a $r) (And (Eq $r none) (Le $a 7)))))
  (Map open    (From Item) (To Bool) (Cases ((Tuple $a $r) (Eq $r none))))

  (Machine ItemLife (States Item)
    (Observe suggest suggest) (Action tick tick) (Action reply on-reply))
  (Carrier Live (Of (Tuple Nat Symbol)) (Reach ItemLife (From start)))
  (Machine GoalEngine  (States Live) (Like ItemLife))              ; PROPOSED Like
  (Machine Commitments (States Live) (Observe open open)
    (ActionsOf ItemLife))                                          ; PROPOSED ActionsOf
  (Machine Both (States Live) (Observe suggest suggest) (Observe open open)
    (ActionsOf ItemLife))
  ;; PROPOSED Consumer; the agent consumer also accepts results that rest on cvc5
  (Consumer EngineQueries     (Of GoalEngine)
    (Accepts Checked (Conditional (TrustedBackend cvc5))) (Custody Agent))
  (Consumer CommitmentQueries (Of Commitments) (Accepts Checked) (Custody Frame))

  ;; what the engine believes through its recall window, and two record designs
  (Map in-window (From Reply) (To Bool)
    (Table (none False) (d0 True) (d1 True) (d2 True) (d3 False)))
  (Map window-view (From Item) (To (Tuple Nat Symbol))
    (Cases ((Tuple $a $r) (Tuple $a (If (in-window $r) closed open)))))
  (Map event-view (From Item) (To (Tuple Nat Symbol))
    (Cases ((Tuple $a $r) (Tuple $a (If (Eq $r none) open closed)))))
  (Map capped-view (From Item) (To (Tuple Nat Symbol))
    (Cases ((Tuple $a $r)
      (If (Eq $a 8) (Tuple 8 dropped) (Tuple $a (If (Eq $r none) open closed))))))
  (Representation WindowView (Of GoalEngine) (Encode window-view))
  (Representation EventView  (Of GoalEngine) (Encode event-view))
  (Representation CapForEngine      (Of GoalEngine)  (Encode capped-view))
  (Representation CapForCommitments (Of Commitments) (Encode capped-view))
  (Derive EngineMemory     (MinimizeForQueries GoalEngine))
  (Derive CommitmentMemory (MinimizeForQueries Commitments))
  (Derive JointMemory      (MinimizeForQueries Both)))
;; @end

;; @excerpt open-items-requests
!(dc.run OpenItems (CheckNow WindowView))
!(dc.run OpenItems (CheckUpdates WindowView))
!(dc.run OpenItems (CheckBehavioral EventView))
!(dc.run OpenItems (CheckUpdates EventView))
!(dc.run OpenItems EngineMemory)
!(dc.run OpenItems CommitmentMemory)
!(dc.run OpenItems JointMemory)
!(dc.run OpenItems (CheckBehavioral CapForEngine))
!(dc.run OpenItems (CheckNow CapForCommitments))
;; @end

;; ============================================================ 1b. deduplication
;; @excerpt dedupe
(DC.Module SuggestionDedupe
  (Profile Crisp)
  (Use NatArith Families)
  (Carrier Flag   (Of Bool) (Enum False True))
  (Carrier Count  (Of Nat) (Enum 0 1 2))
  ;; (n1 received, n2 received, key k1 suggested, key k2 suggested,
  ;;  number of suggestions about the question)
  (Carrier Engine (Of (Tuple Bool Bool Bool Bool Nat))
    (Product Flag Flag Flag Flag Count))
  (Const start Engine (Tuple False False False False 0))
  (Map recv1 (From Engine) (To Engine)
    (Cases ((Tuple $r1 $r2 $s1 $s2 $c) (Tuple True $r2 $s1 $s2 $c))))
  (Map recv2 (From Engine) (To Engine)
    (Cases ((Tuple $r1 $r2 $s1 $s2 $c) (Tuple $r1 True $s1 $s2 $c))))
  ;; person+topic key: the paraphrases carry different topic labels, hence different keys
  (Map run-by-topic (From Engine) (To Engine)
    (Cases ((Tuple $r1 $r2 $s1 $s2 $c)
      (Tuple $r1 $r2 (Or $s1 $r1) (Or $s2 $r2)
        (Min 2 (Add $c (Add (If (And $r1 (Not $s1)) 1 0)
                            (If (And $r2 (Not $s2)) 1 0))))))))
  ;; question key: paraphrase linking gives both notes the key k1
  (Map run-by-question (From Engine) (To Engine)
    (Cases ((Tuple $r1 $r2 $s1 $s2 $c)
      (Tuple $r1 $r2 (Or $s1 (Or $r1 $r2)) $s2
        (Min 2 (Add $c (If (And (Or $r1 $r2) (Not $s1)) 1 0)))))))
  (Map count-of (From Engine) (To Nat) (Cases ((Tuple $r1 $r2 $s1 $s2 $c) $c)))
  (Map repeated (From Engine) (To Bool) (Body ($x) (Le 2 (count-of $x))))
  (Machine ByTopic (States Engine) (Observe repeated repeated)
    (Action recv1 recv1) (Action recv2 recv2) (Action run run-by-topic))
  (Machine ByQuestion (States Engine) (Observe repeated repeated)
    (Action recv1 recv1) (Action recv2 recv2) (Action run run-by-question))
  (Carrier LiveTopic    (Of (Tuple Bool Bool Bool Bool Nat))
    (Reach ByTopic (From start)))
  (Carrier LiveQuestion (Of (Tuple Bool Bool Bool Bool Nat))
    (Reach ByQuestion (From start)))
  (Machine TopicWatch    (States LiveTopic)    (Like ByTopic))
  (Machine QuestionWatch (States LiveQuestion) (Like ByQuestion))
  (BlockPartition OnceByTopic (On LiveTopic)
    (Block Once (Body ($x) (Le (count-of $x) 1)) start)
    (Successor Any Once Once))                                          ; PROPOSED Any
  (BlockPartition OnceByQuestion (On LiveQuestion)
    (Block Once (Body ($x) (Le (count-of $x) 1)) start)
    (Successor Any Once Once)))
;; @end

;; @excerpt dedupe-requests
!(dc.run SuggestionDedupe (CheckBlockPartition OnceByTopic (Of TopicWatch)))
!(dc.run SuggestionDedupe (CheckBlockPartition OnceByQuestion (Of QuestionWatch)))
;; @end

;; ============================================================ 2. the context block
;; @excerpt context-block
(DC.Module ContextBlock
  (Profile Crisp)
  (Use NatArith Families)
  (Carrier Kind   (Of Symbol) (Enum F O A X))          ; fresh, open item, anchor, other
  (Carrier Shown  (Of Symbol) (Enum F O A X hidden))   ; what the block shows in a slot
  (Carrier Slot   (Of Nat) (Enum 1 2 3))               ; slot 1 holds the most recent item
  (Carrier Policy (Of Symbol) (Enum recency relevance protected consumer))
  (Carrier Memory (Of (Tuple Symbol Symbol Symbol)) (Product Kind Kind Kind))

  ;; each consumer asks for the slot of the most recent item of its kind, or 0 if none
  (Map latest-of (From (Tuple Symbol (Tuple Symbol Symbol Symbol))) (To Nat)
    (Cases ((Tuple $k (Tuple $p $q $r))
      (If (Eq $p $k) 1 (If (Eq $q $k) 2 (If (Eq $r $k) 3 0))))))
  (Map latest (Parameters ($k Kind)) (From Memory) (To Nat)
    (Body ($m) (latest-of (Tuple $k $m))))
  (Machine ForFresh  (States Memory) (Observe latest-F (latest F)))
  (Machine ForOpen   (States Memory) (Observe latest-O (latest O)))
  (Machine ForAnchor (States Memory) (Observe latest-A (latest A)))
  ;; PROPOSED Consumer
  (Consumer ReplyWriter  (Of ForFresh)  (Accepts Checked) (Custody Agent))
  (Consumer SpeakerItems (Of ForOpen)   (Accepts Checked) (Custody Agent))
  (Consumer AnchorCues   (Of ForAnchor) (Accepts Checked) (Custody Frame))

  ;; a policy ranks slots; the block of two items hides the slot ranked last
  (Map kind-at (From (Tuple (Tuple Symbol Symbol Symbol) Nat)) (To Symbol)
    (Cases ((Tuple (Tuple $p $q $r) $i) (If (Eq $i 1) $p (If (Eq $i 2) $q $r)))))
  (Map relevance-rank (From Kind) (To Nat) (Table (F 0) (O 1) (X 2) (A 3)))
  (Map protected-rank (From Kind) (To Nat) (Table (A 0) (F 1) (O 2) (X 3)))
  (Map consumer-rank  (From Kind) (To Nat) (Table (A 0) (F 1) (O 2) (X 3)))
  (Map rank (Parameters ($pol Policy))
    (From (Tuple (Tuple Symbol Symbol Symbol) Nat)) (To Nat)
    (Cases ((Tuple $m $i)
      (Switch $pol
        (recency 0)
        (relevance (relevance-rank (kind-at (Tuple $m $i))))
        (protected (protected-rank (kind-at (Tuple $m $i))))
        (consumer (If (Eq (latest-of (Tuple (kind-at (Tuple $m $i)) $m)) $i)
                      (consumer-rank (kind-at (Tuple $m $i))) 3))))))
  (Map key (Parameters ($pol Policy))
    (From (Tuple (Tuple Symbol Symbol Symbol) Nat)) (To Nat)
    (Body ($mi) (Add (Mul 4 (rank $pol $mi)) (GetTuple $mi 1))))
  (Map hidden-slot (Parameters ($pol Policy)) (From Memory) (To Nat)
    (Body ($m)
      (If (And (Le (key $pol (Tuple $m 1)) (key $pol (Tuple $m 3)))
               (Le (key $pol (Tuple $m 2)) (key $pol (Tuple $m 3)))) 3
        (If (Le (key $pol (Tuple $m 1)) (key $pol (Tuple $m 2))) 2 1))))
  (Map mask (From (Tuple (Tuple Symbol Symbol Symbol) Nat))
    (To (Tuple Symbol Symbol Symbol))
    (Cases ((Tuple (Tuple $p $q $r) $d)
      (Tuple (If (Eq $d 1) hidden $p) (If (Eq $d 2) hidden $q)
             (If (Eq $d 3) hidden $r)))))
  (Map block (Parameters ($pol Policy)) (From Memory) (To (Tuple Symbol Symbol Symbol))
    (Body ($m) (mask (Tuple $m (hidden-slot $pol $m)))))
  (Map block-recency   (From Memory) (To (Tuple Symbol Symbol Symbol))
    (Body ($m) (block recency $m)))
  (Map block-relevance (From Memory) (To (Tuple Symbol Symbol Symbol))
    (Body ($m) (block relevance $m)))
  (Map block-protected (From Memory) (To (Tuple Symbol Symbol Symbol))
    (Body ($m) (block protected $m)))
  (Map block-consumer  (From Memory) (To (Tuple Symbol Symbol Symbol))
    (Body ($m) (block consumer $m)))
  (Representation RecencyF   (Of ForFresh)  (Encode block-recency))
  (Representation RecencyO   (Of ForOpen)   (Encode block-recency))
  (Representation RecencyA   (Of ForAnchor) (Encode block-recency))
  (Representation RelevanceF (Of ForFresh)  (Encode block-relevance))
  (Representation RelevanceO (Of ForOpen)   (Encode block-relevance))
  (Representation RelevanceA (Of ForAnchor) (Encode block-relevance))
  (Representation ProtectedF (Of ForFresh)  (Encode block-protected))
  (Representation ProtectedO (Of ForOpen)   (Encode block-protected))
  (Representation ProtectedA (Of ForAnchor) (Encode block-protected))
  (Representation ConsumerF  (Of ForFresh)  (Encode block-consumer))
  (Representation ConsumerO  (Of ForOpen)   (Encode block-consumer))
  (Representation ConsumerA  (Of ForAnchor) (Encode block-consumer)))
;; @end

;; @excerpt context-block-requests
!(dc.run ContextBlock (CheckNow RecencyF))
!(dc.run ContextBlock (CheckNow RecencyO))
!(dc.run ContextBlock (CheckNow RecencyA))
!(dc.run ContextBlock (CheckNow RelevanceF))
!(dc.run ContextBlock (CheckNow RelevanceO))
!(dc.run ContextBlock (CheckNow RelevanceA))
!(dc.run ContextBlock (CheckNow ProtectedF))
!(dc.run ContextBlock (CheckNow ProtectedO))
!(dc.run ContextBlock (CheckNow ProtectedA))
!(dc.run ContextBlock (CheckNow ConsumerF))
!(dc.run ContextBlock (CheckNow ConsumerO))
!(dc.run ContextBlock (CheckNow ConsumerA))
;; @end

;; ============================================================ 3. consolidation
;; @excerpt evidence-memory
(DC.Module EvidenceMemory
  (Profile Crisp)
  (Use NatArith Families)
  (Carrier Count  (Of Nat) (Enum 0 1 2))
  (Carrier Source (Of Symbol) (Enum a b c))
  ;; (supporting a, b, c, contradicting a, b, c); each count is capped at two
  (Carrier Evidence (Of (Tuple Nat Nat Nat Nat Nat Nat))
    (Product Count Count Count Count Count Count))
  (Map plus (Parameters ($s Source)) (From Evidence) (To Evidence)
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Switch $s
        (a (Tuple (Min 2 (Add $pa 1)) $pb $pc $ma $mb $mc))
        (b (Tuple $pa (Min 2 (Add $pb 1)) $pc $ma $mb $mc))
        (c (Tuple $pa $pb (Min 2 (Add $pc 1)) $ma $mb $mc))))))
  (Map minus (Parameters ($s Source)) (From Evidence) (To Evidence)
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Switch $s
        (a (Tuple $pa $pb $pc (Min 2 (Add $ma 1)) $mb $mc))
        (b (Tuple $pa $pb $pc $ma (Min 2 (Add $mb 1)) $mc))
        (c (Tuple $pa $pb $pc $ma $mb (Min 2 (Add $mc 1))))))))
  (Map seen (From Nat) (To Nat) (Table (0 0) (1 1) (2 1)))
  (Carrier Lean  (Of Symbol) (Enum support contradict tie))
  (Carrier First (Of Symbol) (Enum none a b c more))

  ;; the consumers
  (Map contra (From Evidence) (To Bool)
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc) (Le 1 (Add $ma (Add $mb $mc))))))
  (Map eff (From Evidence) (To Nat)
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Min 2 (Add (seen $pa) (Add (seen $pb) (seen $pc)))))))
  (Map regen (From Evidence) (To Bool)
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Le 2 (Add (seen $ma) (Add (seen $mb) (seen $mc)))))))
  (Machine Contra (States Evidence) (Observe contra contra)
    (Action (plus $s) (plus $s) (For $s Source))
    (Action (minus $s) (minus $s) (For $s Source)))
  (Machine Eff    (States Evidence) (Observe eff eff)     (ActionsOf Contra))
  (Machine Regen  (States Evidence) (Observe regen regen) (ActionsOf Contra))
  (Machine ContraRegen (States Evidence) (Observe contra contra) (Observe regen regen)
    (ActionsOf Contra))
  (Machine AllThree (States Evidence) (Observe contra contra) (Observe eff eff)
    (Observe regen regen) (ActionsOf Contra))
  ;; PROPOSED Consumer
  (Consumer ContraProbe      (Of Contra) (Accepts Checked) (Custody Frame))
  (Consumer EffectiveSupport (Of Eff)    (Accepts Checked) (Custody Agent))
  (Consumer AnchorCues       (Of Regen)  (Accepts Checked) (Custody Frame))

  ;; consolidation policies
  (Map majority (From Evidence) (To Symbol)
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (If (Lt (Add $ma (Add $mb $mc)) (Add $pa (Add $pb $pc))) support
        (If (Lt (Add $pa (Add $pb $pc)) (Add $ma (Add $mb $mc))) contradict tie)))))
  (Map counts (From Evidence) (To (Tuple Nat Nat))
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Tuple (Min 2 (Add $pa (Add $pb $pc))) (Min 2 (Add $ma (Add $mb $mc)))))))
  (Map distinct (From Evidence) (To (Tuple Nat Nat))
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Tuple (Add (seen $pa) (Add (seen $pb) (seen $pc)))
             (Add (seen $ma) (Add (seen $mb) (seen $mc)))))))
  (Map protected (From Evidence) (To (Tuple Nat Nat Nat Nat Nat))
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Tuple (Min 2 (Add $pa (Add $pb $pc))) (Min 2 (Add $ma (Add $mb $mc)))
             (seen $ma) (seen $mb) (seen $mc)))))
  (Map provenance (From Evidence) (To (Tuple Nat Nat Nat Nat Nat Nat))
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Tuple (seen $pa) (seen $pb) (seen $pc) (seen $ma) (seen $mb) (seen $mc)))))
  ;; the coarsest adequate memory: per polarity, no source, the only source so far,
  ;; or two or more
  (Map first-or-more (From (Tuple Nat Nat Nat)) (To Symbol)
    (Cases ((Tuple $x $y $z)
      (If (Le 2 (Add (seen $x) (Add (seen $y) (seen $z)))) more
        (If (Le 1 $x) a (If (Le 1 $y) b (If (Le 1 $z) c none)))))))
  (Map minimal (From Evidence) (To (Tuple Symbol Symbol))
    (Cases ((Tuple $pa $pb $pc $ma $mb $mc)
      (Tuple (first-or-more (Tuple $pa $pb $pc)) (first-or-more (Tuple $ma $mb $mc))))))
  (Representation MajorityC (Of Contra) (Encode majority))
  (Representation MajorityE (Of Eff)    (Encode majority))
  (Representation MajorityR (Of Regen)  (Encode majority))
  (Representation CountsC   (Of Contra) (Encode counts))
  (Representation CountsE   (Of Eff)    (Encode counts))
  (Representation CountsR   (Of Regen)  (Encode counts))
  (Representation DistinctC (Of Contra) (Encode distinct))
  (Representation DistinctE (Of Eff)    (Encode distinct))
  (Representation DistinctR (Of Regen)  (Encode distinct))
  (Representation ProtectedC (Of Contra) (Encode protected))
  (Representation ProtectedE (Of Eff)    (Encode protected))
  (Representation ProtectedR (Of Regen)  (Encode protected))
  (Representation ProvenanceAll (Of AllThree) (Encode provenance))
  (Representation MinimalAll    (Of AllThree) (Encode minimal))
  (Derive ContraMemory (MinimizeForQueries Contra))
  (Derive EffMemory    (MinimizeForQueries Eff))
  (Derive RegenMemory  (MinimizeForQueries Regen))
  (Derive AnchorMemory (MinimizeForQueries ContraRegen))
  (Derive FullMemory   (MinimizeForQueries AllThree)))
;; @end

;; @excerpt evidence-memory-requests
!(dc.run EvidenceMemory (Defects MajorityC))
!(dc.run EvidenceMemory (CheckBehavioral CountsC))
!(dc.run EvidenceMemory (CheckUpdates CountsC))
!(dc.run EvidenceMemory (CheckNow CountsE))
!(dc.run EvidenceMemory (CheckNow CountsR))
!(dc.run EvidenceMemory (CheckNow DistinctR))
!(dc.run EvidenceMemory (CheckBehavioral DistinctR))
!(dc.run EvidenceMemory (CheckUpdates DistinctC))
!(dc.run EvidenceMemory (CheckBehavioral ProtectedR))
!(dc.run EvidenceMemory (CheckUpdates ProtectedR))
!(dc.run EvidenceMemory (CheckNow ProtectedE))
!(dc.run EvidenceMemory (CheckUpdates ProvenanceAll))
!(dc.run EvidenceMemory (CheckUpdates MinimalAll))
!(dc.run EvidenceMemory (CheckBehavioral MinimalAll))
!(dc.run EvidenceMemory ContraMemory)
!(dc.run EvidenceMemory EffMemory)
!(dc.run EvidenceMemory RegenMemory)
!(dc.run EvidenceMemory AnchorMemory)
!(dc.run EvidenceMemory FullMemory)
;; @end

;; ============================================================ 3b. the migration cell
;; @excerpt anchor-migration
(DC.Module AnchorMigration
  (Profile Crisp)
  (Carrier Atom    (Of Symbol) (Enum present absent))
  (Carrier OldLink (Of Symbol) (Enum old none))
  (Carrier NewLink (Of Symbol) (Enum new old none))
  (Map old-consistent (From (Tuple Symbol Symbol)) (To Bool)
    (Cases ((Tuple $g $l) (Or (And (Eq $g present) (Eq $l old))
                              (And (Eq $g absent) (Eq $l none))))))
  (Map new-consistent (From (Tuple Symbol Symbol)) (To Bool)
    (Cases ((Tuple $g $l) (Or (And (Eq $g present) (Not (Eq $l none)))
                              (And (Eq $g absent) (Eq $l none))))))
  (Carrier OldAll   (Of (Tuple Symbol Symbol)) (Product Atom OldLink))
  (Carrier NewAll   (Of (Tuple Symbol Symbol)) (Product Atom NewLink))
  (Carrier OldState (Of (Tuple Symbol Symbol)) (Subset OldAll old-consistent))
  (Carrier NewState (Of (Tuple Symbol Symbol)) (Subset NewAll new-consistent))
  ;; a lesion deletes the goal atom and its control link; repair regrows them from cues
  (Map lesion (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol))
    (Body ($x) (Tuple absent none)))
  (Map repair-old (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol))
    (Cases ((Tuple $g $l) (If (Eq $g absent) (Tuple present old) (Tuple $g $l)))))
  ;; naive repair: the cues still name the old policy
  (Map repair-naive (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol))
    (Cases ((Tuple $g $l) (If (Eq $g absent) (Tuple present old) (Tuple $g $l)))))
  ;; repair in the migration cell: its boundary map takes the old name to the new one
  (Map repair-cell (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol))
    (Cases ((Tuple $g $l) (If (Eq $g absent) (Tuple present new) (Tuple $g $l)))))
  (Map live-old (From (Tuple Symbol Symbol)) (To Bool)
    (Cases ((Tuple $g $l) (Eq $l old))))
  (Map live-new (From (Tuple Symbol Symbol)) (To Bool)
    (Cases ((Tuple $g $l) (Eq $l new))))
  (Machine Before    (States OldState) (Observe live live-old)
    (Action lesion lesion) (Action repair repair-old))
  (Machine AfterNaive (States NewState) (Observe live live-new)
    (Action lesion lesion) (Action repair repair-naive))
  (Machine AfterCell  (States NewState) (Observe live live-new)
    (Action lesion lesion) (Action repair repair-cell))
  (Map rename (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol))
    (Cases ((Tuple $g $l) (If (Eq $l old) (Tuple $g new) (Tuple $g $l)))))
  (AbstractionMap NaiveMigration (Source Before) (Target AfterNaive) (Map rename))
  (AbstractionMap CellMigration  (Source Before) (Target AfterCell)  (Map rename)))
;; @end

;; @excerpt anchor-migration-requests
!(dc.run AnchorMigration (CheckAbstractionMap NaiveMigration))
!(dc.run AnchorMigration (CheckAbstractionMap CellMigration))
;; @end

;; ============================================================ 4. task checkpoints
;; @excerpt task-resume
(DC.Module TaskResume
  (Profile Crisp)
  (Carrier Ev   (Of Symbol) (Enum valid withdrawn))
  (Carrier Res  (Of Symbol) (Enum none r1 r2))         ; r1, r2: derived from e1, e2
  (Carrier Flag (Of Symbol) (Enum current stale))
  (Carrier Task (Of (Tuple Symbol Symbol Symbol Symbol)) (Product Ev Ev Res Flag))
  (Const start Task (Tuple valid valid none current))
  (Map derive1 (From Task) (To Task)
    (Cases ((Tuple $v1 $v2 $r $f)
      (If (And (Eq $v1 valid) (Eq $r none))
          (Tuple $v1 $v2 r1 current)
          (Tuple $v1 $v2 $r $f)))))
  (Map derive2 (From Task) (To Task)
    (Cases ((Tuple $v1 $v2 $r $f)
      (If (And (Eq $v2 valid) (Eq $r none))
          (Tuple $v1 $v2 r2 current)
          (Tuple $v1 $v2 $r $f)))))
  (Map withdraw1 (From Task) (To Task)
    (Cases ((Tuple $v1 $v2 $r $f) (Tuple withdrawn $v2 $r (If (Eq $r r1) stale $f)))))
  (Map withdraw2 (From Task) (To Task)
    (Cases ((Tuple $v1 $v2 $r $f) (Tuple $v1 withdrawn $r (If (Eq $r r2) stale $f)))))
  (Map revalidate (From Task) (To Task)
    (Cases ((Tuple $v1 $v2 $r $f)
      (If (Eq $f stale) (Tuple $v1 $v2 none current) (Tuple $v1 $v2 $r $f)))))
  (Map needs-revalidation (From Task) (To Bool)
    (Cases ((Tuple $v1 $v2 $r $f) (Eq $f stale))))
  (Map available (From Task) (To Bool)
    (Cases ((Tuple $v1 $v2 $r $f) (And (Not (Eq $r none)) (Eq $f current)))))
  (Machine Restart (States Task)
    (Observe needs-revalidation needs-revalidation) (Observe available available)
    (Action derive1 derive1) (Action derive2 derive2)
    (Action withdraw1 withdraw1) (Action withdraw2 withdraw2)
    (Action revalidate revalidate))
  (Carrier Live (Of (Tuple Symbol Symbol Symbol Symbol)) (Reach Restart (From start)))
  (Machine Resume (States Live) (Like Restart))
  (Map checkpoint-without-reads (From Task) (To (Tuple Symbol Symbol Bool Symbol))
    (Cases ((Tuple $v1 $v2 $r $f) (Tuple $v1 $v2 (Not (Eq $r none)) $f))))
  (Map checkpoint-with-reads (From Task) (To (Tuple Symbol Symbol Symbol Symbol))
    (Body ($x) $x))
  (Representation NoReadSets (Of Resume) (Encode checkpoint-without-reads))
  (Representation ReadSets   (Of Resume) (Encode checkpoint-with-reads))
  (Derive ResumeMemory (MinimizeForQueries Resume)))
;; @end

;; @excerpt task-resume-requests
!(dc.run TaskResume (CheckNow NoReadSets))
!(dc.run TaskResume (CheckUpdates NoReadSets))
!(dc.run TaskResume (CheckBehavioral NoReadSets))
!(dc.run TaskResume (CheckBehavioral ReadSets))
!(dc.run TaskResume ResumeMemory)
;; @end

;; ============================================================ 5. goals as observers
;; @excerpt item-goals
(DC.Module ItemGoals
  (Profile Crisp)
  (Use NatArith Families)
  (Carrier Status (Of Symbol) (Enum open closed))
  (Carrier Age    (Of Nat) (Enum 0 1 2 3 4))            ; 4 stands for four days or more
  (Carrier Who    (Of Symbol) (Enum ben andy))
  (Carrier Prio   (Of Symbol) (Enum normal urgent))
  (Carrier Record (Of (Tuple Symbol Nat Symbol Symbol)) (Product Status Age Who Prio))
  (Map tick (From Record) (To Record)
    (Cases ((Tuple $s $a $w $p) (Tuple $s (Min 4 (Add $a 1)) $w $p))))
  (Map close (From Record) (To Record)
    (Cases ((Tuple $s $a $w $p) (Tuple closed $a $w $p))))
  (Map escalate (From Record) (To Record)
    (Cases ((Tuple $s $a $w $p) (Tuple $s $a $w urgent))))

  ;; three goals, each an observer on the record
  (Map reply  (From Record) (To Bool)
    (Cases ((Tuple $s $a $w $p) (And (Eq $s open) (Eq $w ben)))))
  (Map nag    (From Record) (To Bool)
    (Cases ((Tuple $s $a $w $p) (And (Eq $s open) (Le $a 2)))))
  (Map triage (From Record) (To Bool)
    (Cases ((Tuple $s $a $w $p) (And (Eq $s open) (Eq $p urgent)))))
  (Machine Reply  (States Record) (Observe reply reply)
    (Action tick tick) (Action close close) (Action escalate escalate))
  (Machine Nag    (States Record) (Observe nag nag)       (ActionsOf Reply))
  (Machine Triage (States Record) (Observe triage triage) (ActionsOf Reply))
  (Machine ReplyNag (States Record) (Observe reply reply) (Observe nag nag)
    (ActionsOf Reply))
  (Machine AllGoals (States Record)
    (Observe reply reply) (Observe nag nag) (Observe triage triage)
    (ActionsOf Reply))
  (Machine ReplyTriage (States Record) (Observe reply reply) (Observe triage triage)
    (ActionsOf Reply))
  (Derive ReplyMemory       (MinimizeForQueries Reply))
  (Derive NagMemory         (MinimizeForQueries Nag))
  (Derive TriageMemory      (MinimizeForQueries Triage))
  (Derive ReplyNagMemory    (MinimizeForQueries ReplyNag))
  (Derive AllGoalsMemory    (MinimizeForQueries AllGoals))
  (Derive ReplyTriageMemory (MinimizeForQueries ReplyTriage))

  ;; three proposed changes to the nag goal
  (Map days-left (From Record) (To (Tuple Bool Nat))
    (Cases ((Tuple $s $a $w $p)
      (Tuple (And (Eq $s open) (Le $a 2)) (If (Eq $s open) (Max 0 (Sub 3 $a)) 0)))))
  (Map nag-ben-first (From Record) (To (Tuple Bool Bool))
    (Body ($x) (Tuple (nag $x) (And (nag $x) (Eq (GetTuple $x 2) ben)))))
  (Map nag-cap3 (From Record) (To Bool)
    (Cases ((Tuple $s $a $w $p) (And (Eq $s open) (Le $a 3)))))
  (Representation DaysLeft (Of Nag) (Encode days-left))
  (Representation BenFirst (Of Nag) (Encode nag-ben-first))
  (Representation Cap3     (Of Nag) (Encode nag-cap3))
  (Machine DaysGoal     (States Record) (Observe days days-left)       (ActionsOf Reply))
  (Machine BenFirstGoal (States Record) (Observe first nag-ben-first)  (ActionsOf Reply))
  (Machine Cap3Goal     (States Record) (Observe nag3 nag-cap3)        (ActionsOf Reply))
  (Representation NagForDays     (Of DaysGoal)     (Encode nag))
  (Representation NagForBenFirst (Of BenFirstGoal) (Encode nag))
  (Representation NagForCap3     (Of Cap3Goal)     (Encode nag))
  (Derive DaysMemory     (MinimizeForQueries DaysGoal))
  (Derive BenFirstMemory (MinimizeForQueries BenFirstGoal))
  (Derive Cap3Memory     (MinimizeForQueries Cap3Goal))

  ;; a schema migration: store the days left in the follow-up window instead of the age
  (Carrier Left (Of Nat) (Enum 3 2 1 0))
  (Carrier DeadlineRecord (Of (Tuple Symbol Nat Symbol Symbol))
    (Product Status Left Who Prio))
  (Map to-deadline (From Record) (To (Tuple Symbol Nat Symbol Symbol))
    (Cases ((Tuple $s $a $w $p) (Tuple $s (Max 0 (Sub 3 $a)) $w $p))))
  (Map tick-left (From DeadlineRecord) (To DeadlineRecord)
    (Cases ((Tuple $s $d $w $p) (Tuple $s (Max 0 (Sub $d 1)) $w $p))))
  (Map close-left (From DeadlineRecord) (To DeadlineRecord)
    (Cases ((Tuple $s $d $w $p) (Tuple closed $d $w $p))))
  (Map escalate-left (From DeadlineRecord) (To DeadlineRecord)
    (Cases ((Tuple $s $d $w $p) (Tuple $s $d $w urgent))))
  (Map nag-left (From DeadlineRecord) (To Bool)
    (Cases ((Tuple $s $d $w $p) (And (Eq $s open) (Lt 0 $d)))))
  (Machine NagByDeadline (States DeadlineRecord) (Observe nag nag-left)
    (Action tick tick-left) (Action close close-left) (Action escalate escalate-left))
  (AbstractionMap ToDeadline (Source Nag) (Target NagByDeadline) (Map to-deadline))
  (Derive DeadlineMemory (MinimizeForQueries NagByDeadline))

  ;; a negated goal: the same information as nag, the opposite answer on every record
  (Map anti-nag (From Record) (To Bool) (Body ($x) (Not (nag $x))))
  (Representation AntiAsNag (Of Nag) (Encode anti-nag))
  (Machine AntiNagGoal (States Record) (Observe anti anti-nag) (ActionsOf Reply))
  (Representation NagForAntiNag (Of AntiNagGoal) (Encode nag))
  (Derive AntiNagMemory (MinimizeForQueries AntiNagGoal))

  ;; what the answers ask of the agent: decoders, declared on the goals' consumers
  ;; (PROPOSED Decode) and held by the frame, as a protected goal's would be
  (Carrier Decision (Of Symbol) (Enum follow-up wait))
  (Map follow-up-if-true (From Bool) (To Decision) (Table (True follow-up) (False wait)))
  (Map wait-if-true      (From Bool) (To Decision) (Table (True wait) (False follow-up)))
  (Map days-meaning      (From (Tuple Bool Nat)) (To Decision)
    (Cases ((Tuple $b $n) (If $b follow-up wait))))
  (Map ben-first-meaning (From (Tuple Bool Bool)) (To Decision)
    (Cases ((Tuple $b $f) (If $b follow-up wait))))
  (Consumer NagFollowUps      (Of Nag)           (Accepts Checked) (Custody Frame)
    (Decode follow-up-if-true))
  ;; the consumers the proposed changes would install
  (Consumer DaysFollowUps     (Of DaysGoal)      (Accepts Checked) (Custody Frame)
    (Decode days-meaning))
  (Consumer BenFirstFollowUps (Of BenFirstGoal)  (Accepts Checked) (Custody Frame)
    (Decode ben-first-meaning))
  (Consumer Cap3FollowUps     (Of Cap3Goal)      (Accepts Checked) (Custody Frame)
    (Decode follow-up-if-true))
  (Consumer DeadlineFollowUps (Of NagByDeadline) (Accepts Checked) (Custody Frame)
    (Decode follow-up-if-true))
  (Consumer AntiNagFollowUps  (Of AntiNagGoal)   (Accepts Checked) (Custody Frame)
    (Decode follow-up-if-true))
  (Consumer AntiNagWaits      (Of AntiNagGoal)   (Accepts Checked) (Custody Frame)
    (Decode wait-if-true)))
;; @end

;; @excerpt item-goals-requests
!(dc.run ItemGoals ReplyMemory)
!(dc.run ItemGoals NagMemory)
!(dc.run ItemGoals TriageMemory)
!(dc.run ItemGoals ReplyNagMemory)
!(dc.run ItemGoals AllGoalsMemory)
!(dc.run ItemGoals ReplyTriageMemory)
!(dc.run ItemGoals (CheckNow DaysLeft))
!(dc.run ItemGoals (CheckNow NagForDays))
!(dc.run ItemGoals (CheckNow BenFirst))
!(dc.run ItemGoals (CheckNow NagForBenFirst))
!(dc.run ItemGoals (CheckNow Cap3))
!(dc.run ItemGoals (CheckNow NagForCap3))
!(dc.run ItemGoals DaysMemory)
!(dc.run ItemGoals BenFirstMemory)
!(dc.run ItemGoals Cap3Memory)
!(dc.run ItemGoals (CheckAbstractionMap ToDeadline))
!(dc.run ItemGoals DeadlineMemory)
;; informational equivalence of the negated goal
!(dc.run ItemGoals (CheckNow AntiAsNag))
!(dc.run ItemGoals (CheckNow NagForAntiNag))
!(dc.run ItemGoals AntiNagMemory)
;; the interpretation obligation, d_new(g_new(x)) = d_old(g_old(x)) on every record
!(dc.run ItemGoals (CheckInterpretation NagFollowUps DaysFollowUps))
!(dc.run ItemGoals (CheckInterpretation NagFollowUps BenFirstFollowUps))
!(dc.run ItemGoals (CheckInterpretation NagFollowUps Cap3FollowUps))
!(dc.run ItemGoals (CheckInterpretation NagFollowUps DeadlineFollowUps (Via ToDeadline)))
!(dc.run ItemGoals (CheckInterpretation NagFollowUps AntiNagFollowUps))
!(dc.run ItemGoals (CheckInterpretation NagFollowUps AntiNagWaits))
;; negative fixtures, both InvalidInput: a schema change without its map, and a map
;; whose source is not the old consumer's machine
!(dc.run ItemGoals (CheckInterpretation NagFollowUps DeadlineFollowUps))
!(dc.run ItemGoals (CheckInterpretation DaysFollowUps DeadlineFollowUps (Via ToDeadline)))
;; @end

;; ============================================================ 6. conflicts
;; @excerpt claim-arbitration
(DC.Module ClaimArbitration
  (Profile Crisp)
  (Use Families)
  (Carrier Conf  (Of Symbol) (Enum low high))
  (Carrier Move  (Of Symbol) (Enum verify consolidate hold none))
  (Carrier Flag  (Of Bool) (Enum False True))
  (Carrier Press (Of Symbol) (Enum calm deadline))
  ;; (confidence, independently checked, consolidated, deadline pressure)
  (Carrier Claim (Of (Tuple Symbol Bool Bool Symbol)) (Product Conf Flag Flag Press))
  (Const start Claim (Tuple low False False calm))

  ;; each goal's preferred move; none: no preference; hold: do not consolidate yet
  (Map throughput (From Claim) (To Symbol)
    (Cases ((Tuple $c $k $d $p)
      (If $d none (If (Or (Eq $c high) (Eq $p deadline)) consolidate none)))))
  (Map verify-first (From Claim) (To Symbol)
    (Cases ((Tuple $c $k $d $p)
      (If $d none (If (Not $k) verify (If (Eq $c high) consolidate hold))))))
  ;; the deontic kernel
  (Map forbidden (From (Tuple (Tuple Symbol Bool Bool Symbol) Symbol)) (To Bool)
    (Cases ((Tuple (Tuple $c $k $d $p) $m) (And (Eq $m consolidate) (Not $k)))))
  (Map conflict (From Claim) (To Bool)
    (Body ($x) (And (Not (Eq (throughput $x) none)) (Not (Eq (verify-first $x) none))
                    (Not (Eq (throughput $x) (verify-first $x))))))

  ;; two arbitration rules: throughput weighs 3/5, verification 2/5
  (Map weighted (From Claim) (To Symbol)
    (Body ($x) (If (Not (Eq (throughput $x) none)) (throughput $x)
                 (If (Not (Eq (verify-first $x) none)) (verify-first $x) hold))))
  (Map permitted (From (Tuple (Tuple Symbol Bool Bool Symbol) Symbol)) (To Bool)
    (Cases ((Tuple $x $m) (And (Not (Eq $m none)) (Not (forbidden (Tuple $x $m)))))))
  (Map norm-first (From Claim) (To Symbol)
    (Body ($x) (If (permitted (Tuple $x (throughput $x))) (throughput $x)
                 (If (permitted (Tuple $x (verify-first $x))) (verify-first $x) hold))))
  (Map apply-move (From (Tuple (Tuple Symbol Bool Bool Symbol) Symbol)) (To Claim)
    (Cases ((Tuple (Tuple $c $k $d $p) $m)
      (If (Eq $m verify) (Tuple $c True $d $p)
        (If (Eq $m consolidate) (Tuple $c $k True $p) (Tuple $c $k $d $p))))))
  (Map act-weighted   (From Claim) (To Claim)
    (Body ($x) (apply-move (Tuple $x (weighted $x)))))
  (Map act-norm-first (From Claim) (To Claim)
    (Body ($x) (apply-move (Tuple $x (norm-first $x)))))
  (Map evidence (From Claim) (To Claim)
    (Cases ((Tuple $c $k $d $p) (Tuple high $k $d $p))))
  (Map deadline (From Claim) (To Claim)
    (Cases ((Tuple $c $k $d $p) (Tuple $c $k $d deadline))))
  (Map unlawful-weighted   (From Claim) (To Bool)
    (Body ($x) (forbidden (Tuple $x (weighted $x)))))
  (Map unlawful-norm-first (From Claim) (To Bool)
    (Body ($x) (forbidden (Tuple $x (norm-first $x)))))

  (Machine Weighted (States Claim) (Observe unlawful unlawful-weighted)
    (Action evidence evidence) (Action deadline deadline) (Action act act-weighted))
  (Machine NormFirst (States Claim) (Observe unlawful unlawful-norm-first)
    (Action evidence evidence) (Action deadline deadline) (Action act act-norm-first))
  (Carrier LiveWeighted  (Of (Tuple Symbol Bool Bool Symbol))
    (Reach Weighted (From start)))
  (Carrier LiveNormFirst (Of (Tuple Symbol Bool Bool Symbol))
    (Reach NormFirst (From start)))
  (Machine WeightedLaw  (States LiveWeighted)  (Like Weighted))
  (Machine NormFirstLaw (States LiveNormFirst) (Like NormFirst))
  (Machine ConflictWatch (States LiveNormFirst) (Observe conflict conflict)
    (ActionsOf NormFirst))
  (BlockPartition LawfulWeighted (On LiveWeighted)
    (Block Lawful (Body ($x) (Not (unlawful-weighted $x))) start)
    (Successor Any Lawful Lawful))
  (BlockPartition LawfulNormFirst (On LiveNormFirst)
    (Block Lawful (Body ($x) (Not (unlawful-norm-first $x))) start)
    (Successor Any Lawful Lawful))
  (BlockPartition Agreement (On LiveNormFirst)
    (Block Agree (Body ($x) (Not (conflict $x))) start)
    (Successor Any Agree Agree)))
;; @end

;; @excerpt claim-arbitration-requests
!(dc.run ClaimArbitration (CheckBlockPartition LawfulWeighted (Of WeightedLaw)))
!(dc.run ClaimArbitration (CheckBlockPartition LawfulNormFirst (Of NormFirstLaw)))
!(dc.run ClaimArbitration (CheckBlockPartition Agreement (Of ConflictWatch)))
;; @end

;; ============================================================ 7. MetaMo on a grid
;; @excerpt motivation-grid
(DC.Module MotivationGrid
  (Profile Graded)
  (Use NatArith Families Contracts)                    ; Contracts: Implementation
  (Carrier Gi      (Of Int) (Enum 1 2 3 4))            ; individuation, in quarters
  (Carrier G1      (Of Int) (Enum 0 1 2 3 4))          ; exploration weight, in quarters
  (Carrier Level   (Of Int) (Enum 0 1 2))              ; arousal and securing, in halves
  (Carrier Bit     (Of Int) (Enum 0 1))                ; stimulus novelty and risk
  (Carrier Variant (Of Symbol) (Enum plain floor damped))
  (Carrier Motive  (Of (Tuple Int Int Int Int Int Int))
    (Product Gi G1 Level Level Bit Bit))
  (Const start Motive (Tuple 3 2 1 1 0 0))

  ;; appraisal updates the modulators only; decision updates the goal weights only
  (Map appraise (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho)
      (Tuple $gi $g1 (Quot (Add (Mul 4 $nu) $g1) 4) (Quot (Add (Mul 4 $rho) $gi) 4)
             $nu $rho))))
  (Map sign (From Int) (To Int) (Body ($d) (If (Lt 0 $d) 1 (If (Lt $d 0) -1 0))))
  (Map decide (Parameters ($v Variant)) (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho)
      (Tuple
        (If (And (Eq $a 2) (Le 3 $g1))
            (Switch $v (plain (Max 1 (Sub $gi 1)))
                       (floor (If (Le 2 $gi) (Max 2 (Sub $gi 1)) (Max 1 (Sub $gi 1))))
                       (damped (If (Le 2 $gi) (Max 2 (Sub $gi 1)) (Max 1 (Sub $gi 1)))))
            (If (Eq $c 2) (Min 4 (Add $gi 1)) $gi))
        (Switch $v (plain (Max 0 (Min 4 (Add $g1 (Sub $a $c)))))
                   (floor (Max 0 (Min 4 (Add $g1 (Sub $a $c)))))
                   (damped (Max 0 (Min 4 (Add $g1 (sign (Sub $a $c)))))))
        $a $c $nu $rho))))
  (Map cycle-plain  (From Motive) (To Motive) (Body ($x) (decide plain (appraise $x))))
  (Map cycle-floor  (From Motive) (To Motive) (Body ($x) (decide floor (appraise $x))))
  (Map cycle-damped (From Motive) (To Motive) (Body ($x) (decide damped (appraise $x))))
  (Map swapped-floor  (From Motive) (To Motive) (Body ($x) (appraise (decide floor $x))))
  (Map swapped-damped (From Motive) (To Motive) (Body ($x) (appraise (decide damped $x))))
  (Map novel    (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Tuple $gi $g1 $a $c 1 $rho))))
  (Map familiar (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Tuple $gi $g1 $a $c 0 $rho))))
  (Map risky    (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Tuple $gi $g1 $a $c $nu 1))))
  (Map safe     (From Motive) (To Motive)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Tuple $gi $g1 $a $c $nu 0))))
  (Map gi-of (From Motive) (To Int) (Cases ((Tuple $gi $g1 $a $c $nu $rho) $gi)))
  (Map below (From Motive) (To Bool) (Body ($x) (Lt (gi-of $x) 2)))

  ;; the safe region: individuation at least one half, from the start, under any stimuli
  (Machine PlainMotive (States Motive) (Observe below below) (Action cycle cycle-plain)
    (Action novel novel) (Action familiar familiar)
    (Action risky risky) (Action safe safe))
  (Machine FloorMotive (States Motive) (Observe below below) (Action cycle cycle-floor)
    (Action novel novel) (Action familiar familiar)
    (Action risky risky) (Action safe safe))
  (Carrier ReachPlain (Of (Tuple Int Int Int Int Int Int))
    (Reach PlainMotive (From start)))
  (Carrier ReachFloor (Of (Tuple Int Int Int Int Int Int))
    (Reach FloorMotive (From start)))
  (Machine PlainWatch (States ReachPlain) (Like PlainMotive))
  (Machine FloorWatch (States ReachFloor) (Like FloorMotive))
  (BlockPartition SafePlain (On ReachPlain)
    (Block Safe (Body ($x) (Le 2 (gi-of $x))) start) (Successor Any Safe Safe))
  (BlockPartition SafeFloor (On ReachFloor)
    (Block Safe (Body ($x) (Le 2 (gi-of $x))) start) (Successor Any Safe Safe))

  ;; distances: the largest coordinate difference, in real units
  (Map gi-real  (From Motive) (To Rational01)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Div $gi 4))))
  (Map g1-real  (From Motive) (To Rational01)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Div $g1 4))))
  (Map a-real   (From Motive) (To Rational01)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Div $a 2))))
  (Map c-real   (From Motive) (To Rational01)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) (Div $c 2))))
  (Map nu-real  (From Motive) (To Rational01)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) $nu)))
  (Map rho-real (From Motive) (To Rational01)
    (Cases ((Tuple $gi $g1 $a $c $nu $rho) $rho)))
  (Tolerance Dist01 (On Rational01) (OneMinusAbsoluteDifference))
  (Tolerance Sup (On Motive)
    (Meet (Pullback gi-real Dist01) (Pullback g1-real Dist01) (Pullback a-real Dist01)
          (Pullback c-real Dist01) (Pullback nu-real Dist01) (Pullback rho-real Dist01)))
  (Map settled (From Motive) (To Bool) (Body ($x) (Eq (appraise $x) $x)))
  (Carrier Settled (Of (Tuple Int Int Int Int Int Int)) (Subset Motive settled))
  (Map same-stimulus
    (From (Tuple (Tuple Int Int Int Int Int Int) (Tuple Int Int Int Int Int Int)))
    (To Bool)
    (Cases ((Tuple (Tuple $i1 $g1 $a1 $c1 $n1 $r1) (Tuple $i2 $g2 $a2 $c2 $n2 $r2))
      (And (Eq $n1 $n2) (Eq $r1 $r2)))))
  (Map near-boundary
    (From (Tuple (Tuple Int Int Int Int Int Int) (Tuple Int Int Int Int Int Int)))
    (To Bool)
    (Body ($pq) (And (same-stimulus $pq)
                     (Or (Eq (gi-of (GetTuple $pq 0)) 2)
                         (Eq (gi-of (GetTuple $pq 1)) 2)))))

  ;; appraisal and decision in either order (MetaMo's modular appraisal-decision
  ;; interface); the Pairs field is PROPOSED
  (Implementation OrderSwapFloor (Ideal cycle-floor) (Actual swapped-floor)
    (Audit Motive) (InputDistance Sup) (OutputDistance Sup) (Pairs same-stimulus))
  (Implementation OrderSwapDamped (Ideal cycle-damped) (Actual swapped-damped)
    (Audit Motive) (InputDistance Sup) (OutputDistance Sup) (Pairs same-stimulus))
  (Implementation OrderSwapSettled (Ideal cycle-floor) (Actual swapped-floor)
    (Audit Settled) (InputDistance Sup) (OutputDistance Sup) (Pairs same-stimulus))
  ;; contraction near the boundary of the safe region (MetaMo's homeostatic drive
  ;; stability)
  (Implementation NearBoundaryFloor (Ideal cycle-floor) (Actual cycle-floor)
    (Audit Motive) (InputDistance Sup) (OutputDistance Sup) (Pairs near-boundary))
  (Implementation NearBoundaryDamped (Ideal cycle-damped) (Actual cycle-damped)
    (Audit Motive) (InputDistance Sup) (OutputDistance Sup) (Pairs near-boundary)))
;; @end

;; @excerpt motivation-grid-requests
!(dc.run MotivationGrid (CheckBlockPartition SafePlain (Of PlainWatch)))
!(dc.run MotivationGrid (CheckBlockPartition SafeFloor (Of FloorWatch)))
!(dc.run MotivationGrid (CheckImplementation OrderSwapFloor (Grade 1 (Rat 1 2))))
!(dc.run MotivationGrid (CheckImplementation OrderSwapDamped (Grade 1 (Rat 1 2))))
!(dc.run MotivationGrid (CheckImplementation OrderSwapSettled (Grade 1 (Rat 1 2))))
!(dc.run MotivationGrid (CheckImplementation OrderSwapSettled (Grade 1 (Rat 1 4))))
!(dc.run MotivationGrid
   (CheckImplementation NearBoundaryFloor (Grade (Rat 1 2) (Rat 3 4))))
!(dc.run MotivationGrid
   (CheckImplementation NearBoundaryFloor (Grade (Rat 1 2) (Rat 1 2))))
!(dc.run MotivationGrid
   (CheckImplementation NearBoundaryDamped (Grade (Rat 1 2) (Rat 5 8))))
;; @end

;; ============================================================ 8. a monitor
;; @excerpt stale-monitor
(DC.Module StaleMonitor
  (Profile Stochastic)
  (Use Decisions Laws Families Monitors)               ; PROPOSED (Example 4)
  (Carrier One   (Of Symbol) (Enum one))
  (Carrier Rate  (Of Symbol) (Enum accepted failing))
  (Map stale-rate (From Rate) (To Rational01)
    (Table (accepted (Rat 1 20)) (failing (Rat 1 5))))
  ;; a suggestion is stale when its item was already closed by an event; 1 = stale
  (Map stale (Parameters ($r Rate)) (From One) (To (Law Nat))
    (Body ($u) (Coin (stale-rate $r))))
  (Monitor Stale (Context One) (Null (stale accepted)) (Alternative (stale failing))
    (Columns (observation "stale")))
  (Stream LiveSuggestions (Source "streams/stale_alt_seed1.json")
    (Digest "sha256:f0d4be8461a2904e728f7b0a8ad895385ccd56f340ec854d729936aaf6a48763")
    (Provenance "simulated: stale with probability 1/5, 400 suggestions, seed 1"))
  (Stream QuietSuggestions (Source "streams/stale_null_seed1.json")
    (Digest "sha256:8e76cbdeee37a8ab4156c6068ee59fab740c2f9d1b02146e3ee7e38c594b59b0")
    (Provenance "simulated: stale with probability 1/20, 400 suggestions, seed 1")))
;; @end

;; @excerpt stale-monitor-requests
!(dc.run StaleMonitor (CheckMonitor Stale))
!(dc.run StaleMonitor (Detect Stale (On LiveSuggestions) (Level (Rat 1 100))))
!(dc.run StaleMonitor (Detect Stale (On QuietSuggestions) (Level (Rat 1 100))))
;; @end
