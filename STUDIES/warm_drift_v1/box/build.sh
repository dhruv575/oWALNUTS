#!/bin/bash
# Unbundle the branch and build the harness once (cores 8-11). Deletes nothing.
set -e
. $(dirname $0)/env.sh
cd $L
if [ ! -d repo ]; then git clone -q ~/owalnuts repo; fi
cd repo && git fetch -q ../wp96.bundle wt/warm-drift && git checkout -q FETCH_HEAD && git log --oneline -1
cd $S/rust && taskset -c 8-11 cargo build --release -j4 2>&1 | tail -2
echo build-done
