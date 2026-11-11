# Past-season feature backtest. Read-only on live code; train 2021-24 (ES on 2024-25), test 2025-26. 2026-27 excluded.
import sys,os,json,glob; sys.path.insert(0,'/workspace/nhl-sog'); os.chdir('/workspace/nhl-sog')
from features import load,feats
import pandas as pd,numpy as np,lightgbm as lgb
from scipy import stats,optimize
OUT='/workspace/nhl-feature-tests-20261103'
df=load(); df=df[df.season<=2025].reset_index(drop=True)   # hold out 2026-27
df=feats(df)
g=df.groupby('playerId',sort=False)
cum=lambda s:s.shift(1).fillna(0).groupby(level=0).cumsum() if False else None
# overall prior rate
df['_one']=1
def prior_cum(keys,col):
    return df.groupby(keys,sort=False)[col].transform(lambda s:s.shift(1).fillna(0).cumsum())
df['n_all']=prior_cum(['playerId'],'_one'); df['s_all']=prior_cum(['playerId'],'shots')
rate_all=(df.s_all+2.0*3)/(df.n_all+3)   # mild prior
# (a) venue split, shrink K=25 games toward player's overall prior rate
K=25; df['n_v']=prior_cum(['playerId','home'],'_one'); df['s_v']=prior_cum(['playerId','home'],'shots')
df['venue_ratio']=((df.s_v+K*rate_all)/(df.n_v+K))/rate_all
# (b) vs opponent, heavy shrink K=40
K2=40; df['n_o']=prior_cum(['playerId','opponentTeamAbbrev'],'_one'); df['s_o']=prior_cum(['playerId','opponentTeamAbbrev'],'shots')
df['vsopp_ratio']=((df.s_o+K2*rate_all)/(df.n_o+K2))/rate_all
# (c) opponent dressed D from opponent's previous game (NHL.com logs)
D=df[df.D==1][['gameId','date','teamAbbrev','playerId','toi','season']]
tg=D[['gameId','date','teamAbbrev']].drop_duplicates().sort_values(['teamAbbrev','date'])
tg['prev_gid']=tg.groupby('teamAbbrev').gameId.shift(1)
# NHL-only proxy: how many of the team's top-4 D (by TOI over prior 20 team games) dressed last game
D=D.sort_values('date'); D['toi_r20']=D.groupby('playerId').toi.transform(lambda s:s.shift(1).rolling(20,min_periods=3).mean())
prevD=D.rename(columns={'gameId':'prev_gid'})
# MoneyPuck prior-season on-ice 5v5 shots-on-goal against per 60 for each D (season totals, prior season only -> leak free)
mp=[]
for f in glob.glob(OUT+'/mp/skaters_*.csv'):
    s=pd.read_csv(f); s=s[(s.situation=='5on5')&(s.position=='D')]
    s['sa60']=s.OnIce_A_shotsOnGoal/(s.icetime/3600); s['useason']=s.season+1   # applies to NEXT season
    mp.append(s[['playerId','useason','sa60','icetime']])
mp=pd.concat(mp).groupby(['playerId','useason'],as_index=False).apply(lambda x:pd.Series({'sa60':np.average(x.sa60,weights=x.icetime),'mp_ice':x.icetime.sum()}))
lg=mp.sa60.median()
prevD=prevD.merge(mp,left_on=['playerId','season'],right_on=['playerId','useason'],how='left')
# shrink each D's sa60 toward league median by ice time (K=20000 s of 5v5)
prevD['sa60s']=(prevD.sa60.fillna(lg)*prevD.mp_ice.fillna(0)+lg*20000)/(prevD.mp_ice.fillna(0)+20000)
agg=prevD.groupby(['prev_gid','teamAbbrev']).apply(lambda x:pd.Series({'oppD_mp_sa60':np.average(x.sa60s,weights=x.toi),
     'oppD_toi_r20_sum':x.toi_r20.fillna(0).sum()})).reset_index()
tg=tg.merge(agg,on=['prev_gid','teamAbbrev'],how='left')
tg=tg.rename(columns={'teamAbbrev':'opponentTeamAbbrev'})[['gameId','opponentTeamAbbrev','oppD_mp_sa60','oppD_toi_r20_sum']]
df=df.merge(tg,on=['gameId','opponentTeamAbbrev'],how='left')
base=json.load(open('models/model_c3ab760178.json'))['features']
G={'base':[],'a_venue':['venue_ratio'],'b_vsopp':['vsopp_ratio'],'c_oppD_nhl':['oppD_toi_r20_sum'],'c_oppD_mp':['oppD_mp_sa60','oppD_toi_r20_sum']}
df=df[df.n_prior>=5]; tr2=df[df.season<2024]; vl=df[df.season==2024]; tr=df[df.season<2025]; te=df[df.season==2025].copy()
P=dict(objective='poisson',learning_rate=0.03,num_leaves=15,min_data_in_leaf=200,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,verbose=-1,seed=1)
nll=lambda k,y,mu:-stats.nbinom.logpmf(y,k,k/(k+mu)).mean()
for name,add in G.items():
    F=base+add; m=lgb.train(P,lgb.Dataset(tr2[F],tr2.shots),3000,valid_sets=[lgb.Dataset(vl[F],vl.shots)],callbacks=[lgb.early_stopping(100,verbose=False)])
    m=lgb.train(P,lgb.Dataset(tr[F],tr.shots),m.best_iteration); mutr=m.predict(tr[F])
    k=optimize.minimize_scalar(lambda k:nll(k,tr.shots.values,mutr),bounds=(.5,200),method='bounded').x
    te['mu_'+name]=m.predict(te[F]); te['k_'+name]=k
    print(name,'iters',m.best_iteration if m.best_iteration else '', 'k',round(k,1),flush=True)
te[['gameId','playerId','skaterFullName','date','shots','D']+[c for c in te.columns if c.startswith(('mu_','k_'))]+['venue_ratio','vsopp_ratio','oppD_mp_sa60','oppD_toi_r20_sum','n_v','n_o']].to_pickle(OUT+'/preds_2025_26.pkl')
print(len(te),'test rows; coverage mp',te.oppD_mp_sa60.notna().mean())
