# Cetta pin

Cetta is a git submodule at `cetta/`, pinned to the commit the Cetta work plan names (§2.1; DEPENDENCIES.json).

- Upstream: https://github.com/zariuq/CeTTa (branch `main`)
- Commit: 12da03b4b055bfecff2add505e7e1ad4125bb352 (2026-08-14 16:58:16 +0200, "purging surface slop", 215 commits)
- Upstream tree: 0051faecb9dc21ab8907138155e2c4e606e1ccd3 (`git rev-parse 12da03b4^{tree}`)
- Pinned: 2026-11-06, hive task t-2026-11-06-mettadinc-m0-prep-submodule. This replaces the copy of the same commit
  that hive task t-2026-11-05-mettadinc-m0-prep had vendored under `cetta/` (same tree, 0051faec); that copy is not
  in this branch's history. On 2026-11-06 upstream `main` had moved past the pin (4c285a97); moving to a newer Cetta
  is a separate task.
- Why this commit: Ben's decision 2 defines "green" against E0's baseline at this commit (`tools/cetta-baseline.sh`).

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
