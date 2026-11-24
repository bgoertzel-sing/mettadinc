;; If/Eq/And/Or/Not forms still outside the M0 fragment: each answers Unsupported, and the reason names the form
;; (t-2026-11-23-mettadinc-m0-cases-logic).  Expected reasons: ../run_m0_cases_logic.py UNS.
;; UA: And with one operand
(DC.Module UA
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (And (Eq $s a)) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run UA (CheckNow R))
;; UB: Or with no operand
(DC.Module UB
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Or) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run UB (CheckNow R))
;; UC: Eq reading a Const (the lowering does not resolve Const names)
(DC.Module UC
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Const ka S a)
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Eq $s ka) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run UC (CheckNow R))
;; UD: If/Eq in a Graded module (lowered only in Crisp)
(DC.Module UD
  (Profile Graded)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Eq $s a) yes no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run UD (CheckNow R))
;; UE: control, an operator that stays outside (Sub), inside an If branch that is taken
(DC.Module UE
  (Profile Crisp)
  (Carrier S (Of Symbol) (Enum a b))
  (Carrier O (Of Symbol) (Enum yes no))
  (Map id (From S) (To S) (Cases ($s $s)))
  (Map ob (From S) (To O) (Cases ($s (If (Eq $s a) (Sub 1 1) no))))
  (Machine M (States S) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode id)))
!(dc.run UE (CheckNow R))
