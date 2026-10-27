#!/bin/bash
# Unbundle the branch and build the harness (release). Built before the lanes were free: nice -n 10, 4 jobs, cores 8-15.
set -eo pipefail
. $(dirname $0)/env.sh
cd $L
if [ ! -d repo ]; then git clone -q ~/owalnuts repo; fi
cd repo && git fetch -q ../wp97.bundle wt/pool-confirm && git checkout -q FETCH_HEAD && git log --oneline -1
cd $S/rust && nice -n 10 taskset -c 8-15 cargo build --release -j4 2>&1 | tail -2
ls -la $W/target/release/wp97
echo build-done
