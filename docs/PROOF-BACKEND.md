# dcalc proof backend pin (M3, spec 15.3)

Symbolic carriers (M3) answer Checked only with a solver proof replayed by an
independent checker. The pipeline is pinned:

| tool | pin | source archive sha256 |
|---|---|---|
| CaDiCaL (solver, LRAT) | tag rel-3.0.1 | 0a8ea563b5a25f5aa064634814edab45cc0e45111ea0f5d412a565f806fd7e11 |
| cake_lpr (checker) | commit 033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2 | cde6b4359c57648bf92be86bbbd89891bff0e145eefbffb7140f9e4d4d094391 |
| obligation generator | dcalc-symgen m3.1 (in src/dcalc/ops_sym.c) | - |

## Environment

- `DCALC_CADICAL`: path to the CaDiCaL binary (required).
- `DCALC_CAKE_LPR`: path to the cake_lpr binary (required).
- `DCALC_PROOF_DIR`: scratch directory for CNF/LRAT files (optional).
- `DCALC_CADICAL_SHA256`, `DCALC_CAKE_LPR_SHA256`: optional binary sha256 pins.

## What dcalc enforces

Once per process, before the first proof, dcalc runs `$DCALC_CADICAL --version`
and refuses the backend unless it prints `3.0.1`. It hashes both binaries; if the
optional `*_SHA256` variables are set the hashes must match. A refused backend
means no Checked answers: decision-diagram results stay Conditional, with the
reason in the envelope. Every Proof form records `SolverSha256` and
`CheckerSha256` (the binaries actually used), the CNF sha256 and the generator
version. cake_lpr has no version flag; its pin is the source archive hash above
plus the recorded binary hash.

Without the backend, `tools/dcalc-run-all.sh` stops with exit 2, and the
forty-bit rows of check_claims.py would be Conditional (negative test 6).

**Memory limit.** cake_lpr reserves about 8 GB of virtual memory at start. Under a
`ulimit -v` below that it exits 3, the proof is not verified and every answer that
needed it degrades to Conditional. Run the gates with `ulimit -v unlimited` (or at
least 9 GB).

**Gate dependencies.** `tests/dcalc/mutations/run_m3_gates.py` needs only the Python 3
standard library (no numpy) and the binaries built by `make tests` (including
`build/dcalc/screen_m3`, which negative gate 7 runs). It works with or without the
`DCALC_*_SHA256` pins set; with them set it also checks that a different solver
binary is refused (neg 3b).

## Build

`tools/dcalc-proof-backend.sh DIR` downloads the two archives, verifies the
sha256 values above, builds both tools in DIR and prints the `export` lines.
