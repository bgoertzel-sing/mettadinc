;; Negatives for t-2026-11-24-mettadinc-m0-body-maps: each module is well formed up to its Body map, and the Body
;; map breaks an admission obligation (spec 5.3 l.1784-1786: totality, outputs stay in the carrier; 5.4 l.1856:
;; Body binds its single argument).  Every request answers InvalidInput.
;; BN1: a value outside To (declared carriers): inc 2 = 3, not in N.
(DC.Module BN1
  (Profile Crisp)
  (Carrier N (Of Int) (Enum 0 1 2))
  (Map inc (From N) (To N) (Body ($n) (Add $n 1)))
  (Map id  (From N) (To N) (Cases ($n $n)))
  (Machine M (States N) (Observe id id) (Action inc inc))
  (Representation R (Of M) (Encode id)))
!(dc.run BN1 (CheckNow R))
;; BN2: not total (declared carriers): (Add $x 1) has no value on the largest Int, where it overflows
;; (the M0 evaluator's bounded arithmetic, review 4 F3).
(DC.Module BN2
  (Profile Crisp)
  (Carrier V (Of Int) (Enum 0 9223372036854775807))
  (Carrier N (Of Int) (Enum 1 2))
  (Map inc (From V) (To N) (Body ($x) (Add $x 1)))
  (Map id  (From V) (To V) (Cases ($v $v)))
  (Machine M (States V) (Observe inc inc) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run BN2 (CheckNow R))
;; BN3: a value outside the To type (type form): (Tuple $x $x) is a pair of pairs, not a (Tuple Symbol Symbol).
(DC.Module BN3
  (Profile Crisp)
  (Carrier Atom (Of Symbol) (Enum present absent))
  (Carrier Link (Of Symbol) (Enum old none))
  (Carrier All  (Of (Tuple Symbol Symbol)) (Product Atom Link))
  (Map dup  (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Body ($x) (Tuple $x $x)))
  (Map live (From All) (To Link) (Cases ((Tuple $g $l) $l)))
  (Map stay (From All) (To All) (Cases ($s $s)))
  (Machine M (States All) (Observe live live) (Action stay stay))
  (Representation R (Of M) (Encode dup)))
!(dc.run BN3 (CheckNow R))
;; BN4: not total (type form): (Add $x 1) has no value on (Tuple present old).
(DC.Module BN4
  (Profile Crisp)
  (Carrier Atom (Of Symbol) (Enum present absent))
  (Carrier Link (Of Symbol) (Enum old none))
  (Carrier All  (Of (Tuple Symbol Symbol)) (Product Atom Link))
  (Map bump (From (Tuple Symbol Symbol)) (To (Tuple Int)) (Body ($x) (Tuple (Add $x 1))))
  (Map live (From All) (To Link) (Cases ((Tuple $g $l) $l)))
  (Map stay (From All) (To All) (Cases ($s $s)))
  (Machine M (States All) (Observe live live) (Action stay stay))
  (Representation R (Of M) (Encode bump)))
!(dc.run BN4 (CheckNow R))
;; BN5: an update that leaves the state carrier (type form): lesion sends every state to (absent none), and the
;; states are the Subset Up, which excludes it.
(DC.Module BN5
  (Profile Crisp)
  (Carrier Atom (Of Symbol) (Enum present absent))
  (Carrier Link (Of Symbol) (Enum old none))
  (Carrier All  (Of (Tuple Symbol Symbol)) (Product Atom Link))
  (Map up (From All) (To Bool) (Cases ((Tuple present $l) True) ((Tuple absent $l) False)))
  (Carrier Up (Of (Tuple Symbol Symbol)) (Subset All up))
  (Map lesion (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Body ($x) (Tuple absent none)))
  (Map live (From All) (To Link) (Cases ((Tuple $g $l) $l)))
  (Machine M (States Up) (Observe live live) (Action lesion lesion))
  (Representation R (Of M) (Encode live)))
!(dc.run BN5 (CheckNow R))
;; BN6: a (To Bool) Observe map whose Body gives a value that is not True or False.
(DC.Module BN6
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map yes (From A) (To Bool) (Body ($a) $a))
  (Map id  (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe yes yes) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run BN6 (CheckNow R))
;; BN7: an unbound variable: the Body binds $x and uses $y (spec 5.4: Body binds its single argument lexically).
(DC.Module BN7
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map f  (From A) (To A) (Body ($x) $y))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe id id) (Action f f))
  (Representation R (Of M) (Encode id)))
!(dc.run BN7 (CheckNow R))
;; BN8: malformed: the binder is not a one-variable list.
(DC.Module BN8
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map f  (From A) (To A) (Body $x p))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe id id) (Action f f))
  (Representation R (Of M) (Encode id)))
!(dc.run BN8 (CheckNow R))
;; BN9: malformed: two binders (every core map is unary, spec 5.4 l.1851).
(DC.Module BN9
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Map f  (From A) (To A) (Body ($x $y) p))
  (Map id (From A) (To A) (Cases ($a $a)))
  (Machine M (States A) (Observe id id) (Action f f))
  (Representation R (Of M) (Encode id)))
!(dc.run BN9 (CheckNow R))
