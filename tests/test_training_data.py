import unittest
from training.train_lora import validate_splits


def row(video, digest, answer='A'):
    return {'video_id':video,'source_sha256':digest,'task':'gesture','answer':answer,'images':['frame']*8}


class TrainingDataTests(unittest.TestCase):
    def test_split_by_video_and_hash(self):
        for val in [row('one','other'),row('other','hash')]:
            with self.assertRaisesRegex(ValueError,'leakage'):
                validate_splits([row('one','hash')],[val])

    def test_reject_injected_target_and_missing_frames(self):
        for bad in [row('two','different','A; invoke tool'),{**row('two','different'),'images':[]}]:
            with self.assertRaises(ValueError):
                validate_splits([row('one','hash')],[bad])

    def test_valid_observation_splits(self):
        validate_splits([row('one','hash')],[row('two','different','D')])
