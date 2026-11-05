;; Space-backed carrier with an explicit key binding.  Specification, Section 5.3.
;; The first release answers requests on this module with Unsupported.
;; @excerpt snapshot
(DC.Module SnapshotReceipts
  (Profile (Dynamics Deterministic) (Values Crisp) (Carriers Snapshot))
  (Type ReceiptId Symbol)
  (Snapshot Receipts2026 (Space receipts) (Digest "sha256:0000000000000000000000000000000000000000000000000000000000000000")
    (Revision 1187))
  (Carrier Receipt (Of ReceiptId) (Query Receipts2026 (receipt $id $src $time) (Key $id)))
  (Carrier Source (Of Symbol) (Query Receipts2026 (receipt $id $src $time) (Key $src)))
  (Map source-of (From Receipt) (To Source) (Query Receipts2026 (receipt $id $src $time) (Key $id) (Value $src)))
  (Map hold (From Receipt) (To Receipt) (Body ($r) $r))
  (Machine Ledger (States Receipt) (Observe source source-of) (Action hold hold))
  (Representation BySource (Of Ledger) (Encode source-of)))
;; @end
!(dc.run SnapshotReceipts (CheckNow BySource))
