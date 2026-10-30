import hashlib,json,runpy,sys,time
from pathlib import Path
p=Path(__file__).resolve().parent;out=Path(sys.argv[1]);seed=int(sys.argv[2]);scenario=int(sys.argv[3]);package=out/'package';package.mkdir()
data=p/f'local_recovery/gp_fresh_data01/scenario-{scenario}/DATA.json'
manifest=json.loads((p/'local_recovery/gp_fresh_data01/SUMMARY.json').read_text());assert hashlib.sha256(data.read_bytes()).hexdigest()==manifest['rows'][scenario]['data_sha256']
for name in ['common.py','conditional_v3.py','prepare_conditional_v3.py']:
    s=(p/'local_recovery/gp_conditional_local01'/name).read_text()
    if name=='common.py':
        s=s.replace('Path(__file__).resolve().parents[2]',repr(str(p)))
        s=s.replace("assert verified_data==MODELS/(NAME+'.data.json')","verified_data=Path("+repr(str(data))+")")
        s=s.replace("data=str(MODELS/(NAME+'.data.json'))","data=str(verified_data)")
    if name=='conditional_v3.py':
        s=s.replace('from common import MODELS,NAME,Target','from common import MODELS,NAME,Target,verified_data').replace("(MODELS/(NAME+'.data.json')).read_text()","verified_data.read_text()")
    (package/name).write_text(s)
sys.path.insert(0,str(package));start=time.perf_counter();runpy.run_path(str(package/'prepare_conditional_v3.py'),run_name='__main__');setup=time.perf_counter()-start
from conditional_v3 import COUNTS
for k in COUNTS:COUNTS[k]=0
refs=json.loads((p/'local_recovery/gp_fresh_reference01/SUMMARY.json').read_text());ref=next(x for x in refs['references'] if x['scenario']==scenario);assert ref['passed'];(package/'REFERENCE.json').write_text(json.dumps(ref))
s=(p/'gp_conditional_confirmation_worker.py').read_text();line="sys.path.insert(0,str(Path(__file__).resolve().parent/'local_recovery/gp_conditional_local01'))";assert line in s;s=s.replace(line,'').replace("Path(__file__).resolve().parent.parent/'gp_count/REFERENCE.json'",repr(str(package/'REFERENCE.json')))
# Keep a Path expression because the original caller invokes read_text().
s=s.replace('json.loads(('+repr(str(package/'REFERENCE.json'))+').read_text())','json.loads(Path('+repr(str(package/'REFERENCE.json'))+').read_text())')
sys.argv=[str(p/'gp_conditional_confirmation_worker.py'),str(seed),str(out)]
exec(compile(s,'newdata_importance','exec'),dict(__name__='__main__',__file__=str(p/'gp_conditional_confirmation_worker.py')))
(out/'SETUP.json').write_text(json.dumps(dict(scenario=scenario,seconds=setup,preflight=json.loads((package/'CONDITIONAL-PREFLIGHT.json').read_text())),indent=2)+'\n')
