#!/usr/bin/env bash
# Diagnostic only (not a baseline run): the rhocalc lane's command with a user-local SWI-Prolog 8.4.2 on PATH
# (Ubuntu jammy swi-prolog-core, -core-packages, -nox debs, extracted with dpkg -x; no pkg-config file is exposed,
# so the build's ENABLE_LIB_PROLOG=auto probe is unaffected).  Same build overrides as latest-run2-overrides.
# The extracted tree needs its autoload index built once, as the Debian postinst does:
#   swipl -g "make_library_index('<root>/usr/lib/swi-prolog/library'), halt."
set -u
cd "$(dirname "$0")/../.."
L=$PWD/build/cetta-baseline/diag-rhocalc-swipl; mkdir -p "$L"
export PATH=$HOME/scratch/mettadinc-e0/deps-swipl/bin:$PATH METTAPEDIA_ROOT=$PWD/build/no-mettapedia-here
P=$HOME/scratch/mettadinc-e0/deps/root/usr   # GMP headers, as MDINC_GMP_PREFIX in the harness
export CPATH="$P/include:$P/include/x86_64-linux-gnu" LIBRARY_PATH="$P/lib/x86_64-linux-gnu:$P/lib"
unset RHOLANG_CLI
s=$(date +%s)
{ echo "== swipl: $(command -v swipl) =="; swipl -g "current_prolog_flag(version,V), writeln(V), halt."
  echo "== make PACK_RELATIVE_RELOCS= 'CFLAGS=-O3 -Wall -Werror -std=c11 -pthread -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized' BUILD=core test-rhocalc =="
  (cd cetta && make PACK_RELATIVE_RELOCS= 'CFLAGS=-O3 -Wall -Werror -std=c11 -pthread -Wno-error=stringop-overflow -Wno-error=maybe-uninitialized' BUILD=core test-rhocalc)
  echo "EXIT=$? SECS=$(( $(date +%s) - s ))"; } > "$L/04_test_rhocalc.log" 2>&1
mkdir -p evidence/cetta-pin-latest/cetta-baseline/diag-rhocalc-swipl; cp "$L/04_test_rhocalc.log" evidence/cetta-pin-latest/cetta-baseline/diag-rhocalc-swipl/
echo done > "$L.done"
