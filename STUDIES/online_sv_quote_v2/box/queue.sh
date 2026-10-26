#!/bin/bash
# Run one preregistered queue (A: cores 4-7, B: 8-11, C: 12-15). Launch with nohup; never rerun a started cell.
set -e
. $(dirname $0)/env.sh
Q=$1; case $Q in A) C=4-7;; B) C=8-11;; C) C=12-15;; *) echo "queue A|B|C"; exit 2;; esac
sudo touch /var/tmp/keep-alive
cd $S && exec taskset -c $C python run_cells.py queue $Q $W
