#!/usr/bin/env bash
# Is cetta/ still upstream zariuq/CeTTa 12da03b4, unmodified?  Exit 0 yes, 1 no.
# Compares the tree of cetta/ in HEAD, without cetta/VENDORED.md, with the upstream tree hash recorded in
# cetta/VENDORED.md, and reports any uncommitted change to tracked files under cetta/.
set -eu
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO"
want=$(sed -n 's/^- Upstream tree: \([0-9a-f]\{40\}\).*/\1/p' cetta/VENDORED.md)
idx=$(mktemp); trap 'rm -f "$idx"' EXIT; rm -f "$idx"
git ls-tree -r HEAD:cetta | grep -v $'\tVENDORED.md$' | GIT_INDEX_FILE="$idx" git update-index --index-info
got=$(GIT_INDEX_FILE="$idx" git write-tree)
files=$(git ls-tree -r HEAD:cetta | grep -vc $'\tVENDORED.md$')
echo "upstream tree (VENDORED.md): $want"
echo "HEAD:cetta minus VENDORED.md: $got ($files files)"
st=0
if [ "$got" = "$want" ]; then echo "committed cetta/: identical to upstream 12da03b4"; else echo "committed cetta/: DIFFERS from upstream"; st=1; fi
if git diff --quiet HEAD -- cetta; then echo "working tree cetta/: no changes to tracked files"
else echo "working tree cetta/: tracked files changed:"; git diff --stat HEAD -- cetta; st=1; fi
exit $st
