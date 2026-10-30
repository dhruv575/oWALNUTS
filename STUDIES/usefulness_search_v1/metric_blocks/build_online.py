import hashlib, json, shutil, sys
from pathlib import Path
root = Path(__file__).resolve().parent
old = root.parent/'reconsider'
source = root/'source'
source.mkdir(exist_ok=False)
assert shutil.disk_usage(root).free > 3*1024**3
for name in ['src', 'integrations', 'STUDIES']:
    shutil.copytree(old/name, source/name, ignore=shutil.ignore_patterns('target', '__pycache__'))
for name in ['Cargo.toml', 'Cargo.lock']:
    shutil.copy2(old/name, source/name)
study = source/'STUDIES/metric_autoselect_confirmation_v1'
shutil.copy2(root/'online.rs', study/'src/bin/online.rs')
with (study/'Cargo.toml').open('a') as f:
    f.write('\n[[bin]]\nname = "online"\npath = "src/bin/online.rs"\n')
inputs = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in source.rglob('*') if p.is_file()}
(root/'SOURCE.json').write_text(json.dumps(inputs, indent=2)+'\n')
sys.path.insert(0, '/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
out = root/'build'; out.mkdir()
r = execute(['/home/ubuntu/.cargo/bin/cargo', 'build', '--release', '--offline', '--locked',
             '--bin', 'online', '-j', '4'], str(study), 300, out, 4*1024**3,
            64*1024**2, out/'worker.log', output_scan_interval=2)
r['unchanged'] = all(hashlib.sha256((source/p).read_bytes()).hexdigest() == h for p,h in inputs.items())
binary = study/'target/release/online'
r['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest() if binary.exists() else None
(root/'BUILD.json').write_text(json.dumps(r, indent=2)+'\n')
print(json.dumps(r))
assert r['exit_code'] == 0 and r['group_drained'] and r['unchanged']
