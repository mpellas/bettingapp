import pandas as pd, glob, os, re
NHL='/workspace/nhl-sog'
rows=[]
for f in sorted(glob.glob(f'{NHL}/sheets/*_picks.xlsx')):
    b=os.path.basename(f)
    m=re.match(r'(\d{8})_(?:D_(\d{4})_picks|D_picks|BOSANA_D_picks_(\d{4}))',b)
    d=m.group(1); p=m.group(2) or m.group(3) or 'base'
    df=pd.read_excel(f,sheet_name='Picks'); df['date']=d; df['pass']=p; df['sheet']=b
    rows.append(df)
S=pd.concat(rows,ignore_index=True)
G=[]
for d in S.date.unique():
    fn=f'{NHL}/graded_overlay/{d}.csv' if os.path.exists(f'{NHL}/graded_overlay/{d}.csv') else None
    if fn is None: continue
    g=pd.read_csv(fn); g['date']=d
    pin=pd.read_csv(f'{NHL}/graded/{d}.csv')[['player','line','game','status']].rename(columns={'status':'status_pinned'})
    g=g.merge(pin,on=['player','line','game'],how='left')
    g=g.rename(columns={'status':'gstatus'}); G.append(g[['date','player','line','game','actual','gstatus','status_pinned']])
G=pd.concat(G).drop_duplicates(['date','player','line','game'])
S=S.merge(G,on=['date','player','line','game'],how='left')
def dec(a):
    a=float(a); return a/100 if a>0 else 100/abs(a)
def pl(hit,price):
    if pd.isna(price) or pd.isna(hit): return float('nan')
    return dec(price) if hit else -1.0
S['graded']=S.gstatus.eq('OK')
S['hit']=pd.NA
ok=S.graded
S.loc[ok,'hit']=[(a>l) if s=='OVER' else (a<l) for a,l,s in zip(S.loc[ok,'actual'],S.loc[ok,'line'],S.loc[ok,'side'])]
S['pl_dk']=[pl(h,p) if g else float('nan') for h,p,g in zip(S.hit,S.dk_price,S.graded)]
S.to_pickle('board.pkl')
print(S.shape, S.groupby('date').size().to_dict())
print(S.status_x.value_counts() if 'status_x' in S else S.columns[S.columns.str.startswith('status')].tolist())
