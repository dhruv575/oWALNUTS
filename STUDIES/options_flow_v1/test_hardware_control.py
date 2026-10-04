import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import hardware_control as hw


class HardwareControlTests(unittest.TestCase):
    def test_cpu_validation(self):
        self.assertEqual(hw.parse_cpus('3, 1'), [1,3])
        for bad in ('', '1,1', '-1', 'a', '1.5', '1,'):
            with self.assertRaises(ValueError): hw.parse_cpus(bad)
        for bad in ([True], [0.0], [], [2]):
            with self.assertRaises(ValueError): hw.validate_cpus(bad,[0,1])

    def test_wrapper_does_not_change_caller(self):
        with patch.object(hw,'set_affinity') as setter:
            command = hw.wrapper_command(['python','a path/script.py'],[2,0],'record.json')
        setter.assert_not_called()
        self.assertEqual(command[-3:], ['--','python','a path/script.py'])
        self.assertIn('0,2', command)

    def test_worker_starts_only_after_enforcement(self):
        events=[]
        worker=Mock(pid=4321,metadata={});worker.wait.return_value=0
        def enforce(cpus): events.append('affinity');return cpus
        def spawn(command): events.append('worker');return worker
        with tempfile.TemporaryDirectory() as directory:
            record=Path(directory)/'affinity.json'
            with patch.object(hw,'get_affinity',return_value=[0,1,2]), \
                 patch.object(hw,'set_affinity',side_effect=enforce), \
                 patch.object(hw,'_ContainedWorker',side_effect=spawn):
                self.assertEqual(hw.run_worker(['fake'],[1],record),0)
            payload=json.loads(record.read_text())
        self.assertEqual(events,['affinity','worker'])
        self.assertEqual(payload['realized_cpus'],[1])
        self.assertTrue(payload['enforced_before_worker_launch'])
        self.assertEqual(payload['status'],'completed')

    def test_invalid_mask_refuses_worker_and_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            record=Path(directory)/'affinity.json'
            with patch.object(hw,'get_affinity',return_value=[0]), \
                 patch.object(hw.subprocess,'Popen') as spawn:
                with self.assertRaises(ValueError): hw.run_worker(['fake'],[1],record)
            spawn.assert_not_called()
            self.assertEqual(json.loads(record.read_text())['status'],'launcher-failed')

    def test_platform_read_is_nonmutating(self):
        # Real platform read only; no test pins this test runner or its parent.
        try: cpus=hw.get_affinity()
        except NotImplementedError: self.skipTest('platform lacks affinity')
        self.assertGreater(len(cpus),0)
        self.assertEqual(cpus,sorted(set(cpus)))

    def test_timeout_kills_and_reaps_worker(self):
        worker=Mock(pid=4321,metadata={})
        worker.wait.side_effect=hw.subprocess.TimeoutExpired('fake',1)
        with tempfile.TemporaryDirectory() as directory:
            record=Path(directory)/'affinity.json'
            with patch.object(hw,'get_affinity',return_value=[0]), \
                 patch.object(hw,'set_affinity',return_value=[0]), \
                 patch.object(hw,'_ContainedWorker',return_value=worker):
                self.assertEqual(hw.run_worker(['fake'],[0],record,timeout=1),124)
            self.assertEqual(json.loads(record.read_text())['status'],'worker-timeout')
        worker.terminate.assert_called_once()
        self.assertEqual(worker.wait.call_count,1)


if __name__ == '__main__':
    unittest.main()
