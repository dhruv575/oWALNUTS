import json
import tempfile
import unittest
from pathlib import Path
from rolling_inventory import inventory
from rolling_record_audit import sha


class Denominators(unittest.TestCase):
    def test_unstarted_timeout_and_reference_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def write(name,value):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            months=[dict(month=m,origins=n,reference_ticks=list(range(1,9))) for m,n in zip(('dec','jan','feb'),(1488,1488,1344))]
            write('PARENT.json',dict(months=months));write('PLAN.json',dict(paths=6,parent='original/PARENT.json',sources={'original/PARENT.json':sha(root/'PARENT.json')}))
            write('SUPERVISION.json',dict(group_drained=True))
            write('REF.json',dict(rows=[dict(month=m['month'],tick=t,extended=dict(passed=t!=8)) for m in months for t in m['reference_ticks']]))
            write('campaign01/job-01/SUPERVISION.json',dict(group_drained=True,exit_code=-15,reason='timeout'))
            result=inventory(root,root/'REF.json',sha(root/'REF.json'))
            self.assertEqual((len(result['jobs']),len(result['spots'])),(6,48))
            self.assertEqual(result['completed_jobs'],0);self.assertEqual(result['available_spots'],0)
            self.assertTrue(result['jobs'][1]['started']);self.assertFalse(result['jobs'][0]['started'])
            self.assertEqual({s['e72_k400_job'] for s in result['spots']},{0,2,4,6,8,10})
            with self.assertRaisesRegex(ValueError,'Reference hash'):
                inventory(root,root/'REF.json','wrong')
            write('SUPERVISION.json',dict(group_drained=False))
            with self.assertRaisesRegex(ValueError,'drain'):
                inventory(root,root/'REF.json',sha(root/'REF.json'))

if __name__=='__main__':unittest.main()
