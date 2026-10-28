import argparse,hashlib,importlib.util,json,sys
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('job',type=int);p.add_argument('out');a=p.parse_args()
    manifest=json.loads(Path(a.manifest).read_bytes())
    for name,want in manifest['new_sources'].items():
        if sha(name)!=want:raise ValueError('New source drift')
    old_path=Path(manifest['parent_manifest'])
    if sha(old_path)!=manifest['parent_sha256']:raise ValueError('Parent drift')
    spec=json.loads(old_path.read_bytes())
    if not 0<=a.job<24:raise ValueError('Job index')
    # Select unchanged historical modules in this isolated process.
    sys.path.insert(0,str(Path(spec['worker_path']).parent));sys.path.append(spec['e62_root'])
    import data_contract
    month=spec['months'][a.job//8];index=a.job%8
    data_contract.configure(month['month'])
    y=data_contract.load_sealed(spec['acquisition'],month['month'])
    selected=dict(spec,reference_ticks=month['reference_ticks'],seeds=dict(month['seeds']))
    selected['seeds']['references']=[703028000+1000*(8*(a.job//8)+i) for i in range(8)]
    selected['dependencies']=dict(spec['dependencies'],independent_adapter=str(Path(__file__).with_name('extended_adapter.py')))
    reference=load(Path(spec['e62_root'])/'run_reference.py','extension_reference')
    reference.TICKS=month['reference_ticks']
    result=reference.run(selected,y,Path(a.out)/month['month'],index)
    print(json.dumps(dict(job=a.job,month=month['month'],status=result['status'],passed=result.get('reference_diagnostics_pass'))))
    return 0 if result['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
