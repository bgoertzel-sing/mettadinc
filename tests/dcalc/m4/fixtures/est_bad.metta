;; M4-estimates smoke fixture: one frozen Stream, EstimateRate only.
(DC.Module EstSmoke
  (Profile Stochastic)
  (Use Estimates)
  (Stream RepliesBefore (Source "replies_before.json")
    (Digest "sha256:3a5629468d69aba06e30587dfc23114cbf4ed6e545e426ed4d77c08caf799703")
    (Provenance "copy of the WMTM validation bundle stream")
    (Population "replies to items at most seven days old at the next cycle")
    (Selection "the rows of Replies released on days 0-21")
    (Policy "log-only phase; parser v1")))
!(dc.run EstSmoke
   (EstimateRate (On RepliesBefore) (Column "stale") (Equals 1) (Level (Rat 1 100))))
