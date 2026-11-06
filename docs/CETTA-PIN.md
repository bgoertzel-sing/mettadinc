# Cetta pin

Cetta is a git submodule at `cetta/`, pinned to zariuq/CeTTa `main` as Zar asked (work group, 2026-11-06).

- Upstream: https://github.com/zariuq/CeTTa (branch `main`)
- Commit: 4c285a97fd8c60e3c3fccd5ccd3b3e5e0ebccb4c (2026-11-05 20:26:01 +0100, "WIP: make pre-main shareable and preserve benchmark evidence", 486 commits)
- Upstream tree: 8424ec7a3c3fdd9f9b24321f29ce95a50d910a99 (`git rev-parse 4c285a97^{tree}`)
- Pinned: 2026-11-06, hive task t-2026-11-06-mettadinc-cetta-pin-latest. `git ls-remote https://github.com/zariuq/CeTTa
  refs/heads/main` returned 4c285a97 at 2026-11-06T05:09:49Z, when the task started (the SHA named when the task was filed).
- Previous pin: 12da03b4b055bfecff2add505e7e1ad4125bb352 (2026-08-14, "purging surface slop", tree 0051faec), pinned by
  hive task t-2026-11-06-mettadinc-m0-prep-submodule. 4c285a97 descends from it: 271 commits later, 6682 files changed.
- Why this commit: Zar asked us to use his latest main. Ben's decision 2 defined "green" against E0's baseline at 12da03b4;
  the plan is to re-freeze the baseline from runs at this pin and name every test that was green at 12da03b4 and is not
  green now in [CETTA-LATEST.md](CETTA-LATEST.md).
- **Status 2026-11-06: 4c285a97 does not build unmodified with gcc on pop-os** (DT_RELR link probe; gcc 11 `-Werror`
  errors). By the hive decision it is built with make command-line **build overrides** only (no Cetta file changed):
  `MDINC_MAKE_ARGS="PACK_RELATIVE_RELOCS= 'CFLAGS=-O3 -Wall -Werror -std=c11 -pthread -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized'"`.
  The baseline is **green at 4c285a97 with build overrides (see [CETTA-LATEST.md](CETTA-LATEST.md))**, with SWI-Prolog
  9.2.9 for the rhocalc lane: set `MDINC_SWIPL_DIR` to its install prefix (on pop-os
  `$HOME/scratch/mettadinc-e0/swipl9/install`, built from source without sudo); `tools/cetta-baseline.sh` puts
  `$MDINC_SWIPL_DIR/bin` first on PATH and records the swipl path and version in summary.txt and every lane log (unset,
  it changes nothing, and the rhocalc lane fails unless a 9.x `swipl` is already on PATH). `tools/cetta-baseline.expected` was re-frozen (hive answer 2)
  from the run `evidence/cetta-pin-latest/cetta-baseline/latest-run3-swipl`: rhocalc 285 passed / 0 failed,
  core 704 PASS / 84 SKIP / 0 FAIL, python 709 / 80 / 0, with `test-test-target-scope` ("Argument list too long",
  upstream issue 6) frozen as the one expected failed target in core and python. Against it the harness is GREEN in all
  three lanes, and a broken test turns it RED (`evidence/cetta-pin-latest/`, run4/run5). Every test that was green at
  12da03b4 and is not green now is named in CETTA-LATEST.md and MISSING.md, with the upstream issues for Zar. The
  harness's default (no MDINC_MAKE_ARGS) remains the unmodified build, which does not build on pop-os at this pin.
  A green rhocalc run rewrites the tracked file `direct_runtime_lock_v1.metta` (upstream issue 7), so restore it
  (`git -C cetta checkout -- .`) before the pin check below.

## Fetching it

```sh
git clone https://github.com/bgoertzel-sing/mettadinc && cd mettadinc
git submodule update --init      # checks out cetta/ at the recorded commit
tools/check-vendored-cetta.sh    # the pin check, below
```

## Status: unmodified

`tools/check-vendored-cetta.sh` is the pin check. It exits 0 only if the gitlink recorded for `cetta/` in HEAD equals the
Commit line above, and the submodule checkout is at that commit with no change to tracked files and no untracked
files outside upstream's `.gitignore` (build outputs that upstream ignores are allowed).

When M0 starts changing Cetta, the change goes to a Cetta branch and the gitlink moves to it; record each change here
(what, why, and whether it is meant for upstream) and update the Commit line. Upstream patches go to zariuq later through
the operators' send-upstream, never pushed from here.
