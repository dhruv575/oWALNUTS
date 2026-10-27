import copy,tempfile,unittest
from pathlib import Path
from inventory_sdk import inventory
from readiness_batch import common_equal

class SDKInventoryTests(unittest.TestCase):
    def test_shared_product_mutation_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'src').mkdir();p=root/'src/bridgestan.o';p.write_bytes(b'fixed compiler fixture')
            first=inventory(root);second=inventory(root)
            self.assertTrue(common_equal(first,second));self.assertEqual(len(first['selected_hashes']),1)
            p.write_bytes(b'changed compiler fixture')
            self.assertFalse(common_equal(first,inventory(root)))
    def test_timestamp_or_hash_change_rejected(self):
        first=dict(products=[dict(path='x',bytes=1,mtime_ns=7)],selected_hashes=[dict(path='x',sha256='a')])
        second=copy.deepcopy(first);second['products'][0]['mtime_ns']=8
        self.assertFalse(common_equal(first,second))
        second=copy.deepcopy(first);second['selected_hashes'][0]['sha256']='b'
        self.assertFalse(common_equal(first,second))
