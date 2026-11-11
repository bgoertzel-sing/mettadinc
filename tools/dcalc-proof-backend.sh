#!/bin/sh
# Fetch, verify and build the pinned M3 proof backend (docs/PROOF-BACKEND.md).
#   tools/dcalc-proof-backend.sh DIR   -> prints export lines for DCALC_CADICAL / DCALC_CAKE_LPR
# Archives are refused unless their sha256 matches the pin. Needs curl or wget, gcc, make.
set -eu
D=${1:?usage: dcalc-proof-backend.sh DIR}
mkdir -p "$D"; cd "$D"; D=$(pwd)
CAD_URL=https://github.com/arminbiere/cadical/archive/refs/tags/rel-3.0.1.tar.gz
CAD_TGZ=cadical-rel-3.0.1.tar.gz
CAD_SHA=0a8ea563b5a25f5aa064634814edab45cc0e45111ea0f5d412a565f806fd7e11
CAKE_REV=033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2
CAKE_URL=https://github.com/tanyongkiam/cake_lpr/archive/$CAKE_REV.tar.gz
CAKE_TGZ=cake_lpr-033aad5.tar.gz
CAKE_SHA=cde6b4359c57648bf92be86bbbd89891bff0e145eefbffb7140f9e4d4d094391
fetch() { [ -f "$2" ] && return 0
  if command -v curl >/dev/null; then curl -fsSL -o "$2" "$1"; else wget -q -O "$2" "$1"; fi; }
verify() { got=$(sha256sum "$1" | cut -d' ' -f1)
  [ "$got" = "$2" ] || { echo "sha256 mismatch for $1: $got (pin $2)" >&2; exit 3; }; }
fetch "$CAD_URL" "$CAD_TGZ"; verify "$CAD_TGZ" "$CAD_SHA"
fetch "$CAKE_URL" "$CAKE_TGZ"; verify "$CAKE_TGZ" "$CAKE_SHA"
[ -d cadical-rel-3.0.1 ] || tar xzf "$CAD_TGZ"
[ -d cake_lpr-$CAKE_REV ] || tar xzf "$CAKE_TGZ"
[ -x cadical-rel-3.0.1/build/cadical ] || (cd cadical-rel-3.0.1 && ./configure >/dev/null && make -j1 >/dev/null)
[ -x cake_lpr-$CAKE_REV/cake_lpr ] || (cd cake_lpr-$CAKE_REV && make cake_lpr >/dev/null)
v=$(cadical-rel-3.0.1/build/cadical --version)
[ "$v" = 3.0.1 ] || { echo "built solver reports $v, not 3.0.1" >&2; exit 4; }
echo "export DCALC_CADICAL=$D/cadical-rel-3.0.1/build/cadical"
echo "export DCALC_CAKE_LPR=$D/cake_lpr-$CAKE_REV/cake_lpr"
echo "export DCALC_CADICAL_SHA256=$(sha256sum cadical-rel-3.0.1/build/cadical | cut -d' ' -f1)"
echo "export DCALC_CAKE_LPR_SHA256=$(sha256sum cake_lpr-$CAKE_REV/cake_lpr | cut -d' ' -f1)"
