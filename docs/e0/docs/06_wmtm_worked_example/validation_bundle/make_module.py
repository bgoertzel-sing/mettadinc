#!/usr/bin/env python3
"""Regenerates the shipped streams from the seed and writes wmtm_example.metta from the template,
filling each {DIGEST:<stream>} placeholder with that stream's SHA-256 digest.

Run: python3 make_module.py        (rewrites streams/ and wmtm_example.metta in place)

The oracle checks that the shipped streams are reproduced byte for byte and that the module pins
them by these digests, so running this script on an unchanged bundle changes nothing.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "models"))

import wx_sim as W  # noqa: E402


def main():
    W.DATA = os.path.join(HERE, "streams")
    digests = W.freeze(W.run())
    text = open(os.path.join(HERE, "wmtm_example.template.metta")).read()
    names = set(re.findall(r"\{DIGEST:([a-z_0-9]+)\}", text))
    missing = names - set(digests)
    assert not missing, "no stream for " + ", ".join(sorted(missing))
    text = re.sub(r"\{DIGEST:([a-z_0-9]+)\}", lambda m: digests[m.group(1)], text)
    assert all(ord(c) < 128 for c in text) and all(len(line) <= 90 for line in text.split("\n"))
    open(os.path.join(HERE, "wmtm_example.metta"), "w").write(text)
    for k, v in sorted(digests.items()):
        print(f"{k:22s} {v}{'' if k in names else '   (not pinned in the module)'}")


if __name__ == "__main__":
    main()
