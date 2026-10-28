import json,tempfile,unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import acquire

class AcquisitionFixtures(unittest.TestCase):
    def fixture(self,folder):
        p=json.loads(Path(acquire.__file__).with_name('ACQUISITION-DRAFT.json').read_bytes())
        p.update(status='frozen_authorized',acquire_source_sha256=acquire.digest(Path(acquire.__file__).read_bytes()))
        path=Path(folder)/'protocol.json';path.write_text(json.dumps(p));return path

    def response(self,url,gap=False):
        lo=int(parse_qs(urlsplit(url).query)['start_timestamp'][0]);ticks=list(range(lo,lo+acquire.DAY,acquire.HALF))
        if gap:ticks[1]=ticks[0]
        result=dict(status='ok',ticks=ticks,open=[100.]*48,high=[101.]*48,low=[99.]*48,close=[100.]*48,volume=[0.]*48)
        return 200,json.dumps(dict(result=result)).encode(),{}

    def test_full_fixed_grid_and_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            protocol=self.fixture(folder);urls=[]
            def fake(url,timeout,cap):urls.append(url);return self.response(url)
            terminal=acquire.acquire(protocol,Path(folder)/'out',fake,clock=lambda:0.,sleep=lambda _:None)
            self.assertTrue(terminal['complete']);self.assertEqual(len(urls),67);self.assertEqual(terminal['valid_bars'],3216)
            self.assertIn('start_timestamp=1756166400000',urls[0])
            rows=json.loads((Path(folder)/'out/bars.json').read_bytes())
            self.assertTrue(all(x['close_available_ms']==x['open_ms']+acquire.HALF for x in rows))

    def test_gap_stops_without_retry_and_preserves_raw(self):
        with tempfile.TemporaryDirectory() as folder:
            terminal=acquire.acquire(self.fixture(folder),Path(folder)/'out',lambda url,*_:self.response(url,True),clock=lambda:0.,sleep=lambda _:None)
            self.assertFalse(terminal['complete']);self.assertEqual(terminal['requests_attempted'],1)
            self.assertTrue((Path(folder)/'out/response-000.json').exists());self.assertFalse((Path(folder)/'out/bars.json').exists())

    def test_draft_never_calls_network_or_creates_output(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'out'
            def forbidden(*args):raise AssertionError('network forbidden')
            with self.assertRaises(ValueError):acquire.acquire(Path(acquire.__file__).with_name('ACQUISITION-DRAFT.json'),out,forbidden)
            self.assertFalse(out.exists())

    def test_http_and_response_cap_fail_closed(self):
        for status,body in [(302,b'redirect'),(200,b'x'*2097153)]:
            with tempfile.TemporaryDirectory() as folder:
                terminal=acquire.acquire(self.fixture(folder),Path(folder)/'out',lambda *args:(status,body,{}),clock=lambda:0.,sleep=lambda _:None)
                self.assertFalse(terminal['complete']);self.assertEqual(terminal['requests_attempted'],1)

if __name__=='__main__':unittest.main()
