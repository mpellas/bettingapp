import pandas as pd,glob,json,os
P4={'1','4','5','8'};G5={'151','12','15','17','37','9','18'}
def tl(t):
  c=t.get('conferenceId')
  return 'Power 4' if (c in P4 or t.get('id')=='87') else ('Group of 5' if c in G5 else 'FCS')
R={'Power 4':0,'Group of 5':1,'FCS':2};lev={}
for f in glob.glob('/workspace/cfb/captures/2026101*.json')+glob.glob('/workspace/cfb/captures/2026102*.json'):
  try: ev=json.load(open(f))['events']
  except Exception: continue
  for e in ev:
    ls=[tl(c['team']) for c in e['competitions'][0]['competitors']]
    lev[int(e['id'])]=max(ls,key=R.get)
d=pd.concat([pd.read_csv(f).assign(pass_=os.path.basename(f)[:13]) for f in sorted(glob.glob('/workspace/cfb/leans/*.csv'))])
d['level']=[l if isinstance(l,str) else lev.get(e,'?') for l,e in zip(d.level,d.event_id)]
d['gap_req']=d.level.map({'Power 4':3.0,'Group of 5':5.0,'FCS':5.0})
sc={}
for e in d.event_id.unique():
  c=json.load(open(f'espn/{e}.json'))['header']['competitions'][0]
  sc[e]=(c['status']['type']['name'],{x['homeAway']:float(x['score']) for x in c['competitors'] if x.get('score')})
def res(r,line):
  st,s=sc[r.event_id]
  if st!='STATUS_FINAL' or len(s)<2: return 'UNGRADED'
  if r.market=='total':
    t=s['home']+s['away'];v=(t-line) if r.side=='over' else (line-t)
  else:
    m=s[r.side]-s['away' if r.side=='home' else 'home'];v=m+line
  return 'W' if v>0 else ('P' if v==0 else 'L')
def u(rs,p):
  if rs=='W': return p/100 if p>0 else 100/-p
  return {'L':-1.0,'P':0.0}.get(rs)
dl=d.dk_line.where(d.dk_line.notna(),d.line)
d['res_fliff']=[res(r,r.line) for r in d.itertuples()];d['res_dk']=[res(r,l) for r,l in zip(d.itertuples(),dl)]
d['u_fliff']=[u(a,p) if pd.notna(p) else None for a,p in zip(d.res_fliff,d.fliff_price)]
d['u_dk']=[u(a,p) if pd.notna(p) else None for a,p in zip(d.res_dk,d.dk_price)]
d['short']=d.gap_req-d.edge_pts
d.to_csv('cfb_all_scored_sides.csv',index=False)
# unique: last pass per side
uq=d.sort_values('pass_').drop_duplicates(['event_id','market','side','line'],keep='last')
uq=d.sort_values('pass_').drop_duplicates(['event_id','market','side'],keep='last');uq.to_csv('cfb_unique_sides_lastpass.csv',index=False)
def summ(x):
  g=x[x.res_fliff.isin(['W','L','P'])]
  return f"{(g.res_fliff=='W').sum()}-{(g.res_fliff=='L').sum()}-{(g.res_fliff=='P').sum()} Fliff {g.u_fliff.sum():+.2f}u DK {g.u_dk.sum():+.2f}u (n={len(x)}, ungraded {len(x)-len(g)})"
print('ALL per-pass rows',summ(d));print('UNIQUE',summ(uq))
bins=[-99,0,1,2,3,5,99];lab=['qualified','0-1','1-2','2-3','3-5','>5']
uq['bucket']=pd.cut(uq.short,bins,labels=lab,right=True)
for b in lab: print('bucket',b,summ(uq[uq.bucket==b]))
for l in ['Power 4','Group of 5','FCS']:
  x=uq[uq.level==l];print(l,summ(x),'| edge max',x.edge_pts.max())
  for b in lab[1:]:
    y=x[x.bucket==b]
    if len(y): print('   ',b,summ(y))
for name,(a,b) in {'2/4':(2,4),'1/3':(1,3)}.items():
  thr=uq.level.map({'Power 4':a,'Group of 5':b,'FCS':b});print('threshold',name,summ(uq[uq.edge_pts>=thr]))
  thr=d.level.map({'Power 4':a,'Group of 5':b,'FCS':b});print('   per-pass',name,summ(d[d.edge_pts>=thr]))
print('edge dist',uq.edge_pts.describe().round(2).to_dict())
# coverage
cov=d.groupby(['pass_','level']).agg(games=('event_id','nunique'),sides=('label','count'),spreads=('market',lambda m:(m=='spread').sum()),totals=('market',lambda m:(m=='total').sum())).reset_index()
cov.to_csv('coverage_scored.csv',index=False);print(cov.to_string())
print('---- finer buckets (short = gap_req - edge)')
uq['b2']=pd.cut(uq.short,[3,4,5,6,7,8,9,99])
for (l,b),x in uq.groupby(['level','b2'],observed=True): print(l,b,summ(x))
# per game: better-edge side vs worse
uq['rk']=uq.groupby(['event_id','market']).edge_pts.rank(ascending=False,method='first')
print('better-priced side of each pair',summ(uq[uq.rk==1]))
# feed coverage
rows=[]
for f in sorted(glob.glob('/workspace/cfb/oddsapi_*.json')):
  p=os.path.basename(f)[8:21];D=json.load(open(f))
  for e in D:
    bk={b['key']:{m['key'] for m in b['markets']} for b in e.get('bookmakers',[])}
    rows.append(dict(pass_=p,game=e['away_team']+' @ '+e['home_team'],dk='draftkings' in bk,fliff='fliff' in bk,both=('draftkings' in bk and 'fliff' in bk),nbooks=len(bk)))
fd=pd.DataFrame(rows);print(fd.groupby('pass_')[['dk','fliff','both']].sum().assign(events=fd.groupby('pass_').size()).to_string())
fd.to_csv('coverage_feed.csv',index=False)
esp=[]
for f in sorted(glob.glob('/workspace/cfb/captures/2026101*_g8*.json')+glob.glob('/workspace/cfb/captures/2026102*_g8*.json')):
  for e in json.load(open(f))['events']:
    esp.append(dict(day=os.path.basename(f)[:8],id=int(e['id']),level=max([tl(c['team']) for c in e['competitions'][0]['competitors']],key=R.get)))
es=pd.DataFrame(esp).drop_duplicates(['day','id'])
sg=d.assign(day=d.pass_.str[:8]).drop_duplicates(['day','event_id'])
print(pd.concat([es.groupby(['day','level']).size().rename('espn_games'),sg.groupby(['day','level']).size().rename('priced_games')],axis=1).fillna(0).to_string())
