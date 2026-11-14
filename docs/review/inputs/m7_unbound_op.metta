;; Neurosymbolic report audit.  Specification, Section 13.1.
;; @excerpt neural
(DC.Module NeuralAudit
  (Profile Crisp)
  (Use Neural)
  (Carrier Bit   (Of Nat) (Enum 0 1))
  (Carrier Input (Of (Tuple Nat Nat)) (Product Bit Bit))
  (Map xor       (From Input) (To Bit) (Cases ((Tuple $a $b) (Xor $a $b))))
  (Map first-bit (From Input) (To Bit) (Cases ((Tuple $a $b) $a)))
  (Map use-report    (From (Product Input Bit)) (To Bit) (Body ($xz) (GetTuple $xz 1)))
  (Map bypass-report (From (Product Input Bit)) (To Bit) (Body ($xz) (xorq (GetTuple $xz 0))))
  (Map stay (From Input) (To Input) (Cases ((Tuple $a $b) (Tuple $a $b))))
  (Machine Task (States Input) (Observe answer xor) (Action stay stay))
  (Representation SymbolicOld (Of Task) (Encode xor))
  (Representation SymbolicNew (Of Task) (Encode first-bit))
  (ReportSystem OldSystem (Input Input) (ReportType Bit) (Encoder xor) (Readout use-report))
  (ReportSystem NewSystem (Input Input) (ReportType Bit) (Encoder first-bit) (Readout bypass-report))
  (Measure Inputs (On Input) (Uniform))
  (PairLaw II (Independent Inputs Inputs) (Diagonal Included)))
;; @end
;; @excerpt neural-requests
!(dc.run NeuralAudit (CheckNow SymbolicOld))
!(dc.run NeuralAudit (CheckNow SymbolicNew))
!(dc.run NeuralAudit (CompareDistinctions SymbolicOld SymbolicNew (Under II)))
!(dc.run NeuralAudit (AuditIntervention (Systems OldSystem NewSystem)
                       (Intervention (SetReport 0)) (Task xor) (Under Inputs) (Metric Accuracy)))
!(dc.run NeuralAudit (Refine SymbolicNew (Preserve Encoding)))
!(dc.run NeuralAudit (MinimizeForQueries Task))
;; @end
