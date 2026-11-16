"""Session registry (sessions.csv) and empty-sensor checks for train_model / evaluate_model."""
import argparse
from contextlib import redirect_stdout
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate_model
import test_evaluation
import test_training
import train_model
from train_model import EXPECTED_FIELDS, load_sessions


def zero_imu2_csv_bytes(sid):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(EXPECTED_FIELDS)
    for seq in range(100):
        writer.writerow([sid, 'P01', 0, seq, 1000000 + seq * 20000] + [.1] * 6 + [0.0] * 6)
    return stream.getvalue().encode('utf-8')


class SessionRegistryTests(unittest.TestCase):
    BAD_SID = '20261113_180239_b5f86fa7'

    def build(self, folder, registry_rows=None):
        data = test_training.TrainingTests.build_data(None, folder)
        (data / f'P01_{self.BAD_SID}_label0.csv').write_bytes(zero_imu2_csv_bytes(self.BAD_SID))
        if registry_rows is not None:
            lines = ['session_id,date,subject,condition,label,mount,status,note']
            lines += [f'{sid},2026-11-13,P01,body,0,unrecorded,{status},{note}'
                      for sid, status, note in registry_rows]
            (Path(folder) / 'sessions.csv').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return data

    def test_empty_sensor_session_is_rejected_without_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.build(tmp)
            with self.assertRaisesRegex(ValueError, 'IMU2'):
                load_sessions(data, registry=None)

    def test_registry_in_parent_folder_excludes_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [(f'session{i}', 'ok', '') for i in range(4)]
            rows.append((self.BAD_SID, 'exclude', 'IMU2 all zero'))
            data = self.build(tmp, rows)
            report = {}
            sessions = load_sessions(data, report=report)
            self.assertEqual(len(sessions), 4)
            self.assertEqual(report['registry'], 'sessions.csv')
            self.assertEqual([x['session_id'] for x in report['excluded']], [self.BAD_SID])
            self.assertEqual(report['unregistered'], [])

    def test_check_and_unregistered_sessions_are_kept_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [('session0', 'check', 'loose strap'), ('session1', 'ok', ''),
                    (self.BAD_SID, 'exclude', 'IMU2 all zero')]
            data = self.build(tmp, rows)
            report = {}
            sessions = load_sessions(data, report=report)
            self.assertEqual(len(sessions), 4)
            self.assertEqual(report['check'], ['session0'])
            self.assertEqual(sorted(report['unregistered']), ['session2', 'session3'])

    def test_invalid_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.build(tmp, [('session0', 'maybe', '')])
            with self.assertRaisesRegex(ValueError, 'status'):
                load_sessions(data)


