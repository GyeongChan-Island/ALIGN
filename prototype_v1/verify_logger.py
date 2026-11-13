"""Local smoke/integrity tests; no hardware or pyserial dependency."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import types
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', 'ALIGN_data_logger/collect_csv.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert len(m.CHANNELS) == 12
valid = '0,20000,' + ','.join(['0', '0', '1', '0', '0', '0'] * 2)
assert m.parse_sample(valid)[1] == 20000
endpoint = '0,20000,' + ','.join(['0','0','1','250.12978','-250.13741','0']*2)
assert m.parse_sample(endpoint)[2][3] == 250.12978
for bad in ('1,2,3', valid.replace('1,0,0,0', 'nan,0,0,0'),
            valid.replace('0,20000', '-1,20000'),
            '0,20000,' + ','.join(['3']*12)):
    try:
        m.parse_sample(bad)
        raise AssertionError('bad input accepted')
    except ValueError:
        pass

class FakeSerial:
    def __init__(self, *a, **kw):
        self.n = 0
        self.in_waiting = 0
        self.fragments = [b'#START,50Hz,g,deg/s\n',
                          (','.join(m.HEADER)+'\n').encode(),
                          valid[:20].encode(), (valid[20:]+'\n').encode(),
                          b'bad,row\n']
    def write(self, data): pass
    def close(self): pass
    def reset_input_buffer(self): pass
    def read_until(self, *a):
        if self.fragments:
            return self.fragments.pop(0)
        time.sleep(.02)
        self.n += 1
        # first subsequent row is seq 2: one deliberately missing slot
        seq = self.n + 1
        return (f'{seq},{20000+seq*20000},' + ','.join(['0','0','1','0','0','0']*2)+'\n').encode()

fake = types.ModuleType('serial')
fake.Serial = FakeSerial
fake.SerialException = type('SerialException', (Exception,), {})
fake.tools = types.ModuleType('serial.tools')
fake.tools.list_ports = types.SimpleNamespace(comports=lambda: [])
with tempfile.TemporaryDirectory() as out:
    with patch.dict(sys.modules, {'serial': fake, 'serial.tools': fake.tools}), \
         patch.object(sys, 'argv', ['collect_csv.py','--port','COM_TEST','--label','1',
                                  '--seconds','0.06','--out',out]):
        assert m.main() == 0
    summary = json.loads(next(Path(out).glob('*.json')).read_text())
    assert summary['rows'] >= 3
    assert summary['missing_slots'] == 1
    assert summary['malformed'] == 1
    import csv
    with next(Path(out).glob('*.csv')).open(newline='') as f:
        rows = list(csv.reader(f))
    assert all(len(r) == 17 for r in rows)
    assert rows[1][2] == '1'
print('PASS: parser, partial serial lines, CSV schema/label, missing-slot and invalid-row accounting')
