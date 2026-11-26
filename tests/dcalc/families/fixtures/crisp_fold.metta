;; t-2026-11-26-mettadinc-families-followups-v2 step 2: specific verdicts for the Families Eq and And folds in a
;; Crisp module (crisp_eq.metta only checks "not InvalidInput").  States low mid high; R merges all three into one
;; code k, so CheckNow is Refuted exactly when the observation differs between states, else Checked.
;;  FE (Eq): obs low = (Eq low low) = True, mid = (Eq mid low) = False, high = (Eq high high) = True.
;;      R (all one code): Refuted (low True vs mid False).  RH ({low,high} -> k1, mid -> k2): Checked.
;;      An Eq-of-symbols-always-false mutant gives all False: R Checked (caught).  Always-true: R Checked (caught).
;;  FA (And): obs low = (And (Eq low low) (Eq high high)) = True, mid = (And (Eq mid mid) (Eq low high)) = False,
;;      high = (And (Eq high high) (Eq mid mid)) = True.  R: Refuted.  RH: Checked.
;;      An And-folded-as-Or mutant gives mid = True, all True: R Checked (caught).
;;  FO (Or control): obs low = (Or (Eq low high) (Eq mid mid)) = True, mid = (Or (Eq mid low) (Eq high low)) = False,
;;      high = True.  R: Refuted.  RH: Checked.  (An Or-folded-as-And mutant gives low False: RH Refuted.)
(DC.Module FE
  (Profile Crisp)
  (Use Families)
  (Carrier Lvl (Of Symbol) (Enum low mid high))
  (Carrier K (Of Symbol) (Enum k1 k2))
  (Map ob (From Lvl) (To Bool) (Cases (low (Eq low low)) (mid (Eq mid low)) (high (Eq high high))))
  (Map id (From Lvl) (To Lvl) (Cases ($a $a)))
  (Map one (From Lvl) (To K) (Cases ($a k1)))
  (Map hl (From Lvl) (To K) (Cases (low k1) (mid k2) (high k1)))
  (Machine M (States Lvl) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode one))
  (Representation RH (Of M) (Encode hl)))
!(dc.run FE (CheckNow R))
!(dc.run FE (CheckNow RH))
(DC.Module FA
  (Profile Crisp)
  (Use Families)
  (Carrier Lvl (Of Symbol) (Enum low mid high))
  (Carrier K (Of Symbol) (Enum k1 k2))
  (Map ob (From Lvl) (To Bool) (Cases (low (And (Eq low low) (Eq high high))) (mid (And (Eq mid mid) (Eq low high))) (high (And (Eq high high) (Eq mid mid)))))
  (Map id (From Lvl) (To Lvl) (Cases ($a $a)))
  (Map one (From Lvl) (To K) (Cases ($a k1)))
  (Map hl (From Lvl) (To K) (Cases (low k1) (mid k2) (high k1)))
  (Machine M (States Lvl) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode one))
  (Representation RH (Of M) (Encode hl)))
!(dc.run FA (CheckNow R))
!(dc.run FA (CheckNow RH))
(DC.Module FO
  (Profile Crisp)
  (Use Families)
  (Carrier Lvl (Of Symbol) (Enum low mid high))
  (Carrier K (Of Symbol) (Enum k1 k2))
  (Map ob (From Lvl) (To Bool) (Cases (low (Or (Eq low high) (Eq mid mid))) (mid (Or (Eq mid low) (Eq high low))) (high (Or (Eq high high) (Eq low mid)))))
  (Map id (From Lvl) (To Lvl) (Cases ($a $a)))
  (Map one (From Lvl) (To K) (Cases ($a k1)))
  (Map hl (From Lvl) (To K) (Cases (low k1) (mid k2) (high k1)))
  (Machine M (States Lvl) (Observe ob ob) (Action id id))
  (Representation R (Of M) (Encode one))
  (Representation RH (Of M) (Encode hl)))
!(dc.run FO (CheckNow R))
!(dc.run FO (CheckNow RH))
