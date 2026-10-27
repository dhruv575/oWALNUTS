#!/bin/bash
# Pre-freeze smoke (diagnostic seeds, never scored): 3 gated reference ticks, a 3-tick K = 5 and a 3-tick K = 200 warm cell,
# analyze.py on them. Cores 0-3.
set -e
. $(dirname $0)/env.sh
cd $S && taskset -c 0-3 python run_cells.py smoke $W $L/prefreeze 2>&1 | tail -60
echo smoke-done
