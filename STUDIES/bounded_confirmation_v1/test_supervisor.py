import json,tempfile,unittest
from pathlib import Path
import supervisor as s

class SupervisorTests(unittest.TestCase):
    def test_full_denominator_last_partial(self):
        self.assertEqual([j for b in range(255) for j in s.indices(b)],list(range(3050)))
        self.assertEqual(s.indices(254),[3048,3049])
        for b in [-1,255,True]:
            with self.assertRaises(ValueError):s.indices(b)

    def test_failed_slots_preserved_in_final(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'batch-254';out.mkdir()
            def fake(*args,**kwargs):return dict(group_drained=True,exit_code=-9)
            self.assertEqual(s.campaign(root,254,fake),0)
            rows=json.loads((out/'FINAL.json').read_text())
            self.assertEqual([r['index'] for r in rows],[3048,3049])
            self.assertTrue(all(r['exit_code']==-9 for r in rows))

    def test_archive_binding_and_drain_required(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'batch-000';p.mkdir();(p/'PLAN.json').write_text('{}')
            (p/'SUPERVISION.json').write_text(json.dumps(dict(group_drained=True,sources_unchanged=True)))
            (p/'FINAL.json').write_text(json.dumps([dict(index=j,group_drained=True) for j in range(12)]))
            a=dict(exact_version_restore_verified=True,version_id='fixture-version',plan_sha256=s.sha(p/'PLAN.json'))
            (p/'ARCHIVE-VERIFIED.json').write_text(json.dumps(a));s.check_previous(temp,1)
            a['plan_sha256']='wrong';(p/'ARCHIVE-VERIFIED.json').write_text(json.dumps(a))
            with self.assertRaises(ValueError):s.check_previous(temp,1)
            a['plan_sha256']=s.sha(p/'PLAN.json');(p/'ARCHIVE-VERIFIED.json').write_text(json.dumps(a))
            (p/'SUPERVISION.json').write_text(json.dumps(dict(group_drained=False,sources_unchanged=True)))
            with self.assertRaises(ValueError):s.check_previous(temp,1)

if __name__=='__main__':unittest.main()
