"""Posthoc lossless artifact-format prototype; no sampler or gate changes."""
import sys,time,json,hashlib,os,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent/'array-probe';OUT.mkdir(exist_ok=False)
sys.path.insert(0,str(ROOT/'STUDIES/options_flow_v1'))
from hardware_control import set_affinity,get_affinity
set_affinity([0])
import numpy as np
from pymc_continuation_workflow import write_json

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
rows=[];sources={str(Path(__file__).resolve()):sha(__file__),str(ROOT/'STUDIES/options_flow_v1/pymc_continuation_workflow.py'):sha(ROOT/'STUDIES/options_flow_v1/pymc_continuation_workflow.py')};tick=time.perf_counter()
for arm in ('public','reference'):
 folder=ROOT/'STUDIES/options_flow_v1/artifacts/fresh-paired-comparison-v1/run-v1'/('pair00-'+arm)
 raw=folder/('draws-2000/python-pymc-flow-raw.json' if arm=='public' else 'draws-2000-raw.json');sources[str(raw)]=sha(raw)
 ts=time.perf_counter();original=json.loads(raw.read_text());q=np.asarray(original.pop('canonical_draws'),dtype=np.float64);loadseconds=time.perf_counter()-ts
 assert q.shape==(4,2000,1012) and np.isfinite(q).all();expected=q.view(np.uint64).copy()
 for repeat in range(3):
  for fmt in (('json','npy') if repeat%2==0 else ('npy','json')):
   dest=OUT/f'{arm}-{repeat}-{fmt}';dest.mkdir();gc.collect();start=time.perf_counter()
   if fmt=='json':
    path=dest/'raw.json';write_json(path,dict(original,canonical_draws=q));files=[path]
   else:
    path=dest/'draws.npy'
    with path.open('xb') as f:np.save(f,q,allow_pickle=False)
    write_json(dest/'metadata.json',dict(metadata=original,array=dict(file=path.name,dtype=q.dtype.str,shape=list(q.shape),sha256=sha(path))));files=[path,dest/'metadata.json']
   written=time.perf_counter()-start;start=time.perf_counter();hashes={p.name:sha(p) for p in files};hashed=time.perf_counter()-start;start=time.perf_counter()
   if fmt=='json':
    decoded=json.loads(path.read_text());got=np.asarray(decoded.pop('canonical_draws'),dtype=np.float64);metadata=decoded
   else:
    meta=json.loads((dest/'metadata.json').read_text());assert sha(path)==meta['array']['sha256'];got=np.load(path,allow_pickle=False);metadata=meta['metadata'];assert list(got.shape)==meta['array']['shape'] and got.dtype.str==meta['array']['dtype']
   readseconds=time.perf_counter()-start;assert metadata==original and np.array_equal(got.view(np.uint64),expected)
   rows.append(dict(arm=arm,repeat=repeat,format=fmt,shape=list(q.shape),source_load_seconds=loadseconds,write_seconds=written,read_seconds=readseconds,hash_seconds=hashed,total_seconds=written+readseconds+hashed,bytes=sum(p.stat().st_size for p in files),bitwise_equal=True,metadata_equal=True,hashes=hashes));del got,metadata
with (OUT/'result.json').open('x') as f:json.dump(dict(scope='Exploratory saved-data IO, OS caches uncontrolled, no fsync/durable-disk throughput claim; sameCPU0, alternating format order, no sampling or diagnostics removed',affinity=get_affinity(),numpy=np.__version__,python=sys.version,sources=sources,rows=rows,elapsed_seconds=time.perf_counter()-tick),f,indent=2)
print(json.dumps(rows,indent=2))
