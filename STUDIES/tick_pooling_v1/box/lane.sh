#!/bin/bash
# Run one preregistered lane (1: cores 0-3, 2: cores 4-7). Launch with nohup; never rerun a started cell.
set -e
. $(dirname $0)/env.sh
Q=$1; case $Q in 1) C=0-3;; 2) C=4-7;; *) echo "lane 1|2"; exit 2;; esac
sudo touch /var/tmp/keep-alive
cd $S && exec taskset -c $C python run_cells.py lane $Q $W
