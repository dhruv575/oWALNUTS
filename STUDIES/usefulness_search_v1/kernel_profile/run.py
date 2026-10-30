import hashlib,json,subprocess,time
from pathlib import Path
root=Path('/dev/shm/kernel-profile-20261029')
out=root/'measured01';out.mkdir(exist_ok=False)
binary=root/'target/release/examples/kernel_bench'
rows=[]
for i in range(5):
    start=time.monotonic()
    r=subprocess.run(['timeout','120','taskset','-c','0',str(binary),'--repeat','1'],capture_output=True)
    (out/f'run-{i}.stdout').write_bytes(r.stdout)
    (out/f'run-{i}.stderr').write_bytes(r.stderr)
    rows.append(dict(rep=i,exit_code=r.returncode,seconds=time.monotonic()-start))
(out/'MANIFEST.json').write_text(json.dumps(dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),runs=rows),indent=2)+'\n')
print(json.dumps(rows))
