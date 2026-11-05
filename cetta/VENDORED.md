# Vendored Cetta

- Upstream: https://github.com/zariuq/CeTTa (branch `main`)
- Commit: 12da03b4b055bfecff2add505e7e1ad4125bb352 (2026-08-14 16:58:16 +0200, "purging surface slop", 215 commits; still the head of `main` per `git ls-remote` on 2026-11-05)
- Upstream tree: 0051faecb9dc21ab8907138155e2c4e606e1ccd3 (`git rev-parse 12da03b4^{tree}`)
- sha256 of `git ls-tree -r 12da03b4`: aaa5bb7d6c827ed7a6bb7b107e09367ea2672adc9c0f2f93baa109e41f488025
- Vendored: 2026-11-05, hive task t-2026-11-05-mettadinc-m0-prep, from the clone E0 inspected
  (projects/mettadinc/repos/cetta on pop-os), with
  `git -C <clone> archive --format=tar 12da03b4b055bfecff2add505e7e1ad4125bb352 | tar -x -C cetta`.
  3321 files (94 executable), no symlinks, no submodules, no `.git`, no build outputs.
- Why vendored: the plan pins this commit (Cetta work plan §2.1; DEPENDENCIES.json); Ben's decision 2 defines
  "green" against E0's baseline at this commit (`tools/cetta-baseline.sh`).

## Status: unmodified

This file is the only file under `cetta/` that is not upstream's. `tools/check-vendored-cetta.sh` checks that the
committed `cetta/` without this file has exactly the upstream tree hash above, and that the working tree has no
changes to tracked files. When M0 starts changing Cetta, record each change here (what, why, and whether it is
meant for upstream); upstream patches go to zariuq later through the operators' send-upstream, never pushed from
here.

Note: `cetta/.gitignore` (upstream's) ignores `/_archive/`, `/runtime/*` and other paths that upstream tracks; the
vendored files under them were added with `git add -f`. Use `git add -f` for new files there too.
