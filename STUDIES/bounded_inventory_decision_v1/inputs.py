"""Hash-verified reads from sealed E64, no acquisition or fitting."""
import hashlib,io,json,importlib.util,sys
from pathlib import Path
import numpy as np
MONTHS=[('2026-04',1440),('2026-05',1488),('2026-06',1440)]
REF_TICKS={'2026-04':[1,207,412,618,823,1029,1234,1440],'2026-05':[1,213,426,638,851,1063,1276,1488],'2026-06':[1,207,412,618,823,1029,1234,1440]}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def module(path,name):
    path=Path(path).resolve()
    if str(path.parent)not in sys.path:sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def origins():return [(month,tick) for month,n in MONTHS for tick in range(1,n+1)]
def references():return [(month,i,tick) for month,n in MONTHS for i,tick in enumerate(REF_TICKS[month])]

class Archive:
 def __init__(self,spec):
    self.spec=spec;self.root=Path(spec['input']['root']).resolve();raw=(self.root/'ARTIFACTS.sha256').read_bytes()
    if sha(raw)!=spec['input']['inventory_sha256']:raise ValueError('E64 artifact inventory changed')
    self.index={}
    for line in raw.decode().splitlines():
        digest,name=line.split('  ',1);name=name.removeprefix('./')
        if name in self.index:raise ValueError('Duplicate archive identity')
        self.index[name]=digest
    self.used={};self.y={}
    if sha(self.read('PRODUCTION-AUTHORIZED.json'))!=spec['input']['original_manifest_sha256']:raise ValueError('Original E64 manifest mismatch')
 def read(self,name):
    path=(self.root/name).resolve()
    if not path.is_relative_to(self.root):raise ValueError('Input escaped archive')
    raw=path.read_bytes();digest=sha(raw)
    if self.index.get(name)!=digest:raise ValueError('Sealed input mismatch: '+name)
    self.used[name]=digest;return raw
 def json(self,name):return json.loads(self.read(name))
 def candidate(self,month,tick):
    base=f'campaign01/batch/{month}/candidate';record=self.json(base+f'/records/{tick:06d}.json')
    if record['tick']!=tick or record['native_status']!='ok':raise ValueError('Original native origin unavailable')
    raw=self.read(base+'/'+record['compact']['file'])
    if sha(raw)!=record['compact']['sha256']:raise ValueError('Compact record hash disagreement')
    a=np.load(io.BytesIO(raw),allow_pickle=False)
    if a.shape!=(4,400,4) or a.dtype!=np.dtype('float64'):raise ValueError('Candidate draw schema changed')
    return a
 def reference(self,month,index,tick):
    base=f'campaign01/batch/{month}/references/{index:02d}';record=self.json(base+'/reference.json')
    if record['index']!=index or record['tick']!=tick or record['status']!='complete':raise ValueError('Original reference unavailable')
    raw=self.read(base+'/'+record['compact']['file'])
    if sha(raw)!=record['compact']['sha256']:raise ValueError('Reference record hash disagreement')
    a=np.load(io.BytesIO(raw),allow_pickle=False)
    if a.shape!=(4,4000,4) or a.dtype!=np.dtype('float64'):raise ValueError('Reference schema changed')
    return a,record
 def baseline(self,month,tick,arm):
    value=self.json(f'campaign01/batch/{month}/baselines/{arm}/tick-{tick:04d}.json')
    if value['tick']!=tick or value['arm']!=arm:raise ValueError('Baseline identity changed')
    return value['fit']
 def label(self,month,tick):
    if month not in self.y:
        old=self.json('PRODUCTION-AUTHORIZED.json');contract=module(self.spec['dependencies']['e64_data_contract'],'bound_e64_data_contract')
        bindings=dict(old['acquisition'],directory=str(self.root/'acquisition'),supervisor_final_path=str(self.root/'acquisition-supervisor-final.json'))
        # Original sealed loader checks bars/raw responses; inventory binds the same bytes too.
        for name in ['terminal.json','protocol.json','bars.json']+sum(([f'response-{i:03d}.json',f'response-{i:03d}-metadata.json'] for i in range(97)),[]):self.read('acquisition/'+name)
        self.read('acquisition-supervisor-final.json');self.y[month]=contract.load_sealed(bindings,month)
    return float(self.y[month][250+tick])
 def verify_used(self):
    for name,want in list(self.used.items()):
        if sha((self.root/name).read_bytes())!=want:raise ValueError('Consumed input drift: '+name)
    return dict(files=len(self.used),hashes=self.used)
