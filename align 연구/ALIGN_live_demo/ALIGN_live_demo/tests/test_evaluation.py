import argparse
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import fit_model
from evaluate_model import evaluate_saved, run, training_manifest
from train_model import flatten, load_sessions, read_session
from test_core import valid_model
import test_training as fixtures
from test_training import csv_bytes


class SavedEvaluationTests(unittest.TestCase):
    def trained(self, folder):
        sessions = load_sessions(fixtures.TrainingTests().build_data(folder))
        x, y = flatten(sessions, range(len(sessions)))
        model = valid_model()
        model.update(params=fit_model(x, y),
                     training_sessions=[s['session_id'] for s in sessions],
                     training_subjects=sorted({s['subject_id'] for s in sessions}),
                     training_files=[{k:v for k,v in s.items() if k not in ('features','window_ends')}
                                     for s in sessions])
        return model, sessions

    def test_new_measurement_scores_without_changing_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, _ = self.trained(tmp)
            frozen = copy.deepcopy(model)
            heldout = [read_session('new.csv', csv_bytes('new_session', 'P03', 1, .02))]
            report = evaluate_saved(model, heldout)
            self.assertEqual(report['correct'], 2)
            self.assertEqual(report['windows'], 2)
            self.assertIsNone(report['recall_label0'])
            self.assertEqual(report['overlapping_subject_ids'], [])
            self.assertEqual(model, frozen)

    def test_training_record_rejected_even_after_relabeling_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, sessions = self.trained(tmp)
            with self.assertRaisesRegex(ValueError, '겹칩니다'):
                evaluate_saved(model, sessions[:1])
            copied = read_session('copy.csv', csv_bytes('fresh_id', 'P09', 0))
            with self.assertRaisesRegex(ValueError, '겹칩니다'):
                evaluate_saved(model, [copied])

    def test_missing_or_incomplete_provenance_is_not_independent_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, _ = self.trained(tmp)
            del model['training_files'][0]['signal_sha256']
            with self.assertRaises(ValueError): training_manifest(model)
        with self.assertRaises(ValueError): training_manifest(valid_model())

    def test_cli_outputs_and_existing_results_are_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = self.trained(tmp)
            model_path = root/'model.json'
            model_path.write_text(json.dumps(model), encoding='utf-8')
            test_dir = root/'test_data';test_dir.mkdir()
            (test_dir/'new.csv').write_bytes(csv_bytes('new_session','P01',1,.02))
            args = argparse.Namespace(model=str(model_path), data=str(test_dir), out=str(root/'evaluation'))
            with redirect_stdout(io.StringIO()): report=run(args)
            self.assertEqual(report['overlapping_subject_ids'], ['P01'])
            self.assertTrue((root/'evaluation'/'predictions.csv').exists())
            self.assertTrue((root/'evaluation'/'evaluation.json').exists())
            with self.assertRaises(ValueError): run(args)


if __name__=='__main__': unittest.main()
