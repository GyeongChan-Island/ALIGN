"""Shared, dependency-free preprocessing for training, replay and live inference."""
import json
import math
from pathlib import Path
import re

CHANNELS = [f'imu{i}_{axis}_{unit}' for i in (1, 2) for axis, unit in
            [('ax','g'),('ay','g'),('az','g'),('gx','dps'),('gy','dps'),('gz','dps')]]
HEADER = ['seq', 'time_us'] + CHANNELS
WINDOW_ROWS = 50


def parse_sample(line):
    p = line.strip().split(',')
    if len(p) != 14 or not all(re.fullmatch(r'[0-9]+', x) for x in p[:2]):
        raise ValueError('14 columns with nonnegative integer seq/time_us required')
    v = [float(x) for x in p[2:]]
    if not all(math.isfinite(x) for x in v):
        raise ValueError('NaN/Infinity is not allowed')
    if any(abs(x) > (2.00001 if i % 6 < 3 else 32768/131 + .00001) for i, x in enumerate(v)):
        raise ValueError('outside configured +/-2g, +/-250deg/s digital range')
    return int(p[0]), int(p[1]), v


class WindowBuffer:
    def __init__(self):
        self.reset()

    def reset(self):
        self.rows = []
        self.previous = None

    def feed(self, seq, ts, values):
        if len(values) != 12 or not all(math.isfinite(x) for x in values):
            self.reset()
            raise ValueError('12 finite channels required')
        broken = self.previous is not None and (
            seq - self.previous[0] != 1 or abs(ts - self.previous[1] - 20000) > 5000)
        self.previous = (seq, ts)
        if broken:
            self.rows.clear()
        if any(abs(x) >= (1.98 if i % 6 < 3 else 247.5) for i, x in enumerate(values)):
            self.rows.clear()
            return None, 'saturated'
        self.rows.append(list(values))
        if len(self.rows) == WINDOW_ROWS:
            means = [sum(row[i] for row in self.rows)/WINDOW_ROWS for i in range(12)]
            self.rows.clear()
            return means, 'ready'
        return None, 'gap' if broken else 'collecting'


def fit_model(features, labels):
    if len(features) != len(labels) or set(labels) != {0, 1}:
        raise ValueError('Both labels 0 and 1 required')
    if any(len(row) != 12 or not all(math.isfinite(v) for v in row) for row in features):
        raise ValueError('12 finite features required')
    n = len(features)
    mean = [sum(row[i] for row in features)/n for i in range(12)]
    scale = [math.sqrt(sum((row[i]-mean[i])**2 for row in features)/n) for i in range(12)]
    scale = [s if s >= 1e-8 else 1.0 for s in scale]
    centers = []
    for label in (0, 1):
        rows = [r for r,y in zip(features,labels) if y==label]
        centers.append([sum((r[i]-mean[i])/scale[i] for r in rows)/len(rows) for i in range(12)])
    return dict(mean=mean, scale=scale, centers=centers)


def predict(features, params):
    if len(features) != 12 or not all(math.isfinite(v) for v in features):
        raise ValueError('12 finite features required')
    z = [(v-m)/s for v,m,s in zip(features,params['mean'],params['scale'])]
    distances = [sum((x-c)**2 for x,c in zip(z,center)) for center in params['centers']]
    return dict(label=int(distances[1]<distances[0]), distances=distances)


def load_model(path):
    model = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    expected = dict(schema_version=1, channels=CHANNELS, window_rows=50, target_hz=50,
                    feature='channel_means', method='standardized_nearest_centroid')
    if not isinstance(model,dict) or any(model.get(k)!=v for k,v in expected.items()):
        raise ValueError('Model format/channels/window/rate do not match this program')
    if model.get('kind') not in ('hand','body'):
        raise ValueError('Model kind must be hand or body')
    try:
        p=model['params']
        vectors=[p['mean'],p['scale'],*p['centers']]
        if len(p['centers'])!=2 or len(vectors)!=4:
            raise ValueError('two centers required')
        if any(len(v)!=12 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in v) for v in vectors):
            raise ValueError('non-finite or wrong dimension')
        if any(s<=0 for s in p['scale']):
            raise ValueError('scale must be positive')
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError(f'Invalid model parameters: {exc}') from exc
    return model
