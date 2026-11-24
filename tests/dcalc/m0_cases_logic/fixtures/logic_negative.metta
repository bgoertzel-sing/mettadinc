;; Malformed uses of If/Eq/And/Or/Not in Crisp Cases bodies: each answers InvalidInput, and the reason names
;; the form (t-2026-11-23-mettadinc-m0-cases-logic).  Expected reasons: ../run_m0_cases_logic.py NEG.
;; NA: If condition not a Bool
(DC.Module NA
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If $s yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NA (CheckNow R))
;; NB: If with two arguments
(DC.Module NB
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Eq $s a) yes))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NB (CheckNow R))
;; NC: Eq with one argument
(DC.Module NC
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Eq $s) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NC (CheckNow R))
;; ND: Not of a non-Bool
(DC.Module ND
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Not $s) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run ND (CheckNow R))
;; NE: And with a non-Bool operand
(DC.Module NE
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (And (Eq $s a) $s) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NE (CheckNow R))
;; NF: Or with a non-Bool operand
(DC.Module NF
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Or (Eq $s b) $s) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NF (CheckNow R))
;; NG: a Bool value in a carrier without True/False (the map's To carrier is S)
(DC.Module NG
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To S) (Cases ($s (Eq $s a))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NG (CheckNow R))
;; NH: Not with two arguments, in a type-form map
(DC.Module NH
  (Profile Crisp)
  (Carrier A (Of Symbol) (Enum p q))
  (Carrier AA (Of (Tuple Symbol Symbol)) (Product A A))
  (Map id (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Cases ((Tuple $a $b) (Tuple $a $b))))
  (Map pick (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Cases ((Tuple $a $b) (If (Not (Eq $a p) (Eq $b p)) (Tuple $a $b) (Tuple $b $a)))))
  (Machine M (States AA) (Observe id id) (Action pick pick))
  (Representation R (Of M) (Encode id)))
!(dc.run NH (CheckNow R))
;; NI: a Subset predicate whose If condition is not a Bool
(DC.Module NI
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Map keep (From S) (To Bool) (Cases ($s (If $s True False))))
  (Carrier T (Of Symbol) (Subset S keep))
  (Map id (From T) (To T) (Cases ($s $s)))
  (Machine M (States T) (Observe id id) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run NI (CheckNow R))
