import hashlib,io,json,tempfile,unittest
from pathlib import Path
import numpy as np
import data_contract as d
from tail_inputs import seal_inference,Archive,origins,references

class Contract(unittest.TestCase):
    def test_actual_calendar_import_closure(self):
        from reuse import calendar
        root=Path(__file__).resolve().parents[1]/'fresh_real_value_v1'
        for row in d.MONTHS:
            modules=calendar(row['month'],root)
            self.assertEqual(modules['worker'].ORIGINS,row['origins']);self.assertEqual(modules['reference'].TICKS,row['reference_ticks'])
    def test_complete_new_calendar_aggregate(self):
        import tail_report
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for m,n in tail_report.MONTHS:
                p=root/'reports'/m/'summary.json';p.parent.mkdir(parents=True)
                arm=dict(mean_width=2.,tails={s:dict(mean_pinball=1.,mean_limit=1.,exceedance_rate=.05,signed_exceedance_minus_05=0.) for s in ('long','short')})
                p.write_text(json.dumps(dict(full_scientific_panel=True,comparisons={'ewma_t5_long':dict(mean_advantage=.2)},arms={a:arm for a in tail_report.ARMS})))
            result=tail_report.batch_summary({},root);self.assertEqual(result['status'],'complete');self.assertAlmostEqual(result['origin_weighted_comparisons']['ewma_t5_long'],.2)
    def test_complete_calendars_and_causality(self):
        bars=[dict(open_ms=1764028800000+i*d.HALF,close_available_ms=1764028800000+(i+1)*d.HALF,close=100+i*.01) for i in range(4608)]
        for row in d.MONTHS:
            d.configure(row['month']);y=d.panel_returns(bars,row['month']);self.assertEqual(len(y),row['origins']+251)
            first=d.inputs(y,1);last=d.inputs(y,row['origins']);self.assertEqual(first['origin_ms'],row['first_origin_ms']);self.assertEqual(first['label_index'],251)
            self.assertEqual(last['label_available_ms'],row['first_origin_ms']+row['origins']*d.HALF)
            changed=y.copy();changed[251:]+=1
            self.assertTrue(np.array_equal(d.inputs(y,1)['window'],d.inputs(changed,1)['window']))
        self.assertEqual(len(origins()),4320);self.assertEqual(len(references()),24)
    def test_native_only_seal_preserves_draw_and_detects_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=root/'inference/2025-12/candidate';(base/'native').mkdir(parents=True);(base/'draws').mkdir()
            path=base/'draws/000001.npy';np.save(path,np.zeros((4,400,4)))
            record=dict(tick=1,native_status='ok',compact=dict(file='draws/000001.npy',sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            (base/'native/000001.json').write_text(json.dumps(record));sealed=seal_inference({},root)
            a=Archive(dict(input=dict(root=str(root),inventory_sha256=sealed['sha256'])));self.assertEqual(a.candidate('2025-12',1).shape,(4,400,4))
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):a.verify_used()
    def test_empty_tail_accounting(self):
        import tail_report
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);s=dict(input=dict(root=str(root)))
            r=tail_report.terminal_accounting(s,root,[])
            self.assertEqual(r['planned_candidate_origins'],4320);self.assertEqual(r['planned_arm_origins'],12960);self.assertEqual(r['valid_arm_origins'],0)
            a=tail_report.batch_summary(s,root);self.assertEqual(a['status'],'incomplete');self.assertIsNone(a['origin_weighted_comparisons'])
    def test_empty_unified_accounting(self):
        import worker
        with tempfile.TemporaryDirectory() as folder:
            spec=dict(e62_root=str(Path(__file__).resolve().parents[1]/'fresh_real_value_v1'))
            result=worker.terminal_accounting(spec,folder,[])
            self.assertTrue(result['accounting_complete']);self.assertTrue(result['artifact_integrity']['integrity_ok'])
            self.assertEqual(result['planned_origins'],4320);self.assertEqual(result['tail']['valid_arm_origins'],0)
if __name__=='__main__':unittest.main()
