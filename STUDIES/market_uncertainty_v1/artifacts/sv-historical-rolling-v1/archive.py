import hashlib,json,zipfile,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];base=ROOT/'target/sv-historical-rolling-v1';run=base/'run-v1';out=ROOT/'STUDIES/market_uncertainty_v1/artifacts/sv-historical-rolling-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf8')
start=time.perf_counter();out.mkdir(exist_ok=True);c=json.loads((base/'prepared/config-frozen.json').read_text());r=json.loads((base/'report-result-v1.json').read_text());checks=[]
for p,h in c['bindings'].items():assert sha(Path(p))==h,p
for p,h in c['runtime_bindings'].items():assert sha(Path(p))==h,p
for cell in c['cells']:
 h=json.loads((run/(cell['id']+'-hardware.json')).read_text());rep=json.loads((run/cell['id']/'report.json').read_text())
 assert h['returncode']==0 and h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0,1,2,3] and h['enforced_before_worker_launch'] and h['containment']['assigned_before_worker_execution'],cell['id']
 if cell['arm']=='public':assert rep['runtime_bindings']==c['runtime_bindings'],cell['id']
 else:
  for p,h in rep['reference_runtime_bindings'].items():assert c['bindings'][p]==h and sha(Path(p))==h,p
 checks.append(cell['id'])
raw=[dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(run.rglob('*.npy'))]
save(out/'external-raw-manifest.json',dict(committed=False,files=raw,total_bytes=sum(x['bytes'] for x in raw),scope='Integrity inventory only; no retained-array numerical recomputation'))
files=[p for p in base.rglob('*') if p.is_file() and p.suffix in ('.json','.py','.zip','.md','.log') and p.name!='archive.py']
members={}
with zipfile.ZipFile(out/'evidence.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files:
  name=p.relative_to(base).as_posix();data=p.read_bytes();z.writestr(name,data);members[name]=hashlib.sha256(data).hexdigest()
with zipfile.ZipFile(out/'evidence.zip') as z:
 assert set(z.namelist())==set(members)
 for n,h in members.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
save(out/'zip-members.json',members)
ratios=[p['reference_over_public'] for p in r['conditional_both_pass_runtime_pairs']]
save(out/'verification.json',dict(source_bindings_pass=True,runtime_bindings_pass=True,hardware_pass_ids=checks,all360_usable=all(x['usable'] for x in r['ledger']),matched_pairs=len(ratios),median_pair_ratio=statistics.median(ratios),ratio_total_cost=r['both_flow_runtime']['reference']['total_seconds']/r['both_flow_runtime']['public']['total_seconds'],raw_files=len(raw),archive_seconds=time.perf_counter()-start))
(out/'.gitattributes').write_text('* -text\n')
(out/'RESULTS.md').write_text('''# Historical rolling SV comparison

All 360 intended fits passed; all 72 evaluation origins have labels and usable intervals for all six compared forecasting models. This is dependent retrospective September history with zero publication lag assumed, not live calibration or certified market utility.

| Model | Coverage | Mean width | Mean interval score | Lower / upper misses |
|---|---:|---:|---:|---:|
| SV neither | 90.28% | .00809684 | .01054978 | 2 / 5 |
| SV mean flow | 91.67% | .00807734 | .01058844 | 2 / 4 |
| SV scale flow | 88.89% | .00788205 | .01065461 | 2 / 6 |
| SV both flow | 87.50% | .00788145 | .01059432 | 3 / 6 |
| Exact price baseline | 94.44% | .01010530 | .01206660 | 2 / 2 |
| Exact flow baseline | 94.44% | .01009498 | .01201039 | 2 / 2 |

Lower interval score is better. SV intervals are narrower and have lower mean scores than these exact baselines. Flow adds no clear score benefit over the SV model without flow; selecting an ablation from these same outcomes would be exploratory. No SV log-density score or iid confidence interval is claimed.

The 72 matched both-flow fits cost 467.436504 s public versus 648.340462 s reference, including all intended fit costs; all pairs passed. Their total-cost ratio is descriptive, not a new qualified speed claim. Campaign outer elapsed was 2449.989469 s, including the other three public ablations and controller overhead. The full reporter result retains each cell and the individual/common grids.

All frozen source/input and released runtime hashes rechecked; all 360 hardware records show clean containment, four-CPU affinity and exit 0. Full reports, configurations, fixtures, source ZIPs and logs are in evidence.zip. NPY arrays stay external with hashes and byte counts; they were not numerically re-audited here. Earlier launch-only archive remains immutable. ZIP members were extracted in memory and verified against zip-members.json.
''',encoding='utf8')
save(out/'checksums.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='checksums.json'})
print(json.dumps(dict(files=len(members),raw_files=len(raw),seconds=time.perf_counter()-start)))

