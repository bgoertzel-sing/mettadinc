;; Example 2: auditing an administrative access-control policy on forty-bit words.
;; Two modules: the policy as written, and the corrected policy with the audit's
;; certificates, slices and quotients.  Forms marked PROPOSED need ex2_registry_patch.json.

;; @excerpt access-policy
(DC.Module AccessPolicy
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)                         ; PROPOSED library: Parameters, For, Switch, Exists
  (Carrier Word (Of (BitVector 40)) (All))
  (Carrier User (Of Symbol) (Enum alice bob carol dave))
  (Carrier Role (Of Symbol) (Enum staff clerk approver auditor admin))
  (Map slot (From User) (To Nat) (Table (alice 0) (bob 10) (carol 20) (dave 30)))
  (Map rank (From Role) (To Nat) (Table (staff 0) (clerk 1) (approver 2) (auditor 3) (admin 4)))

  ;; bit 10u+r says that u is assigned r; bit 10u+5+r says that u has r active
  (Map holds (Parameters ($u User) ($r Role)) (From Word) (To Bool)
    (Body ($x) (Eq (BitAt $x (Add (slot $u) (rank $r))) 1)))
  (Map active (Parameters ($u User) ($r Role)) (From Word) (To Bool)
    (Body ($x) (Eq (BitAt $x (Add (Add (slot $u) 5) (rank $r))) 1)))
  (Map other-admin (Parameters ($u User)) (From Word) (To Bool)
    (Body ($x) (Exists $v User (And (Not (Eq $v $u)) (active $v admin $x)))))

  ;; the can-assign rules; as written, the approver rule reads the auditor session
  (Map may-receive (Parameters ($u User) ($r Role)) (From Word) (To Bool)
    (Body ($x)
      (Switch $r
        (staff    True)
        (clerk    (holds $u staff $x))
        (approver (And (holds $u clerk $x) (Not (active $u auditor $x))))
        (auditor  (And (holds $u staff $x) (Not (holds $u approver $x))))
        (admin    (holds $u staff $x)))))
  (Map grant (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x) (SetBit $x (Add (slot $u) (rank $r)) 1)))
  (Map drop (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x) (SetBit (SetBit $x (Add (slot $u) (rank $r)) 0) (Add (Add (slot $u) 5) (rank $r)) 0)))
  (Map assign (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x) (If (And (other-admin $u $x) (may-receive $u $r $x)) (grant $u $r $x) $x)))
  ;; revocation cascades along role dependencies; as written, revoking clerk keeps approver
  (Map revoke (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x)
      (If (other-admin $u $x)
          (Switch $r
            (staff    (drop $u staff (drop $u clerk (drop $u approver (drop $u auditor (drop $u admin $x))))))
            (clerk    (drop $u clerk $x))
            (approver (drop $u approver $x))
            (auditor  (drop $u auditor $x))
            (admin    (drop $u admin $x)))
          $x)))
  ;; sessions: approver and auditor are never active together
  (Map activate (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x)
      (If (And (holds $u $r $x)
               (Switch $r
                 (staff True) (clerk True) (admin True)
                 (approver (Not (active $u auditor $x)))
                 (auditor  (Not (active $u approver $x)))))
          (SetBit $x (Add (Add (slot $u) 5) (rank $r)) 1)
          $x)))
  (Map deactivate (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x) (SetBit $x (Add (Add (slot $u) 5) (rank $r)) 0)))

  ;; access decisions and the auditor's alarms
  (Map may-read (Parameters ($u User)) (From Word) (To Bool)
    (Body ($x) (Or (Or (active $u staff $x) (active $u clerk $x))
                   (Or (active $u approver $x) (active $u auditor $x)))))
  (Map may-write     (Parameters ($u User)) (From Word) (To Bool)
    (Body ($x) (Or (active $u clerk $x) (active $u approver $x))))
  (Map may-approve   (Parameters ($u User)) (From Word) (To Bool) (Body ($x) (active $u approver $x)))
  (Map may-audit     (Parameters ($u User)) (From Word) (To Bool) (Body ($x) (active $u auditor $x)))
  (Map may-configure (Parameters ($u User)) (From Word) (To Bool) (Body ($x) (active $u admin $x)))
  (Map sod-breach (From Word) (To Bool)
    (Body ($x) (Exists $u User (And (holds $u approver $x) (holds $u auditor $x)))))
  (Map clerkless-approval (From Word) (To Bool)
    (Body ($x) (Exists $u User (And (active $u approver $x) (Not (holds $u clerk $x))))))
  (Map well-formed (Parameters ($u User)) (From Word) (To Bool)
    (Body ($x)
      (And (ForAll $r Role (Or (Not (active $u $r $x)) (holds $u $r $x)))
        (And (Or (Not (holds $u clerk $x)) (holds $u staff $x))
          (And (Or (Not (holds $u approver $x)) (holds $u clerk $x))
            (And (Or (Not (holds $u auditor $x)) (holds $u staff $x))
              (And (Or (Not (holds $u admin $x)) (holds $u staff $x))
                (Not (And (holds $u approver $x) (holds $u auditor $x))))))))))
  (Map consistent (From Word) (To Bool) (Body ($x) (ForAll $u User (well-formed $u $x))))

  (Machine Policy (States Word)
    (Observe (read $u)      (may-read $u)      (For $u User))
    (Observe (write $u)     (may-write $u)     (For $u User))
    (Observe (approve $u)   (may-approve $u)   (For $u User))
    (Observe (audit $u)     (may-audit $u)     (For $u User))
    (Observe (configure $u) (may-configure $u) (For $u User))
    (Action (assign $u $r)     (assign $u $r)     (For $u User) (For $r Role))
    (Action (revoke $u $r)     (revoke $u $r)     (For $u User) (For $r Role))
    (Action (activate $u $r)   (activate $u $r)   (For $u User) (For $r Role))
    (Action (deactivate $u $r) (deactivate $u $r) (For $u User) (For $r Role)))

  ;; alice: staff and admin, admin active; bob: staff and clerk, clerk active; carol: staff, active
  (Const start Word 34672145)
  (Carrier Live (Of (BitVector 40)) (Reach Policy (From start)))
  (Machine SoDWatch   (States Live) (Observe breach sod-breach) (ActionsOf Policy))         ; PROPOSED
  (Machine ClerkWatch (States Live) (Observe clerkless clerkless-approval) (ActionsOf Policy))
  (Machine Hygiene    (States Live) (Observe wellformed consistent) (ActionsOf Policy))
  (BlockPartition NoBreach (On Live)
    (Block Quiet (Body ($x) (Not (sod-breach $x))) start) (Successor Any Quiet Quiet))       ; PROPOSED Any
  (BlockPartition ClerksOnly (On Live)
    (Block Quiet (Body ($x) (Not (clerkless-approval $x))) start) (Successor Any Quiet Quiet))
  (BlockPartition WellFormed (On Live)
    (Block Good (Body ($x) (consistent $x)) start) (Successor Any Good Good)))
