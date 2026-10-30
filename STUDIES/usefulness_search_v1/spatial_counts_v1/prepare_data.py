import hashlib,json,sys,importlib.metadata
from pathlib import Path
import numpy as np
sys.path.insert(0,'/home/dhruv/.cache/owalnuts/rdata-reader01')
import rdata
base=Path(__file__).resolve().parent;source=base/'source/bei.rda';provenance=json.loads((base/'source/PROVENANCE.json').read_text(encoding='utf-8-sig'))
for record in provenance['files']:assert hashlib.sha256((base/'source'/record['path']).read_bytes()).hexdigest()==record['sha256']
d=rdata.read_rda(source);point=d['bei'];x=np.asarray(point['x']);y=np.asarray(point['y']);n=int(point['n'][0]);assert n==len(x)==len(y)==3604 and np.isfinite(x).all() and np.isfinite(y).all();assert ((x>=0)&(x<=1000)&(y>=0)&(y<=500)).all();assert np.array_equal(point['window']['xrange'],[0,1000]) and np.array_equal(point['window']['yrange'],[0,500])
edgesx=np.arange(0,1001,50);edgesy=np.arange(0,501,50);centres=np.array([(i,j) for i in np.arange(25,1000,50) for j in np.arange(25,500,50)]);covariates=[]
for key in ['elev','grad']:
    im=d['bei.extra'][key];values=np.asarray(im['v']);assert values.shape==(len(im['yrow']),len(im['xcol']));v=[]
    for cx,cy in centres:
        ix=np.flatnonzero(np.asarray(im['xcol'])==cx);iy=np.flatnonzero(np.asarray(im['yrow'])==cy);assert len(ix)==len(iy)==1;v.append(float(values[iy[0],ix[0]]))
    covariates.append(v)
covariates=np.asarray(covariates).T;assert covariates.shape==(200,2) and np.isfinite(covariates).all();mean=covariates.mean(0);sd=covariates.std(0,ddof=0);assert (sd>0).all();design=np.c_[np.ones(200),(covariates-mean)/sd]
mask=np.random.default_rng(952000001).random(n)<.2
def counts(which):return np.histogram2d(x[which],y[which],bins=[edgesx,edgesy])[0].astype(int).reshape(-1)
train=counts(mask);held=counts(~mask);full=counts(np.ones(n,dtype=bool));assert train.sum()==mask.sum() and held.sum()==(~mask).sum() and np.array_equal(train+held,full) and full.sum()==n
# Independent integer cell assignment checks both histogram orientation and edges.
ix=np.minimum((x/50).astype(int),19);iy=np.minimum((y/50).astype(int),9);assigned=ix*10+iy
assert np.array_equal(np.bincount(assigned[mask],minlength=200),train) and np.array_equal(np.bincount(assigned[~mask],minlength=200),held)
out=base/'data01';out.mkdir(exist_ok=False);cfg=dict(N=200,x=(centres/100).tolist(),design=design.tolist(),coef_scale=[5.,2.,2.],exposure=.2,y=train.tolist());(out/'GP-TRAIN.json').write_text(json.dumps(cfg,indent=2)+'\n');(out/'HELDOUT.json').write_text(json.dumps(dict(exposure=.8,y=held.tolist()),indent=2)+'\n')
np.savez_compressed(out/'SOURCE-AND-SPLIT.npz',x=x,y=y,training_mask=mask,centres=centres,covariates=covariates,covariate_mean=mean,covariate_sd=sd,full=full,train=train,heldout=held,edgesx=edgesx,edgesy=edgesy)
result=dict(passed=True,source_points=n,documented_points=3605,discrepancy='Pinned R object contains3604 coordinates; documentation says3605; cause unestablished',cells=200,parameters=205,training_points=int(train.sum()),seed=952000001,training_exposure=.2,heldout_exposure=.8,covariate_mean=mean.tolist(),covariate_sd=sd.tolist(),parser_version=importlib.metadata.version('rdata'),numpy_version=np.__version__,files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir()},inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [source,base/'source/PROVENANCE.json',base/'source/bei.Rd',base/'source/DESCRIPTION',base/'CANDIDATE-AND-DATA-PROTOCOL.md',base/'SOURCE-DISCREPANCY.md',Path(__file__)]},scope='Data preparation only; no heldout scores or inference results')
(out/'MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,source_points=n,training_points=int(train.sum()),cells=200,parameters=205)),flush=True)
