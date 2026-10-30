import hashlib,json,shutil,difflib
from pathlib import Path
p=Path(__file__).resolve().parent;repo=p.parents[2];l=p/'local_recovery';out=l/'momentum_pool_source01';out.mkdir(exist_ok=False);shutil.copytree(repo/'src',out/'src');(out/'Cargo.toml').write_text((l/'cold_wal_source01/Cargo.toml').read_text().replace('owalnuts-recycling-research','owalnuts-momentum-pool-research'));(out/'ORIGINAL-SOURCE.json').write_text(json.dumps({str(f.relative_to(repo)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (repo/'src').rglob('*') if f.is_file()},indent=2)+'\n')
f=out/'src/kernel.rs';old=f.read_text();text=old;needle='''let rho_sum = if momentum_sum {
            state.rho.clone()''';assert text.count(needle)==1;text=text.replace(needle,'''let rho_sum = if momentum_sum {
            acquire_momentum_sum(&state.rho)''');needle='''        Self {
            backward: earlier.backward,''';assert text.count(needle)==1;text=text.replace(needle,'''        release_momentum_sum(later.rho_sum);
        Self {
            backward: earlier.backward,''');text+='\n'+(p/'momentum_pool_fragment.rs').read_text();f.write_text(text);(p/'MOMENTUM-POOL-KERNEL.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='src/kernel.rs',tofile='momentum_pool_source01/src/kernel.rs',n=0)))
for oldname,newname in [('cold_wal_original_runner','momentum_pool_runner'),('allocation_probe_runner','momentum_pool_probe_runner')]:
    d=p/newname;d.mkdir(exist_ok=False);(d/'src').mkdir();manifest=(p/oldname/'Cargo.toml').read_text().replace(oldname.replace('_','-'),newname.replace('_','-')).replace('owalnuts = { path = "../../../.." }','owalnuts = {package="owalnuts-momentum-pool-research",path="../local_recovery/momentum_pool_source01"}');assert 'owalnuts-momentum-pool-research' in manifest;(d/'Cargo.toml').write_text(manifest);(d/'src/main.rs').write_text((p/oldname/'src/main.rs').read_text())
build=(p/'build_allocation_probe.py').read_text().replace('allocation_probe_build01','momentum_pool_build01').replace("[('allocation_probe_runner',[])]","[('momentum_pool_runner',[]),('momentum_pool_probe_runner',[])]");(p/'build_momentum_pool.py').write_text(build)
