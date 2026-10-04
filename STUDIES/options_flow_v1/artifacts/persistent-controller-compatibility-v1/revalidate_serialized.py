"""Replay serialized proof validation without importing numerical libraries or sampling.
Usage: python revalidate_serialized.py EVIDENCE_DIRECTORY
Requires original raw.json files at their relative paths (raw-manifest.json binds them).
"""
import hashlib,json,sys,tempfile,zipfile
from pathlib import Path
root=Path(sys.argv[1]).resolve()
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected=json.loads((root/'serialized-validation-v2.json').read_text())
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    with zipfile.ZipFile(root/'exact-smoke-sources.zip') as z:z.extractall(tmp)
    with zipfile.ZipFile(root/'serialized-v2-controller.zip') as z:z.extractall(tmp)
    assert digest(tmp/'persistent_comparison_plan.py')==expected['controller_sha256']
    for name,item in json.loads((root/'raw-manifest.json').read_text()).items():assert digest(root/name)==item['sha256']
    sys.path.insert(0,str(tmp))
    from persistent_comparison_plan import load,sha,validate_transport_proofs,validate_fit
    rows=[]
    for backend,offset in [('numpyro',0),('pymc',10)]:
        for i in range(3):
            fp=root/f'fixture-{i}.json';f=load(fp);directory=root/f'pair0-{backend}/fit-{i}';r=load(directory/'report.json')
            contract=dict(path=str(fp),sha256=sha(fp),starts=f['data']['initial_positions'],forecast_cells=f['precision_family'])
            validate_transport_proofs(r,contract,196120001+offset+i,backend,directory)
            row=dict(backend=backend,index=i,transport_pass=True)
            try:validate_fit(r,contract,196120001+offset+i,backend,directory)
            except ValueError as exc:row['production_rejection']=str(exc)
            rows.append(row)
    assert rows==expected['rows']
    print(json.dumps(dict(status='passed',proofs=len(rows),no_sampling=True)))
