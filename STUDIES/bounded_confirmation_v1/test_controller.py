import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from controller import next_action, transfer_spec, BUCKET, remote
import controller_remote


class ControllerTests(unittest.TestCase):
    def test_connection_failure_never_blindly_retries_mutation(self):
        for result in [Mock(returncode=255, stdout=''),
                       Mock(returncode=1, stdout='{"error_type":"BlockingIOError"}')]:
            with patch('controller.subprocess.run', return_value=result) as command:
                with self.assertRaises(ConnectionError): remote('launch', 11)
                command.assert_called_once()
        with patch('controller.subprocess.run', return_value=Mock(returncode=1, stdout='{"error_type":"ValueError"}')):
            with self.assertRaises(RuntimeError): remote('finish', 11)

    def state(self):
        return dict(live=[], exists=True, final=True,
                    supervision=dict(group_drained=True, sources_unchanged=True),
                    packed=None, upload=None, restore=None, verified=None)

    def test_live_process_wins_over_receipts(self):
        s = self.state(); s['live'] = [123]
        self.assertEqual(next_action(s), 'wait')

    def test_incomplete_existing_batch_never_relaunched(self):
        s = self.state(); s['final'] = False
        with self.assertRaises(ValueError): next_action(s)
        s['exists'] = False
        self.assertEqual(next_action(s), 'launch')

    def test_archive_sequence_and_resume_verified(self):
        s = self.state()
        for key, expected in [('packed', 'pack'), ('upload', 'upload'), ('restore', 'verify')]:
            self.assertEqual(next_action(s), expected); s[key] = {'present': True}
        self.assertEqual(next_action(s), 'finish')
        s = self.state(); s['verified'] = {'exact_version_restore_verified': True}
        self.assertEqual(next_action(s), 'finish')

    def test_exact_version_signing_and_mismatch(self):
        client = Mock(); client.generate_presigned_url.return_value = 'secret'
        packed = dict(sha256='a'*64, bytes=123)
        spec = transfer_spec(client, packed, 4)
        self.assertEqual(client.generate_presigned_url.call_args.kwargs['Params']['ServerSideEncryption'], 'AES256')
        upload = dict(spec, version_id='fixed-version'); upload.pop('url')
        transfer_spec(client, packed, 4, upload)
        self.assertEqual(client.generate_presigned_url.call_args.kwargs['Params']['VersionId'], 'fixed-version')
        upload['bytes'] = 124
        with self.assertRaises(ValueError): transfer_spec(client, packed, 4, upload)

    def test_trim_requires_verified_bound_unchanged_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            lane = Path(d); folder = lane/'batch-000'; folder.mkdir()
            sampler = folder/'job-0/SAMPLER.json'; sampler.parent.mkdir(); sampler.write_bytes(b'raw')
            plan = folder/'PLAN.json'; plan.write_bytes(b'plan')
            manifest = folder/'RAW-MANIFEST.json'
            manifest.write_text(json.dumps({'batch-000/job-0/SAMPLER.json':dict(bytes=3,sha256=hashlib.sha256(b'raw').hexdigest())}))
            receipt = dict(exact_version_restore_verified=True, version_id='v',
                plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
            with patch.object(controller_remote, 'LANE', lane), patch('archive_batch.drained'):
                with self.assertRaises(ValueError): controller_remote.trim(folder)
                (folder/'ARCHIVE-VERIFIED.json').write_text(json.dumps(receipt))
                sampler.write_bytes(b'bad')
                with self.assertRaises(ValueError): controller_remote.trim(folder)
                self.assertTrue(sampler.exists())
                sampler.write_bytes(b'raw'); controller_remote.trim(folder)
                self.assertFalse(sampler.exists())
                self.assertTrue(json.loads((folder/'CONTROLLER-TRIM.json').read_text())['completed'])


if __name__ == '__main__': unittest.main()
