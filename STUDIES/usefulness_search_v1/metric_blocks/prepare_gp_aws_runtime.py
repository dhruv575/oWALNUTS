import hashlib,json,shutil,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_aws_runtime_bundle01';r.mkdir(exist_ok=False)
for n in ['models','data']:(r/n).mkdir()
for n in ['native_common.py','count_target.cpp','check_gp_aws_runtime.py']:shutil.copyfile(p/n,r/n)
shutil.copyfile(l/'counter01/bridgestan.h',r/'bridgestan.h')
name='gp_pois_regr-gp_pois_regr';d=l/'threaded_targets01'/name
for src,dst in [(d/(name+'_model.so'),'raw.so'),(d/(name+'.stan'),'raw.stan'),(l/'bounded_gp_target01/bounded_gp_model.so','bounded.so'),(p/'bounded_gp.stan','bounded.stan'),(l/'gp_widegrid_bundle01/libtbb.so.2','libtbb.so.2')]:shutil.copyfile(src,r/'models'/dst)
build=json.loads((l/'gp_wal_build02/SUMMARY.json').read_text());binary=Path(build['rows'][1]['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['rows'][1]['binary_sha256'];shutil.copyfile(binary,r/'gp-wal-tuned-runner');(r/'gp-wal-tuned-runner').chmod(0o755)
for i in range(4):
 shutil.copyfile(l/f'gp_fresh_data01/scenario-{i}/DATA.json',r/f'data/{i}.json')
 for arm in ['affine','bounded']:shutil.copyfile(l/f'gp_wal_pilot01/scenario-{i}/{arm}.json',r/f'data/{i}-{arm}.json')
manifest={str(f.relative_to(r)):hashlib.sha256(f.read_bytes()).hexdigest() for f in r.rglob('*') if f.is_file()};(r/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(l/'gp_aws_runtime_bundle01.tar.gz','w:gz') as t:
 for f in r.rglob('*'):
  if f.is_file():t.add(f,arcname=str(f.relative_to(r)),recursive=False)
print(hashlib.sha256((l/'gp_aws_runtime_bundle01.tar.gz').read_bytes()).hexdigest())
