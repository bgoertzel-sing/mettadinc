#!/usr/bin/env bash
# Pin check: is cetta/ the submodule zariuq/CeTTa at the commit recorded in docs/CETTA-PIN.md, unmodified?
# Exit 0 yes, 1 no.  Checks that
#   1. the gitlink for cetta/ in HEAD equals the Commit line of docs/CETTA-PIN.md;
#   2. the submodule checkout cetta/ is at that commit (fetch it with `git submodule update --init`);
#   3. the checkout is clean: no change to tracked files, and no untracked files outside upstream's .gitignore
#      (build outputs that upstream ignores are allowed).
# (The file keeps its m0-prep name; with the submodule it checks the pin instead of a vendored copy.)
set -eu
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO"
want=$(sed -n 's/^- Commit: \([0-9a-f]\{40\}\).*/\1/p' docs/CETTA-PIN.md | head -1)
[ -n "$want" ] || { echo "docs/CETTA-PIN.md: no '- Commit: <40-hex SHA>' line"; exit 1; }
link=$(git ls-tree HEAD cetta | awk '$2 == "commit" { print $3 }')
echo "pin (docs/CETTA-PIN.md):  $want"
echo "gitlink HEAD:cetta:       ${link:-none}"
st=0
if [ "$link" = "$want" ]; then echo "gitlink: equals the pin"; else echo "gitlink: DIFFERS from the pin (or cetta/ is not a submodule)"; st=1; fi
if ! git -C cetta rev-parse --git-dir >/dev/null 2>&1 || [ "$(git -C cetta rev-parse --show-toplevel)" != "$REPO/cetta" ]; then
  echo "checkout cetta/: not initialised (run: git submodule update --init)"; exit 1
fi
head=$(git -C cetta rev-parse HEAD)
echo "checkout cetta/ HEAD:     $head"
if [ "$head" = "$want" ]; then echo "checkout: at the pin"; else echo "checkout: NOT at the pin"; st=1; fi
dirty=$(git -C cetta status --porcelain --untracked-files=all)
if [ -z "$dirty" ]; then echo "checkout: clean (no tracked changes, no untracked files outside upstream's .gitignore)"
else echo "checkout: NOT clean:"; echo "$dirty" | head -50; st=1; fi
exit $st
