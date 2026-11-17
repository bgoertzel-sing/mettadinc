;; @excerpt literal-congruence
(DC.Module LiteralCongruence
  (Profile Crisp)
  (Carrier Three (Of Nat) (Enum 0 1 2))
  (Carrier Unit  (Of Nat) (Enum 0))
  (Carrier Bit   (Of Nat) (Enum 0 1))
  (Map none  (From Three) (To Unit) (Table (0 0) (1 0) (2 0)))
  (Map hop   (From Three) (To Three) (Table (0 0) (1 2) (2 2)))
  (Map split (From Three) (To Bit) (Table (0 0) (1 0) (2 1)))
  (Tolerance AllCodes (On Bit) (Trivial))
  (Machine M (States Three) (Observe none none) (Action hop hop))
  (Representation Blurred (Of M) (Encode split) (Codes AllCodes)))
!(dc.run LiteralCongruence (MeasureNow Blurred))
!(dc.run LiteralCongruence (CheckUpdates Blurred))
!(dc.run LiteralCongruence (InduceExactly Blurred))
;; @end
