import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import worker

class ConfirmationWorkerTests(unittest.TestCase):
    def test_calendar_mapping(self):
        for i,r in enumerate(worker.CELLS):
            fixture,cap,seed=worker.cell(i)
            self.assertEqual(fixture,(0 if r['month']=='2025-09' else 1440)+r['tick']-1)
            self.assertEqual((cap,seed),(r['cap'],r['nuts_seed']))
        for i in [-1,3050]:
            with self.assertRaises(ValueError):worker.cell(i)

    def test_first_method_failure_preserved_and_second_attempted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'case.npz';np.savez_compressed(p,window=np.zeros(250),history=np.zeros(250))
            (root/'FIXTURES.json').write_text(json.dumps([dict(index=0,fixture=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())]))
            (root/'LABELS.json').write_text(json.dumps([dict(index=0,label=0.)]))
            (root/'BASELINES.json').write_text(json.dumps([dict(index=0,method=n,score=None) for n in ['a','b','c']]))
            calls=[]
            def execute(command,*args,**kwargs):
                name=command[3];calls.append(name)
                if name=='walnuts':Path(command[-1],'REPORT.json').write_text(json.dumps(dict(status='sampled',qualified=False,prediction=dict(status='failed'))))
                return dict(exit_code=-9 if name=='nuts' else 0,group_drained=True)
            with patch.object(worker,'execute',side_effect=execute):worker.run(0,root,root/'fit')
            r=json.loads((root/'fit/REPORT.json').read_text())
            self.assertEqual(calls,['nuts','walnuts']);self.assertEqual(r['methods']['nuts']['status'],'failed')
            self.assertEqual(r['methods']['walnuts']['status'],'sampled')
            self.assertFalse(r['methods']['nuts']['qualified'])

if __name__=='__main__':unittest.main()
