import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from inventory import inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('SUPERVISION.json', {'group_drained': True})
        months = [dict(month=m, origins=8, reference_ticks=list(range(1, 9)))
                  for m in ('2025-12', '2026-01', '2026-02')]
        self.write('PARENT.json', {'months': months})
        self.write('MANIFEST.json', {'parent_sha256': hashlib.sha256((self.root/'PARENT.json').read_bytes()).hexdigest(), 'new_sources': {}})
        self.write('REFERENCE.json', {'rows': [dict(month=m['month'], tick=t, extended=dict(passed=t != 8 or m['month'] == '2026-01')) for m in months for t in m['reference_ticks']]})

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def run_inventory(self):
        return inventory(self.root, self.root/'REFERENCE.json')

    def test_unstarted_and_failed_slots_remain(self):
        self.write('campaign01/job-01/MONITOR.json', {'exit_code': -15, 'group_drained': True, 'reason': 'timeout'})
        self.write('campaign01/job-01/candidate/records/000001.json', {'tick': 1, 'score_status': 'unavailable', 'native_health': [{'divergences': 3}]})
        result = self.run_inventory()
        self.assertEqual((len(result['jobs']), len(result['spots'])), (12, 96))
        self.assertEqual(result['planned_passing_reference_spots'], 88)
        self.assertEqual(result['completed_jobs'], 0)
        self.assertEqual(result['available_spots'], 0)
        self.assertEqual(result['jobs'][1]['recorded_divergences'], 3)
        self.assertEqual(result['jobs'][1]['recorded_updates'], 1)

    def test_live_or_undrained_evidence_rejected(self):
        self.write('SUPERVISION.json', {'group_drained': False})
        with self.assertRaisesRegex(ValueError, 'drain'):
            self.run_inventory()

    def test_complete_path_requires_records_and_successful_scores(self):
        base = 'campaign01/job-00/candidate/'
        self.write('campaign01/job-00/MONITOR.json', {'exit_code': 0, 'group_drained': True})
        self.write(base+'DONE.json', {'status': 'complete', 'native_completed': 8})
        for tick in range(1, 9):
            name = f'arrays/{tick:06d}.npz'
            self.write(base+name, {})
            digest = hashlib.sha256((self.root/base/name).read_bytes()).hexdigest()
            self.write(base+f'records/{tick:06d}.json', {'tick': tick, 'native_status': 'ok', 'score_status': 'ok', 'arrays': {'file': name, 'sha256': digest}})
        result = self.run_inventory()
        self.assertEqual(result['completed_jobs'], 1)
        self.assertEqual(result['available_spots'], 8)
        self.write(base+'records/000008.json', {'tick': 8, 'native_status': 'ok', 'score_status': 'unavailable'})
        self.assertEqual(self.run_inventory()['completed_jobs'], 0)

    def test_record_gap_rejected(self):
        self.write('campaign01/job-00/candidate/records/000002.json', {'tick': 2})
        with self.assertRaisesRegex(ValueError, 'gap'):
            self.run_inventory()

    def test_corrupt_retained_array_rejected(self):
        base = 'campaign01/job-00/candidate/'
        self.write(base+'arrays/000001.npz', {})
        self.write(base+'records/000001.json', {'tick': 1, 'score_status': 'ok', 'arrays': {'file': 'arrays/000001.npz', 'sha256': 'incorrect'}})
        with self.assertRaisesRegex(ValueError, 'array identity'):
            self.run_inventory()


if __name__ == '__main__':
    unittest.main()
