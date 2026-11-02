"""Build both revisions, then interleave identical benchmark executables."""
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

root=Path(__file__).resolve().parents[2]
out=Path(__file__).parent
metadata=out/'baseline-build.json'
if not metadata.exists() or not Path(json.loads(metadata.read_text())['directory']).exists():
    subprocess.run([sys.executable,str(out/'run_baseline.py')],check=True)
baseline=Path(json.loads(metadata.read_text())['directory'])
shutil.copyfile(root/'examples/performance_suite.rs',baseline/'examples/performance_suite.rs')
environment=dict(os.environ,CARGO_BUILD_JOBS='1')
with (out/'comparison-build.log').open('w') as log:
    for directory in [baseline,root]:
        subprocess.run(['cargo','build','--release','--features','research','--example','performance_suite'],cwd=directory,env=environment,stdout=log,stderr=subprocess.STDOUT,check=True)
records={'before':[],'after':[]}
for iteration in range(4):
    order=[('before',baseline),('after',root)]
    if iteration%2:order.reverse()
    for label,directory in order:
        result=subprocess.check_output([str(directory/'target/release/examples/performance_suite')],text=True)
        with (out/f'comparison-{label}.txt').open('a') as log:log.write(result)
        for line in result.splitlines():
            fields=line.split()
            records[label].append(dict(workload=fields[0],**dict(field.split('=') for field in fields[1:])))
summary={}
for name in sorted({r['workload'] for r in records['before']}):
    pairs={}
    for label in records:
        rows=[r for r in records[label] if r['workload']==name]
        pairs[label]={k:statistics.median(float(r[k]) for r in rows) for k in ['ms','allocations','bytes']}
        pairs[label]['ms_range']=[min(float(r['ms']) for r in rows),max(float(r['ms']) for r in rows)]
        pairs[label]['fingerprints']=sorted({r['fingerprint'] for r in rows})
    assert pairs['before']['fingerprints']==pairs['after']['fingerprints'],name
    pairs['speedup']=pairs['before']['ms']/pairs['after']['ms']
    summary[name]=pairs
(out/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
