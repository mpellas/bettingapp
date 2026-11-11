# Independent rebuild of Tester1's att and total from raw nhl-sog logs / graded files / ESPN.
import glob, json, random, urllib.request, time, numpy as np, pandas as pd
NHL='/workspace/nhl-sog'; T1='/workspace/tester1-review/shot_attempts_20261109'
L=pd.concat([pd.read_pickle(f) for f in sorted(glob.glob(f'{NHL}/data/s20*.pkl'))]).drop_duplicates(['playerId','gameId'])
L=L[L.timeOnIcePerGame.fillna(0)>0].sort_values(['playerId','gameDate','gameId'])
by={k:v for k,v in L.groupby('playerId')}
def att_over(pid,iso):
    g=by.get(int(pid))
    if g is None: return None
    g=g[g.gameDate<iso]; r=g.tail(10); b=g.iloc[max(0,len(g)-92):max(0,len(g)-10)]
    ar,ab=r.totalShotAttempts.sum(),b.totalShotAttempts.sum(); hr,hb=r.timeOnIcePerGame.sum(),b.timeOnIcePerGame.sum()
    if len(r)<10 or len(b)<30 or ar<15 or hr<=0 or hb<=0 or ab<=0: return None
    a=(ar/hr)/(ab/hb)-1; acc_r=r.shots.sum()/ar; acc_b=b.shots.sum()/ab
    bb=acc_b/acc_r-1 if acc_r>0 else np.nan
    s=lambda x: 0 if not np.isfinite(x) else (1 if x>=0.1 else (-1 if x<=-0.1 else 0))
    return int(np.sign(s(a)+s(bb)))
T=pd.read_csv(f'{T1}/cache/espn_totals.csv',dtype={'event':str}); tot=dict(zip(T.event,T.open_total))
S=pd.read_csv(f'{T1}/out/backtest_live_sides.csv')
rows=[]
for f in sorted(glob.glob(f'{NHL}/graded/2026*.csv')):
    d=f.split('/')[-1][:8]; G=pd.read_csv(f,dtype={'event':str}); iso=f'{d[:4]}-{d[4:6]}-{d[6:]}'
    for _,r in G.iterrows():
        v=att_over(r.nhl_id,iso); t=tot.get(str(r.event),np.nan)
        tv=np.nan if pd.isna(t) else (1 if t>=6.5 else (-1 if t<=5.5 else 0))
        for side,price in (('over',r.over),('under',r.under)):
            sg=lambda x: 'n/a' if x is None or (isinstance(x,float) and np.isnan(x)) else {1:'+',0:'0',-1:'-'}[int(x) if side=='over' else -int(x)]
            rows.append(dict(date=int(d),nhl_id=r.nhl_id,line=r.line,side=side,status=r.status,actual=r.actual,price=price,my_att=sg(v),my_total=sg(tv)))
M=pd.DataFrame(rows)
print('my rows',len(M),'their rows',len(S)); print('statuses',M.status.value_counts().to_dict())
J=S.merge(M,on=['date','nhl_id','line','side'],how='left')
print('unmatched',J.my_att.isna().sum())
ta=J.sig_x_att.fillna('n/a').where(~J.att_na,'n/a'); print('att mismatches',(ta!=J.my_att).sum(),'of',len(J))
print(pd.crosstab(ta,J.my_att))
print('total mismatches',(J.sig_x_total.astype(str)!=J.my_total).sum())
# group hits from my own signs
J['w']=(J.win==True).astype(int)
for k in ('my_att','my_total'):
    for v in ('+','-'):
        s=J[J[k]==v]; print(k,v,len(s),round(s.w.mean(),3))
# spot-check 8 events against ESPN live
random.seed(1); ev=random.sample(sorted(T.event.unique()),8); bad=0
for e in ev:
    u=f'https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/{e}/competitions/{e}/odds'
    try:
        d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15))
        it=[i for i in d.get('items',[]) if str(i.get('provider',{}).get('id'))=='100']
        o=it[0]['open']['total']['american'] if it and it[0].get('open',{}).get('total') else None
        print(e,'espn open',o,'cache',tot.get(e)); bad+= (o is not None and float(o)!=tot.get(e))
    except Exception as x: print(e,'fetch err',x)
    time.sleep(0.5)
print('espn spot-check mismatches',bad)
