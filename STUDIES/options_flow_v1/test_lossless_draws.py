import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import lossless_draws as ld


class LosslessDrawTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'bundle'
        self.q = np.array([0., -0., np.nextafter(0., 1.), -1.25,
                           np.finfo(float).max, np.finfo(float).tiny]).reshape(1, 2, 3)
        self.metadata = dict(coordinates='canonical', starts=np.array([[1., -0., 3.]]),
                             diagnostics=[dict(divergent=False, count=np.int64(3))])

    def write(self, q=None):
        return ld.write_artifact(self.path, self.q if q is None else q, self.metadata)

    def edit(self, callback):
        p = self.path/'manifest.json'; value = json.loads(p.read_text())
        callback(value); p.write_text(json.dumps(value))

    def read(self, **kw):
        return ld.read_artifact(self.path, schema=ld.SCHEMA, **kw)

    def test_exact_bits_metadata_and_noncontiguous(self):
        q = self.q[..., ::-1]; info = self.write(q)
        got = self.read(expected_manifest_sha256=info['sha256'])
        np.testing.assert_array_equal(got.pop('canonical_draws').view(np.uint64), q.view(np.uint64))
        self.assertEqual(got, ld._native(self.metadata))

    def test_big_endian_bits_preserved(self):
        q = self.q.astype('>f8'); self.write(q); got = self.read()['canonical_draws']
        self.assertEqual(got.dtype.str, '>f8'); self.assertEqual(got.tobytes(), q.tobytes())

    def test_exclusive_write_preserves_existing(self):
        info = self.write()
        with self.assertRaises(FileExistsError):self.write()
        self.assertEqual(ld._sha(self.path/'manifest.json'), info['sha256'])

    def test_failed_publication_is_unreadable_and_cannot_retry(self):
        with patch.object(ld.os, 'link', side_effect=OSError('publication failure')):
            with self.assertRaises(OSError):self.write()
        with self.assertRaises(FileNotFoundError):self.read()
        with self.assertRaises(FileExistsError):self.write()

    def test_existing_manifest_never_overwritten_during_publication(self):
        real_link = ld.os.link
        def racing_link(src, dst):
            Path(dst).write_text('reserved'); return real_link(src, dst)
        with patch.object(ld.os, 'link', side_effect=racing_link):
            with self.assertRaises(FileExistsError):self.write()
        self.assertEqual((self.path/'manifest.json').read_text(), 'reserved')

    def test_corrupt_payload_hash_and_truncation(self):
        self.write(); p = self.path/'draws.npy'; data = p.read_bytes()
        p.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaisesRegex(ValueError, 'hash'):self.read()
        p.write_bytes(data[:-8])
        with self.assertRaisesRegex(ValueError, 'size/hash'):self.read()

    def test_shape_dtype_and_trailing_data_even_with_updated_hash(self):
        self.write()
        self.edit(lambda m:m['array'].update(shape=[1, 3, 2]))
        with self.assertRaisesRegex(ValueError, 'header'):self.read()
        self.edit(lambda m:m['array'].update(shape=[1, 2, 3], dtype='<f4'))
        with self.assertRaisesRegex(ValueError, 'float64'):self.read()
        p = self.path/'draws.npy'; p.write_bytes(p.read_bytes()+b'extra')
        self.edit(lambda m:m['array'].update(dtype='<f8',bytes=p.stat().st_size,sha256=ld._sha(p)))
        with self.assertRaisesRegex(ValueError, 'header/payload'):self.read()

    def test_metadata_corruption_and_trusted_manifest(self):
        info = self.write(); self.edit(lambda m:m['metadata'].update(coordinates='other'))
        with self.assertRaisesRegex(ValueError, 'Metadata digest'):self.read()
        with self.assertRaisesRegex(ValueError, 'Trusted manifest'):self.read(expected_manifest_sha256=info['sha256'])

    def test_path_escape_rejected(self):
        self.write()
        for name in ('../draws.npy', str(self.path/'draws.npy'), 'sub/draws.npy'):
            self.edit(lambda m:m['array'].update(file=name))
            with self.assertRaisesRegex(ValueError, 'path escape'):self.read()

    def test_pickle_payload_never_loaded(self):
        self.write(); p = self.path/'draws.npy'
        np.save(p, np.array([object()], dtype=object), allow_pickle=True)
        self.edit(lambda m:m['array'].update(bytes=p.stat().st_size, sha256=ld._sha(p)))
        with patch.object(ld.np, 'load', side_effect=AssertionError('must reject header first')):
            with self.assertRaisesRegex(ValueError, 'header/payload'):self.read()

    def test_invalid_array_and_metadata_rejected_before_reservation(self):
        for q in (np.zeros((1, 2, 3), dtype='f4'), self.q.tolist(), np.zeros((0, 2, 3)),
                  np.full((1, 2, 3), np.nan), np.full((1, 2, 3), np.inf)):
            with self.assertRaises(ValueError):self.write(q)
            self.assertFalse(self.path.exists())
        for metadata in ({'canonical_draws':[]}, {'x':float('nan')}, {1:'x'}, {'x':object()}):
            with self.assertRaises(ValueError):ld.write_artifact(self.path,self.q,metadata)
            self.assertFalse(self.path.exists())

    def test_nonfinite_payload_even_with_matching_hash_rejected(self):
        self.write(); p=self.path/'draws.npy'; np.save(p,np.full((1,2,3),np.nan),allow_pickle=False)
        self.edit(lambda m:m['array'].update(bytes=p.stat().st_size,sha256=ld._sha(p)))
        with self.assertRaisesRegex(ValueError, 'finite'):self.read()

    def test_limits_and_explicit_schema(self):
        self.write()
        with self.assertRaises(ValueError):self.read(max_array_bytes=47)
        with self.assertRaises(ValueError):self.read(max_json_bytes=1)
        with self.assertRaises(ValueError):self.read(max_array_bytes=True)
        with self.assertRaises(ValueError):ld.read_artifact(self.path,schema='auto')
        with self.assertRaises(TypeError):ld.read_artifact(self.path)

    def test_legacy_read_only_exact_bits(self):
        p=Path(self.temp.name)/'legacy.json';p.write_text(json.dumps(dict(ld._native(self.metadata),canonical_draws=self.q.tolist())))
        before=ld._sha(p);got=ld.read_artifact(p,schema=ld.LEGACY,expected_manifest_sha256=before)
        np.testing.assert_array_equal(got.pop('canonical_draws').view(np.uint64),self.q.view(np.uint64))
        self.assertEqual(got,ld._native(self.metadata));self.assertEqual(ld._sha(p),before)
        p.write_text('{"canonical_draws": [[[NaN]]]}')
        with self.assertRaises(ValueError):ld.read_artifact(p,schema=ld.LEGACY)

    def test_duplicate_json_keys_rejected(self):
        self.write();p=self.path/'manifest.json';p.write_text('{"schema":"a","schema":"b"}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.read()

    def test_array_symlink_rejected_before_loading(self):
        self.write();p=self.path/'draws.npy';actual_is_symlink=Path.is_symlink
        with patch.object(Path,'is_symlink',lambda x: x==p or actual_is_symlink(x)):
            with self.assertRaisesRegex(ValueError,'escapes'):self.read()

    def test_boolean_shape_rejected(self):
        self.write();self.edit(lambda m:m['array'].update(shape=[True,2,3]))
        with self.assertRaisesRegex(ValueError,'shape'):self.read()


if __name__ == '__main__':
    unittest.main()
