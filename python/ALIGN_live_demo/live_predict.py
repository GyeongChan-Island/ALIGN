"""ALIGN desktop demo: live serial prediction or paced CSV replay."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import queue
import threading
import time
import uuid

from common import CHANNELS, HEADER, WindowBuffer, load_model, parse_sample, predict

ROOT = Path(__file__).resolve().parent
MESSAGES = {'gap':'데이터 간격이 끊겨 새 1초 구간을 모으고 있습니다.',
            'saturated':'센서 측정 한계 근처 값: 판정을 보류합니다.',
            'invalid':'잘못된 데이터: 새 구간을 모으고 있습니다.',
            'waiting':'데이터 수신 대기 중입니다.'}


class Worker(threading.Thread):
    def __init__(self, model_path, port, replay, events, stop):
        super().__init__(daemon=True)
        self.model_path=Path(model_path)
        self.port=port
        self.replay=Path(replay) if replay else None
        self.events=events
        self.stop=stop
        self.window=WindowBuffer()
        self.last_prediction=time.monotonic()

    def emit(self, kind, **payload):
        event=dict(kind=kind, **payload)
        # Only presentation events are bounded; serial samples are processed here.
        try:
            self.events.put_nowait(event)
        except queue.Full:
            try: self.events.get_nowait()
            except queue.Empty: pass
            self.events.put_nowait(event)

    def run(self):
        try:
            self.model=load_model(self.model_path)
            digest=hashlib.sha256(self.model_path.read_bytes()).hexdigest()
            logs=ROOT/'logs'; logs.mkdir(exist_ok=True)
            dest=logs/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.csv')
            with dest.open('x',newline='',encoding='utf-8-sig') as f:
                self.logfile=f
                self.writer=csv.writer(f)
                self.writer.writerow(['pc_time','mode','model_kind','model_sha256','seq','time_us','status','predicted_label','distance0','distance1'])
                self.digest=digest
                self.emit('info',message=f'모델: {self.model["kind"]} / 판정 기록: {dest}')
                if self.replay: self.run_replay()
                else: self.run_serial()
        except Exception as exc:
            self.emit('error',message=str(exc))
        finally:
            self.emit('done',message='종료했습니다. 다시 시작할 수 있습니다.')

    def record(self, seq, ts, status, result=None):
        d=result or {}
        distances=d.get('distances',['',''])
        self.writer.writerow([datetime.now().astimezone().isoformat(timespec='milliseconds'),
                              'replay' if self.replay else 'serial',self.model['kind'],self.digest,
                              seq,ts,status,d.get('label',''),*distances])
        self.logfile.flush()

    def accept(self, seq, ts, values):
        feat,status=self.window.feed(seq,ts,values)
        if status in ('gap','saturated'):
            self.record(seq,ts,status)
            self.emit('status',message=MESSAGES[status])
        if feat is not None:
            result=predict(feat,self.model['params'])
            self.record(seq,ts,'prediction',result)
            self.last_prediction=time.monotonic()
            self.emit('prediction',result=result,seq=seq,time_us=ts)

    def run_replay(self):
        with self.replay.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            required=['session_id','subject_id','label']+HEADER
            if reader.fieldnames != required:
                raise ValueError('재생 CSV 열이 다릅니다. collect_csv.py로 저장한 원본 CSV를 선택하세요.')
            sid=None
            for row in reader:
                if self.stop.is_set(): break
                if sid is None: sid=row['session_id']
                if row['session_id'] != sid:
                    raise ValueError('한 파일에 여러 세션이 있습니다. 세션별 원본 CSV를 사용하세요.')
                seq,ts,v=parse_sample(','.join(row[k] for k in HEADER))
                self.accept(seq,ts,v)
                if self.stop.wait(.02): break

    def run_serial(self):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError('pyserial 설치 필요: py -m pip install -r requirements.txt') from exc
        if not self.port: raise ValueError('COM 포트를 선택하세요.')
        ser=None
        try:
            ser=serial.Serial(self.port,115200,timeout=.1,write_timeout=1)
            self.emit('status',message='ESP32 부팅 대기 중… 약 3초 걸립니다.')
            if self.stop.wait(3): return
            ser.write(b'X\n')
            if self.stop.wait(.2): return
            # Retain fatal/ID warnings from boot before discarding pre-session data.
            boot=ser.read(ser.in_waiting).decode('ascii',errors='replace')
            if '#FATAL' in boot or '#WARN' in boot:
                raise RuntimeError('보드 초기화 경고를 확인하세요. 시리얼 모니터에서 EN/RESET 후 확인:\n'+boot[-1500:])
            ser.reset_input_buffer()  # once, before starting a new stream
            ser.write(b'S\n')
            started=False; header=False
            pending=bytearray()
            last_valid=time.monotonic()
            last_warning=0.
            anchor=None; last_pair=None
            while not self.stop.is_set():
                now=time.monotonic()
                if now-last_valid>5:
                    raise RuntimeError('5초 동안 유효한 데이터가 없습니다. COM 포트·전원·로거 업로드를 확인하세요.')
                if now-last_valid>1.5 and now-last_warning>1:
                    self.window.reset()
                    self.emit('status',message=MESSAGES['waiting'])
                    last_warning=now
                n=ser.in_waiting
                if n>4096:
                    raise RuntimeError('수신 데이터가 밀렸습니다. 오래된 판정을 막기 위해 중단합니다. 다른 작업을 줄이고 다시 연결하세요.')
                pending.extend(ser.read(n or 1))
                while b'\n' in pending:
                    raw,_,rest=pending.partition(b'\n'); pending=bytearray(rest)
                    try: line=raw.decode('ascii').strip()
                    except UnicodeDecodeError:
                        self.window.reset(); self.record('','','invalid')
                        self.emit('status',message=MESSAGES['invalid']); continue
                    if line.startswith('#'):
                        if line.startswith(('#FATAL','#WARN')):
                            raise RuntimeError(line)
                        if line.startswith('#START'):
                            if started: raise RuntimeError('측정 중 재시작됐습니다. 다시 연결하세요.')
                            if line!='#START,50Hz,g,deg/s': raise RuntimeError('50Hz / g / deg/s 로거가 필요합니다.')
                            started=True
                        elif started and line.startswith(('#READY','#INIT','#STOP')):
                            raise RuntimeError('보드가 재시작 또는 중단됐습니다. 다시 연결하세요.')
                        elif line.startswith('#READ_FAIL'):
                            self.window.reset(); self.record('','','read_fail')
                            self.emit('status',message='센서 읽기 실패: 배선을 확인하세요.')
                        continue
                    if line==','.join(HEADER):
                        header=True; continue
                    if not started or not header: continue
                    try: seq,ts,v=parse_sample(line)
                    except ValueError:
                        self.window.reset(); self.record('','','invalid')
                        self.emit('status',message=MESSAGES['invalid']); continue
                    if last_pair is not None and (seq<=last_pair[0] or ts<=last_pair[1]):
                        raise RuntimeError('순번/시간이 역행했습니다. 다시 연결하세요.')
                    last_pair=(seq,ts)
                    now=time.monotonic()
                    if anchor is None: anchor=(now,ts)
                    if (now-anchor[0])-(ts-anchor[1])/1e6>2:
                        raise RuntimeError('보드 시간보다 수신이 2초 이상 늦습니다. 다시 연결하세요.')
                    last_valid=now
                    self.accept(seq,ts,v)
                if len(pending)>2048:
                    raise RuntimeError('시리얼 행이 너무 깁니다. 115200 baud와 로거 형식을 확인하세요.')
        finally:
            if ser is not None:
                try: ser.write(b'X\n')
                except Exception: pass
                ser.close()


class App:
    def __init__(self, root, args):
        import tkinter as tk
        from tkinter import ttk
        self.root=root; self.args=args
        self.events=queue.Queue(maxsize=32);self.worker=None;self.stop_event=threading.Event()
        self.closing=False;self.last_result=None;self.kind='hand'
        root.title('ALIGN 센서 상태 분류 연습');root.geometry('800x600');root.minsize(720,540)
        root.configure(bg='#f4f6fa')
        style=ttk.Style();style.configure('TButton',font=('맑은 고딕',10),padding=7)
        outer=ttk.Frame(root,padding=20);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='ALIGN 실시간 판정',font=('맑은 고딕',20,'bold')).pack(anchor='w')
        self.scope=tk.StringVar()
        ttk.Label(outer,textvariable=self.scope,font=('맑은 고딕',10),wraplength=740).pack(anchor='w',pady=(5,16))
        modelrow=ttk.Frame(outer);modelrow.pack(fill='x')
        self.modelpath=tk.StringVar(value=str(args.model.resolve()))
        ttk.Entry(modelrow,textvariable=self.modelpath,state='readonly').pack(side='left',fill='x',expand=True)
        self.model_button=ttk.Button(modelrow,text='모델 선택',command=self.choose_model);self.model_button.pack(side='left',padx=(8,0))
        ports=ttk.Frame(outer);ports.pack(fill='x',pady=12)
        ttk.Label(ports,text='COM 포트').pack(side='left')
        self.port=tk.StringVar(value=args.port or '')
        self.combo=ttk.Combobox(ports,textvariable=self.port,width=14);self.combo.pack(side='left',padx=8)
        self.refresh_button=ttk.Button(ports,text='새로고침',command=self.refresh);self.refresh_button.pack(side='left')
        self.connect_button=ttk.Button(ports,text='실시간 연결',command=lambda:self.start(None));self.connect_button.pack(side='left',padx=8)
        self.replay_button=ttk.Button(ports,text='CSV 재생',command=self.choose_replay);self.replay_button.pack(side='left')
        self.stop_button=ttk.Button(ports,text='중지',command=self.stop,state='disabled');self.stop_button.pack(side='right')
        self.mode=tk.StringVar(value='연결 전 · 시리얼 모니터와 CSV 수집 프로그램을 닫으세요.')
        ttk.Label(outer,textvariable=self.mode,wraplength=740).pack(anchor='w',pady=8)
        self.card=tk.Label(outer,text='대기',font=('맑은 고딕',36,'bold'),bg='#e8edf4',fg='#334155',height=2)
        self.card.pack(fill='x',pady=12)
        self.status=tk.StringVar(value='모델을 확인하고 실시간 연결 또는 CSV 재생을 누르세요.')
        ttk.Label(outer,textvariable=self.status,wraplength=740,font=('맑은 고딕',11)).pack(anchor='w',pady=8)
        self.detail=tk.StringVar(value='연속 50샘플(약 1초)을 모을 때마다 갱신합니다.')
        ttk.Label(outer,textvariable=self.detail,wraplength=740).pack(anchor='w',pady=6)
        ttk.Label(outer,text='판정은 두 학습 상태 중 더 가까운 상태입니다. 확률·의학적 진단을 뜻하지 않습니다.',wraplength=740).pack(anchor='w',pady=8)
        self.info=tk.StringVar()
        ttk.Label(outer,textvariable=self.info,wraplength=740,foreground='#526174').pack(anchor='w',pady=8)
        self.refresh();self.update_model()
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.poll)
        if args.replay: root.after(200,lambda:self.start(args.replay))

    def update_model(self):
        try:
            m=load_model(self.modelpath.get());self.kind=m['kind']
            self.scope.set('손 기울기 연습 모델 · 실제 인체 자세 성능을 평가한 모델이 아닙니다.' if self.kind=='hand'
                           else '착용 데이터로 학습한 모델 · 정상/불량은 학습 때 정한 라벨 기준입니다.')
            return True
        except Exception as exc:
            self.status.set(f'모델을 불러올 수 없습니다: {exc}');return False

    def refresh(self):
        try:
            from serial.tools import list_ports
            self.combo['values']=[p.device for p in list_ports.comports()]
        except ImportError:
            self.status.set('실시간 연결에는 pyserial이 필요합니다. CSV 재생은 설치 없이 가능합니다.')

    def choose_model(self):
        from tkinter import filedialog
        path=filedialog.askopenfilename(title='학습 모델 선택',initialdir=ROOT/'models',filetypes=[('JSON model','*.json')])
        if path: self.modelpath.set(path);self.update_model()

    def choose_replay(self):
        from tkinter import filedialog
        path=filedialog.askopenfilename(title='collect_csv.py 원본 CSV 선택',initialdir=ROOT.parent.parent/'data'/'hand_tilt_practice_01',filetypes=[('Sensor CSV','*.csv')])
        if path: self.start(path)

    def start(self,replay):
        if self.worker and self.worker.is_alive(): return
        if not self.update_model(): return
        self.events=queue.Queue(maxsize=32);self.stop_event=threading.Event()
        self.card.config(text='수집 중',bg='#e8edf4',fg='#334155');self.last_result=None
        self.status.set('새로운 1초 구간을 기다립니다.')
        self.mode.set('CSV 재생 · 학습에 쓴 CSV의 재생은 새로운 성능 평가가 아닙니다.' if replay else f'실시간 · {self.port.get()} · 115200 baud')
        self.worker=Worker(self.modelpath.get(),self.port.get(),replay,self.events,self.stop_event)
        self.set_busy(True);self.worker.start()

    def set_busy(self,busy):
        for w in (self.connect_button,self.replay_button,self.model_button,self.refresh_button):
            w.config(state='disabled' if busy else 'normal')
        self.combo.config(state='disabled' if busy else 'normal')
        self.stop_button.config(state='normal' if busy else 'disabled')

    def stop(self):
        self.stop_event.set();self.last_result=None
        self.card.config(text='중지 중',bg='#e8edf4',fg='#334155')

    def close(self):
        self.closing=True;self.stop()

    def poll(self):
        while True:
            try: e=self.events.get_nowait()
            except queue.Empty: break
            kind=e['kind']
            if kind=='prediction' and not self.stop_event.is_set():
                label=e['result']['label'];self.last_result=time.monotonic()
                names=['상태 0','상태 1'] if self.kind=='hand' else ['정상 자세 0','불량 자세 1']
                self.card.config(text=names[label],bg=['#dbeafe','#ffedd5'][label],fg=['#1d4ed8','#9a3412'][label])
                self.status.set('최근 연속 50샘플의 예측 결과입니다.')
                self.detail.set(f"순번 {e['seq']} · 센서 시간 {e['time_us']/1e6:.2f}초 · 다음 약 1초 후 갱신")
            elif kind in ('status','error'):
                self.last_result=None
                self.card.config(text='판정 대기' if kind=='status' else '확인 필요',bg='#e8edf4',fg='#334155')
                self.status.set(e['message'])
            elif kind=='info': self.info.set(e['message'])
            elif kind=='done':
                self.last_result=None;self.card.config(text='종료',bg='#e8edf4',fg='#334155')
                self.detail.set(e['message']);self.set_busy(False)
        if self.last_result and time.monotonic()-self.last_result>2:
            self.last_result=None;self.card.config(text='판정 대기',bg='#e8edf4',fg='#334155')
            self.status.set('최근 2초간 새 판정이 없습니다.')
        if self.closing and (self.worker is None or not self.worker.is_alive()):
            self.root.destroy();return
        self.root.after(100,self.poll)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',default='')
    p.add_argument('--model',type=Path,default=ROOT/'models'/'hand'/'model.json')
    p.add_argument('--replay',type=Path)
    p.add_argument('--list-ports',action='store_true')
    args=p.parse_args()
    if args.list_ports:
        from serial.tools import list_ports
        for port in list_ports.comports(): print(port.device,port.description)
        return
    import tkinter as tk
    root=tk.Tk();App(root,args);root.mainloop()


if __name__=='__main__': main()
