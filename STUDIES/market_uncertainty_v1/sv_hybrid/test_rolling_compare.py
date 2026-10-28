import json
import tempfile
import unittest
from pathlib import Path
from rolling_compare import pair_rows
from rolling_record_audit import sha


class PairIdentity(unittest.TestCase):
    def test_missing_pairs_and_window_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);nr=[];wr=[]
            for j in range(6):
                for tick in range(1,9):
                    row=dict(job=j,tick=tick,month=str(j//2),reference_pass=True,reference={},metrics_status='unavailable')
                    nr.append(row);wr.append(dict(row,job=2*j))
            nuts=dict(rows=nr,inventory=dict(reference_sha256='same'))
            walnuts=dict(rows=wr,inventory=dict(reference_sha256='same'))
            pairs=pair_rows(nuts,walnuts,root)
            self.assertEqual(len(pairs),48);self.assertEqual(sum(p['available'] for p in pairs),0)
            path=root/'campaign01/job-00/candidate/records/000001.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dict(window_sha256='window',label_index=251)))
            for row in (nr[0],wr[0]):
                row.update(metrics_status='available',record_sha256=sha(path),window_sha256='window',label_index=251,
                           difference=dict(logpdf=.1,pit=.01),candidate=dict(logpdf=1.,pit=.5,logpdf_mcse=.01,pit_mcse=.001))
            self.assertEqual(sum(p['available'] for p in pair_rows(nuts,walnuts,root)),1)
            nr[0]['label_index']=252
            with self.assertRaisesRegex(ValueError,'Causal'):
                pair_rows(nuts,walnuts,root)

if __name__=='__main__':unittest.main()
