"""Isolated mechanism probe; does not modify the project worktree."""
from pathlib import Path
import shutil,subprocess,json,hashlib
root=Path('/dev/shm/kernel-profile-20261029')
binary=root/'target/release/examples/kernel_bench'
shutil.copy2(binary,root/'baseline')
p=root/'src/kernel.rs';text=p.read_text()
old='''                let reverse_schedule =
                    generate_reverse_schedule(level, micro_steps, step, tuning.min_micro_steps);'''
new='''                let reverse_schedule = if cfg!(feature = "research")
                    || tuning.reverse_coarsening_order == ReverseCoarseningOrder::CoarsestToFinest
                {
                    generate_reverse_schedule(level, micro_steps, step, tuning.min_micro_steps)
                } else {
                    Vec::new()
                };'''
assert text.count(old)==1;p.write_text(text.replace(old,new))
with (root/'candidate-build.log').open('wb') as f:
    subprocess.run(['timeout','300','/home/ubuntu/.cargo/bin/cargo','build','--release','--locked','--offline','--example','kernel_bench','-j','4'],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
shutil.copy2(binary,root/'candidate')
out=root/'paired01';out.mkdir(exist_ok=False);rows=[]
for rep in range(8):
    for arm in (('baseline','candidate') if rep%2==0 else ('candidate','baseline')):
        r=subprocess.run(['timeout','120','taskset','-c','0',str(root/arm),'--repeat','1'],capture_output=True)
        (out/f'{rep}-{arm}.stdout').write_bytes(r.stdout);(out/f'{rep}-{arm}.stderr').write_bytes(r.stderr)
        rows.append(dict(rep=rep,arm=arm,exit_code=r.returncode))
hashes={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['baseline','candidate','src/kernel.rs','candidate.py']}
(out/'MANIFEST.json').write_text(json.dumps(dict(runs=rows,hashes=hashes),indent=2)+'\n')
print(json.dumps(rows))
