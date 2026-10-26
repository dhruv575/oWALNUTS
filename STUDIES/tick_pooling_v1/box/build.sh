#!/bin/bash
# Unbundle the branch and build the harness (release). Cores 0-3.
set -e
. $(dirname $0)/env.sh
cd $L
if [ ! -d repo ]; then git clone -q ~/owalnuts repo; fi
cd repo && git fetch -q ../wp93.bundle wt/tick-pooling && git checkout -q FETCH_HEAD && git log --oneline -1
cd $S/rust && taskset -c 0-3 cargo build --release -j4 2>&1 | tail -2
ls -la $W/target/release/wp93
echo build-done
