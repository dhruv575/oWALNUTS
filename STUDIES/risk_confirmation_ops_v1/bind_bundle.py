"""Offline exact-source/runtime binding with opaque sealed acquisition identities."""
import argparse,hashlib,json
from pathlib import Path
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bind(bundle,remote,e64_manifest,e65_manifest,acquisition,out):
    bundle=Path(bundle);remote=remote.rstrip('/');old=json.loads(Path(e64_manifest).read_bytes());tail=json.loads(Path(e65_manifest).read_bytes())
    if old['status']!='frozen_scoring_authorized' or tail['status']!='frozen_authorized' or old['runtime']!=tail['runtime'] or old['python']!=tail['python']:raise ValueError('Executed prior runtime mismatch')
    sources=dict(old['sources'])
    for name,want in tail['sources'].items():
        if name in sources and sources[name]!=want:raise ValueError('Prior source identity disagreement')
        sources[name]=want
    inventory=json.loads((bundle/'BUNDLE-MANIFEST.json').read_bytes())
    for name,want in inventory['files'].items():
        path=(bundle/name).resolve()
        if not path.is_relative_to(bundle.resolve()) or sha(path)!=want:raise ValueError('Bundle source drift '+name)
        sources[remote+'/'+name]=want
    study=bundle/'STUDIES/fresh_risk_confirmation_v1';ops=bundle/'STUDIES/risk_confirmation_ops_v1';draft=json.loads((study/'COMPUTE-DRAFT.json').read_bytes());fixed=json.loads((ops/'OPS-DRAFT.json').read_bytes());reserved=json.loads((ops/'SEED-RESERVATIONS.json').read_bytes());sdk=json.loads((ops/'SDK-BUILD-HASH-INVENTORY.json').read_bytes())
    if any(draft['bounds'].get(k)!=v for k,v in fixed['bounds'].items()) or draft['bounds']['score_call_seconds']!=5:raise ValueError('Bounds changed')
    if reserved['collisions'] or reserved['bounded_metadata_audit']['hits']:raise ValueError('Unresolved seed collision')
    for month,seeds in zip(draft['months'],reserved['months']):
        expected=dict(candidate=dict(initial=seeds['initial'],warm=seeds['warm']),references=[seeds['reference_base']+1000*i for i in range(8)],bootstrap=seeds['bootstrap'])
        if month['month']!=seeds['month'] or month['origins']!=seeds['origins'] or month['seeds']!=expected:raise ValueError('Seed/calendar reservation mismatch')
    if draft['reference']['engine_options']!=old['reference']['engine_options']:raise ValueError('Independent sampler options changed')
    for product in sdk['selected_hashes']:sources[sdk['root']+'/'+product['path']]=product['sha256']
    e62_root=old['e62_root']
    for name,want in json.loads((study/'REUSE-IDENTITIES.json').read_bytes())['sources'].items():
        oldpath=e62_root+'/STUDIES/fresh_real_value_v1/'+name
        if old['sources'].get(oldpath)!=want:raise ValueError('Native dependency drift '+name)
    acquisition=json.loads(Path(acquisition).read_bytes());local=Path(acquisition['directory'])
    for name,key in (('terminal.json','terminal_sha256'),('protocol.json','protocol_sha256'),('bars.json','bars_sha256')):
        if sha(local/name)!=acquisition[key]:raise ValueError('Sealed acquisition identity changed '+name)
    if sha(acquisition['supervisor_final_path'])!=acquisition['supervisor_final_sha256']:raise ValueError('Acquisition admission changed')
    lane=remote.rsplit('/',1)[0];acquisition['directory']=lane+'/acquisition';acquisition['supervisor_final_path']=lane+'/acquisition-supervisor-final.json'
    dependencies=dict(old['dependencies']);dependencies['numerical_backend']=tail['dependencies']['numerical_backend']
    draft.update(status='frozen_scoring_pending_authorization',runtime=old['runtime'],python=old['python'],sources=sources,dependencies=dependencies,reference=old['reference'],e62_root=e62_root,
        worker_path=remote+'/STUDIES/fresh_risk_confirmation_v1/worker.py',readiness_path=remote+'/STUDIES/fresh_risk_confirmation_v1/readiness.py',ops_root=remote+'/STUDIES/risk_confirmation_ops_v1',acquisition=acquisition,
        bootstrap_seeds={m['month']:m['seeds']['bootstrap'] for m in draft['months']},sdk_build=sdk,
        provenance=dict(e64_manifest_sha256=sha(e64_manifest),e65_manifest_sha256=sha(e65_manifest),bundle_inventory_sha256=sha(bundle/'BUNDLE-MANIFEST.json'),seed_reservations_sha256=sha(ops/'SEED-RESERVATIONS.json'),sdk_inventory_sha256=sha(ops/'SDK-BUILD-HASH-INVENTORY.json'),binder_sha256=sha(__file__)))
    out=Path(out);out.mkdir(exist_ok=False)
    with (out/'PRODUCTION-PENDING.json').open('x') as f:json.dump(draft,f,indent=2);f.write('\n')
    dev=json.loads(json.dumps(draft));dev.update(status='development_pending_authorization',acquisition=None)
    for month in dev['months']:month['seeds']=dict(candidate=dict(initial=993711000,warm=993712000),references=[993713000]*8,bootstrap=17)
    dev['bootstrap_seeds']={m['month']:17 for m in dev['months']};dev['provenance']['scope']='Fixed literal engineering replay and deliberately reused development seeds; no market input path'
    with (out/'READINESS-PENDING.json').open('x') as f:json.dump(dev,f,indent=2);f.write('\n')
    print(json.dumps({p.name:sha(p) for p in out.iterdir()}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--remote',required=True);p.add_argument('--e64-manifest',required=True);p.add_argument('--e65-manifest',required=True);p.add_argument('--acquisition',required=True);p.add_argument('--out',required=True);a=p.parse_args();bind(a.bundle,a.remote,a.e64_manifest,a.e65_manifest,a.acquisition,a.out)
