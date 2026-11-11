import json,glob,re,unicodedata,pandas as pd,numpy as np
B='/workspace/props-finder/analysis/nov01/box/'
box={};abmap={'WSH':'WAS','LAR':'LA'};played=set()
def norm(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower(); s=re.sub(r"[.'\-]"," ",s); s=re.sub(r"\b(jr|sr|ii|iii|iv)\b","",s); return re.sub(r"\s+"," ",s).strip()
for f in glob.glob(B+'*.json'):
    d=json.load(open(f))
    for t in d['boxscore'].get('players',[]):
        ab=abmap.get(t['team']['abbreviation'],t['team']['abbreviation']); played.add(ab)
        for s in t['statistics']:
            for a in s['athletes']:
                n=norm(a['athlete']['displayName']); st=dict(zip(s['keys'],a['stats'])); r=box.setdefault((ab,n),{})
                k={'passing':('pass_yds','passingYards'),'rushing':('rush_yds','rushingYards'),'receiving':('reception_yds','receivingYards')}.get(s['name'])
                if k: r[k[0]]=float(st[k[1]])
def find(team,p):
    p=norm(p)
    if (team,p) in box: return (team,p)
    c=[k for k in box if k[0]==team and (k[1].replace(' ','')==p.replace(' ','') or (k[1].split()[-1]==p.split()[-1] and k[1][0]==p[0]))]
    return c[0] if len(c)==1 else None
def grade(r):
    if r.team not in played: return 'ungraded','',0.0
    k=find(r.team,r.player)
    if k is None: return 'void(DNP/not found)','',0.0
    a=box[k].get(r.market,0.0)
    if a==r.line: return 'push',a,0.0
    w=(a>r.line)==(r.side=='Over'); pr=float(r.price)
    return ('win' if w else 'loss'),a,((100/abs(pr) if pr<0 else pr/100) if w else -1.0)
D=pd.read_csv('sides_deduped.csv')
g=D.apply(lambda r:pd.Series(grade(r),index=['result','actual','units']),axis=1); D=pd.concat([D,g],axis=1)
D['band']=(D.price<=110)&(D.price>=-150); D['healthy']=D.injury.isin(['not listed','Active'])
D['model_ok']=D.in_model&(D.model_p>=.55)
D.to_csv('sides_graded.csv',index=False)
def rec(x):
    w=(x.result=='win').sum();l=(x.result=='loss').sum();p=(x.result=='push').sum();u=(x.result.isin(['ungraded'])|x.result.str.startswith('void')).sum()
    return f"{w}-{l}-{p} ({u} ungraded/void), {x.units.sum():+.2f}u"
out=[]
H=D[D.healthy&D.fair_excl.notna()]
print('sides total',len(D),'with >=1 other book',D.fair_excl.notna().sum(),'healthy',len(H))
for thr in (2,0):
  for sharp in (True,False):
    for mod in (False,True):
      m=(H.ev_excl>=thr)&((H.n_sharp_other>=2) if sharp else True)&(H.model_ok if mod else True)
      x=H[m]; xb=x[x.band]
      print(f"EV>={thr} sharp2={sharp} model={mod}: {len(x)} pass, {len(xb)} in band | band record {rec(xb) if len(xb) else '-'}")
# all-books (builder method) sanity
print('builder-method EV>=2 any:',(H.ev_all>=2).sum())
# passers list: EV>=0, no sharp gate, in band
P=H[(H.ev_excl>=0)&H.band].sort_values('ev_excl',ascending=False)
P['gates']=np.where(P.ev_excl>=2,'EV2','EV0')+np.where(P.n_sharp_other>=2,'+2sharp','')+np.where(P.model_ok,'+model','')
cols=['game','team','player','market','line','side','book','price','fair_excl','ev_excl','n_other_books','sharps','model_p','gates','actual','result','units','pull']
P[cols].to_csv('passers_band_ev0.csv',index=False); print(P[cols].round(3).to_string())
print('\nper game (EV>=0 band passers):'); print(P.groupby('game').apply(rec).to_string())
R=D[D.model_ok&D.band&D.healthy]; R.to_csv('model55_band_sides.csv',index=False)
print('\nmodel 55%+ band reference:',len(R),rec(R)); print(R.groupby('game').apply(rec).to_string())
