import hashlib,json,math
from pathlib import Path
root=Path(__file__).resolve().parent;pdb=Path('/home/ubuntu/infra/posteriordb/posterior_database')
compiled=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
rows=[]
for p in sorted((pdb/'posteriors').glob('*.json')):
    info=json.loads(p.read_text());d=sum(math.prod(v) if isinstance(v,list) else v for v in info.get('dimensions',{}).values());ref=info.get('reference_posterior_name')
    if not 2<=d<=16 or not ref or (compiled/(p.stem+'_model.so')).exists():continue
    stan=pdb/'models/stan'/(info['model_name']+'.stan');draws=pdb/'reference_posteriors/draws/draws'/(ref+'.json.zip')
    data=pdb/'data/data'/(info['data_name']+'.json.zip')
    if not all(q.exists() for q in [stan,draws,data]):continue
    rows.append(dict(model=p.stem,reported_dimension=d,keywords=info.get('keywords'),model_source=stan.read_text(),
        paths={k:str(q) for k,q in [('stan',stan),('data',data),('reference',draws),('info',p)]},
        hashes={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [stan,draws,data,p]}))
(root/'REMAINING-INVENTORY.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps([dict(model=r['model'],d=r['reported_dimension'],keywords=r['keywords']) for r in rows]))
