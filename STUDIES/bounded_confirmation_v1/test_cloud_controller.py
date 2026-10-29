import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import cloud_controller as cloud


class CloudControllerTests(unittest.TestCase):
    def clients(self):
        session = Mock()
        session.client.return_value.get_caller_identity.return_value = dict(
            Account='712710405275', Arn='arn:aws:sts::712710405275:assumed-role/owalnuts-confirmation-archive/i-test')
        return session

    def test_wrong_identity_stops_before_launch(self):
        session = self.clients()
        session.client.return_value.get_caller_identity.return_value['Account'] = 'wrong'
        with patch('boto3.Session', return_value=session), patch.object(cloud.operations, 'action') as action:
            with self.assertRaises(ValueError): cloud.run(0)
            action.assert_not_called()

    def test_complete_final_batch_preserves_before_completion(self):
        session = self.clients()
        with tempfile.TemporaryDirectory() as d, patch.object(cloud, 'STATE', Path(d)), \
             patch('boto3.Session', return_value=session), \
             patch('supervisor.check_previous') as previous, \
             patch.object(cloud.operations, 'snapshot', return_value={}), \
             patch.object(cloud, 'next_action', side_effect=['wait', 'launch', 'pack', 'upload', 'verify', 'finish']), \
             patch.object(cloud, 'transfer', return_value={}), \
             patch.object(cloud.operations, 'action', return_value={'review':'review.tar.gz','verified':{'version_id':'v'}}) as action, \
             patch('import_review.run', side_effect=lambda archive, destination, batch: (destination.mkdir(), (destination/'LOCAL-VERIFICATION.json').write_text('{}'))) as review, \
             patch.object(cloud, 'preserve_review') as preserve, \
             patch.object(cloud.time, 'sleep'):
            # Supply the fields used by the transfer phase without reading outcomes.
            with patch.object(cloud.operations, 'snapshot', return_value={'packed':{},'upload':{}}):
                cloud.run(254)
            previous.assert_called_once()
            self.assertEqual([c.args[0] for c in action.call_args_list], ['launch','pack','upload','verify','finish'])
            review.assert_called_once(); preserve.assert_called_once()
            self.assertEqual(json.loads((Path(d)/'status.json').read_text())['state'], 'all_255_batches_preserved_no_scores_unsealed')

    def test_stop_does_not_launch_or_interrupt_job(self):
        session = self.clients()
        with tempfile.TemporaryDirectory() as d, patch.object(cloud, 'STATE', Path(d)), \
             patch('boto3.Session', return_value=session), patch.object(cloud.operations, 'action') as action:
            (Path(d)/'STOP').touch()
            cloud.run(0)
            action.assert_not_called()


if __name__ == '__main__': unittest.main()
