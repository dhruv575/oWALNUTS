import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.study = self.root/'STUDIES'/'options_flow_v1'
        for crate in (self.root, self.study, self.root/'integrations'/'autodiff'):
            (crate/'src'/'bin').mkdir(parents=True)
            (crate/'Cargo.toml').write_text('manifest')
            (crate/'Cargo.lock').write_text('lock')
            (crate/'src'/'main.rs').write_text('source')
        (self.study/'src'/'bin'/'other.rs').write_text('nested source')
        self.output = self.study/'target'/'release'
        self.output.mkdir(parents=True)
        self.binaries = {}
        for name in build.BINARY_NAMES:
            name += '.exe' if os.name == 'nt' else ''
            binary = self.output/name
            binary.write_bytes(b'binary')
            self.binaries[name] = build.sha256(binary)
        self.record = {'schema_version':1, 'status':'built-and-verified',
                       'source_sha256':build.source_snapshot(self.study),
                       'executables':self.binaries}
        build.atomic_json(build.manifest_path(self.study), self.record)

    def test_nested_source_tamper_refused(self):
        build.verify_attestation(self.study)
        (self.study/'src'/'bin'/'other.rs').write_text('changed source')
        with self.assertRaisesRegex(ValueError, 'sources changed'):
            build.verify_attestation(self.study)

    def test_core_source_tamper_refused(self):
        (self.root/'src'/'main.rs').write_text('changed library')
        with self.assertRaises(ValueError):
            build.verify_attestation(self.study)

    def test_binary_tamper_refused(self):
        (self.output/next(iter(self.binaries))).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'Executable missing or changed'):
            build.verify_attestation(self.study)

    def test_autodiff_dependency_tamper_refused(self):
        (self.root/'integrations'/'autodiff'/'src'/'main.rs').write_text('changed autodiff')
        with self.assertRaisesRegex(ValueError, 'sources changed'):
            build.verify_attestation(self.study)

    def test_artifacts_do_not_invalidate(self):
        (self.study/'artifacts').mkdir()
        (self.study/'artifacts'/'run.json').write_text('{}')
        self.assertEqual(build.verify_attestation(self.study), self.record)

    def test_changed_during_build_has_no_attestation(self):
        def mutate(*args, **kwargs):
            (self.root/'src'/'main.rs').write_text('changed during build')
        with patch.object(build.subprocess,'check_output',return_value='rustc test'), \
             patch.object(build.subprocess,'run',side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, 'changed during compilation'):
                build.build('test',self.study)
        self.assertFalse(build.manifest_path(self.study).exists())

    def test_unattested_and_external_binary_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside attested'):
            build.verify_attestation(self.study, self.root/'other.exe')
        build.manifest_path(self.study).unlink()
        with self.assertRaisesRegex(ValueError, 'Unattested'):
            build.verify_attestation(self.study)


if __name__ == '__main__':
    unittest.main()
