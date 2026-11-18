;; D-kant-classpairs (t-2026-11-18-mettadinc-m4m6-differential): minimal input.
;; a, b, c report 0; p reports 1, q reports 2 (absorbing). a -> p, c -> q, b -> 1/2 p + 1/2 q.
;; The encoding sends a, b, c to the representative b.
;; d_beh(a,c) = 1, d_beh(a,b) = d_beh(b,c) = 1/2 (horizon 1 and unbounded, discount 1).
;; Spec Def 4.4(3) + l.1080: for a crisp encoding, delta_beh is "the largest behavioral distance between
;; two states with the same code" -> max over ALL same-code pairs = d(a,c) = 1.
;; Oracle (spec): Checked, BehavioralDefect 1. dcalc (pairs with the representative only): see report.
;; Found as seed 100 case 177 of run_diff.py (dcalc 17/192 vs oracle 5/48 at horizon 3).
(DC.Module DKantClassPairs
  (Profile Stochastic)
  (Carrier S (Of Symbol) (Enum a b c p q))
  (Carrier Report (Of Nat) (Enum 0 1 2))
  (Map report (From S) (To Report) (Cases (a 0) (b 0) (c 0) (p 1) (q 2)))
  (TransitionKernel Step (From S) (To S)
    (Row a (Mass p 1)) (Row b (Mass p (Rat 1 2)) (Mass q (Rat 1 2))) (Row c (Mass q 1))
    (Row p (Mass p 1)) (Row q (Mass q 1)))
  (Machine Chain (States S) (Observe report report) (Action step Step))
  (Map enc (From S) (To S) (Cases (a b) (b b) (c b) (p p) (q q)))
  (Representation Rep (Of Chain) (Encode enc)))
!(dc.run DKantClassPairs (MeasureBehavioral Rep (Horizon (Steps 1))))
!(dc.run DKantClassPairs (MeasureBehavioral Rep))
