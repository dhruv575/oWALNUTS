"""Build binaries with source-bound provenance; never attest an existing build retroactively.

Run: python build.py --toolchain 1.88.0-x86_64-pc-windows-gnu
Check: python build.py --verify
This records a reproducibility chain, not a signed or adversary-resistant attestation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BINARY_NAMES = ('options-flow-v1', 'local-level-v1')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_snapshot(study_dir=HERE):
    """Hash all library/study source (including bin/), manifests, locks and build config."""
    study = Path(study_dir).resolve()
    root = study.parents[1]
    paths = set()
    crates = [root, study]
    if (root/'integrations'/'autodiff'/'Cargo.toml').is_file():
        crates.append(root/'integrations'/'autodiff')
    for crate in crates:
        for required in ('Cargo.toml', 'Cargo.lock'):
            path = crate / required
            if not path.is_file():
                raise ValueError(f'Missing required build input: {path}')
            paths.add(path)
        paths.update(p for p in (crate / 'src').rglob('*') if p.is_file())
        for name in ('build.rs', 'rust-toolchain', 'rust-toolchain.toml'):
            if (crate / name).is_file():
                paths.add(crate / name)
    # Cargo searches config from the build cwd through its ancestors.
    for directory in (study, *study.parents):
        for name in ('config', 'config.toml'):
            path = directory / '.cargo' / name
            if path.is_file():
                paths.add(path)
    if (study / 'build.py').is_file():
        paths.add(study / 'build.py')
    return {os.path.relpath(p, root).replace('\\', '/'): sha256(p)
            for p in sorted(paths)}


def manifest_path(study_dir=HERE):
    return Path(study_dir) / 'target' / 'release' / 'build-provenance.json'


def verify_attestation(study_dir=HERE, executable=None):
    """Raise ValueError for absent/stale/tampered provenance; return the manifest."""
    study = Path(study_dir).resolve()
    path = manifest_path(study)
    if not path.is_file():
        raise ValueError('Unattested build: run build.py before qualification')
    record = json.loads(path.read_text())
    if record.get('schema_version') != 1 or record.get('status') != 'built-and-verified':
        raise ValueError('Unsupported or incomplete build provenance')
    current = source_snapshot(study)
    if current != record.get('source_sha256'):
        raise ValueError('Build sources changed since attested compilation')
    expected_names = {name + ('.exe' if os.name == 'nt' else '') for name in BINARY_NAMES}
    recorded = record.get('executables', {})
    if set(recorded) != expected_names:
        raise ValueError('Incomplete executable provenance')
    for name, digest in recorded.items():
        binary = study / 'target' / 'release' / name
        if not binary.is_file() or sha256(binary) != digest:
            raise ValueError(f'Executable missing or changed: {name}')
    if executable is not None:
        binary = Path(executable).resolve()
        if binary.parent != (study / 'target' / 'release').resolve() or binary.name not in recorded:
            raise ValueError('Requested executable is outside attested binaries')
    return record


def atomic_json(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build(toolchain, study_dir=HERE):
    study = Path(study_dir).resolve()
    before = source_snapshot(study)
    compiler = subprocess.check_output(['rustc', f'+{toolchain}', '-Vv'], text=True).strip()
    command = ['cargo', f'+{toolchain}', 'build', '--release', '--locked',
               '--manifest-path', str(study / 'Cargo.toml'),
               '--target-dir', str(study / 'target')]
    # Invalidate old evidence before attempting a new build, including a failed one.
    output = manifest_path(study)
    output.unlink(missing_ok=True)
    subprocess.run(command, cwd=study, check=True)
    after = source_snapshot(study)
    if before != after:
        raise RuntimeError('Build inputs changed during compilation; no attestation written')
    suffix = '.exe' if os.name == 'nt' else ''
    binaries = {name + suffix: sha256(study / 'target' / 'release' / (name + suffix))
                for name in BINARY_NAMES}
    record = {
        'schema_version': 1, 'status': 'built-and-verified',
        'built_at_utc': datetime.now(timezone.utc).isoformat(),
        'command': command, 'toolchain': toolchain, 'rustc_verbose': compiler,
        'source_sha256': after, 'executables': binaries,
        'build_environment': {key: value for key, value in os.environ.items()
                              if key in ('RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS',
                                         'RUSTC_WRAPPER', 'RUSTC_WORKSPACE_WRAPPER',
                                         'CARGO_BUILD_TARGET', 'CARGO_HOME')},
        'limitations': 'Local unsigned source/binary binding; does not authenticate compiler or dependency supply chain.'
    }
    atomic_json(output, record)
    verify_attestation(study)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', default='1.88.0-x86_64-pc-windows-gnu' if os.name == 'nt' else '1.88.0')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    record = verify_attestation() if args.verify else build(args.toolchain)
    print(json.dumps({'status': record['status'], 'manifest': str(manifest_path()),
                      'executables': record['executables']}, indent=2))


if __name__ == '__main__':
    main()
