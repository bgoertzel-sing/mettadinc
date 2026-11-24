;; D6-trace-classpairs (t-2026-11-20-mettadinc-d6-trace-check): minimal input.
;; a, b, c report 0; p reports 1, q reports 2 (absorbing). a -> p, c -> q, b -> 1/2 p + 1/2 q.
;; The encoding sends a, b, c to the representative b, so {a, b, c} is one 3-state class.
;; Spec Def 4.4(4) (l.1044-1059): delta_tr^h = max over same-code pairs x, x' of max_w TV(P_x^w, P_x'^w).
;; For h >= 1: TV(a, c) = 1, TV(a, b) = TV(b, c) = 1/2, so the spec answer is 1 (pair a, c).
;; dcalc (stoch.c MeasureTrace/CheckTrace with Horizon) compares x only with E(x) and reports 1/2 (pair b a).
;; EXPECTED-BUG canary in gate.sh asserts today's 1/2; flip it to 'TraceDefect 1' when D6 is fixed.
(DC.Module DTraceClassPairs
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
!(dc.run DTraceClassPairs (MeasureTrace Rep (Horizon (Steps 1))))
!(dc.run DTraceClassPairs (MeasureTrace Rep (Horizon (Steps 3))))
!(dc.run DTraceClassPairs (MeasureTrace Rep (Horizon (Steps 1)) (Policies ObservationBased)))
!(dc.run DTraceClassPairs (CheckTrace Rep (Horizon (Steps 1)) (Within (Rat 3 4))))
!(dc.run DTraceClassPairs (CheckTrace Rep))
