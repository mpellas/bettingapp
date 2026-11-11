import pandas as pd, numpy as np, glob, os, re, json
NHL='/workspace/nhl-sog'
S=pd.read_pickle('board.pkl')
# attach lineup age from GATE files
gr=[]
for f in glob.glob(f'{NHL}/picks/*_D_*GATE.csv'):
    b=os.path.basename(f); m=re.match(r'(\d{8})_D_(\d{4})_GATE',b)
    if not m: continue
    g=pd.read_csv(f,usecols=lambda c: c in ['player','line','game','dfo_updated','captured_utc','team_dfo'])
    g['date']=m.group(1); g['pass']=m.group(2); gr.append(g)
GT=pd.concat(gr).drop_duplicates(['date','pass','player','line','game'])
GT['lineup_age_h']=(pd.to_datetime(GT.captured_utc,utc=True,errors='coerce')-pd.to_datetime(GT.dfo_updated,utc=True,errors='coerce')).dt.total_seconds()/3600
S=S.merge(GT[['date','pass','player','line','game','lineup_age_h','team_dfo']],on=['date','pass','player','line','game'],how='left')
# dedupe sides across passes (first chronological pass; 'base' last)
S['pord']=S['pass'].where(S['pass']!='base','9999')
S=S.sort_values(['date','pord']).drop_duplicates(['date','player','side','line','game'],keep='first')
def dec(a): a=float(a); return a/100 if a>0 else 100/abs(a)
def plf(hit,price): return np.nan if (pd.isna(price) or pd.isna(hit)) else (dec(price) if hit else -1.0)
S['edge']=S.p_model-S.p_novig
S['reason_cat']=S.status_reason.astype(str).str.replace(r'\s*\(.*','',regex=True).str.replace(r'model \+.*','CANDIDATE',regex=True)
S.to_pickle('board_dedup.pkl')
print(len(S), S.groupby('date').size().to_dict())
print(S.reason_cat.value_counts().to_string())
