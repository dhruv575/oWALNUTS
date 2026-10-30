import hashlib,json
from pathlib import Path
import bridgestan as bs
root=Path(__file__).resolve().parent
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
pdb=Path('/home/ubuntu/infra/posteriordb/posterior_database');rows=[]
for name in ['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered',
             'garch-garch11','gp_pois_regr-gp_pois_regr','seeds_data-seeds_centered_model']:
    so=models/(name+'_model.so');data=models/(name+'.data.json');stan=models/(name+'.stan')
    target=bs.StanModel(str(so),data=data.read_text(),seed=1)
    info=pdb/'posteriors'/f'{name}.json';posterior=json.loads(info.read_text())
    refname=posterior.get('reference_posterior_name')
    ref=pdb/'reference_posteriors/draws/draws'/(refname+'.json.zip') if refname else None
    rows.append(dict(model=name,dimension=len(target.param_unc_names()),coordinates=target.param_unc_names(),
        model_source=stan.read_text(),reference_path=str(ref) if ref else None,reference_exists=bool(ref and ref.exists()),
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [so,data,stan,info]+([ref] if ref and ref.exists() else [])}))
(root/'NONCONJUGATE-INVENTORY.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps([dict(model=r['model'],dimension=r['dimension'],reference_exists=r['reference_exists']) for r in rows]))
