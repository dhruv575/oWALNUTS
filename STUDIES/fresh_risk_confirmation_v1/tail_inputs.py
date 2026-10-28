"""Immutable post-inference input seal and same-byte tail readers."""
import hashlib,io,json,importlib.util,sys
from pathlib import Path
import numpy as np
from data_contract import MONTHS as CONTRACTS,load_sealed
MONTHS=[(m['month'],m['origins']) for m in CONTRACTS]
REF_TICKS={m['month']:m['reference_ticks'] for m in CONTRACTS}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def module(path,name):
    path=Path(path).resolve()
    if str(path.parent)not in sys.path:sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def origins():return [(m,t) for m,n in MONTHS for t in range(1,n+1)]
def references():return [(m,i,t) for m,_ in MONTHS for i,t in enumerate(REF_TICKS[m])]

def seal_inference(spec,root):
    from tail_worker import exclusive
    root=Path(root).resolve();index={}
    def add(path):
        path=Path(path).resolve()
        if not path.is_relative_to(root):raise ValueError('Inference file escaped root')
        if not path.exists():return None
        raw=path.read_bytes();index[path.relative_to(root).as_posix()]=sha(raw);return raw
    for m,t in origins():
        base=root/'inference'/m/'candidate'
        for folder in ('records','native'):
            raw=add(base/folder/f'{t:06d}.json')
            if raw is not None:
                row=json.loads(raw)
                if 'compact'in row:
                    draw=add(base/row['compact']['file'])
                    if draw is None or sha(draw)!=row['compact']['sha256']:raise ValueError('Native compact identity mismatch')
        for arm in ('rolling_t5','ewma_t5'):add(root/'inference'/m/'baselines'/arm/f'tick-{t:04d}.json')
    for m,i,t in references():
        base=root/'inference'/m/'references'/f'{i:02d}';raw=add(base/'reference.json')
        if raw is not None:
            row=json.loads(raw)
            if 'compact'in row:
                draw=add(base/row['compact']['file'])
                if draw is None or sha(draw)!=row['compact']['sha256']:raise ValueError('Reference compact identity mismatch')
    value=dict(status='sealed',planned_origins=4320,planned_references=24,files=index)
    path=root/'INFERENCE-INPUT-SEAL.json';exclusive(path,value)
    return dict(path=str(path),sha256=sha(path.read_bytes()),files=len(index))

class Archive:
 def __init__(self,spec):
    self.spec=spec;self.root=Path(spec['input']['root']).resolve();raw=(self.root/'INFERENCE-INPUT-SEAL.json').read_bytes()
    if sha(raw)!=spec['input']['inventory_sha256']:raise ValueError('Inference seal changed')
    value=json.loads(raw)
    if value['status']!='sealed' or value['planned_origins']!=4320 or value['planned_references']!=24:raise ValueError('Inference seal denominator mismatch')
    self.index=value['files'];self.used={};self.y={}
 def read(self,name):
    path=(self.root/name).resolve()
    if not path.is_relative_to(self.root):raise ValueError('Input escaped root')
    raw=path.read_bytes()
    if sha(raw)!=self.index.get(name):raise ValueError('Sealed inference input mismatch: '+name)
    self.used[name]=sha(raw);return raw
 def json(self,name):return json.loads(self.read(name))
 def candidate(self,m,t):
    base=f'inference/{m}/candidate';record=base+f'/records/{t:06d}.json'
    if record not in self.index:record=base+f'/native/{t:06d}.json'
    row=self.json(record)
    if row['tick']!=t or row['native_status']!='ok':raise ValueError('Native draw unavailable')
    raw=self.read(base+'/'+row['compact']['file'])
    if sha(raw)!=row['compact']['sha256']:raise ValueError('Draw record hash mismatch')
    a=np.load(io.BytesIO(raw),allow_pickle=False)
    if a.shape!=(4,400,4) or a.dtype!=np.dtype('float64'):raise ValueError('Candidate shape mismatch')
    return a
 def reference(self,m,i,t):
    base=f'inference/{m}/references/{i:02d}';row=self.json(base+'/reference.json')
    if row['tick']!=t or row['status']!='complete':raise ValueError('Reference unavailable')
    raw=self.read(base+'/'+row['compact']['file'])
    if sha(raw)!=row['compact']['sha256']:raise ValueError('Reference record hash mismatch')
    a=np.load(io.BytesIO(raw),allow_pickle=False)
    if a.shape!=(4,4000,4) or a.dtype!=np.dtype('float64'):raise ValueError('Reference shape mismatch')
    return a,row
 def baseline(self,m,t,arm):
    row=self.json(f'inference/{m}/baselines/{arm}/tick-{t:04d}.json')
    if row['tick']!=t or row['arm']!=arm or row['status']!='ok':raise ValueError('Baseline fit unavailable')
    return row['fit']
 def label(self,m,t):
    if m not in self.y:self.y[m]=load_sealed(self.spec['acquisition'],m)
    return float(self.y[m][250+t])
 def verify_used(self):
    for name,want in self.used.items():
        if sha((self.root/name).read_bytes())!=want:raise ValueError('Consumed inference file drift')
    # Acquisition loader revalidates original responses and causal mapping.
    for m in self.y:load_sealed(self.spec['acquisition'],m)
    return dict(files=len(self.used),hashes=self.used)
