# Evidence: m0-prep redone with Cetta as a pinned submodule

Hive task t-2026-11-06-mettadinc-m0-prep-submodule, on pop-os (gcc 11.4.0, GNU Make 4.3, Python 3.10.12; GMP headers
from an extracted libgmp-dev package via `MDINC_GMP_PREFIX`, as in E0 and m0-prep). All runs at commit 2e8e1a2 (the
replayed m0-prep head), with `cetta/` the submodule checkout at 12da03b4b055bfecff2add505e7e1ad4125bb352 fetched from
https://github.com/zariuq/CeTTa by `git submodule add`. Driver: [rerun-submodule.sh](rerun-submodule.sh) (run from
`build/`, which git ignores). The older `evidence/m0-prep/` is m0-prep's run on the vendored copy, kept unchanged.

| File | What | Result |
|---|---|---|
| 00_pin_check.out, 00_pin_check_after_builds.out | `tools/check-vendored-cetta.sh` before and after the three builds | exit 0, exit 0 |
| 00_pin_check_negative.out | pin line changed, checkout moved to 12da03b4^, untracked file, submodule deinit | exit 1 each; exit 0 after reverting |
| 00_submodule_status.out | `git submodule status`, the gitlink, .gitmodules | 12da03b4 |
| registry/03_adopt_check.out | `adopt_registry.py --supersede requests.Detect=wx --check` | up to date: fc046d14…f3f61, exit 0 |
| registry/04_check_fixtures.out | `cd validation && python3 check_fixtures.py` | conforms, exit 0 |
| registry/05_check_bundles_detect.out, 05b_check_bundles.out | each bundle's ex_check.py against the registry alone | 0 diagnostics for all seven bundles |
| registry/digest.out | registry/DIGEST and sha256 of the registry | both fc046d14…f3f61 |
| cetta-baseline/sub-run1-green | `tools/cetta-baseline.sh` on the clean checkout | rhocalc 253/0; core 502 PASS / 6 SKIP / 1 FAIL (py-call); python 503 / 6 / 0; HARNESS_EXIT=0 (green) |
| cetta-baseline/sub-run2-broken (+ BREAK.txt, pin_check_while_broken.out) | one line appended to cetta/tests/rhocalc/translate_rho_to_mrho.expected in the checkout | RED in all three lanes, HARNESS_EXIT=1; pin check exit 1 (M tests/rhocalc/…) |
| cetta-baseline/pin_check_after_revert.out | after `git -C cetta checkout -- tests/rhocalc/translate_rho_to_mrho.expected` | exit 0 |
| cetta-baseline/sub-run3-reverted | the harness again | GREEN, HARNESS_EXIT=0 |
| oracles/ | `tools/run-oracles.sh` | 157 / 305 / 195 / 94 / 99, 0 failures, ORACLES_EXIT=0 |

## Old commits to new

| Old (PR #2) | New | Content differences |
|---|---|---|
| b37eaa9 vendor CeTTa (3321 files, 2.18M lines) | 7fa631e | Replaced: `.gitmodules` + gitlink `cetta` → 12da03b4, and docs/CETTA-PIN.md (from cetta/VENDORED.md: URL, full SHA, tree, date, `git submodule update --init`) |
| 548633e harness, VENDORED.md, vendor check | af1e401 | cetta/VENDORED.md dropped (now docs/CETTA-PIN.md); tools/check-vendored-cetta.sh rewritten as the pin check; tools/cetta-baseline.sh reads the pin from docs/CETTA-PIN.md, reports gitlink and submodule HEAD, checks the checkout's tracked files, hints `git submodule update --init`. Message updated. Author and date kept |
| 154319b registry tooling | 07908eb | README: "vendored" wording and the cetta/VENDORED.md link replaced by the submodule and docs/CETTA-PIN.md. Everything else identical |
| fe6f509 evidence (vendored run) | 70514b7 | Identical |
| cca2dfb registry | 2e8e1a2 | Identical |
| (new) | this commit | evidence/m0-prep-submodule/ |