;; @end

;; @excerpt access-policy-requests
!(dc.run AccessPolicy (CheckBlockPartition NoBreach (Of SoDWatch)))
!(dc.run AccessPolicy (CheckBlockPartition ClerksOnly (Of ClerkWatch)))
!(dc.run AccessPolicy (CheckBlockPartition WellFormed (Of Hygiene)))
;; @end

;; @excerpt access-policy-fixed
(DC.Module AccessPolicyFixed
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Symbolic))
  (Use BitVectors Families)
  (Import AccessPolicy
    (Only Word User Role slot rank holds active other-admin grant drop activate deactivate
          may-read may-write may-approve may-audit may-configure sod-breach clerkless-approval
          well-formed consistent start))
  (Map may-receive (Parameters ($u User) ($r Role)) (From Word) (To Bool)
    (Body ($x)
      (Switch $r
        (staff    True)
        (clerk    (holds $u staff $x))
        (approver (And (holds $u clerk $x) (Not (holds $u auditor $x))))       ; the assignment
        (auditor  (And (holds $u staff $x) (Not (holds $u approver $x))))
        (admin    (holds $u staff $x)))))
  (Map assign (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x) (If (And (other-admin $u $x) (may-receive $u $r $x)) (grant $u $r $x) $x)))
  (Map revoke (Parameters ($u User) ($r Role)) (From Word) (To Word)
    (Body ($x)
      (If (other-admin $u $x)
          (Switch $r
            (staff    (drop $u staff (drop $u clerk (drop $u approver (drop $u auditor (drop $u admin $x))))))
            (clerk    (drop $u clerk (drop $u approver $x)))                    ; cascades
            (approver (drop $u approver $x))
            (auditor  (drop $u auditor $x))
            (admin    (drop $u admin $x)))
          $x)))
  (Machine Policy (States Word)
    (Observe (read $u)      (may-read $u)      (For $u User))
    (Observe (write $u)     (may-write $u)     (For $u User))
    (Observe (approve $u)   (may-approve $u)   (For $u User))
    (Observe (audit $u)     (may-audit $u)     (For $u User))
    (Observe (configure $u) (may-configure $u) (For $u User))
    (Action (assign $u $r)     (assign $u $r)     (For $u User) (For $r Role))
    (Action (revoke $u $r)     (revoke $u $r)     (For $u User) (For $r Role))
    (Action (activate $u $r)   (activate $u $r)   (For $u User) (For $r Role))
    (Action (deactivate $u $r) (deactivate $u $r) (For $u User) (For $r Role)))
  (Carrier Live (Of (BitVector 40)) (Reach Policy (From start)))
  (Machine LivePolicy (States Live) (Like Policy))                                          ; PROPOSED
  (Machine SoDWatch   (States Live) (Observe breach sod-breach) (ActionsOf Policy))
  (Machine ClerkWatch (States Live) (Observe clerkless clerkless-approval) (ActionsOf Policy))

  ;; safety certificates on the reachable configurations
  (BlockPartition NoBreach (On Live)
    (Block Quiet (Body ($x) (Not (sod-breach $x))) start) (Successor Any Quiet Quiet))
  (BlockPartition ClerksOnly (On Live)
    (Block Quiet (Body ($x) (Not (clerkless-approval $x))) start) (Successor Any Quiet Quiet))
  (BlockPartition ClerksOnlyProved (On Live)
    (Block Quiet (Body ($x) (Not (clerkless-approval $x))) start) (Successor Any Quiet Quiet)
    (Invariant consistent))                                                                 ; PROPOSED

  ;; compaction: assignments alone, the whole interface, and one targeted question
  (Map assignments (From Word) (To (BitVector 20))
    (Body ($x) (Gather $x 0 1 2 3 4 10 11 12 13 14 20 21 22 23 24 30 31 32 33 34)))       ; PROPOSED
  (Representation AssignmentsOnly (Of Policy) (Encode assignments))
  (Machine BobApproves     (States Word) (Observe approve-bob (may-approve bob)) (ActionsOf Policy))
  (Machine BobApprovesLive (States Live) (Observe approve-bob (may-approve bob)) (ActionsOf Policy))
  (Map bob-cone (From Word) (To (BitVector 17))
    (Body ($x) (Gather $x 0 4 9 10 11 12 13 14 17 18 19 20 24 29 30 34 39)))
  (Map bob-bits (From Word) (To (BitVector 10)) (Body ($x) (Slice $x 10 19)))
  (Representation BobCone (Of BobApproves) (Encode bob-cone))
  (Representation BobOnly (Of BobApproves) (Encode bob-bits))
  (Derive WholeInterface (MinimizeForQueries Policy))
  (Derive LiveInterface  (MinimizeForQueries LivePolicy))
  (Derive BobSlice       (InduceExact BobCone))
  (Derive BobQuotient    (MinimizeForQueries BobApproves))
  (Derive BobLiveQuotient (MinimizeForQueries BobApprovesLive)))
;; @end

;; @excerpt access-policy-fixed-requests
!(dc.run AccessPolicyFixed (CheckBlockPartition NoBreach (Of SoDWatch)))
!(dc.run AccessPolicyFixed (CheckBlockPartition ClerksOnly (Of ClerkWatch) (Budget (Unrollings 6))))
!(dc.run AccessPolicyFixed (CheckBlockPartition ClerksOnlyProved (Of ClerkWatch)))
!(dc.run AccessPolicyFixed (CheckNow AssignmentsOnly))
!(dc.run AccessPolicyFixed WholeInterface)
!(dc.run AccessPolicyFixed LiveInterface)
!(dc.run AccessPolicyFixed BobSlice)
!(dc.run AccessPolicyFixed (Defects BobOnly))
!(dc.run AccessPolicyFixed (InduceExact BobOnly))
!(dc.run AccessPolicyFixed (CheckBehavioral BobOnly))
!(dc.run AccessPolicyFixed BobQuotient)
!(dc.run AccessPolicyFixed BobLiveQuotient)
;; @end
