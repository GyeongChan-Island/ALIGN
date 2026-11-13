"""Run with: python -m unittest discover -s tests -v (from package folder)."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import CHANNELS, WindowBuffer, fit_model, load_model, parse_sample, predict


def line(seq=0, ts=1000000, values=None):
    values = [0, 0, 1, 0, 0, 0] * 2 if values is None else values
    return ','.join(map(str, [seq, ts] + values))


def valid_model():
    return dict(schema_version=1, channels=CHANNELS.copy(), window_rows=50,
                target_hz=50, feature='channel_means',
                method='standardized_nearest_centroid', kind='hand',
                params=fit_model([[0.] * 12, [1.] * 12], [0, 1]))


class ParserTests(unittest.TestCase):
    def test_signed_digital_endpoints_are_valid_not_malformed(self):
        values = [0, -2.0, 1.99994, 250.12978, -250.13741, 0] * 2
        seq, ts, actual = parse_sample(line(25, 4294967298, values))
        self.assertEqual((seq, ts), (25, 4294967298))
        self.assertEqual(actual, values)

    def test_missing_extra_bad_integer_nonfinite_and_range_are_rejected(self):
        bad = ['0,1,2', line() + ',0', line(-1), line(ts='1.5')]
        for index, value in [(0, float('nan')), (3, float('inf')),
                             (4, 250.2), (0, 2.1)]:
            v = [0.] * 12
            v[index] = value
            bad.append(line(values=v))
        for sample in bad:
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                parse_sample(sample)


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.buffer = WindowBuffer()

    def test_exactly_fifty_rows_and_no_overlap(self):
        for i in range(100):
            features, status = self.buffer.feed(i, i * 20000, [i / 100.] * 12)
            if i in (49, 99):
                self.assertEqual(status, 'ready')
                self.assertAlmostEqual(features[0], .245 if i == 49 else .745)
            else:
                self.assertIsNone(features)
                self.assertEqual(status, 'collecting')

    def test_missing_slot_discards_pre_gap_rows(self):
        for i in range(49):
            self.buffer.feed(i, i * 20000, [.1] * 12)
        features, status = self.buffer.feed(50, 1000000, [.7] * 12)
        self.assertIsNone(features)
        self.assertEqual(status, 'gap')
        for i in range(51, 99):
            self.assertIsNone(self.buffer.feed(i, i * 20000, [.7] * 12)[0])
        features, status = self.buffer.feed(99, 1980000, [.7] * 12)
        self.assertEqual(status, 'ready')
        self.assertTrue(all(abs(x - .7) < 1e-12 for x in features))

    def test_clock_jump_duplicate_and_reset_cannot_complete_old_window(self):
        for new_seq, new_ts in [(49, 990001), (48, 980000), (0, 0), (49, 900000)]:
            with self.subTest(seq=new_seq, ts=new_ts):
                self.buffer.reset()
                for i in range(49):
                    self.buffer.feed(i, i * 20000, [.1] * 12)
                features, status = self.buffer.feed(new_seq, new_ts, [.7] * 12)
                self.assertIsNone(features)
                self.assertEqual(status, 'gap')

    def test_timing_tolerance_boundaries(self):
        self.buffer.feed(0, 100000, [.1] * 12)
        self.assertEqual(self.buffer.feed(1, 115000, [.1] * 12)[1], 'collecting')
        self.assertEqual(self.buffer.feed(2, 140000, [.1] * 12)[1], 'collecting')
        self.assertEqual(self.buffer.feed(3, 165001, [.1] * 12)[1], 'gap')

    def test_saturation_discards_partial_window_and_saturated_row(self):
        for i in range(49):
            self.buffer.feed(i, i * 20000, [.1] * 12)
        v = [.1] * 12
        v[4] = 250.12978
        self.assertEqual(self.buffer.feed(49, 980000, v), (None, 'saturated'))
        for i in range(50, 99):
            self.assertIsNone(self.buffer.feed(i, i * 20000, [.7] * 12)[0])
        features, status = self.buffer.feed(99, 1980000, [.7] * 12)
        self.assertEqual(status, 'ready')
        self.assertAlmostEqual(features[4], .7)

    def test_explicit_reset_starts_fresh_window(self):
        for i in range(49):
            self.buffer.feed(i, i * 20000, [.1] * 12)
        self.buffer.reset()
        self.assertEqual(self.buffer.feed(0, 0, [.7] * 12), (None, 'collecting'))


class ModelTests(unittest.TestCase):
    def test_training_population_standardization_and_distances(self):
        p = fit_model([[x] * 12 for x in (-1., 1., 9., 11.)], [0, 0, 1, 1])
        self.assertEqual(p['mean'], [5.] * 12)
        self.assertAlmostEqual(p['scale'][0], math.sqrt(26))
        self.assertAlmostEqual(p['centers'][0][0], -5 / math.sqrt(26))
        result = predict([1.] * 12, p)
        self.assertEqual(result['label'], 0)
        self.assertAlmostEqual(result['distances'][0], 12 / 26)
        self.assertAlmostEqual(result['distances'][1], 12 * 81 / 26)

    def test_constant_features_stay_finite_and_missing_class_rejected(self):
        p = fit_model([[0.] * 12, [0.] * 12], [0, 1])
        self.assertEqual(p['scale'], [1.] * 12)
        self.assertEqual(predict([0.] * 12, p)['distances'], [0., 0.])
        with self.assertRaises(ValueError):
            fit_model([[0.] * 12], [0])

    def test_json_round_trip_preserves_predictions(self):
        model = valid_model()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'model.json'
            path.write_text(json.dumps(model), encoding='utf-8')
            loaded = load_model(path)
            self.assertEqual(predict([.7] * 12, loaded['params']),
                             predict([.7] * 12, model['params']))

    def test_incompatible_or_invalid_model_rejected(self):
        bad_models = []
        for key, value in [('channels', CHANNELS[::-1]), ('window_rows', 100),
                           ('target_hz', 100), ('kind', 'unknown'),
                           ('feature', 'other'), ('schema_version', 2)]:
            m = valid_model(); m[key] = value; bad_models.append(m)
        for key, value in [('scale', [0.] * 12), ('mean', [float('nan')] * 12),
                           ('centers', [[0.] * 12]), ('mean', [False] * 12)]:
            m = valid_model(); m['params'][key] = value; bad_models.append(m)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'model.json'
            for i, model in enumerate(bad_models):
                with self.subTest(case=i):
                    path.write_text(json.dumps(model), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        load_model(path)


if __name__ == '__main__':
    unittest.main()
