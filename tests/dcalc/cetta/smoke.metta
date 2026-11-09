!(import! &self dcalc)
!(dcalc:run-file "@FIXTURES@/eight_state.metta" EightState AB)
!(dcalc:run-file "@FIXTURES@/hypotheses.metta" LiteralCongruence (InduceExact Blurred))
!(dcalc:run "(DC.Module T (Carrier B (Of Nat) (Enum 0 1)))" T (MeasureNow Nope))
