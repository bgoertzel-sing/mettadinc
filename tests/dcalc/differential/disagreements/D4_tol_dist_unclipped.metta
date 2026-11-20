;; D4 second site (review-1 F2, t-2026-11-19-mettadinc-d4-contract-clip): dc_tol_dist (model.c, DC_TOL_ONE_MINUS_ABS).
;; Graded machine, states P,Q fixed by step, observations 0 and 2 under OneMinusAbsoluteDifference.
;; Spec l.686-694: distance = 1 - max(0, 1 - |p - q|) = min(1, |2 - 0|) = 1, so d(P,Q) = 1 and the kernel degree is 0.
;; Unclipped |p - q| = 2 gives a degree of -1, outside [0, 1].
(DC.Module D4Tol
  (Profile Graded)
  (Carrier S (Of Symbol) (Enum P Q))
  (Map obs (From S) (To Rational) (Cases (P 0) (Q 2)))
  (Map step (From S) (To S) (Cases (P P) (Q Q)))
  (Tolerance Gap (On Rational) (OneMinusAbsoluteDifference))
  (Machine M (States S)
    (Observe obs obs (Values Gap))
    (Action step step)))
!(dc.run D4Tol (BehavioralTolerance M))
