;; monitors-followups item 3: a context carrier with two elements and an If-bodied law, so CheckMonitor's
;; per-context loop runs twice.  In context a the null is Bernoulli 1/4, in b it is Bernoulli 1/2;
;; the alternative is Bernoulli 1/2 in both: chi2(a) = 1/3, chi2(b) = 0, NullMean 1 in both.
(DC.Module MonCtx
  (Profile Stochastic)
  (Use Decisions Laws Families Monitors)
  (Carrier Two (Of Symbol) (Enum a b))
  (Map nul (From Two) (To (Law Nat)) (Body ($u) (Coin (If (Eq $u a) (Rat 1 4) (Rat 1 2)))))
  (Map alt (From Two) (To (Law Nat)) (Body ($u) (Coin (Rat 1 2))))
  (Monitor Split (Context Two) (Null (nul)) (Alternative (alt)) (Columns (observation "x")))
  (Monitor Flat  (Context Two) (Null (alt)) (Alternative (alt)) (Columns (observation "x"))))
!(dc.run MonCtx (CheckMonitor Split))
!(dc.run MonCtx (CheckMonitor Flat))
