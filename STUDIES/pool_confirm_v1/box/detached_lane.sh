#!/bin/bash
# One externally detached lane, durable lifecycle records, bounded runtime.
set -euo pipefail
lane=${1:?lane 3 or 4 required}
run_id=${2:?unique run ID required}
case "$lane" in 3|4) ;; *) exit 2;; esac
case "$run_id" in *[!a-zA-Z0-9_-]*|'') exit 2;; esac
L=/home/ubuntu/lanes/pool_confirm_v1
S=$L/repo/STUDIES/pool_confirm_v1
R=$L/runs/$run_id
mkdir -p "$R"
test ! -e "$R/lane-$lane.pid"
echo "$$" > "$R/lane-$lane.pid"
finish() {
    status=$?
    date -u +%Y-%m-%dT%H:%M:%SZ > "$R/lane-$lane.end"
    printf '%s\n' "$status" > "$R/lane-$lane.exit.tmp"
    mv "$R/lane-$lane.exit.tmp" "$R/lane-$lane.exit"
    trap - EXIT
    exit "$status"
}
trap finish EXIT
{
    date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'lane=%s deadline_seconds=7200\n' "$lane"
    git -C "$L/repo" rev-parse HEAD
    sha256sum "$S/protocol.json" "$S/rust/src/main.rs" "$L/work/target/release/wp97"
} > "$R/lane-$lane.start"
flock -n "$L/lane-$lane.lock" timeout --kill-after=30s 120m bash "$S/box/lane.sh" "$lane"
