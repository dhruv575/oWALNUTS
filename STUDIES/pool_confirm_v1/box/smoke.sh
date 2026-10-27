#!/bin/bash
# Pre-freeze smoke (diagnostic seeds, never scored): 3 gated reference ticks per dataset, a 3-tick K = 200 sim and a 3-tick
# K = 20 real warm cell, analyze.py on them. Cores 8-11 (lane 3), only after WP96 released the lane.
set -e
. $(dirname $0)/env.sh
cd $S && taskset -c 8-11 python run_cells.py smoke $W $L/prefreeze 2>&1 | tail -80
echo smoke-done
