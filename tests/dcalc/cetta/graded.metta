; Review-1 F3: the CeTTa lane must reach the M2 graded path, not only crisp M1 requests.
!(import! &self dcalc)
!(dcalc:run-file "@FIXTURES@/graded_closure.metta" GradedClosure Increase)
!(dcalc:run-file "@FIXTURES@/graded_closure.metta" GradedClosure (CheckTransitive Alpha))
!(dcalc:run-file "@ROOT@/tests/dcalc/claimless/min_pairs.metta" MinPairs (MinimizeForQueries M))
