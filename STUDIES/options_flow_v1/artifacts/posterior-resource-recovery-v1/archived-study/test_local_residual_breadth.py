"""Controller tests with mocked workers; never import a numerical stack."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import local_residual_breadth as runner


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        fixture=self.directory/'fixture.json';fixture.write_text('{}')
        self.cell=dict(id='candidate-00',arm='candidate',fixture=str(fixture),fixture_sha256=runner.digest(fixture),chain_seed=99810001)
        self.plan=dict(frozen=True,python='python',cells=[self.cell])
        self.path=self.directory/'plan.json'
        self.freeze()

    def freeze(self):
        self.path.write_text(json.dumps(self.plan))
        self.original=runner.digest(self.path)
        self.path.with_suffix('.sha256').write_text(self.original)

    def invoke(self,worker=None,source_error=None):
        with patch.object(runner,'verify_sources',side_effect=source_error),patch.object(runner.subprocess,'run',side_effect=worker or self.worker):
            return runner.run_cell(self.plan,self.path,self.cell,self.directory,self.original)

    def worker(self,*args,**kwargs):
        output=self.directory/self.cell['id'];output.mkdir()
        (output/'python-pymc-report.json').write_text(json.dumps(dict(status='completed',precision_pass=True,healthy=True,retained_divergences=0,coordinates='observation_residual',evaluation={'functionals':dict.fromkeys(runner.FUNCTIONALS,{})})))
        return SimpleNamespace(returncode=0)

    def test_success_and_no_retry(self):
        record=self.invoke()
        self.assertTrue(record['accepted']);self.assertEqual(record['status'],'passed')
        self.assertGreaterEqual(record['elapsed_seconds'],0)
        self.assertTrue((self.directory/'candidate-00.started.json').exists())
        self.assertTrue((self.directory/'candidate-00.status.json').exists())
        with self.assertRaises(FileExistsError):self.invoke()

    def test_timeout_missing_report_is_charged(self):
        record=self.invoke(lambda *a,**k:SimpleNamespace(returncode=124))
        self.assertEqual(record['status'],'failed');self.assertFalse(record['accepted'])
        self.assertEqual(record['returncode'],124);self.assertGreaterEqual(record['elapsed_seconds'],0)

    def test_stale_source_terminalizes(self):
        record=self.invoke(source_error=ValueError('source changed'))
        self.assertEqual(record['status'],'executor_failed')
        self.assertIn('source changed',record['error'])

    def test_simultaneous_plan_and_sidecar_mutation(self):
        def worker(*args,**kwargs):
            result=self.worker()
            self.path.write_text('{"mutated":true}')
            self.path.with_suffix('.sha256').write_text(runner.digest(self.path))
            return result
        record=self.invoke(worker)
        self.assertEqual(record['status'],'executor_failed')
        self.assertIn('Plan or sidecar changed',record['error'])
        self.assertFalse(record['accepted'])

    def test_malformed_report_terminalizes(self):
        def worker(*args,**kwargs):
            output=self.directory/self.cell['id'];output.mkdir()
            (output/'python-pymc-report.json').write_text('not json')
            return SimpleNamespace(returncode=0)
        record=self.invoke(worker)
        self.assertEqual(record['status'],'executor_failed');self.assertFalse(record['accepted'])

    def test_worker_exception_terminalizes(self):
        def worker(*args,**kwargs):raise OSError('launch failed')
        record=self.invoke(worker)
        self.assertIn('launch failed',record['error'])
        self.assertGreaterEqual(record['elapsed_seconds'],0)

    def test_30_cell_manifest_and_unknown_cell(self):
        self.plan['cells']=[dict(self.cell,id=f'candidate-{i:02}') for i in range(24)]+[dict(self.cell,id=f'reference-{i:02}',arm='reference') for i in range(6)]
        self.freeze()
        argv=['runner','--plan',str(self.path),'--cell','candidate-00']
        with patch('sys.argv',argv),patch.object(runner,'run_cell',return_value={}) as call,contextlib.redirect_stdout(io.StringIO()):runner.main()
        self.assertEqual(call.call_count,1)
        self.plan['cells'].pop();self.freeze()
        with patch('sys.argv',argv),self.assertRaisesRegex(ValueError,'30 unique'):runner.main()

    def test_commands_bind_coordinates_and_reference_acceptance(self):
        command,_=runner.worker_command(self.plan,self.cell,self.directory/'output')
        self.assertIn('1800',command);self.assertIn('observation_residual',command)
        reference=dict(self.cell,arm='reference')
        command,_=runner.worker_command(self.plan,reference,self.directory/'output')
        self.assertEqual(command[command.index('--target-accept')+1],'0.9')


if __name__=='__main__':unittest.main()
