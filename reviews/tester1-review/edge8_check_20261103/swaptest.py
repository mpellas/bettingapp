import csv,glob
from leanslib import shots_by_id
import collections
S={'conf':[], 'unconf':[]}
for f in sorted(glob.glob('in/picks/2026*_D.csv')):
    dte=f.split('/')[-1][:8]
    if not '20261011'<=dte<='20261102': continue
    sh=shots_by_id(dte)
    for r in csv.DictReader(open(f)):
        try: nid=int(float(r['nhl_id'])); nv=float(r['nv_over']); pm=float(r['p_model_over'])
        except: continue
        if nid not in sh: continue
        S['conf' if r['side_method']=='milestone' else 'unconf'].append((nv,pm,sh[nid]>float(r['line'])))
for k,v in S.items():
    n=len(v); o=sum(x[2] for x in v)
    b1=sum((x[0]-x[2])**2 for x in v)/n; b2=sum((1-x[0]-x[2])**2 for x in v)/n
    bm=sum((x[1]-x[2])**2 for x in v)/n
    print(k,n,f'over hit {o/n:.3f} mean nv_over {sum(x[0] for x in v)/n:.3f} Brier nv-as-labeled {b1:.4f} nv-swapped {b2:.4f} model {bm:.4f}')
# the 69 unconf 8+ leans
v=[x for x in S['unconf'] if abs(x[1]-x[0])>=0.08]
n=len(v); print('unconf8+',n,'Brier labeled',round(sum((x[0]-x[2])**2 for x in v)/n,4),'swapped',round(sum((1-x[0]-x[2])**2 for x in v)/n,4),
 'model',round(sum((x[1]-x[2])**2 for x in v)/n,4),'market side hit',sum(((x[0]>.5)==x[2]) for x in v))
