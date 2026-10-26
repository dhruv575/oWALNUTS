#!/bin/bash
# WP90 post-processing on the box: analysis, hash manifests of the out-of-git draws and telemetry, tarball of
# the artifacts (without draws / telemetry) for scp back to the worktree.
set -u
source ~/lanes/trap_guard_confirmation_v1/env.sh
cd $D
grep -q ALL-CELLS-FINISHED $L/logs/evidence.log || { echo "evidence run not finished"; exit 1; }
$TS $PY run_study.py analyze > $L/logs/analyze.log 2>&1; echo ANALYZE_EXIT $?
tail -3 $L/logs/analyze.log
(cd $L/draws && sha256sum *.npz) > $WP90_ART/draws-manifest.sha256
(cd $WP90_ART/telemetry && sha256sum *.json.gz) > $WP90_ART/telemetry-manifest.sha256
cp $L/logs/evidence.log $WP90_ART/box-evidence-log.txt
mkdir -p $WP90_ART/box-logs && cp $L/logs/*.log $L/logs/library.diff $L/logs/wp85-models.sha256 $WP90_ART/box-logs/ 2>/dev/null
rm -rf $WP90_ART/smoke/telemetry $WP90_ART/smoke/draws
cd $L && tar czf $L/wp90-art.tgz --exclude=art/telemetry --exclude=art/draws art
ls -la $L/wp90-art.tgz | awk '{print $5}'
echo POST-DONE
