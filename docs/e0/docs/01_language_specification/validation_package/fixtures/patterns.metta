;; Patterns as checked descriptions with cost.  Specification, Section 12.6.
;; @excerpt patterns
(DC.Module Patterns
  (Profile Crisp)
  (Use Hyperseed)
  (DescriptionSystem Streams
    (Description Literal6 (Literal (Tokens A B A B A B)))
    (Description RepeatAB (Repeat (Tokens A B) 3))
    (Decoder Expand)
    (Cost (Tokens 1) (Operator 1) (Count 1))
    (Baseline Literal6))
  (PatternWitness Periodic (System Streams) (Target (Tokens A B A B A B)) (Description RepeatAB)))
;; @end
!(dc.run Patterns (FindCheapestDescription Streams (Target (Tokens A B A B A B))))
!(dc.run Patterns (CheckPatternWitness Periodic))
