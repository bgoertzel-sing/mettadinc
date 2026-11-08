; Review-2 finding 1: the documented thin surface lib/dcalc.metta must reduce.
!(import! &self dcalc)
!(import! &self @ROOT@/lib/dcalc)
!(dc.field (dc.run-file "@FIXTURES@/eight_state.metta" EightState AB) Status)
!(dc.status (dc.run-file "@FIXTURES@/hypotheses.metta" LiteralCongruence (InduceExact Blurred)))
!(dc.status (dc.run-source "(DC.Module T (Carrier B (Of Nat) (Enum 0 1)))" T (MeasureNow Nope)))
