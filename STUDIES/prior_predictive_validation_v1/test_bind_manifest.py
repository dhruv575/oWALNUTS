import json,tempfile,unittest
from pathlib import Path
from bind_manifest import bind
class BindingFixtures(unittest.TestCase):
 def test_failed_or_undrained_smoke_cannot_bind(self):
  for record in ({'readiness_complete':False,'group_drained':True},{'readiness_complete':True,'group_drained':False}):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);(root/'supervisor.json').write_text(json.dumps(record))
    with self.assertRaises(ValueError):bind(root,root,root,root/'output.json')
    self.assertFalse((root/'output.json').exists())
 def test_missing_stage_cannot_bind(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'supervisor.json').write_text(json.dumps({'readiness_complete':True,'group_drained':True}));(root/'stages').mkdir()
   (root/'stages/stages.json').write_text(json.dumps({'status':'complete','stages':[{'stage':'candidate','status':'complete'}]}))
   with self.assertRaises(ValueError):bind(root,root,root,root/'output.json')
   self.assertFalse((root/'output.json').exists())
if __name__=='__main__':unittest.main()
