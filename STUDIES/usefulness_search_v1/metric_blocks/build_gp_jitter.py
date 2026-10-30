import hashlib,json,os,sys,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'gp_jitter_build01';root.mkdir(exist_ok=False);cache=Path('/home/dhruv/.cache/owalnuts/native-recycling01');cache.mkdir(exist_ok=True)
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']=str(cache);sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
rows=[]
for name,features in [('gp_jitter_original_runner',[]),('gp_jitter_candidate_runner',[])]:
    folder=root/name;folder.mkdir();package=study/name
    for label,command,cap in [('lock',['cargo','+stable','generate-lockfile'],180),('fetch',['cargo','+stable','fetch','--locked'],180),('build',['cargo','+stable','build','--release','--offline','--locked','-j','1']+features,300),('test',['cargo','+stable','test','--release','--offline','--locked','-j','1']+features,180)]:
        assert shutil.disk_usage(cache).free>2*1024**3;r=execute(command,str(package),cap,cache,4*1024**3 if label in ['build','test'] else 2*1024**3,2*1024**3,folder/(label+'.log'),output_scan_interval=2);(folder/(label+'-SUPERVISION.json')).write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'],(name,label)
    binary=cache/'release'/name.replace('_','-');rows.append(dict(package=name,binary=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,compiler='rustc 1.99.1 (58cf8f9c3 2026-10-13)'),indent=2)+'\n');print(json.dumps(rows))
