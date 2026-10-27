"""Offline source/runtime and sealed-input identity binding; never reads draw values."""
import argparse,hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bind(bundle,remote_root,e64,remote_input,output):
    bundle=Path(bundle);e64=Path(e64);remote_root=remote_root.rstrip('/');inventory=json.loads((bundle/'BUNDLE-MANIFEST.json').read_bytes())
    source={}
    for name,want in inventory['files'].items():
        path=(bundle/name).resolve()
        if not path.is_relative_to(bundle.resolve()) or sha(path)!=want:raise ValueError('Bundle integrity failure '+name)
        source[remote_root+'/'+name]=want
    study=bundle/'STUDIES/predictive_risk_limits_v1';ops=bundle/'STUDIES/return_tail_ops_v1'
    draft=json.loads((study/'COMPUTE-DRAFT.json').read_bytes());fixed=json.loads((ops/'OPS-DRAFT.json').read_bytes());reserved=json.loads((ops/'BOOTSTRAP-RESERVATIONS.json').read_bytes())
    if draft['bounds']!=fixed['bounds'] or draft['bootstrap_seeds']!=reserved['bootstrap']:raise ValueError('Reviewed bounds or reservations changed')
    if reserved['inventory_collisions'] or reserved['bounded_source_audit']['hits']:raise ValueError('Unresolved seed collision')
    if [{k:m[k] for k in ('month','origins')} for m in draft['months']]!=fixed['months'] or draft['probabilities']!=[.05,.95] or draft['shards']!=12:raise ValueError('Fixed study scope changed')
    old=json.loads((e64/'PRODUCTION-AUTHORIZED.json').read_bytes())
    if old['status']!='frozen_scoring_authorized':raise ValueError('E64 input not authorized')
    dependencies={}
    names={'numerical_backend':'STUDIES/resident_predictive_harness_v1/numerical_backend.py','predictive_density':'STUDIES/predictive_value_diagnostic_v1/predictive_density.py','e64_data_contract':'STUDIES/market_replication_v1/data_contract.py'}
    for name,path in names.items():
        if remote_root+'/'+path not in source:raise ValueError('Dependency absent '+path)
        dependencies[name]=remote_root+'/'+path
    for path,want in json.loads((study/'DEPENDENCY-INVENTORY.json').read_bytes()).items():
        if source.get(remote_root+'/'+path)!=want:raise ValueError('Frozen dependency mismatch '+path)
    if remote_root+'/STUDIES/market_replication_v1/acquire.py' not in source:raise ValueError('Transitive calendar validator absent')
    acquire_hashes={value for name,value in old['sources'].items() if name.endswith('/STUDIES/market_replication_v1/acquire.py')}
    if acquire_hashes!={source[remote_root+'/STUDIES/market_replication_v1/acquire.py']}:raise ValueError('Transitive calendar validator differs from executed E64')
    draft.update(status='frozen_pending_authorization',python=old['python'],runtime=old['runtime'],sources=source,dependencies=dependencies,
        worker_path=remote_root+'/STUDIES/predictive_risk_limits_v1/worker.py',readiness_path=remote_root+'/STUDIES/predictive_risk_limits_v1/readiness.py',ops_root=remote_root+'/STUDIES/return_tail_ops_v1',
        input=dict(root=remote_input.rstrip('/'),inventory_sha256=sha(e64/'ARTIFACTS.sha256'),original_manifest_sha256=sha(e64/'PRODUCTION-AUTHORIZED.json')),
        provenance=dict(bundle_inventory_sha256=sha(bundle/'BUNDLE-MANIFEST.json'),seed_reservations_sha256=sha(ops/'BOOTSTRAP-RESERVATIONS.json'),binder_sha256=sha(__file__),scope='Stored E64 draws only; no sampling/acquisition; host lifecycle external'))
    out=Path(output);out.mkdir(exist_ok=False)
    with (out/'PRODUCTION-PENDING.json').open('x') as f:json.dump(draft,f,indent=2);f.write('\n')
    dev=json.loads(json.dumps(draft));dev['status']='development_pending_authorization';dev['input']=None;dev['provenance']['scope']='Twelve fixed literal engineering checks; no market input path or RNG consumption'
    with (out/'READINESS-PENDING.json').open('x') as f:json.dump(dev,f,indent=2);f.write('\n')
    print(json.dumps({p.name:sha(p) for p in out.iterdir()}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--remote-root',required=True);p.add_argument('--e64',required=True);p.add_argument('--remote-input',required=True);p.add_argument('--output',required=True);a=p.parse_args();bind(a.bundle,a.remote_root,a.e64,a.remote_input,a.output)
