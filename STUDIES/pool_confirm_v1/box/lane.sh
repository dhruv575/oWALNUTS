#!/bin/bash
# Run one preregistered lane (3: cores 8-11, 4: cores 12-15). Launch with nohup; never rerun a started cell.
set -e
. $(dirname $0)/env.sh
Q=$1; case $Q in 3) C=8-11;; 4) C=12-15;; *) echo "lane 3|4"; exit 2;; esac
sudo touch /var/tmp/keep-alive
cd $S && exec taskset -c $C python run_cells.py lane $Q $W
