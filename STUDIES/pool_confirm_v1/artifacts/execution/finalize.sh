#!/bin/bash
set -euo pipefail
L=/home/ubuntu/lanes/pool_confirm_v1
S=$L/repo/STUDIES/pool_confirm_v1
R=$L/runs/evidence-20261027
P=/home/ubuntu/venv/bin/python
test ! -e "$R/finalize.start"
date -u +%Y-%m-%dT%H:%M:%SZ > "$R/finalize.start"
echo "$$" > "$R/finalize.pid"
finish() {
    status=$?
    date -u +%Y-%m-%dT%H:%M:%SZ > "$R/finalize.end"
    printf '%s\n' "$status" > "$R/finalize.exit"
    trap - EXIT
    exit "$status"
}
trap finish EXIT
for lane in 3 4; do
    test -f "$R/lane-$lane.exit"
done
test ! -e "$S/artifacts/official"
test ! -e "$S/artifacts/supplemental"
mkdir "$S/artifacts/official" "$S/artifacts/supplemental" "$S/artifacts/execution"
cp "$0" "$S/artifacts/execution/finalize.sh"
cp "$R"/lane-* "$S/artifacts/execution/"
cp "$R/inventory-prelaunch.json" "$S/artifacts/execution/"
{
    date -u +%Y-%m-%dT%H:%M:%SZ
    git -C "$L/repo" rev-parse HEAD
    sha256sum "$S/protocol.json" "$S/analyze.py" "$S/audit_reference.py" "$L/work/target/release/wp97"
    uname -a
    "$P" -c 'import numpy,arviz; print(numpy.__version__,arviz.__version__)'
    ps -eo pid,etimes,pcpu,comm,args
} > "$S/artifacts/execution/analysis-context.txt"
"$P" "$S/audit_inventory.py" "$S/artifacts/cells" --hash-draws > "$S/artifacts/execution/inventory-final.json"
"$P" -c 'import json,sys; r=json.load(open(sys.argv[1])); assert not any(c["errors"] or c["duplicate_ticks"] or c["unexpected_ticks"] for c in r["cells"]), "Integrity issue: inspect original records before analysis"; print("Final inventory:", r["existing_cells"], "existing;", r["complete_record_sets"], "complete record sets")' "$S/artifacts/execution/inventory-final.json"
export OMP_NUM_THREADS=1 RAYON_NUM_THREADS=4
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/artifacts/execution/analysis.start"
set +e
timeout --kill-after=30s 20m taskset -c 8-11 "$P" "$S/analyze.py" "$S/artifacts/cells" --out "$S/artifacts/official" > "$R/analysis.log" 2>&1
code=$?
set -e
echo "$code" > "$S/artifacts/execution/analysis.exit"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/artifacts/execution/analysis.end"
test "$code" -eq 0
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/artifacts/execution/reference-audit.start"
set +e
timeout --kill-after=30s 20m taskset -c 8-11 "$P" "$S/audit_reference.py" "$S/artifacts/cells" --out "$S/artifacts/supplemental/reference-audit.json" > "$R/reference-audit.log" 2>&1
code=$?
set -e
echo "$code" > "$S/artifacts/execution/reference-audit.exit"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/artifacts/execution/reference-audit.end"
test "$code" -eq 0
cp "$R/analysis.log" "$R/reference-audit.log" "$S/artifacts/execution/"
cd "$S"
find artifacts -type f -print0 | sort -z | xargs -0 sha256sum > "$R/final-files.sha256"
tar -czf "$R/final-artifacts.tar.gz" artifacts
cd "$R"
sha256sum final-artifacts.tar.gz final-files.sha256 > final-archive.sha256
date -u +%Y-%m-%dT%H:%M:%SZ > finalize.complete
cat final-archive.sha256
