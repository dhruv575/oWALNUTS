import unittest
from pathlib import Path
from run import command,TIERS
class Commands(unittest.TestCase):
 def test_equal_gate_schedule(self):
  for arm in ['public','reference']:
   cmd=command(arm,4101,Path('out'),Path('fixture'))
   start=cmd.index('--tiers')+1;self.assertEqual(cmd[start:start+len(TIERS)],list(map(str,TIERS)))
   self.assertEqual(cmd[cmd.index('--chains')+1],'4');self.assertEqual(cmd[cmd.index('--warmup')+1],'1000')
 def test_parallel_and_exact_reference_batch(self):
  pub=command('public',1,Path('o'),Path('f'));ref=command('reference',1,Path('o'),Path('f'))
  self.assertEqual(pub[pub.index('--threads')+1],'4');self.assertEqual(ref[ref.index('--chain-method')+1],'parallel')
  batch=int(ref[ref.index('--batch')+1]);self.assertTrue(all(x%batch==0 for x in TIERS));self.assertEqual(batch,500)
 def test_unknown_arm(self):
  with self.assertRaises(ValueError):command('unknown',1,Path('o'),Path('f'))
if __name__=='__main__':unittest.main()
