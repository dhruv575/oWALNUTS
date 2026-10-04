import ast,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import profile_whitening_pair as pair

class ProfilePlanTests(unittest.TestCase):
    def test_eight_cells_frozen_before_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);deps=[]
            for name in ['python.exe','adapter.py','extension.pyd']:
                f=root/name;f.write_bytes(name.encode());deps.append(f)
            out=root/'plan'
            with patch.object(pair,'sources',return_value={'fake.py':'fixed'}),patch.object(pair.subprocess,'run') as run:
                pair.create(out,*deps);run.assert_not_called()
                plan=json.loads((out/'plan.json').read_text());pair.verify(out/'plan.json',plan)
                self.assertEqual(len(plan['cells']),8)
                for t in [32,128,512,1000]:
                    cells=[c for c in plan['cells'] if c['periods']==t]
                    self.assertEqual({c['solve'] for c in cells},{'original','combined'})
                    for c in cells:
                        self.assertIn('--cpus',c['command']);self.assertIn('--calls-per-block',c['command'])
                deps[-1].write_bytes(b'drift')
                with self.assertRaises(ValueError):pair.verify(out/'plan.json',plan)
    def test_worker_parse_and_no_import_time_execution(self):
        root=Path(__file__).parent
        for name in ['profile_whitening_cfunc.py','profile_whitening_pair.py']:
            ast.parse((root/name).read_text())

if __name__=='__main__':unittest.main()
