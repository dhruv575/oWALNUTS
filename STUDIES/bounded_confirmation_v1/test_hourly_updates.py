import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import hourly_updates as updates


class Response(io.BytesIO):
    status = 202
    def __init__(self): super().__init__(b'{"id":"consult:test"}')


class HourlyTests(unittest.TestCase):
    def test_request_id_stable_and_slot_specific(self):
        a = updates.request_id('machine','thread','hour-1')
        self.assertEqual(a, updates.request_id('machine','thread','hour-1'))
        self.assertNotEqual(a, updates.request_id('machine','thread','hour-2'))
        self.assertEqual(len(a),36)

    def exercise(self, fail_first):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); config=root/'config.json'
            config.write_text(json.dumps(dict(relayUrl='https://example.invalid',bridgeKey='test',
                machineId='machine',thread_id='thread',anchor_epoch=0)))
            with patch.object(updates,'STATE',root/'state'), patch.object(updates,'CONFIG',config), \
                 patch.dict('sys.modules',{'fcntl':types.SimpleNamespace(flock=lambda *args:None,LOCK_EX=1,LOCK_NB=2)}), \
                 patch.object(updates.time,'time',return_value=3601), \
                 patch.object(updates,'summary',side_effect=['original','changed']) as summary, \
                 patch.object(updates.urllib.request,'urlopen',side_effect=([OSError('network'),Response()] if fail_first else [Response()])) as send:
                if fail_first:
                    with self.assertRaises(OSError): updates.main()
                updates.main(); updates.main()
                self.assertEqual(send.call_count,2 if fail_first else 1)
                summary.assert_called_once()
                if fail_first:
                    self.assertEqual(send.call_args_list[0].args[0].data, send.call_args_list[1].args[0].data)
                self.assertFalse((root/'state/pending.json').exists())

    def test_one_message_per_hour(self): self.exercise(False)
    def test_retry_keeps_identical_message_and_id(self): self.exercise(True)


if __name__ == '__main__': unittest.main()
