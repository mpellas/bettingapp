"""Edge-8+ investigation (Tester2, 2026-11-03). READ-ONLY on /workspace/nhl-sog; writes only to this folder.
Usage: python3 edge8.py   (needs network once for NHL box scores; cached in box_cache/)"""
import pandas as pd, numpy as np, glob, json, os, re, requests
from datetime import datetime, timezone, timedelta
R='/workspace/nhl-sog'; OUT=os.path.dirname(os.path.abspath(__file__)); os.makedirs(f'{OUT}/box_cache',exist_ok=True)
PT=timezone(timedelta(hours=-7))  # PDT through Nov 1 2026, PST after
def pt(date): return timezone(timedelta(hours=-8)) if date>='20261101' else PT
def am(p): p=float(p); return 100/(100-p) if p<0 else 1+p/100   # decimal odds... returns dec
def dec(p): p=float(p); return 1+100/-p if p<0 else 1+p/100
def bucket(e): return '<5' if e<5 else '5-8' if e<8 else '8-12' if e<12 else '12+'
# ---- box scores (NHL.com stats API, same source as grade.py)
def box(date):
    f=f'{OUT}/box_cache/{date}.json'
    if not os.path.exists(f):
        iso=f'{date[:4]}-{date[4:6]}-{date[6:]}'
        r=requests.get('https://api.nhle.com/stats/rest/en/skater/summary',params={'isAggregate':'false','isGame':'true','limit':-1,'cayenneExp':f'gameDate="{iso}" and gameTypeId=2'},timeout=60).json()['data']
        json.dump(r,open(f,'w'))
    r=json.load(open(f)); return {(x['playerId'],x['gameId']):(x['shots'],x.get('timeOnIcePerGame')) for x in r}
# ---- closes: same rule as close.py (latest snapshot 0-30 min out) but NOT writing anything
def closes(date):
    d=f'{R}/captures/{date}'; C={}
    eids={os.path.basename(f).split('_')[0] for f in glob.glob(f'{d}/*_*.json')+glob.glob(f'{d}/archive/*.json')}
    for e in eids:
        fs=glob.glob(f'{d}/archive/{e}_*.json') or [f for f in glob.glob(f'{d}/{e}_*.json') if not f.endswith('_CLOSE.json')]
        S=sorted([json.load(open(f)) for f in fs],key=lambda s:s['captured_utc'])
        for s in S:
            if 0<=s.get('minutes_to_start',-1)<=30:
                for l in [l for l in (s.get('sog_lines') or []) if l.get('nhl_id')]: C.setdefault((str(e),int(l['nhl_id'])),{})[float(l['line'])]=dict(l,cap=s['captured_utc'],mts=s['minutes_to_start'])
    return C
# ---- posted sides
pat=re.compile(r'^(Fliff check|DK bet): (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]?\d+).*?model ([+-][\d.]+) pts')
posts=[]
for f in sorted(glob.glob(f'{R}/picks/*_post.txt')):
    m0=re.match(r'(\d{8})_(\d{4})_post',os.path.basename(f))
    if not m0: continue
    for ln in open(f):
        m=pat.match(ln.strip())
        if m: posts.append(dict(date=m0[1],list=f'{m0[1]}_{m0[2]}',hhmm=m0[2],kind=m[1],player=m[2],side=m[3],line=float(m[4]),dk_list=int(m[5]),edge_posted=float(m[6])))
