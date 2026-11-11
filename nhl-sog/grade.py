"""Grade picks/<date>_D.csv vs NHL box scores; z-CLV D->C from C captures. Usage: python3 grade.py YYYYMMDD
C = per-line close from close.py (latest price 0-30 min out; pulled lines never backfilled).
VOID: no C for line (VOID_pulled_before_close if pulled), player DNP (no box row). CLV: market P(side) at C, re-expressed at the D line via NB(mu_C,k) fitted to C no-vig; z = (logit pC - logit pD)."""
import pandas as pd,numpy as np,requests,json,glob,sys,os
from scipy import stats,optimize
date=sys.argv[1]; iso=f'{date[:4]}-{date[4:6]}-{date[6:]}'
P=pd.read_csv(f'picks/{date}_D.csv'); k=json.load(open(f"models/model_{P.model_hash.iloc[0]}.json"))['k']
r=requests.get('https://api.nhle.com/stats/rest/en/skater/summary',params={'isAggregate':'false','isGame':'true','limit':-1,'cayenneExp':f'gameDate="{iso}" and gameTypeId=2'},timeout=60).json()['data']
box={(x['playerId'],x['gameId']):x['shots'] for x in r}
GAMES_WITH_BOX={x['gameId'] for x in r}  # a game with no box rows yet is PENDING, not DNP
import close
C={}; PULLED=set()
for dd in glob.glob('captures/*/'):
    for e,cr in close.build_day(os.path.basename(dd.rstrip('/'))).items():
        if not cr: continue
        for l in cr['closed']:
            if l['market']=='sog': C.setdefault((cr['event'],l['nhl_id']),[]).append(l)
        for l in cr['pulled_before_close']:
            if l['market']=='sog': PULLED.add((cr['event'],l['nhl_id'],l['line']))
def mu_from(nv,line): return optimize.brentq(lambda mu:(1-stats.nbinom.cdf(np.floor(line),k,k/(k+mu)))-nv,0.01,20)
lg=lambda p:np.log(p/(1-p))
out=[]
for _,x in P.iterrows():
    y=box.get((x.nhl_id,x.gameId)); c=C.get((str(x.event),x.nhl_id)) or C.get((x.event,x.nhl_id))
    row=dict(x); row['actual']=y; row['status']='OK'
    if y is None: row['status']='VOID_dnp' if x.gameId in GAMES_WITH_BOX else 'PENDING_no_box'
    if c:
        cl=min(c,key=lambda l:abs(l['line']-x.line)); pC=cl['nv_over'] if cl['line']==x.line else 1-stats.nbinom.cdf(np.floor(x.line),k,k/(k+mu_from(cl['nv_over'],cl['line'])))
        row['nv_over_C']=pC; row['line_C']=cl['line']
    elif row['status'] in ('OK',): row['status']='VOID_pulled_before_close' if (str(x.event),x.nhl_id,float(x.line)) in PULLED else 'VOID_noC'
    if x.pick in ('OVER','UNDER') and y is not None:
        row['hit']=int(y>x.line) if x.pick=='OVER' else int(y<x.line)
        dec=(1+100/-x[x.pick.lower()]) if x[x.pick.lower()]<0 else 1+x[x.pick.lower()]/100
        row['units']=dec-1 if row['hit'] else -1
    if 'nv_over_C' in row and x.pick in ('OVER','UNDER'):
        pD,pC=x.nv_over,row['nv_over_C']; s=1 if x.pick=='OVER' else -1; row['zclv']=s*(lg(np.clip(pC,1e-3,1-1e-3))-lg(np.clip(pD,1e-3,1-1e-3)))
    out.append(row)
G=pd.DataFrame(out); G.to_csv(f'graded/{date}.csv',index=False)
pk=G[G.pick.isin(['OVER','UNDER'])&(G.status=='OK')]
print(f'{date}: {len(G)} lines, {len(pk)} graded picks; hits {pk.hit.sum() if len(pk) else 0}/{len(pk)}; units {pk.units.sum() if len(pk) else 0:.2f}; mean zCLV {pk.zclv.mean() if len(pk) else float("nan"):.3f}; voids {G.status.value_counts().to_dict()}')
