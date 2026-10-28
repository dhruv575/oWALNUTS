"""One frozen T250 reference fit; invoke only through the Linux supervisor."""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, allow_nan=False)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate(spec):
    if spec.get('status') != 'frozen_authorized':
        raise ValueError('Frozen manifest required')
    required = ('worker', 'stan', 'adapter', 'capture', 'monitor', 'sdk_makefile', 'runtime_inventory')
    for name in required:
        binding = spec['bindings'][name]
        if sha(binding['path']) != binding['sha256']:
            raise ValueError('Source binding drift: '+name)
    if Path(spec['bindings']['worker']['path']).resolve() != Path(__file__).resolve():
        raise ValueError('Worker identity mismatch')
    runtime = json.loads(Path(spec['bindings']['runtime_inventory']['path']).read_bytes())['runtime']
    if sys.prefix != runtime['prefix']:
        raise ValueError('Runtime prefix drift')
    for name, version in runtime['packages'].items():
        if importlib.metadata.version(name) != version:
            raise ValueError('Runtime package drift: '+name)
    for name, digest in runtime['binaries'].items():
        if sha(name) != digest:
            raise ValueError('Runtime binary drift: '+name)
    if spec.get('sampling') != dict(chains=4, draws=4000, tune=2000, cores=4):
        raise ValueError('Fixed sampling schedule required')
    if spec.get('limits') != dict(seconds=900, rss_bytes=4*1024**3, output_bytes=512*1024**2):
        raise ValueError('Fixed resource limits required')
    seed = spec['seed']
    if type(seed) is not int or not 0 <= seed < 2**32-1:
        raise ValueError('Interoperable sampling/initialization seeds required')
    if spec.get('seed_audit', {}).get('reserved_seeds') != [seed, seed+1]:
        raise ValueError('Both external seeds must be audited')
    audit = spec['seed_audit']
    if sha(audit['path']) != audit['sha256']:
        raise ValueError('Seed audit drift')
    record = json.loads(Path(audit['path']).read_bytes())
    if record.get('status') != 'passed' or record.get('reserved_seeds') != [seed, seed+1] or record.get('collisions') != []:
        raise ValueError('Seed audit did not pass for both seeds')
    if spec.get('reference_settings', {}).get('api_and_target_verified') is not True:
        raise ValueError('Verified reference settings required')
    return spec


def extract_full(trace):
    columns = []
    for name in ('mu', 'log_sigma', 'beta'):
        a = np.asarray(trace.posterior[name].transpose('chain', 'draw'))
        if a.shape != (4, 4000):
            raise ValueError('Scalar axes mismatch')
        columns.append(a[..., None])
    z = trace.posterior['z']
    extra = [d for d in z.dims if d not in ('chain', 'draw')]
    if len(extra) != 1:
        raise ValueError('Innovation axes mismatch')
    z = np.asarray(z.transpose('chain', 'draw', extra[0]))
    if z.shape != (4, 4000, 250):
        raise ValueError('Innovation dimensions mismatch')
    full = np.concatenate(columns+[z], axis=-1)
    if full.dtype != np.float64 or not np.isfinite(full).all():
        raise ValueError('Finite float64 full draws required')
    return full


def worker(manifest, root):
    spec = validate(json.loads(Path(manifest).read_bytes()))
    root = Path(root); root.mkdir(exist_ok=False)
    started = time.monotonic()
    result = dict(status='incomplete', manifest_sha256=sha(manifest))
    try:
        binding = lambda name: spec['bindings'][name]['path']
        workspace = root/'compiler-workspace'; workspace.mkdir()
        os.environ['TMPDIR'] = str(workspace.resolve())
        tempfile.tempdir = str(workspace.resolve())
        os.environ['BRIDGESTAN'] = str(Path(binding('sdk_makefile')).resolve().parent)
        import nutpie
        import bridgestan
        adapter = load(binding('adapter'), 'literal_reference_adapter')
        capture = load(binding('capture'), 'literal_reference_capture')
        result['api'] = adapter.api_inventory(nutpie)
        y = np.resize(np.array([.001, -.002, .0005, 0., .003]), 250)
        np.save(root/'window.npy', y, allow_pickle=False)
        captures = []
        with capture.capture_compiler(bridgestan, root/'captured-libraries', captures):
            compiled = nutpie.compile_stan_model(code=Path(binding('stan')).read_text(encoding='utf-8-sig'), cleanup=False)
        if not captures:
            raise ValueError('Compiled provenance missing')
        write(root/'COMPILER.json', captures)
        model = compiled.with_data(seed=spec['seed']+1, **adapter.stan_data(y))
        trace = nutpie.sample(model, **spec['sampling'], seed=spec['seed'], save_warmup=True,
                              progress_bar=False, **spec['reference_settings']['engine_options'])
        # Preserve the full engine evidence before extracting or diagnosing it.
        trace.to_netcdf(root/'trace.nc')
        compact, metadata = adapter.extract(trace)
        full = extract_full(trace)
        np.savez_compressed(root/'draws.npz', full=full, compact=compact)
        validate(spec)
        result.update(status='complete', metadata=metadata, arrays_sha256=sha(root/'draws.npz'),
                      trace_sha256=sha(root/'trace.nc'), window_sha256=sha(root/'window.npy'))
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        result['elapsed_seconds'] = time.monotonic()-started
        write(root/'FINAL.json', result)
    return 0 if result['status']=='complete' else 1


def supervise(manifest, root):
    manifest = Path(manifest).resolve()
    spec = validate(json.loads(manifest.read_bytes()))
    root = Path(root).resolve(); root.mkdir(exist_ok=False)
    if len(os.sched_getaffinity(0)) != 4:
        raise ValueError('Exactly four allocated cores required')
    monitor = load(spec['bindings']['monitor']['path'], 'literal_reference_monitor')
    receipt = monitor.execute([sys.executable, str(Path(__file__).resolve()), str(manifest),
                               str(root/'fit'), '--worker'], cwd=str(root), cap=900,
                              output_root=root, rss_limit=4*1024**3, byte_limit=512*1024**2,
                              log_path=root/'worker.log', output_scan_interval=1,
                              utilization_path=root/'utilization.jsonl', phase_reserved_cores={'startup':4})
    write(root/'SUPERVISION.json', receipt)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') is True else 1


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('manifest'); p.add_argument('root'); p.add_argument('--worker', action='store_true')
    a=p.parse_args(); raise SystemExit((worker if a.worker else supervise)(a.manifest,a.root))