P=pd.DataFrame(posts).drop_duplicates(['date','player','side','line'],keep='first')
fl=pd.concat([pd.read_csv(f,dtype=str) for f in glob.glob(f'{R}/fliff_prices/*.csv')])
rows=[]; CC={}; BB={}
for _,p in P.iterrows():
    d=p.date; Df=f'{R}/picks/{d}_D_{p.hhmm}.csv'; Gf=f'{R}/picks/{d}_D_{p.hhmm}_GATE.csv'
    if not os.path.exists(Df): Df=f'{R}/picks/{d}_D.csv'; Gf=f'{R}/picks/{d}_D_GATE.csv'
    D=pd.read_csv(Df); x=D[(D.player==p.player)&(D.line==p.line)]
    if x.empty: x=D[D.player==p.player]
    if x.empty: rows.append(dict(p,note='no D row')); continue
    x=x.iloc[0]; s=1 if p.side=='OVER' else -1
    g=pd.read_csv(Gf) if os.path.exists(Gf) else pd.DataFrame(); g=g[g.player==p.player].iloc[0] if len(g) and (g.player==p.player).any() else {}
    if d not in BB: BB[d]=box(d); CC[d]=closes(d)
    b=BB[d].get((int(x.nhl_id),int(x.gameId)))
    pm=x.p_model_over if s>0 else 1-x.p_model_over; nv=x.nv_over if s>0 else 1-x.nv_over
    pb=x.p_blend_over if s>0 else 1-x.p_blend_over
    lt=datetime.strptime(d+p.hhmm,'%Y%m%d%H%M').replace(tzinfo=pt(d))
    cap=datetime.fromisoformat(str(x.captured_utc))
    c=CC[d].get((str(x.event),int(x.nhl_id)),{})
    cl=c.get(p.line) ; cls=sorted(c)  # close lines available
    nvC=(cl['nv_over'] if s>0 else 1-cl['nv_over']) if cl else np.nan
    pC=(cl['over'] if s>0 else cl['under']) if cl else None
    alt=None if cl or not cls else min(cls,key=lambda L:abs(L-p.line))
    # line move against us: over & close line higher / under & close line lower
    lm='same' if cl else ('pulled/no close' if alt is None else ('against' if (alt-p.line)*s>0 else 'with'))
    f=fl[(fl.date==d)&(fl.player==p.player)&(fl.side==p.side)]
    fls=';'.join(sorted(set(f.fliff_status.dropna()))) if len(f) else ''
    fline=f.fliff_line.dropna().iloc[-1] if len(f) and f.fliff_line.notna().any() else ''
    off = '' if fline=='' else ('yes' if float(fline)!=p.line else 'no')
    nvo=x.over_open; nv_open=np.nan
    try:
        o,u=1/dec(x.over_open),1/dec(x.under_open); nv_open=(o/(o+u)) if s>0 else (u/(o+u))
    except Exception: pass
    act=b[0] if b else np.nan
    hit=np.nan if b is None else int(act>p.line) if s>0 else int(act<p.line)
    dfo=g.get('dfo_updated') if len(g) else None
    rows.append(dict(date=d,list=p.list,kind=p.kind,game=x.game,player=p.player,slot=x.slot,pos='D' if str(x.slot).startswith('D') else 'F',
      toi_r5=round(x.toi_r5,1),side=p.side,line=p.line,edge_pts=round((pm-nv)*100,1),edge_posted=p.edge_posted,bucket=bucket((pm-nv)*100),
      p_model=round(pm,4),p_blend=round(pb,4),nv_dk_list=round(nv,4),nv_dk_open=round(nv_open,4),dk_list=p.dk_list,
      move_open_to_list_pts=round((nv-nv_open)*100,1),
      close_line=p.line if cl else alt,close_price=pC,nv_close=round(nvC,4),clv_pts=round((nvC-nv)*100,1),line_move=lm,
      books_at_line=1+(off=='no'),fliff_status=fls,fliff_line=fline,off_market_vs_fliff=off,
      snap_age_min=round((lt-cap).total_seconds()/60),
      snap_min_to_start=None, dfo_age_h=round((lt-datetime.fromisoformat(str(dfo).replace('Z','+00:00'))).total_seconds()/3600,1) if isinstance(dfo,str) else np.nan,
      role_change=g.get('role_change') if len(g) else '', role_mismatch=g.get('role_mismatch') if len(g) else '',
      actual=act,hit=hit,units=np.nan if np.isnan(hit) else (dec(p.dk_list)-1 if hit else -1.0)))
