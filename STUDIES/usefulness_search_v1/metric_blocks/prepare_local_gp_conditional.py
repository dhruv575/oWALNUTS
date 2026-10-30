"""Explicit local path adapter; preserve archived cloud implementations."""
import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parent;source=p.parent/'gp_count';out=p/'local_recovery/gp_conditional_local01';out.mkdir(exist_ok=False)
manifest={}
for name in ['common.py','conditional_v3.py','prepare_conditional_v3.py']:
    f=source/name;manifest[name]=hashlib.sha256(f.read_bytes()).hexdigest()
    text=f.read_text()
    if name=='common.py':
        old="MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');NAME='gp_pois_regr-gp_pois_regr'"
        new="""import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from native_common import model_files
NAME='gp_pois_regr-gp_pois_regr'
verified_so,verified_data,verified_source=model_files(NAME)
MODELS=verified_so.parent
assert verified_data==MODELS/(NAME+'.data.json')"""
        assert old in text;text=text.replace(old,new)
    compile(text,name,'exec');(out/name).write_text(text)
(out/'ADAPTER.json').write_text(json.dumps(dict(original_source_hashes=manifest,scope='Only common.py model path resolution replaced with verified native_common.model_files; preparation and conditional algorithm copied unchanged.',adapted_hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.glob('*.py')}),indent=2)+'\n')
print('Prepared isolated local conditional preflight')
