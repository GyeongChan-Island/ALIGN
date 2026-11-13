"""Package and smoke-test the portable ALIGN demonstration."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root = Path('ALIGN_live_demo')
target = Path('ALIGN_live_demo.zip')
files = sorted(p for p in root.rglob('*') if p.is_file()
               and '__pycache__' not in p.parts and 'logs' not in p.parts)
required = ['run_demo.cmd', 'README_ko.md', 'requirements.txt', 'common.py',
            'live_predict.py', 'train_model.py', 'evaluate_model.py',
            'models/hand/model.json', 'models/hand/evaluation.json']
assert all((root/p).is_file() for p in required)
assert len(list((root/'sample_data').glob('*.csv'))) == 10
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path,path.as_posix())
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert not any('__pycache__' in n or '/logs/' in n for n in archive.namelist())
    with tempfile.TemporaryDirectory(prefix='align_demo_') as folder:
        archive.extractall(folder)  # only this script's known generated files
        package = Path(folder)/root
        result = subprocess.run([sys.executable,str(package/'train_model.py'),
                                 '--data',str(package/'sample_data'),'--kind','hand',
                                 '--split','session','--out',str(Path(folder)/'trained')],
                                capture_output=True,text=True,encoding='utf-8',
                                env={**__import__('os').environ,'PYTHONIOENCODING':'utf-8'})
        assert result.returncode == 0, result.stderr
        trained=json.loads((Path(folder)/'trained/model.json').read_text(encoding='utf-8'))
        supplied=json.loads((package/'models/hand/model.json').read_text(encoding='utf-8'))
        assert trained['params'] == supplied['params']
        assert trained['training_sessions'] == supplied['training_sessions']
        assert trained['evaluation']['correct'] == 87
        for entry in ('live_predict.py','evaluate_model.py'):
            help_result=subprocess.run([sys.executable,str(package/entry),'--help'],
                                       capture_output=True)
            assert help_result.returncode == 0
print(f'PASS: ZIP integrity, {len(files)} files, portable retraining, model parameter parity, 87/100 evaluation')
print(f'ZIP: {target.resolve()} ({target.stat().st_size:,} bytes)')