T=pd.DataFrame(rows); T.to_csv(f'{OUT}/posted_sides.csv',index=False)
# ---- all model lean sides from final D files (bigger n, calibration)
A=[]
for f in sorted(glob.glob(f'{R}/picks/2026*_D.csv')):
    d=os.path.basename(f)[:8]
    if not ('20261011'<=d<='20261102'): continue
    D=pd.read_csv(f)
    if d not in BB: BB[d]=box(d); CC[d]=closes(d)
    for _,x in D.iterrows():
        b=BB[d].get((int(x.nhl_id),int(x.gameId)))
        if b is None: continue
        s=1 if x.p_model_over>x.nv_over else -1; pm=x.p_model_over if s>0 else 1-x.p_model_over; nv=x.nv_over if s>0 else 1-x.nv_over
        side='OVER' if s>0 else 'UNDER'; pr=x.over if s>0 else x.under
        cl=CC[d].get((str(x.event),int(x.nhl_id)),{}).get(float(x.line))
        nvC=(cl['nv_over'] if s>0 else 1-cl['nv_over']) if cl else np.nan
        hit=int(b[0]>x.line) if s>0 else int(b[0]<x.line)
        A.append(dict(date=d,game=x.game,player=x.player,pos='D' if str(x.slot).startswith('D') else 'F',toi_r5=x.toi_r5,side=side,line=x.line,
          edge_pts=(pm-nv)*100,bucket=bucket((pm-nv)*100),p_model=pm,nv=nv,price=pr,nv_close=nvC,clv_pts=(nvC-nv)*100,actual=b[0],hit=hit,units=dec(pr)-1 if hit else -1.0,side_method=x.side_method))
A=pd.DataFrame(A); A.to_csv(f'{OUT}/all_lean_sides.csv',index=False)
# ---- summaries
def summ(df,by):
    g=df.dropna(subset=['hit']).groupby(by,observed=True)
    return g.agg(n=('hit','size'),hits=('hit','sum'),hit_rate=('hit','mean'),units=('units','sum'),roi=('units','mean'),p_model=('p_model','mean'),
                 nv=('nv_dk_list' if 'nv_dk_list' in df else 'nv','mean'),clv_pts=('clv_pts','mean'),n_close=('clv_pts','count')).round(3)
order=['<5','5-8','8-12','12+']
for d_ in (T,A): d_['bucket']=pd.Categorical(d_.bucket,order,ordered=True); d_['big']=np.where(d_.edge_pts>=8,'8+','<8')
L=[]
def w(t,df): L.append(f'\n## {t}\n\n'+df.to_markdown())
w('Posted sides by bucket',summ(T,'bucket'))
for c in ['side','line','pos','line_move','off_market_vs_fliff','kind']: w(f'Posted sides: big x {c}',summ(T,['big',c]))
T['stale']=np.where(T.snap_age_min>60,'snap>60m','fresh'); w('Posted: big x snapshot age',summ(T,['big','stale']))
T['dfo12']=np.where(T.dfo_age_h>12,'dfo>12h',np.where(T.dfo_age_h.isna(),'n/a','<=12h')); w('Posted: big x DFO age',summ(T,['big','dfo12']))
T['clvsign']=np.where(T.clv_pts.isna(),'no close',np.where(T.clv_pts<0,'close moved against','close flat/with')); w('Posted: big x CLV sign',summ(T,['big','clvsign']))
T['lowtoi']=np.where(T.toi_r5<14,'toi<14','toi>=14'); w('Posted: big x TOI',summ(T,['big','lowtoi']))
T['rolech']=T.role_change.fillna('').astype(str).replace('', 'none'); w('Posted: big x role change',summ(T,['big','rolech']))
w('ALL lean sides by bucket (calibration)',summ(A,'bucket'))
for c in ['side','line','pos','side_method']: w(f'ALL lean: big x {c}',summ(A,['big',c]))
A['clvsign']=np.where(A.clv_pts.isna(),'no close',np.where(A.clv_pts<0,'against','flat/with')); w('ALL lean: big x CLV sign',summ(A,['big','clvsign']))
open(f'{OUT}/tables.md','w').write('\n'.join(L)); print('\n'.join(L))
