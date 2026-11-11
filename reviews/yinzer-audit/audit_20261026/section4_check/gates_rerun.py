import re,glob,math,sys,os
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from scipy.stats import poisson
sys.path.insert(0,'/workspace/nhl-sog'); os.chdir('/workspace/nhl-sog')
import game_starts
PT=ZoneInfo('America/Los_Angeles')
pat=re.compile(r'^(DK bet|Fliff check): (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]\d+), Fliff at ([+-]\d+) or better\) - model \+?(-?[\d.]+) pts')
def dec(a): a=float(a); return 1+a/100 if a>0 else 1+100/-a
def shop(p):
    d=1/p
    return math.ceil(100*(d-1)-1e-9) if d>=2 else -math.floor(100/(d-1)+1e-9)
rows=[]
for f in sorted(glob.glob('picks/2026101[7-9]_*_post.txt')+['picks/20261017_post.txt']+glob.glob('picks/2026102[0-5]_*_post.txt')):
    if 'prerule' in f: continue
    b=os.path.basename(f); d,hm=b.split('_')[:2]
    if hm=='post.txt': hm='morning'
    txt=open(f).read().splitlines()
    for i,l in enumerate(txt):
        m=pat.match(l)
        if not m: continue
        ev=' '.join(x for x in txt[i+1:i+4] if x.startswith(' '))
        ag=re.search(r'agrees (\d) of 7',ev)
        mv=re.search(r'no-vig moved ([\d.]+) pts (toward|away)',ev)
        rows.append(dict(date=d,hhmm=hm,player=m[2],side=m[3].lower(),line=float(m[4]),dk=int(m[5]),shop_posted=int(m[6]),model_pts_posted=float(m[7]),
            agrees=int(ag[1]) if ag else None,move=float(mv[1]) if mv else None,move_dir=mv[2] if mv else None,toi_txt='TOI last 5' in ev, evidence=ev[:300]))
P=pd.DataFrame(rows)
out=[]
for r in P.itertuples():
    g=None
    for gf in ([f'picks/{r.date}_D_GATE.csv'] if r.hhmm=='morning' else [f'picks/{r.date}_D_{r.hhmm}_GATE.csv']):
        if os.path.exists(gf):
            G=pd.read_csv(gf); x=G[(G.player==r.player)&(G.line==r.line)]
            if len(x): g=x.iloc[-1]; src=gf; break
    o=r._asdict()
    if g is None: o['gate_src']='MISSING'; out.append(o); continue
    o['gate_src']=src
    nv=g.nv_over if r.side=='over' else 1-g.nv_over
    pm=g.p_model_over if r.side=='over' else 1-g.p_model_over
    pb=g.p_blend_over if r.side=='over' else 1-g.p_blend_over
    o['model_pts']=round(100*(pm-nv),1); o['model_pts_ok']=abs(o['model_pts']-r.model_pts_posted)<=0.1
    o['shop_calc']=shop(pb); o['shop_ok']=o['shop_calc']==r.shop_posted
    st=game_starts.starts_for([int(g.gameId)]).get(int(g.gameId))
    pt=pd.Timestamp(g.captured_utc).to_pydatetime() if r.hhmm=='morning' else datetime.strptime(r.date+r.hhmm,'%Y%m%d%H%M').replace(tzinfo=PT)
    o['pass_time_pt']=pt.astimezone(PT).strftime('%H:%M')
    o['puck_pt']=st.astimezone(PT).strftime('%m-%d %H:%M') if st else None
    mins=(st-pt).total_seconds()/60 if st else None
    o['mins_to_drop']=round(mins) if mins is not None else None
    o['window_ok']=mins is not None and 150<=mins<=210+1e-9
    o['pre_noon']=st is not None and game_starts.is_pre_noon(st)
    floor_on=r.hhmm!='morning' and (r.date+r.hhmm)>='202610201513'
    o['floor_applies']=floor_on; o['floor_ok']=(not floor_on) or (pm-nv)>=0.05
    rmu=g.sog60_r10*g.toi_r5/60; pov=1-poisson.cdf(math.floor(r.line),rmu)
    pr=pov if r.side=='over' else 1-pov
    o['recent_pts']=round(100*(pr-nv),1); o['recent_ok']=pr>nv
    if r.side=='under':
        rv=g.get('role_veto_under'); o['role_veto_under']=rv; o['role_ok']=str(rv).lower()!='true'
    else:
        rv=g.get('role_veto_over'); o['role_veto_over']=rv; o['role_ok']=str(rv).lower()!='true'
    o['shop_ok_flag']=g.get('shop_ok')
    o['agree_le2']=r.agrees is not None and r.agrees<=2
    o['agrees_ex_huge']=(r.agrees-1) if (r.move_dir=='toward' and r.move and r.move>=5) else r.agrees
    o['huge_move_toward']=r.move_dir=='toward' and r.move is not None and r.move>=5
    out.append(o)
O=pd.DataFrame(out); O.to_csv('/workspace/yinzer-audit/audit_20261026/section4_check/gates_yinzer.csv',index=False)
print(len(O),'sides',O.date.value_counts().sort_index().to_dict(), 'passes',O[['date','hhmm']].drop_duplicates().shape[0])
for c in ['model_pts_ok','shop_ok','window_ok','floor_ok','recent_ok','role_ok']:
    bad=O[O[c]!=True]; print(c,'fail',len(bad)); 
    if len(bad): print(bad[['date','hhmm','player','side','line','model_pts','model_pts_posted','shop_calc','shop_posted','mins_to_drop','recent_pts','gate_src']].to_string())
print('pre_noon');print(O[O.pre_noon][['date','hhmm','player','side','line','puck_pt']].to_string())
print('agree<=2');print(O[O.agree_le2][['date','hhmm','player','side','line','agrees']].to_string())
print('huge');print(O[O.huge_move_toward][['date','hhmm','player','side','move','agrees']].to_string())
print('agree<=2 excluding huge moves');print(O[O.agrees_ex_huge<=2][['date','hhmm','player','side','agrees','agrees_ex_huge']].to_string())
print('TOI vote text sides', O.toi_txt.sum())
