"""Versioned canonical-draw bundles; publication of manifest.json commits a bundle.

The exclusive directory is retained after a failed write, preventing accidental
retry/overwrite. Readers reject incomplete bundles. Hashes detect corruption;
pass a trusted expected_manifest_sha256 to bind provenance, not just consistency.
No sampler, coordinate transform, diagnostics or RNG is invoked here.
"""
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

SCHEMA = 'canonical-npy-v1'
LEGACY = 'legacy-json-v1'
DEFAULT_MAX_BYTES = 2**31


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def _native(value):
    if isinstance(value, np.ndarray):
        return _native(value.tolist())
    if isinstance(value, np.generic):
        return _native(value.item())
    if isinstance(value, dict):
        if any(type(k) is not str for k in value):
            raise ValueError('Metadata keys must be strings')
        return {k: _native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(v) for v in value]
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError('Metadata must contain finite JSON values')


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _read_json(path):
    with Path(path).open('r', encoding='utf-8') as f:
        value = json.load(f, object_pairs_hook=_unique_object,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    return _native(value)


def _limit(limit):
    if type(limit) is not int or limit <= 0:
        raise ValueError('max_array_bytes must be a positive integer')


def _array(q, limit):
    _limit(limit)
    if not isinstance(q, np.ndarray) or q.dtype.kind != 'f' or q.dtype.itemsize != 8:
        raise ValueError('Canonical draws must be a float64 ndarray; no implicit cast')
    if q.ndim != 3 or any(n <= 0 for n in q.shape) or q.nbytes > limit:
        raise ValueError('Expected nonempty chain x draw x parameter array within limit')
    if not np.isfinite(q).all():
        raise ValueError('Canonical draws must be finite')


def _metadata(metadata):
    if not isinstance(metadata, dict) or 'canonical_draws' in metadata:
        raise ValueError('Metadata must be a dict without canonical_draws')
    return _native(metadata)


def write_artifact(directory, canonical_draws, metadata, *, max_array_bytes=DEFAULT_MAX_BYTES):
    """Create a new bundle only; manifest returned after atomic publication.

    Caller must not mutate draws/metadata concurrently. Array bytes are written
    without coercion; signed zero and all finite float64 bits are retained.
    """
    _array(canonical_draws, max_array_bytes)
    metadata = _metadata(metadata)
    directory = Path(directory)
    directory.mkdir()  # Exclusive reservation; parents must already exist.
    array_path = directory/'draws.npy'
    pending = directory/'draws.npy.pending'
    with pending.open('xb') as f:
        np.save(f, canonical_draws, allow_pickle=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(pending, array_path)
    manifest = dict(schema=SCHEMA, array=dict(file='draws.npy',
        sha256=_sha(array_path), bytes=array_path.stat().st_size,
        dtype=canonical_draws.dtype.str, shape=list(canonical_draws.shape)),
        metadata=metadata, metadata_sha256=hashlib.sha256(_json_bytes(metadata)).hexdigest())
    temporary = directory/'manifest.json.pending'
    with temporary.open('xb') as f:
        f.write(_json_bytes(manifest)); f.flush(); os.fsync(f.fileno())
    # Same-directory hard link publishes complete bytes atomically and refuses
    # an existing destination, unlike replacement. Unsupported FS fails closed.
    committed = directory/'manifest.json'
    os.link(temporary, committed)
    temporary.unlink()
    return dict(schema=SCHEMA, path=str(committed.resolve()),
                sha256=_sha(committed), array_sha256=manifest['array']['sha256'])


def read_artifact(path, *, schema, expected_manifest_sha256=None,
                  max_array_bytes=DEFAULT_MAX_BYTES, max_json_bytes=DEFAULT_MAX_BYTES):
    """Read an explicitly selected schema; legacy JSON is read-only.

    For canonical-npy-v1, path is the bundle directory. For legacy-json-v1 it
    is the legacy raw JSON file. The optional expected digest binds respectively
    manifest.json or the complete legacy JSON file. No format auto-detection.
    max_json_bytes separately bounds encoded JSON before parsing; parsing legacy
    JSON can use more memory than its file size. max_array_bytes bounds decoded
    array payload. Both limits require explicit overrides for larger artifacts.
    """
    _limit(max_array_bytes)
    _limit(max_json_bytes)
    if schema not in (SCHEMA, LEGACY):
        raise ValueError('Unknown explicit artifact schema')
    path = Path(path)
    manifest_path = path/'manifest.json' if schema == SCHEMA else path
    if path.is_symlink() or manifest_path.is_symlink():
        raise ValueError('Symlink artifact paths are not allowed')
    if manifest_path.stat().st_size > max_json_bytes:
        raise ValueError('JSON exceeds encoded byte limit')
    if expected_manifest_sha256 is not None and _sha(manifest_path) != expected_manifest_sha256:
        raise ValueError('Trusted manifest hash mismatch')
    value = _read_json(manifest_path)
    if schema == LEGACY:
        if not isinstance(value, dict) or 'canonical_draws' not in value:
            raise ValueError('Legacy raw JSON lacks canonical_draws')
        try:
            q = np.asarray(value.pop('canonical_draws'), dtype=np.float64)
        except (TypeError, ValueError) as exc:
            raise ValueError('Malformed legacy draws') from exc
        _array(q, max_array_bytes)
        return dict(_metadata(value), canonical_draws=q)
    if not isinstance(value, dict) or set(value) != {'schema', 'array', 'metadata', 'metadata_sha256'} or value['schema'] != SCHEMA:
        raise ValueError('Invalid manifest schema')
    metadata = _metadata(value['metadata'])
    if hashlib.sha256(_json_bytes(metadata)).hexdigest() != value['metadata_sha256']:
        raise ValueError('Metadata digest mismatch')
    a = value['array']
    if not isinstance(a, dict) or set(a) != {'file','sha256','bytes','dtype','shape'} or a['file'] != 'draws.npy':
        raise ValueError('Invalid array descriptor or path escape')
    shape = a['shape']
    if not isinstance(shape, list) or len(shape) != 3 or any(type(n) is not int or n <= 0 for n in shape):
        raise ValueError('Invalid array shape')
    if math.prod(shape)*8 > max_array_bytes:
        raise ValueError('Declared array exceeds byte limit')
    try:
        dtype = np.dtype(a['dtype'])
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid dtype') from exc
    if dtype.kind != 'f' or dtype.itemsize != 8 or dtype.str != a['dtype']:
        raise ValueError('Only explicit float64 dtype supported')
    file = path/a['file']
    if file.is_symlink() or file.resolve().parent != path.resolve():
        raise ValueError('Array escapes bundle')
    if type(a['bytes']) is not int or file.stat().st_size != a['bytes'] or _sha(file) != a['sha256']:
        raise ValueError('Array size/hash mismatch')
    with file.open('rb') as f:
        version = np.lib.format.read_magic(f)
        if version == (1, 0):
            header_shape, fortran, header_dtype = np.lib.format.read_array_header_1_0(f)
        elif version == (2, 0):
            header_shape, fortran, header_dtype = np.lib.format.read_array_header_2_0(f)
        else:
            raise ValueError('Unsupported NPY version')
        if tuple(shape) != header_shape or header_dtype != dtype or f.tell()+math.prod(shape)*8 != a['bytes']:
            raise ValueError('NPY header/payload differs from manifest')
        f.seek(0)
        q = np.load(f, allow_pickle=False)
    _array(q, max_array_bytes)
    return dict(metadata, canonical_draws=q)
