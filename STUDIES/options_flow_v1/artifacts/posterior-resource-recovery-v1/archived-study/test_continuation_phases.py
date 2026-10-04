import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PhaseTests(unittest.TestCase):
    def test_adapt_failure_leaves_last_phase_and_terminal(self):
        import numpy as np
        import continuation_precision as worker
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fixture=root/'fixture.json';out=root/'out'
            fixture.write_text(json.dumps(dict(data=dict(y=[0.],dt=[],anchor=0.,anchor_mode='exogenous',nu=5.))))
            starts=np.array([[0.,-2.,-2.]])
            argv=['worker','--fixture',str(fixture),'--out',str(out),'--model','local_level','--seed','1','--chains','1','--warmup','1','--batch-size','4','--tiers','4']
            with patch('sys.argv',argv),patch.object(worker,'local_configuration',return_value=(starts,starts,lambda q:0.,lambda q:q)),patch.object(worker,'ContinuedReference') as sampler,contextlib.redirect_stdout(io.StringIO()):
                sampler.return_value.adapt.side_effect=RuntimeError('test adaptation failure')
                self.assertEqual(worker.main(),2)
            events=[json.loads(line)['event'] for line in (out/'phase-events.jsonl').read_text().splitlines()]
            self.assertEqual(events,['worker_configuring','sampler_constructing','adapt_begin','worker_error','worker_terminal'])
            report=json.loads((out/'numpyro-continuation-report.json').read_text())
            self.assertEqual(report['status'],'failed')


if __name__=='__main__':unittest.main()
