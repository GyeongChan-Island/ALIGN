import csv
import io
import json
from pathlib import Path
import queue
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HEADER
import live_predict
from test_core import line, valid_model
from test_training import csv_bytes


class FastStop:
    """Deterministic test stop: boot and replay delays do not sleep."""
    def __init__(self): self.stopped = False
    def is_set(self): return self.stopped
    def set(self): self.stopped = True
    def wait(self, timeout): return self.stopped


class FakeSerial:
    def __init__(self, stop, packets, boot=b'#INIT,0x68=OK,0x69=OK\n'):
        self.stop = stop
        self.packets = list(packets)
        self.boot = boot
        self.active = False
        self.closed = False
        self.writes = []
        self.clears = 0

    @property
    def in_waiting(self):
        if not self.active: return len(self.boot)
        return len(self.packets[0]) if self.packets else 0

    def read(self, n):
        if not self.active:
            value, self.boot = self.boot, b''
            return value
        if self.packets: return self.packets.pop(0)
        self.stop.set()
        return b''

    def write(self, data):
        self.writes.append(data)
        if data == b'S\n': self.active = True

    def reset_input_buffer(self): self.clears += 1
    def close(self): self.closed = True


class LiveTests(unittest.TestCase):
    def run_worker(self, folder, packets=None, boot=None, replay=False):
        root = Path(folder)
        model = root / 'model.json'
        model.write_text(json.dumps(valid_model()), encoding='utf-8')
        events = queue.Queue()
        stop = FastStop()
        if replay:
            source = root / 'source.csv'
            source.write_bytes(csv_bytes('demo', 'P01', 0))
            worker = live_predict.Worker(model, '', source, events, stop)
            with patch.object(live_predict, 'ROOT', root): worker.run()
            serial = None
        else:
            kwargs = {} if boot is None else {'boot': boot}
            serial = FakeSerial(stop, packets, **kwargs)
            fake_module = types.SimpleNamespace(Serial=lambda *a, **kw: serial)
            worker = live_predict.Worker(model, 'COM_TEST', None, events, stop)
            with patch.object(live_predict, 'ROOT', root), patch.dict(sys.modules, {'serial': fake_module}):
                worker.run()
        observed = []
        while not events.empty(): observed.append(events.get_nowait())
        log = next((root / 'logs').glob('*.csv'))
        with log.open(encoding='utf-8-sig', newline='') as f: logged = list(csv.DictReader(f))
        return observed, logged, serial

    def packets(self, count=100):
        return [b'#START,50Hz,g,deg/s\n', (','.join(HEADER)+'\n').encode()] + [
            (line(i, 1000000+i*20000)+'\n').encode() for i in range(count)]

    def test_paced_csv_replay_predicts_logs_and_finishes_without_serial(self):
        with tempfile.TemporaryDirectory() as tmp:
            events, logged, _ = self.run_worker(tmp, replay=True)
        self.assertEqual(sum(e['kind']=='prediction' for e in events), 2)
        self.assertFalse(any(e['kind']=='error' for e in events))
        self.assertEqual(events[-1]['kind'], 'done')
        self.assertEqual([r['mode'] for r in logged], ['replay', 'replay'])

    def test_serial_framing_partial_and_multiple_lines_cleanup(self):
        packets = self.packets()
        packets[2:5] = [b''.join(packets[2:5])[:17], b''.join(packets[2:5])[17:]]
        with tempfile.TemporaryDirectory() as tmp:
            events, logged, ser = self.run_worker(tmp, packets)
        self.assertEqual(sum(e['kind']=='prediction' for e in events), 2)
        self.assertEqual([r['seq'] for r in logged], ['49', '99'])
        self.assertEqual(ser.writes, [b'X\n', b'S\n', b'X\n'])
        self.assertEqual(ser.clears, 1)
        self.assertTrue(ser.closed)

    def test_startup_warning_blocks_predictions_and_stops_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            events, logged, ser = self.run_worker(tmp, self.packets(), boot=b'#WARN,bad ID\n')
        self.assertTrue(any(e['kind']=='error' for e in events))
        self.assertFalse(any(e['kind']=='prediction' for e in events))
        self.assertNotIn(b'S\n', ser.writes)
        self.assertTrue(ser.closed)

    def test_reset_during_run_clears_result_via_error_and_done(self):
        packets = self.packets(50) + [b'#READY,send S\n']
        with tempfile.TemporaryDirectory() as tmp:
            events, logged, ser = self.run_worker(tmp, packets)
        self.assertEqual(sum(e['kind']=='prediction' for e in events), 1)
        self.assertEqual([e['kind'] for e in events][-2:], ['error', 'done'])
        self.assertTrue(ser.closed)

    def test_missing_or_malformed_sample_does_not_mix_windows(self):
        packets = self.packets(100)
        # Replace sample 49: no prediction until a fresh 50 good rows arrive.
        packets[2+49] = b'invalid,row\n'
        with tempfile.TemporaryDirectory() as tmp:
            events, logged, _ = self.run_worker(tmp, packets)
        predictions = [r for r in logged if r['status']=='prediction']
        self.assertEqual([r['seq'] for r in predictions], ['99'])
        self.assertTrue(any(r['status']=='invalid' for r in logged))

    def test_backlog_aborts_instead_of_displaying_old_predictions(self):
        packets = self.packets(0) + [b'0'*4097]
        with tempfile.TemporaryDirectory() as tmp:
            events, logged, ser = self.run_worker(tmp, packets)
        self.assertTrue(any(e['kind']=='error' for e in events))
        self.assertFalse(any(e['kind']=='prediction' for e in events))
        self.assertTrue(ser.closed)


if __name__ == '__main__': unittest.main()
