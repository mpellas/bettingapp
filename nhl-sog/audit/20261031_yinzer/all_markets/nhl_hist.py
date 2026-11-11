import pandas as pd,glob,re,os
P='/workspace/nhl-sog/'
import csv
cd=pd.DataFrame([r[:4] for r in csv.reader(open(P+'card_decisions.csv'))][1:],columns=['list','player','side','decision'])
skipset={(str(r.list)[:8],r.player,r.side) for r in cd.itertuples() if r.decision=='skip'}
cards={(str(r.list)[:8],r.player,r.side) for r in cd.itertuples() if r.decision=='card'}
G={}
def grade(date,gid,nid):
  if date not in G:
    f=P+f'graded/{date}.csv'; G[date]=pd.read_csv(f) if os.path.exists(f) else None
  g=G[date]
  if g is None: return None
  m=g[(g.gameId==gid)&(g.nhl_id==nid)]
  return None if m.empty or pd.isna(m.actual.iloc[0]) else m.actual.iloc[0]
gate={}
for f in sorted(glob.glob(P+'picks/2026101*_GATE.csv')+glob.glob(P+'picks/2026102[0-5]*_GATE.csv')):
  d=os.path.basename(f)[:8]; gate.setdefault(d,[]).append(pd.read_csv(f))
rows=[]
rx=re.compile(r'Fliff check: (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]?\d+|n/a)[^,]*, Fliff at ([+-]?\d+)')
for f in sorted(glob.glob(P+'picks/2026101*_post*.txt')+glob.glob(P+'picks/2026102[0-5]*_post*.txt')):
  if 'prerule' in f: continue
  d=os.path.basename(f)[:8]
  for m in rx.finditer(open(f).read()):
    rows.append(dict(date=d,src=os.path.basename(f),player=m[1],side=m[2],line=float(m[3]),dk=m[4],shop=m[5],bucket='1_fliff_check'))
fl=pd.DataFrame(rows).drop_duplicates(['date','player','side','line'])
fl['reason']=['tester_skip' if (r.date,r.player,r.side) in skipset else 'not_reached_price' for r in fl.itertuples()]
fl=fl[[ (r.date,r.player,r.side) not in cards for r in fl.itertuples()]]
out=[]
for d,gs in gate.items():
  g=pd.concat(gs)
  for r in g.itertuples():
    base=dict(date=d,player=r.player,line=r.line,gameId=r.gameId,nhl_id=r.nhl_id)
    if isinstance(getattr(r,'slot_veto',None),str): out.append({**base,'side':r.slot_veto,'bucket':'3_veto','reason':'slot','dk':r.over if r.slot_veto=='OVER' else r.under})
    if getattr(r,'role_veto_over',False)==True: out.append({**base,'side':'OVER','bucket':'3_veto','reason':'role_demotion','dk':r.over})
    if getattr(r,'role_veto_under',False)==True: out.append({**base,'side':'UNDER','bucket':'3_veto','reason':'role_promotion','dk':r.under})
    if getattr(r,'lineup_veto_over',False)==True: out.append({**base,'side':'OVER','bucket':'2_stale','reason':'stale_lineup','dk':r.over})
ve=pd.DataFrame(out).drop_duplicates(['date','player','side','line','reason'])
# ids for fliff rows
allg=pd.concat([pd.concat(v) for v in gate.values()])
ids=allg.drop_duplicates(['player','gameId']).assign(date=lambda x:x.captured_utc.str[:10])
def lk(r):
  g=grade(r.date,0,0) or G.get(r.date)
  g=G.get(r.date)
  if g is None: return (None,None)
  m=g[(g.player==r.player)&(g.line==r.line)]
  return (m.gameId.iloc[0],m.nhl_id.iloc[0]) if len(m) else (None,None)
for r in fl.itertuples(): grade(r.date,0,0)
fl[['gameId','nhl_id']]=[lk(r) for r in fl.itertuples()]
a=pd.concat([fl,ve],ignore_index=True)
def pay(p):
  try:p=float(p)
  except:return None
  return p/100 if p>0 else 100/-p
res=[]
for r in a.itertuples():
  act=grade(r.date,r.gameId,r.nhl_id) if pd.notna(r.gameId) else None
  if act is None: res.append(('UNGRADED',None,None,None));continue
  w=act>r.line if r.side=='OVER' else act<r.line
  pd_,ps=pay(r.dk),pay(getattr(r,'shop',None))
  res.append(('W' if w else 'L',act,(pd_ if w else -1) if pd_ is not None else None,(ps if w else -1) if ps is not None else None))
a[['result','actual','u_dk','u_shop']]=res
a.to_csv('nhl_pre1026_skips.csv',index=False)
print(a.groupby(['bucket','reason','result']).size())
