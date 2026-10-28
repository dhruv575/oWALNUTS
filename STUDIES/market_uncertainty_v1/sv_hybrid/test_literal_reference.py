import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import xarray as xr
import literal_reference as runner


class ReferenceTests(unittest.TestCase):
    def test_supervisor_contract_and_non_drained_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest=root/'manifest.json'; manifest.write_text('{}')
            def execute(command, **kwargs):
                self.assertEqual(kwargs['phase_reserved_cores'], {'startup':4})
                self.assertEqual(kwargs['cap'],900)
                self.assertEqual(kwargs['rss_limit'],4*1024**3)
                self.assertEqual(kwargs['byte_limit'],512*1024**2)
                self.assertEqual(command[-1],'--worker')
                return dict(exit_code=0,group_drained=False)
            spec=dict(bindings=dict(monitor=dict(path='fixture')))
            with patch.object(runner,'validate',return_value=spec), patch.object(runner,'load',return_value=SimpleNamespace(execute=execute)), patch.object(runner.os,'sched_getaffinity',return_value={0,1,2,3},create=True):
                self.assertEqual(runner.supervise(manifest,root/'out'),1)
            self.assertFalse(json.loads((root/'out/SUPERVISION.json').read_bytes())['group_drained'])

    def fixture(self, root):
        audit=root/'audit.json'; audit.write_text(json.dumps(dict(status='passed',reserved_seeds=[123,124],collisions=[])))
        source=Path(runner.__file__).resolve()
        binding=dict(path=str(source),sha256=runner.sha(source))
        spec = dict(status='frozen_authorized',bindings={k:dict(binding) for k in
                    ('worker','stan','adapter','capture','monitor','sdk_makefile','runtime_inventory')},
                    sampling=dict(chains=4,draws=4000,tune=2000,cores=4),
                    limits=dict(seconds=900,rss_bytes=4*1024**3,output_bytes=512*1024**2),
                    seed=123,seed_audit=dict(path=str(audit),sha256=runner.sha(audit),reserved_seeds=[123,124]),
                    reference_settings=dict(api_and_target_verified=True,engine_options={}))
        runtime=root/'runtime.json'
        runtime.write_text(json.dumps(dict(runtime=dict(prefix=runner.sys.prefix,packages={},binaries={}))))
        spec['bindings']['runtime_inventory']=dict(path=str(runtime),sha256=runner.sha(runtime))
        return spec

    def test_rejects_source_drift_and_unreserved_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            spec=self.fixture(Path(directory)); runner.validate(spec)
            altered=copy.deepcopy(spec); altered['bindings']['stan']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'drift'):runner.validate(altered)
            altered=copy.deepcopy(spec); altered['seed_audit']['reserved_seeds']=[123]
            with self.assertRaisesRegex(ValueError,'Both'):runner.validate(altered)

    def test_rejects_budget_or_schedule_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            spec=self.fixture(Path(directory)); spec['limits']['seconds']=901
            with self.assertRaisesRegex(ValueError,'resource'):runner.validate(spec)
            spec=self.fixture(Path(directory)); spec['sampling']['draws']=8000
            with self.assertRaisesRegex(ValueError,'sampling'):runner.validate(spec)

    def test_full_extraction_preserves_named_axes_and_rejects_nonfinite(self):
        ds=xr.Dataset({name:(('draw','chain'),np.full((4000,4),float(i)))
                       for i,name in enumerate(('mu','log_sigma','beta'))})
        ds['z']=(('innovation','chain','draw'),np.broadcast_to(np.arange(250.)[:,None,None],(250,4,4000)).copy())
        full=runner.extract_full(SimpleNamespace(posterior=ds))
        self.assertEqual(full.shape,(4,4000,253))
        np.testing.assert_array_equal(full[2,17,:3],[0.,1.,2.])
        np.testing.assert_array_equal(full[2,17,3:],np.arange(250.))
        ds['z'].values[0,0,0]=np.nan
        with self.assertRaisesRegex(ValueError,'Finite'):runner.extract_full(SimpleNamespace(posterior=ds))


if __name__=='__main__':unittest.main()
