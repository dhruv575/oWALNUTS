import hashlib,json,os,sys,shutil,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'compact_wal_stable_build01';r.mkdir(exist_ok=False)
cache=Path('/home/dhruv/.cache/owalnuts/compact-wal-stable01');cache.mkdir(exist_ok=True)
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']=str(cache)
sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
rows=[]
for name in ['compact_original_runner','compact_recycling_runner']:
    folder=r/name;folder.mkdir()
    for action in ['build','test']:
        assert shutil.disk_usage(cache).free>2*1024**3
        result=execute(['cargo','+stable',action,'--release','--offline','--locked','-j','1'],str(p/name),300,cache,4*1024**3,2*1024**3,folder/(action+'.log'),output_scan_interval=2)
        (folder/(action+'-SUPERVISION.json')).write_text(json.dumps(result,indent=2)+'\n');assert result['exit_code']==0 and result['group_drained']
    binary=cache/'release'/name.replace('_','-');rows.append(dict(package=name,binary=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,compiler=subprocess.check_output(['rustc','+stable','--version'],text=True).strip()),indent=2)+'\n')
