import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path('ALIGN_analysis_01')
d=json.loads((out/'analysis.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors=['#2563eb','#d97706']
fig,axes=plt.subplots(3,2,figsize=(12,10),sharex=True,sharey='row')
for label in (0,1):
    for k,s in enumerate(s for s in d['sessions'] if s['label']==label):
        v=np.array(s['values']); t=np.array(s['relative_time_s'])
        a=np.linalg.norm(v[:,:3],axis=1);b=np.linalg.norm(v[:,6:9],axis=1)
        angle=np.degrees(np.arccos(np.clip((v[:,:3]*v[:,6:9]).sum(1)/(a*b),-1,1)))
        axes[0,label].plot(t,angle,lw=1,alpha=.75,label=f'Session {k+1}')
        axes[1,label].plot(t,np.linalg.norm(v[:,3:6],axis=1),lw=.8,alpha=.7)
        axes[2,label].plot(t,np.linalg.norm(v[:,9:12],axis=1),lw=.8,alpha=.7)
    axes[0,label].set_title(f'Label {label} (hand-tilted sensors)',fontsize=12,fontweight='bold')
    axes[0,label].legend(fontsize=8,ncol=2,loc='upper right')
    axes[2,label].set_xlabel('Session elapsed time (s)')
for ax in axes.ravel():
    ax.grid(alpha=.2); ax.set_xlim(0,10)
axes[0,0].set_ylabel('Angle between acceleration vectors (deg)')
axes[1,0].set_ylabel('IMU 1 gyro vector magnitude (deg/s)')
axes[2,0].set_ylabel('IMU 2 gyro vector magnitude (deg/s)')
fig.suptitle('ALIGN collection practice: 10 independent recordings',fontsize=16,fontweight='bold',y=.98)
fig.text(.5,.015,'Vector angle is a descriptive sensor-axis measure, not a calibrated anatomical angle. Motion also affects it.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.035,1,.955));fig.savefig(out/'signal_overview.png',dpi=150);plt.close(fig)

fig,ax=plt.subplots(figsize=(10,4.5))
for label in (0,1):
    ss=[s for s in d['sessions'] if s['label']==label]
    for j,c in enumerate([0,1,2,6,7,8]):
        vals=[s['mean'][c] for s in ss]
        xs=j+(label-.5)*.22
        ax.scatter(np.full(5,xs),vals,color=colors[label],alpha=.85,s=40,
                   label=f'Label {label}: 5 session means' if j==0 else None)
ax.set_xticks(range(6),['IMU1 ax','IMU1 ay','IMU1 az','IMU2 ax','IMU2 ay','IMU2 az'])
ax.set_ylabel('Session mean acceleration (g)');ax.grid(axis='y',alpha=.2)
ax.set_title('Label 1 varies substantially across hand-tilting sessions',fontweight='bold')
ax.legend(loc='lower right');fig.tight_layout();fig.savefig(out/'session_means.png',dpi=150);plt.close(fig)
print('Two PNG figures saved')
