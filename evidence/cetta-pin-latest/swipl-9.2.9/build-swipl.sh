#!/usr/bin/env bash
# SWI-Prolog 9.2.9 built from source, without sudo, for the rhocalc lane (hive answer 2, decision 1 "A2").
# Source: https://www.swi-prolog.org/download/stable/src/swipl-9.2.9.tar.gz (the last 9.x stable release;
# 10.0.x is the current stable series).  sha256 53f428e2d9bbdf30e53b06c9c42def9a13ff82fc36a111d410fc8b0bc889ee2d,
# the same as published on https://www.swi-prolog.org/download/stable (checked 2026-11-06).
# Install prefix: $HOME/scratch/mettadinc-e0/swipl9/install; use it with MDINC_SWIPL_DIR=<that prefix>.
# GMP is off (pop-os has no libgmp-dev; SWI-Prolog then uses its bundled LibBF for big integers); the Java, X11,
# ODBC, Qt and Python (janus) packages, the documentation and the test suite are off; everything else as cmake
# finds it (OpenSSL 3 headers for library(crypto)/ssl, zlib, pcre2, uuid, libffi; no readline/editline/curses).
set -eu
cd "$HOME/scratch/mettadinc-e0/swipl9"
echo "53f428e2d9bbdf30e53b06c9c42def9a13ff82fc36a111d410fc8b0bc889ee2d  swipl-9.2.9.tar.gz" | sha256sum -c
rm -rf swipl-9.2.9 build install && tar xzf swipl-9.2.9.tar.gz && mkdir build && cd build
cmake -G Ninja -DCMAKE_INSTALL_PREFIX=$HOME/scratch/mettadinc-e0/swipl9/install -DCMAKE_BUILD_TYPE=Release \
  -DUSE_GMP=OFF -DSWIPL_PACKAGES_JAVA=OFF -DSWIPL_PACKAGES_X=OFF -DSWIPL_PACKAGES_ODBC=OFF -DSWIPL_PACKAGES_QT=OFF \
  -DSWIPL_PACKAGES_PYTHON=OFF -DINSTALL_DOCUMENTATION=OFF -DBUILD_TESTING=OFF ../swipl-9.2.9
ninja -j8 && ninja install