class RegistryReviewTests(unittest.TestCase):
    """PR #7 리뷰(김도현) 지적 사항."""
    BAD_SID = SessionRegistryTests.BAD_SID

    def write_registry(self, folder, rows):
        lines = ['session_id,date,subject,condition,label,mount,status,note']
        lines += [f'{sid},2026-11-13,P01,body,{label},unrecorded,{status},'
                  for sid, label, status in rows]
        (Path(folder) / 'sessions.csv').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_duplicate_session_id_in_registry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = test_training.TrainingTests.build_data(None, tmp)
            self.write_registry(tmp, [(self.BAD_SID, 0, 'exclude'), (self.BAD_SID, 0, 'ok')])
            with self.assertRaisesRegex(ValueError, '중복'):
                load_sessions(data)

    def test_exclude_applies_even_when_file_name_is_not_logger_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = test_training.TrainingTests.build_data(None, tmp)
            (data / 'renamed_by_hand.csv').write_bytes(zero_imu2_csv_bytes(self.BAD_SID))
            self.write_registry(tmp, [(f'session{i}', i % 2, 'ok') for i in range(4)]
                                + [(self.BAD_SID, 0, 'exclude')])
            report = {}
            self.assertEqual(len(load_sessions(data, report=report)), 4)
            self.assertEqual(report['excluded'][0]['file'], 'renamed_by_hand.csv')

    def test_label_mismatch_between_registry_and_csv_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = test_training.TrainingTests.build_data(None, tmp)
            # session1, session3 are label 1 in the CSV but written as 0 here.
            self.write_registry(tmp, [(f'session{i}', 0, 'ok') for i in range(4)])
            report = {}
            load_sessions(data, report=report)
            self.assertEqual(sorted(x['session_id'] for x in report['label_mismatch']),
                             ['session1', 'session3'])

    def test_a_few_zero_rows_do_not_stop_a_short_session(self):
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(EXPECTED_FIELDS)
        for seq in range(100):
            imu2 = [0.0] * 6 if seq == 10 else [.1] * 6
            writer.writerow(['short', 'P01', 0, seq, 1000000 + seq * 20000] + [.1] * 6 + imu2)
        session = train_model.read_session('short.csv', stream.getvalue().encode('utf-8'))
        self.assertEqual(session['rows'], 100)

    def test_registry_search_stops_at_repository_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            (outer / 'sessions.csv').write_text('session_id,status\n', encoding='utf-8')
            repo = outer / 'ALIGN'
            (repo / '.git').mkdir(parents=True)
            data = repo / 'data' / 'hand'
            data.mkdir(parents=True)
            self.assertIsNone(train_model.find_registry(data))
            (repo / 'sessions.csv').write_text('session_id,status\n', encoding='utf-8')
            self.assertEqual(train_model.find_registry(data), repo / 'sessions.csv')

    def test_evaluate_model_records_excluded_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, _ = test_evaluation.SavedEvaluationTests().trained(tmp)
            model_path = root / 'model.json'
            model_path.write_text(json.dumps(model), encoding='utf-8')
            test_dir = root / 'heldout'
            test_dir.mkdir()
            (test_dir / 'new.csv').write_bytes(test_training.csv_bytes('new_session', 'P03', 1, .02))
            (test_dir / f'P01_{self.BAD_SID}_label0.csv').write_bytes(zero_imu2_csv_bytes(self.BAD_SID))
            self.write_registry(test_dir, [('new_session', 1, 'ok'), (self.BAD_SID, 0, 'exclude')])
            args = argparse.Namespace(model=str(model_path), data=str(test_dir), out=str(root / 'eval'))
            with redirect_stdout(io.StringIO()) as out:
                report = evaluate_model.run(args)
            self.assertEqual([x['session_id'] for x in report['session_registry']['excluded']], [self.BAD_SID])
            saved = json.loads((root / 'eval' / 'evaluation.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['session_registry']['registry'], 'sessions.csv')
            self.assertIn('제외 1세션', out.getvalue())
            args.no_sessions, args.out = True, str(root / 'eval_all')
            with self.assertRaisesRegex(ValueError, 'IMU2'):
                with redirect_stdout(io.StringIO()):
                    evaluate_model.run(args)

    def test_emoji_note_does_not_stop_training_when_output_is_piped(self):
        # Windows pipes/log files default to cp949, which cannot encode emoji
        # (ALIGN-data notes link Notion pages with a bug icon).
        with tempfile.TemporaryDirectory() as tmp:
            data = test_training.TrainingTests.build_data(None, tmp)
            (data / f'P01_{self.BAD_SID}_label0.csv').write_bytes(zero_imu2_csv_bytes(self.BAD_SID))
            lines = ['session_id,date,subject,condition,label,mount,status,note']
            lines += [f'session{i},2026-11-13,P01,body,{i % 2},unrecorded,ok,' for i in range(4)]
            lines.append(f'{self.BAD_SID},2026-11-13,P01,body,0,unrecorded,exclude,IMU2 \U0001f41e')
            (Path(tmp) / 'sessions.csv').write_text('\n'.join(lines) + '\n', encoding='utf-8')
            env = {k: v for k, v in os.environ.items() if k not in ('PYTHONIOENCODING', 'PYTHONUTF8')}
            script = Path(train_model.__file__).resolve()
            done = subprocess.run(
                [sys.executable, str(script), '--data', str(data), '--kind', 'hand',
                 '--out', str(Path(tmp) / 'out')],
                capture_output=True, env=env, cwd=script.parent, timeout=120)
            self.assertEqual(done.returncode, 0, done.stderr.decode('utf-8', 'replace'))
            self.assertIn('IMU2 \U0001f41e', done.stdout.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
