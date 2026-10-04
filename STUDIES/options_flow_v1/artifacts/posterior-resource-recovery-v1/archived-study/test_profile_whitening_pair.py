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



class ProfileExecutionTests(unittest.TestCase):
    def setup_plan(self,root):
        deps=[]
        for name in ['python.exe','adapter.py','extension.pyd']:
            f=root/name;f.write_bytes(name.encode());deps.append(f)
        out=root/'plan'
        pair.create(out,*deps)
        return out,deps,json.loads((out/'plan.json').read_text())
    def test_nonzero_retained_and_remaining_attempted(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td,patch.object(pair,'sources',return_value={'fake.py':'fixed'}):
            out,deps,plan=self.setup_plan(Path(td))
            with patch.object(pair.subprocess,'run',return_value=SimpleNamespace(returncode=2)) as run:pair.execute(out/'plan.json')
            self.assertEqual(run.call_count,8)
            for c in plan['cells']:
                self.assertEqual(json.loads((out/(c['id']+'-status.json')).read_text())['status'],'worker_failed')
                self.assertEqual(json.loads((out/(c['id']+'-exit.json')).read_text())['returncode'],2)
    def test_drift_preserves_return_and_terminalizes_remaining(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td,patch.object(pair,'sources',return_value={'fake.py':'fixed'}):
            out,deps,plan=self.setup_plan(Path(td))
            def run(*args,**kwargs):deps[-1].write_bytes(b'drift');return SimpleNamespace(returncode=7)
            with patch.object(pair.subprocess,'run',side_effect=run) as worker:pair.execute(out/'plan.json')
            self.assertEqual(worker.call_count,1)
            records=[json.loads((out/(c['id']+'-status.json')).read_text()) for c in plan['cells']]
            self.assertEqual(records[0]['returncode'],7);self.assertEqual(records[0]['status'],'provenance_or_executor_failed')
            self.assertTrue(all(r['status']=='unattempted_provenance_abort' for r in records[1:]))
            self.assertEqual(json.loads((out/(plan['cells'][0]['id']+'-exit.json')).read_text())['returncode'],7)
    def test_runtime_adapter_path_or_hash_mismatch_ineligible(self):
        from types import SimpleNamespace
        for field,value in [('adapter_path','unbound-adapter.py'),('adapter_sha256','wrong')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as td,patch.object(pair,'sources',return_value={'fake.py':'fixed'}):
                out,deps,plan=self.setup_plan(Path(td));cell=plan['cells'][0]
                runtime=dict(source_sha256={'fake.py':'fixed'},python_path=str(deps[0]),python_executable_sha256=pair.sha(deps[0]),adapter_path=str(deps[1]),adapter_sha256=pair.sha(deps[1]),extension_path=str(deps[2]),extension_sha256=pair.sha(deps[2]));runtime[field]=value
                def run(*args,**kwargs):
                    pair.save(out/(cell['id']+'.json'),dict(source_before=runtime,source_after=runtime));return SimpleNamespace(returncode=0)
                with patch.object(pair.subprocess,'run',side_effect=run):pair.execute(out/'plan.json')
                record=json.loads((out/(cell['id']+'-status.json')).read_text());self.assertEqual(record['returncode'],0);self.assertEqual(record['status'],'provenance_or_executor_failed')

if __name__=='__main__':unittest.main()
