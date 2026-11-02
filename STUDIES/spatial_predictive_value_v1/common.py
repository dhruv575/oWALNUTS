import os,sys,json,hashlib
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
BASE=Path(__file__).resolve().parent
ALG=Path('/home/ubuntu/lanes/algorithmic-speedups-20261101')
sys.path.insert(0,str(ALG))
import numpy as np
from grid_backend import Native
from grid import GridGP
GP_PATHS=[ALG/'grid_precision01/nuts_grid-954100004/artifact',ALG/'next01/confirmation-954100005/artifact']
WAL_PATHS=[Path('/home/ubuntu/lanes/spatial-counts-reference-20261031-v2/results')/str(i) for i in [2,3]]
def data():return json.loads((BASE/'inputs/GP-TRAIN.json').read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def physical(q,model):
    out=np.empty((*q.shape[:2],405));flat=out.reshape(-1,405);scale=np.array(model.data['coef_scale'])
    for i,row in enumerate(q.reshape(-1,205)):
        f=model.field(model.factor(row[:2]),row[2:]);flat[i]=np.r_[np.exp(row[:2]),scale*row[2:5],f,np.exp(f)]
    return out
def verify_freeze():
    frozen=json.loads((BASE/'FREEZE.json').read_text())
    for name,h in frozen.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name

