#!/bin/bash
# WP94 post-processing on the box: analysis, hash manifests of the out-of-git draws and telemetry, tarball of
# the artifacts (without draws / telemetry) for scp back to the worktree.
set -u
source ~/lanes/grad_init_metric_v1/env.sh
cd $D
grep -q ALL-CELLS-FINISHED $L/logs/evidence.log || { echo "evidence run not finished"; exit 1; }
cp $D/artifacts/environment.json $WP94_ART/environment.json
$TS0 $PY run_study.py analyze > $L/logs/analyze.log 2>&1; echo ANALYZE_EXIT $?
tail -3 $L/logs/analyze.log
(cd $L/draws && sha256sum *.npz) > $WP94_ART/draws-manifest.sha256
(cd $WP94_ART/telemetry && sha256sum *.json.gz) > $WP94_ART/telemetry-manifest.sha256
cp $L/logs/evidence.log $WP94_ART/box-evidence-log.txt
mkdir -p $WP94_ART/box-logs && cp $L/logs/*.log $L/logs/library.diff $L/logs/wp85-models.sha256 $WP94_ART/box-logs/ 2>/dev/null
rm -rf $WP94_ART/smoke/telemetry $WP94_ART/smoke/draws
cd $L && tar czf $L/wp94-art.tgz --exclude=art/telemetry --exclude=art/draws art
ls -la $L/wp94-art.tgz | awk '{print $5}'
echo POST-DONE
