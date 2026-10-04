import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import correlated_reference_study as study
ROOT=Path(__file__).resolve().parents[2]
class ControllerTests(unittest.TestCase):
 def test_cli_string_output_reaches_allocation_as_path(self):
  import reference_bank_allocation
  class BoundaryReached(Exception):pass
  with tempfile.TemporaryDirectory() as d:
   def allocation(plan,cell,out):
    self.assertIsInstance(out,Path)
    (out/'boundary.json').write_text('{}')
    raise BoundaryReached()
   with patch.object(reference_bank_allocation,'cell_worker',side_effect=allocation):
    with self.assertRaises(BoundaryReached):
     study.worker({'study':str(ROOT/'STUDIES/options_flow_v1')},{},str(d))
   self.assertTrue((Path(d)/'boundary.json').exists())
 def plan(self,root):
  marker=root/'history.txt';marker.write_text('test historical evidence')
  audit=root/'audit.json';study.save(audit,dict(status='complete',reserved_seeds=[999999],inventory_files={str(marker):study.sha(marker)},auditor='test',scope='Test only; no production seed approval'))
  return study.make_plan(list(range(3612)),ROOT/'STUDIES/options_flow_v1',__import__('sys').executable,audit)
 def test_exact_plan_rejects_schedule_gates_collision_and_source(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=self.plan(root);study.validate(p)
   for field,value in [('wall_seconds',3601),('relative_half_width',.2),('prefixes',[1024,8192])]:
    q=json.loads(json.dumps(p));q[field]=value
    with self.assertRaises(ValueError):study.validate(q)
   q=json.loads(json.dumps(p));q['cells'][0]['fit_seeds'][0]=q['cells'][1]['fit_seeds'][0]
   with self.assertRaises(ValueError):study.validate(q)
   q=json.loads(json.dumps(p));q['cells'].reverse()
   with self.assertRaises(ValueError):study.validate(q)
 def test_freeze_sidecar_drift(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=self.plan(root);path=root/'plan-draft.json';study.save(path,p);study.freeze(path);study.read_frozen(root/'plan.json');path.write_text('{}')
   with self.assertRaises(ValueError):study.read_frozen(root/'plan.json')
 def test_failed_sentinels_keep28(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=self.plan(root);path=root/'plan.json';study.save(path,p)
   with patch.object(study,'read_frozen',return_value=p),patch.object(study.subprocess,'run',side_effect=RuntimeError('mocklaunchfailure')):study.execute(path,root/'out')
   s=study.load(root/'out/summary.json');self.assertEqual(len(s['rows']),28);self.assertEqual(sum(r['status']=='failed' for r in s['rows']),4);self.assertEqual(sum(r['status']=='not_started' for r in s['rows']),24)
   with self.assertRaises(FileExistsError):
    with patch.object(study,'read_frozen',return_value=p):study.execute(path,root/'out')
 def test_provenance_abort_retains_remainder(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=self.plan(root);path=root/'plan.json';study.save(path,p)
   with patch.object(study,'read_frozen',side_effect=[p,ValueError('drift'),ValueError('drift')]):study.execute(path,root/'out')
   s=study.load(root/'out/summary.json');self.assertEqual(len(s['rows']),28);self.assertEqual(s['rows'][0]['status'],'failed');self.assertTrue(all(r['status']=='not_started' for r in s['rows'][1:]));self.assertEqual(s['integrity_error'],'drift')
 def test_deadline_keeps_cleanup_reserve(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=self.plan(root);path=root/'plan.json';study.save(path,p)
   ticks=iter([0.,3590.]);last=[3590.]
   def clock():
    try:last[0]=next(ticks)
    except StopIteration:pass
    return last[0]
   with patch.object(study,'read_frozen',return_value=p),patch.object(study.time,'monotonic',side_effect=clock),patch.object(study.subprocess,'run') as run:study.execute(path,root/'out')
   self.assertFalse(run.called);self.assertTrue(all(r['status']=='not_started' for r in study.load(root/'out/summary.json')['rows']))
 def test_saved_smoke_covariance_missing_or_corrupt_fails(self):
  import shutil
  source=ROOT/'STUDIES/options_flow_v1/artifacts/correlated-reference-smoke-v2'
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)
   for name in ['result.json','resources.json','bank.json','prefix-diagnostic.json']:shutil.copyfile(source/name,out/name)
   c=study.load(out/'result.json')['cell'];p=dict(memory_bytes=2*1024**3,bootstrap_replicates=300,prefixes=[16,32,64]);study.validate_outputs(out,c,p)
   original=study.load(out/'prefix-diagnostic.json')
   for change in ['missing','nan','wrongn','nonpsd','negativeerror','estimate']:
    q=json.loads(json.dumps(original))
    if change=='missing':q['covariance']=None
    elif change=='nan':q['covariance'][0]['cdf_covariance'][0][0]=float('nan')
    elif change=='wrongn':q['covariance'][0]['n']=999
    elif change=='nonpsd':q['covariance'][0]['cdf_covariance']=[[1.,2.],[2.,1.]]
    elif change=='negativeerror':q['covariance'][0]['quadrature_error_estimate'][0][0]=-1
    else:q['estimates']['64'][0][0]+=1
    (out/'prefix-diagnostic.json').write_text(json.dumps(q))
    with self.assertRaises(ValueError):study.validate_outputs(out,c,p)
if __name__=='__main__':unittest.main()
