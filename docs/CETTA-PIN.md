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
  with this pin the baseline is re-frozen from the runs at 4c285a97 (`evidence/cetta-pin-latest/`), and every test that
  was green at 12da03b4 and is not green now is named in [CETTA-LATEST.md](CETTA-LATEST.md).

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
