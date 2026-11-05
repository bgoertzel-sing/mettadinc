;; Schemas and methods.  Specification, Section 12.5.
;; @excerpt methods
(DC.Module HyperseedMethods
  (Profile Graded)
  (Use Hyperseed FiniteSets)
  (Import HyperseedMemory (Only Memory PosteriorOnly))
  (Schema MemoryContract
    (Parameters ($machine InterfaceRef) ($encoding MapRef))
    (Build (Representation (Of $machine) (Encode $encoding))))
  (Method RepairMemory
    (Parameters ($q RepresentationRef))
    (Returns ExactAbstraction)
    (Body
      (LetResult $repair (Refine $q (Preserve Encoding) (Until Stable))
        (InduceExact (Output $repair Representation)))))
  (Derive Repaired (RepairMemory PosteriorOnly)))
;; @end
!(dc.run HyperseedMethods Repaired)
