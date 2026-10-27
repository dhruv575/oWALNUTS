"""Bounded exact-decimal-token audit; no RNG and no raw numerical payload scan."""
import argparse, hashlib, json, pathlib, re, subprocess, time

p = argparse.ArgumentParser()
p.add_argument('--inventory', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
root = pathlib.Path('C:/dev/owalnuts')
inventory = pathlib.Path(a.inventory)
raw = inventory.read_bytes()
value = json.loads(raw)
print('Inventory keys:', sorted(value))
if 'long_roles' not in value or 'real_roles' not in value:
    raise ValueError('Expected explicit long roles and real_roles inventory')
reserved = {int(n) for group in ('long_roles', 'real_roles') for values in value[group].values() for n in values}
listed = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
selected = []
for name in listed:
    path = pathlib.PurePosixPath(name)
    if not name or path.suffix.lower() not in {'.py', '.rs', '.json', '.md', '.toml'}:
        continue
    parts = {s.lower() for s in path.parts}
    excluded = bool(parts & {'artifacts', 'draws', 'raw', 'data', 'datasets', 'vendor', 'node_modules', 'target', 'evidence'})
    metadata = path.suffix.lower() == '.json' and any(s in path.name.lower() for s in ('manifest', 'protocol', 'seed', 'config'))
    if excluded and not metadata:
        continue
    if path.suffix.lower() == '.json' and not metadata:
        continue
    selected.append(name)
selected.sort()
token = re.compile(r'(?<![\w.])\d(?:[\d_]*\d)?(?![\w.])')
started = time.monotonic()
hits, skipped, checked, checked_bytes = [], [], 0, 0
stopped = None
for name in selected:
    if checked >= 5000 or time.monotonic() - started >= 30:
        stopped = 'file_or_time_bound'
        break
    path = root / name
    if not path.is_file():
        skipped.append({'path': name, 'reason': 'not_present'})
        continue
    if path.stat().st_size > 2 * 1024**2:
        skipped.append({'path': name, 'reason': 'over_2MiB'})
        continue
    data = path.read_bytes()
    text = data.decode('utf8', errors='replace')
    matches = [int(m.group().replace('_', '')) for m in token.finditer(text)]
    count = sum(n in reserved for n in matches)
    if count:
        hits.append({'path': name, 'matching_token_count': count})
    checked += 1
    checked_bytes += len(data)
result = dict(scope='Tracked main source/docs and named manifest/protocol/seed/config JSON only; raw arrays and unnamed payload JSON excluded. Exact decimal integer lexical tokens, including underscore separators. Not a universal historical seed proof.', inventory_sha256=hashlib.sha256(raw).hexdigest(), reserved_unique=len(reserved), selected_files=len(selected), checked_files=checked, checked_bytes=checked_bytes, skipped=skipped, stopped=stopped, hits=hits, elapsed_seconds=time.monotonic()-started)
with pathlib.Path(a.output).open('x', encoding='utf8') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
print(json.dumps({k: result[k] for k in ('reserved_unique', 'selected_files', 'checked_files', 'stopped', 'hits', 'elapsed_seconds')}))
