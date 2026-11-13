;; M6 review-2 F4 probe: Def 10.2 intertwining is on method parts only.
;; Response [m = m0] on both states; identity transfers both ways; a gauge at A
;; swapping the two equal-response states with identity methods. Coherent per spec.
(DC.Module Iw2
  (Profile Crisp)
  (Use Transfers Hives)
  (Carrier S (Of Symbol) (Enum s0 s1))
  (Carrier M (Of Symbol) (Enum m0 m1))
  (Carrier Bit (Of Nat) (Enum 0 1))
  (Map isM0 (From (Product S M)) (To Bit)
    (Cases ((Tuple s0 m0) 1) ((Tuple s0 m1) 0) ((Tuple s1 m0) 1) ((Tuple s1 m1) 0)))
  (Map idS (From S) (To S) (Cases (s0 s0) (s1 s1)))
  (Map swS (From S) (To S) (Cases (s0 s1) (s1 s0)))
  (Map idM (From M) (To M) (Cases (m0 m0) (m1 m1)))
  (MethodSystem A (States S) (Methods M) (Response isM0))
  (MethodSystem B (States S) (Methods M) (Response isM0))
  (Transfer AB (Source A) (Target B) (StatePullback idS) (MethodPushforward idM))
  (Transfer BA (Source B) (Target A) (StatePullback idS) (MethodPushforward idM))
  (Symmetry SwapA (Of A) (States swS) (Methods idM))
  (TransferHive H (Member A) (Member B) (Edge AB) (Edge BA) (Cycle A B) (Gauge A SwapA)))
!(dc.run Iw2 (CheckTransferHive H))
!(dc.run Iw2 (KernelOf H (Saturate Gauge)))
