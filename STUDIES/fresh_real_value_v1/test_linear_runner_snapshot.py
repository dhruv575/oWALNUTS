import json,tempfile,unittest
from pathlib import Path
import numpy as np
from linear_runner import run_lane

class Engine:
 def __init__(self,y,seeds,fail=None,close_fail=False):self.y=y.copy();self.seeds=seeds;self.index=0;self.fail=fail;self.close_fail=close_fail;self.initial={'fixture':True};self.closed=False
 def advance(self,value,k):
  self.index+=1
  if self.index==self.fail:raise RuntimeError('native fixture failure')
  self.y=np.append(self.y[1:],value);a=np.full((4,400,4),float(self.index));self.last=a
  return a,dict(call_index=self.index-1,seed=self.seeds['warm']+4*(self.index-1),work=[{'transitions':400,'divergences':0}]*4,diagnostics=[{'divergent':np.zeros(400,dtype=bool),'stop':np.zeros(400,dtype=int),'depth':np.full(400,3),'max_abs_energy_error':np.full(400,.1),'zero_density_evaluations':np.zeros(400,dtype=int)}]*4)
 def close(self):
  self.closed=True
  if self.close_fail:raise RuntimeError('close fixture failure')

class LinearFixtures(unittest.TestCase):
 def test_causal_immutable_and_scoring_failure_continues(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lane';seen=[];engine=[]
   def factory(y,seeds):engine.append(Engine(y,seeds));return engine[-1]
   def score(a,w,label,tick):
    self.assertTrue((root/'draws'/f'{tick:06d}.npy').exists());self.assertTrue((root/'native'/f'{tick:06d}.json').exists())
    self.assertEqual(w[0],tick);self.assertEqual(w[-1],249+tick);self.assertEqual(label,250+tick);self.assertFalse(a.flags.writeable)
    seen.append(tick)
    if tick==2:raise ValueError('GH fixture failure')
    return dict(status='ok',pit=.5,logpdf=0.,perdraw=np.zeros((4,400)))
   result=run_lane(np.arange(254,dtype=float),updates=3,seeds={'initial':11,'warm':17},score_ticks=[1,2,3],retain_ticks=[1,2,3],engine_factory=factory,score_hook=score,output=root)
   self.assertEqual(result['status'],'partial_scores');self.assertEqual(result['native_completed'],3);self.assertEqual(result['score_counts'],{'ok':2,'partial':0,'unavailable':1});self.assertEqual(seen,[1,2,3]);self.assertTrue(engine[0].closed)
   self.assertEqual(len(list((root/'records').glob('*.json'))),3)
   record=json.loads((root/'records/000002.json').read_text());self.assertEqual(record['native_status'],'ok');self.assertEqual(record['score_status'],'unavailable')
 def test_native_failure_denominator_and_close_failure_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lane'
   result=run_lane(np.arange(255,dtype=float),updates=4,seeds={'initial':11,'warm':17},score_ticks=[1,2,3,4],retain_ticks=[1,2,3,4],engine_factory=lambda y,s:Engine(y,s,fail=2,close_fail=True),score_hook=lambda *a:{'status':'ok'},output=root)
   self.assertEqual(result['native_completed'],1);self.assertEqual(result['unattempted_from'],3);self.assertEqual(result['score_counts']['unavailable'],1);self.assertEqual(result['terminal_error']['phase'],'native');self.assertIn('close fixture',result['close_error'])
 def test_compact_hash_every_tick_only_checkpoint_raw_retained(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lane'
   r=run_lane(np.arange(255,dtype=float),updates=4,seeds={'initial':11,'warm':17},score_ticks=[2,4],retain_ticks=[2,4],engine_factory=Engine,score_hook=lambda *a:{'status':'ok'},output=root)
   self.assertEqual(r['status'],'complete');self.assertEqual(len(list((root/'draws').glob('*.npy'))),2)
   for tick in range(1,5):
    row=json.loads((root/'records'/f'{tick:06d}.json').read_text());self.assertIn('compact_value_sha256',row);self.assertEqual(row['native_health'][0]['maximum_depth'],3);self.assertEqual(row['native_health'][0]['stop_counts'],{'0':400})
 def test_score_mutation_cannot_change_native_saved_draws(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lane'
   def mutate(a,*args):a.flags.writeable=True;a[:]=999.;return {'status':'ok'}
   r=run_lane(np.arange(252,dtype=float),updates=1,seeds={'initial':11,'warm':17},score_ticks=[1],retain_ticks=[1],engine_factory=Engine,score_hook=mutate,output=root)
   self.assertEqual(r['status'],'complete');self.assertTrue(np.all(np.load(root/'draws/000001.npy')==1))
 def test_process_exit_inside_scorer_preserves_native_files(self):
  import subprocess,sys
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lane'
   code="import os,numpy as np;from linear_runner import run_lane;from test_linear_runner_snapshot import Engine;run_lane(np.arange(252,dtype=float),updates=1,seeds={'initial':11,'warm':17},score_ticks=[1],retain_ticks=[1],engine_factory=Engine,score_hook=lambda *args:os._exit(7),output="+repr(str(root))+")"
   child=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parent,timeout=10)
   self.assertEqual(child.returncode,7);self.assertTrue((root/'draws/000001.npy').exists());self.assertTrue((root/'native/000001.json').exists());self.assertFalse((root/'records/000001.json').exists())
   events=[json.loads(line) for line in (root/'progress.jsonl').read_text().splitlines()];self.assertEqual(events[-1]['event'],'score_started')
if __name__=='__main__':unittest.main()
