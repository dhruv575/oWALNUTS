import hashlib,json,os,subprocess
from pathlib import Path
root=Path('/dev/shm/bounded-init-20261030');study=root/'STUDIES/grad_init_metric_v1'
import tarfile
patches={
 'pdb_cell.rs': ('"gradinit" => custom()?.with_initial_metric(InitialMetric::nutpie())?,','"bounded" => custom()?.with_initial_metric(InitialMetric::GradientScaled { lower: 0.1, upper: 1000.0 })?,'),
 'sv_cell.rs': ('"gradinit" => Adaptation::Custom(custom()?.with_initial_metric(InitialMetric::nutpie())?),','"bounded" => Adaptation::Custom(custom()?.with_initial_metric(InitialMetric::GradientScaled { lower: 0.1, upper: 1000.0 })?),'),
 'funnel.rs': ('"gradinit" => gradinit(custom()?)?,','"bounded" => custom()?.with_initial_metric(InitialMetric::GradientScaled { lower: 0.1, upper: 1000.0 }).map_err(|e| e.to_string())?,')}
prepared=[]
with tarfile.open(root/'source.tar') as tar:
 for name,(old,new) in patches.items():
  p=study/'src/bin'/name;s=tar.extractfile('STUDIES/grad_init_metric_v1/src/bin/'+name).read().decode();assert s.count(old)==1,(name,s.count(old));prepared.append((p,s.replace(old,old+'\n        '+new)))
for p,s in prepared:p.write_text(s)
env=os.environ.copy();env['CARGO_TARGET_DIR']=str(root/'target');env['CARGO_BUILD_JOBS']='4'
steps=[('build',['build','--release','--offline','--locked','--bins'],study),('tests',['test','--release','--offline','--locked','--features','research','--test','grad_init_metric','--test','kernel_fingerprint'],root)]
results=[]
for label,args,cwd in steps:
 with (root/(label+'.log')).open('xb') as f:r=subprocess.run(['timeout','300','/home/ubuntu/.cargo/bin/cargo',*args],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(step=label,exit_code=r.returncode))
 if r.returncode:break
files=[root/'src/walnutpie.rs',root/'src/kernel.rs',Path(__file__)]+list((study/'src/bin').glob('*.rs'))+[root/'target/release'/name for name in ['pdb-cell','sv-cell','funnel'] if (root/'target/release'/name).exists()]
(root/'BUILD.json').write_text(json.dumps(dict(steps=results,files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2)+'\n');print(json.dumps(results));raise SystemExit(results[-1]['exit_code'])
