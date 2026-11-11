import pandas as pd
T={6:pd.read_parquet('/workspace/nfl-props/data/track/2026_wk06.parquet'),7:pd.read_parquet('/workspace/nfl-props/data/track/2026_wk07.parquet')}
out=[]
for w,f in [(6,'oct18/nfl_wk6_oct18_all_sides.csv'),(7,'oct25/nfl_wk7_oct25_all_sides.csv')]:
  d=pd.read_csv('/workspace/props-finder/analysis/'+f);s=d[d.status=='skip'].copy();t=T[w]
  act=t.dropna(subset=['actual']).groupby(['player_name','market']).actual.first()
  pw=pd.read_csv('pw.csv');pw=pw[pw.week==w];M={'reception_yds':'receiving_yards','rush_yds':'rushing_yards','pass_yds':'passing_yards'}
  nv={(r.player_display_name,m):getattr(r,c) for r in pw.itertuples() for m,c in M.items()}
  s['week']=w;s['src']=['track' if pd.notna(act.get((r.player,r.market))) else ('nflverse' if (r.player,r.market) in nv else 'none') for r in s.itertuples()]
  s['actual']=[act.get((r.player,r.market)) if pd.notna(act.get((r.player,r.market))) else nv.get((r.player,r.market)) for r in s.itertuples()]
  # cross-check track vs nflverse
  for r in s.itertuples():
    a1=act.get((r.player,r.market));a2=nv.get((r.player,r.market))
    if pd.notna(a1) and a2 is not None and a1!=a2: print('MISMATCH',w,r.player,r.market,a1,a2)
  s['result']=['UNGRADED' if pd.isna(a) else ('W' if (a>r.line if r.side=='Over' else a<r.line) else ('P' if a==r.line else 'L')) for r,a in zip(s.itertuples(),s.actual)]
  def u(r):
    if r.result!='W': return -1.0 if r.result=='L' else None
    p=r.price if pd.notna(r.price) else -110
    return p/100 if p>0 else 100/-p
  s['units']=s.apply(u,axis=1);s['model_side']=s.ev_pct>0;out.append(s)
a=pd.concat(out);a[['week','player','market','line','side','book','price','fair_prob','ev_pct','reason','src','actual','result','units','model_side']].to_csv('nfl_injury_skips.csv',index=False)
for k,x in [('all',a),('ev>0',a[a.model_side])]:
  g=x[x.result!='UNGRADED'];print(k,len(x),'graded',len(g),'hit',(g.result=='W').sum(),'units',round(g.units.sum(),2),'| over',((g.side=='Over')&(g.result=='W')).sum(),'/',(g.side=='Over').sum(),' under',((g.side=='Under')&(g.result=='W')).sum(),'/',(g.side=='Under').sum())
print(a[a.model_side][['week','player','market','line','side','book','price','ev_pct','actual','result']].to_string())
print(a[a.result=='UNGRADED'].player.unique())
