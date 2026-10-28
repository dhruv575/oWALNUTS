import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import bounded_market_worker as worker

class FailureIsolation(unittest.TestCase):
    def test_first_method_resource_failure_does_not_suppress_second(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixtures=root/'fixtures';fixtures.mkdir();p=fixtures/'case.npz'
            np.savez_compressed(p,window=np.zeros(250),history=np.zeros(250))
            (fixtures/'FIXTURES.json').write_text(json.dumps([dict(index=0,fixture=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())]))
            (fixtures/'LABELS.json').write_text(json.dumps([dict(index=0,label=0.)]))
            (fixtures/'BASELINES.json').write_text(json.dumps([dict(index=0,method=n,score=dict(logpdf=0.)) for n in ['a','b','c']]))
            calls=[]
            def execute(command,*args,**kwargs):
                name=command[3];calls.append(name)
                if name=='walnuts':
                    Path(command[-1],'REPORT.json').write_text(json.dumps(dict(status='sampled',qualified=False,prediction=dict(status='failed'))))
                return dict(exit_code=-9 if name=='nuts' else 0,group_drained=True)
            with patch.object(worker,'execute',side_effect=execute):worker.run(0,fixtures,root/'out')
            report=json.loads((root/'out/REPORT.json').read_text())
            self.assertEqual(calls,['nuts','walnuts'])
            self.assertEqual(report['methods']['nuts']['status'],'failed')
            self.assertEqual(report['methods']['walnuts']['status'],'sampled')
            self.assertFalse(report['methods']['nuts']['qualified'])
            self.assertEqual(report['comparisons'],[])

if __name__=='__main__':unittest.main()
