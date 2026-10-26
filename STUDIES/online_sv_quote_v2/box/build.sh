#!/bin/bash
# Unbundle the branch, build the harness and the Python wheel, run the target check and prep. Cores 4-7.
set -e
. $(dirname $0)/env.sh
cd $L
if [ ! -d repo ]; then git clone -q ~/owalnuts repo; fi
cd repo && git fetch -q ../wp88.bundle wt/online-sv-v2 && git checkout -q FETCH_HEAD && git log --oneline -1
cd $S/rust && taskset -c 4-7 cargo build --release -j4 2>&1 | tail -2
cd $S && taskset -c 4-7 python run_cells.py check $W && taskset -c 4-7 python run_cells.py prep $W
cd $L/repo/integrations/python && VIRTUAL_ENV=$L/venv PATH=$L/venv/bin:$PATH CARGO_BUILD_JOBS=4 taskset -c 4-7 maturin develop --release -j 4 2>&1 | tail -1
$WP88_PYVENV -I -c "import owalnuts; print('python owalnuts', owalnuts.__file__, owalnuts.ALGORITHM_REVISION)"
echo build-done
