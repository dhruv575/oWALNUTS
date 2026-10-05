"""Archive immutable October launch evidence only; never inspect live fit outputs.

Run only after root confirms the frozen config and immutable handle record exist.
Large acquisition bodies, fixtures and joined features remain external, hash-bound.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def archive(config_path, handle_path, destination):
    config_path, handle_path = Path(config_path).resolve(), Path(handle_path).resolve()
    config = json.loads(config_path.read_text())
    if config.get('status') != 'frozen_awaiting_root_launch_authorization':
        raise ValueError('Reviewed frozen config required')
    if 'handle' not in handle_path.name or handle_path.name == 'execution.json':
        raise ValueError('Immutable execution-handle record required, not live execution output')
    json.loads(handle_path.read_text())
    acquisition = HERE / 'october-acquisition-v1'
    terminal = json.loads((acquisition / 'terminal.json').read_text())
    if terminal.get('status') != 'completed' or terminal.get('complete') is not True:
        raise ValueError('Acquisition must be terminal and complete')
    prepared = config_path.parent
    required = ['protocol-draft.json', 'protocol-frozen.json', 'seed-audit.json',
                'acquisition-protocol-draft.json', 'acquisition-protocol-frozen.json',
                'acquisition-command.json', 'acquisition-execution-handle.json',
                'existing-acquisition-review.json', 'root-prelaunch-review.json']
    copies = {HERE / name: 'launch/' + name for name in required}
    copies.update({acquisition / name: 'acquisition/' + name for name in
                   ['terminal.json', 'launch-identity.json', 'protocol.json', 'source.py',
                    'completed-trade-leaves.json']})
    for p in prepared.iterdir():
        if p.name.startswith('config') and p.suffix == '.json' or p.name in (
                'pregeneration-intent.json', 'source-rebind.json', 'sources.zip',
                'revised-sources.zip'):
            copies[p] = 'prepared/' + p.name
    copies[config_path] = 'prepared/' + config_path.name
    copies[handle_path] = 'launch/' + handle_path.name
    copies[Path(__file__).resolve()] = 'archive_launch.py'
    external = list(acquisition.glob('request-*.json')) + list(acquisition.glob('response-*.json'))
    external += [acquisition / n for n in ('bars.json', 'trades.jsonl', 'trades.sqlite')]
    external += [Path(c['fixture']) for c in config['cells'] if c['admission_status'] == 'ready']
    external += [Path(config['joined_features'])]
    paths = set(copies) | set(external)
    before = {str(p.resolve()): dict(sha256=digest(p), bytes=p.stat().st_size) for p in paths}
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for p, name in copies.items():
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != before[str(p.resolve())]['sha256']:
            raise ValueError('Source changed during archive: ' + str(p))
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if any(digest(p) != before[str(p.resolve())]['sha256'] for p in paths):
        raise ValueError('Immutable evidence changed during archive; incomplete archive retained')
    manifest = dict(schema='october-launch-archive-v1', status='complete',
                    config_sha256=digest(config_path), original_files=before,
                    copied_files={name: before[str(p.resolve())] for p, name in copies.items()},
                    external_only=[str(p.resolve()) for p in sorted(set(external))],
                    scope='Launch evidence only. No live execution outputs or posterior outcomes pinned; external raw bodies and fixture payloads are not copied.')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    (destination / '.gitattributes').write_text('* -text\n', encoding='utf8')
    checksums = {str(p.relative_to(destination)): digest(p) for p in destination.rglob('*') if p.is_file()}
    (destination / 'checksums.json').write_text(json.dumps(checksums, indent=2), encoding='utf8')
    print(json.dumps(dict(status='complete', destination=str(destination), files=len(checksums))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--execution-handle', required=True)
    parser.add_argument('--root-confirmed-ready', action='store_true', required=True)
    parser.add_argument('--out', default=str(ROOT / 'STUDIES/market_uncertainty_v1/artifacts/sv-october-validation-launch-v1'))
    args = parser.parse_args()
    archive(args.config, args.execution_handle, args.out)
