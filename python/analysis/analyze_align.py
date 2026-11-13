"""Reproducible read-only ZIP audit and session-separated exploratory baseline."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np

REPO = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description='손 기울기 연습 데이터 분석 재현')
parser.add_argument('--data', type=Path, default=REPO/'data/hand_tilt_practice_01')
parser.add_argument('--out', type=Path, default=REPO/'results/hand_tilt_analysis')
args = parser.parse_args()
SOURCE, OUT = args.data, args.out

class CSVFolder:
    def __init__(self, root): self.root=root
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def namelist(self): return sorted(p.name for p in self.root.iterdir() if p.is_file())
    def read(self, name): return (self.root/name).read_bytes()
    def testzip(self): return None

OUT.mkdir(parents=True, exist_ok=True)
CHANNELS = [f'imu{i}_{a}_{u}' for i in (1,2) for a,u in
            [('ax','g'),('ay','g'),('az','g'),('gx','dps'),('gy','dps'),('gz','dps')]]
sessions = []
X, Y, G = [], [], []
with (CSVFolder(SOURCE) if SOURCE.is_dir() else zipfile.ZipFile(SOURCE)) as z:
    assert z.testzip() is None
    for name in sorted(n for n in z.namelist() if n.endswith('.csv')):
        raw = z.read(name)
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        rows = list(reader)
        assert reader.fieldnames == ['session_id','subject_id','label','seq','time_us']+CHANNELS
        sid = rows[0]['session_id']
        label = int(rows[0]['label'])
        assert all(r['session_id']==sid and int(r['label'])==label and r['subject_id']=='P01' for r in rows)
        values = np.array([[float(r[c]) for c in CHANNELS] for r in rows])
        seq = np.array([int(r['seq']) for r in rows])
        ts = np.array([int(r['time_us']) for r in rows], dtype=np.int64)
        assert np.isfinite(values).all() and (np.diff(seq)>0).all() and (np.diff(ts)>0).all()
        summary = json.loads(z.read(name[:-4]+'.summary.json'))
        events = z.read(name[:-4]+'.events.txt').decode('utf-8')
        gaps = int(seq[0]+np.sum(np.diff(seq)-1))
        timing = int(np.sum(np.abs(np.diff(ts)-np.diff(seq)*20000)>5000))
        near = int(np.any(np.abs(values)>=np.array(([1.98]*3+[247.5]*3)*2),axis=1).sum())
        hz = (len(rows)-1)*1e6/(ts[-1]-ts[0])
        assert summary['rows']==len(rows) and summary['missing_slots']==gaps
        assert abs(summary['received_hz']-hz)<1e-8
        assert summary['near_full_scale_rows']==near and summary['timing_anomalies']==timing
        assert summary['label']==label and summary['session_id']==sid
        norms = [np.linalg.norm(values[:,i:i+3],axis=1) for i in [0,6]]
        cosine = np.sum(values[:,:3]*values[:,6:9],axis=1)/(norms[0]*norms[1])
        angle = np.degrees(np.arccos(np.clip(cosine,-1,1)))
        session = dict(file=name,sha256=hashlib.sha256(raw).hexdigest(),session_id=sid,
                       label=label,rows=len(rows),hz=hz,missing=gaps,timing_anomalies=timing,
                       near_full_scale_rows=near,source_summary=summary,events=events,
                       mean=values.mean(0).tolist(),std=values.std(0,ddof=1).tolist(),
                       accel_norm_mean=[float(n.mean()) for n in norms],
                       gravity_vector_angle_mean=float(angle.mean()),
                       relative_time_s=((ts-ts[0])/1e6).tolist(),values=values.tolist())
        gi=len(sessions)
        sessions.append(session)
        # 50-row non-overlapping windows; no crossing session or gap boundaries.
        for start in range(0,len(rows)-49,50):
            end=start+50
            if np.any(np.diff(seq[start:end])!=1) or np.any(np.abs(np.diff(ts[start:end])-20000)>5000):
                continue
            X.append(values[start:end].mean(0))
            Y.append(label)
            G.append(gi)

assert len(set(s['session_id'] for s in sessions))==len(sessions)
assert len(set(s['sha256'] for s in sessions))==len(sessions), 'Identical CSV files'
X,Y,G=np.array(X),np.array(Y),np.array(G)
by_label=[[i for i,s in enumerate(sessions) if s['label']==k] for k in (0,1)]
assert len(by_label[0])==len(by_label[1])==5
pred=np.full(len(Y),-1)
folds=[]
for k in range(5):
    test_groups=[by_label[0][k],by_label[1][k]]
    test=np.isin(G,test_groups)
    train=~test
    assert set(G[train]).isdisjoint(set(G[test]))
    mean=X[train].mean(0)
    scale=X[train].std(0)
    scale=np.where(scale<1e-8,1.,scale)
    Z=(X-mean)/scale
    centers=np.stack([Z[train & (Y==c)].mean(0) for c in (0,1)])
    dist=((Z[test,None,:]-centers[None,:,:])**2).sum(2)
    pred[test]=np.argmin(dist,axis=1)
    folds.append(dict(fold=k+1,train_sessions=[sessions[i]['session_id'] for i in range(10) if i not in test_groups],
                      test_sessions=[sessions[i]['session_id'] for i in test_groups],
                      train_windows=int(train.sum()),test_windows=int(test.sum()),
                      correct=int((pred[test]==Y[test]).sum()),accuracy=float((pred[test]==Y[test]).mean())))
assert (pred>=0).all()
cm=np.zeros((2,2),dtype=int)
for a,b in zip(Y,pred): cm[a,b]+=1
session_correct=0
for i,s in enumerate(sessions):
    p=pred[G==i]
    # Abstain on equal votes; do not count a tie as correct.
    vote=int(p.mean()>.5) if p.mean()!=.5 else None
    s['test_window_count']=len(p)
    s['test_window_correct']=int((p==s['label']).sum())
    s['session_vote']=vote
    session_correct+=vote==s['label']
results=dict(source=SOURCE.name,source_sha256=(hashlib.sha256(SOURCE.read_bytes()).hexdigest() if SOURCE.is_file() else None),
             channels=CHANNELS,sessions=sessions,window_size_rows=50,window_overlap_rows=0,
             feature_definition='mean of each of 12 channels; fixed before scoring',
             model='train-standardized Euclidean nearest class centroid (NumPy)',
             validation='5 folds; nth chronological session of each label held out together; no tuning',
             window_accuracy=float((Y==pred).mean()),confusion_matrix=cm.tolist(),
             session_vote_correct=int(session_correct),session_vote_total=len(sessions),folds=folds)
(OUT/'analysis.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'session_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
    fields=['session_id','label','rows','hz','missing','timing_anomalies','near_full_scale_rows','test_window_count','test_window_correct','session_vote']
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(sessions)
with (OUT/'window_predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['session_id','window_index','true_label','predicted_label'])
    for i,s in enumerate(sessions):
        for wi,pr in enumerate(pred[G==i]): w.writerow([s['session_id'],wi,s['label'],int(pr)])
print(json.dumps({k:v for k,v in results.items() if k not in ['sessions','folds']},indent=2))
for i,s in enumerate(sessions):
    print(i,s['label'],s['rows'],round(s['hz'],3),'gaps',s['missing'],'warnings',s['source_summary']['warnings'],
          'accel mean',np.round(np.array(s['mean'])[[0,1,2,6,7,8]],3),'angle',round(s['gravity_vector_angle_mean'],2),
          'correct',s['test_window_correct'],'/',s['test_window_count'])
