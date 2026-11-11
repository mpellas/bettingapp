import sys; sys.path.insert(0,'/workspace/nhl-sog'); import os; os.chdir('/workspace/nhl-sog')
from features import load,feats
import pandas as pd,numpy as np,lightgbm as lgb,json
from scipy import stats,optimize
df=feats(load()); df['sh']=df.shTimeOnIce.fillna(0)/60
g=df.groupby('playerId',sort=False)
df['shtoi_r10']=g.sh.transform(lambda s:s.shift(1).rolling(10,min_periods=1).mean())
def team_roll(keycols,val,grp,name,w=20):
    t=df.groupby(keycols+['date'],as_index=False)[val].sum().sort_values('date')
    t[name]=t.groupby(grp)[val].transform(lambda s:s.shift(1).rolling(w,min_periods=3).mean()); return t.drop(columns=[val,'date'])
# A: opp shots allowed by position (F/D)
A=team_roll(['gameId','opponentTeamAbbrev','D'],'shots',['opponentTeamAbbrev','D'],'opp_sa_pos_r20'); df=df.merge(A,on=['gameId','opponentTeamAbbrev','D'],how='left')
# C: opp attempts allowed and shot-through ratio
C=team_roll(['gameId','opponentTeamAbbrev'],'att',['opponentTeamAbbrev'],'opp_aa_r20'); df=df.merge(C,on=['gameId','opponentTeamAbbrev'],how='left')
df['opp_thru']=df.opp_sa_r20/df.opp_aa_r20
# D: pace — team attempts for, opponent attempts for (opp offense -> possession)
D1=team_roll(['gameId','teamAbbrev'],'att',['teamAbbrev'],'team_af_r20'); df=df.merge(D1,on=['gameId','teamAbbrev'],how='left')
o=D1.rename(columns={'teamAbbrev':'opponentTeamAbbrev','team_af_r20':'opp_af_r20'}); df=df.merge(o,on=['gameId','opponentTeamAbbrev'],how='left')
# B: role share — player's toi_r5 share of team-game TOI, team pp time
df['tm_toi']=df.groupby(['gameId','teamAbbrev']).toi.transform('sum'); df['pp_share']=df.pptoi/df.groupby(['gameId','teamAbbrev']).pptoi.transform('max').replace(0,np.nan)
df['pp_share_r5']=g.pp_share.transform(lambda s:s.shift(1).rolling(5,min_periods=1).mean()) if False else df.groupby('playerId',sort=False).pp_share.transform(lambda s:s.shift(1).rolling(5,min_periods=1).mean())
# E: opp rest/b2b
r=df.groupby(['gameId','teamAbbrev'],as_index=False).b2b.max().rename(columns={'teamAbbrev':'opponentTeamAbbrev','b2b':'opp_b2b'}); df=df.merge(r,on=['gameId','opponentTeamAbbrev'],how='left')
base=json.load(open('models/model_c3ab760178.json'))['features']
G={'base':[],'A_opp_by_pos':['opp_sa_pos_r20'],'C_opp_attempts_thru':['opp_aa_r20','opp_thru'],'D_pace':['team_af_r20','opp_af_r20'],
   'B_pp_share_pk':['pp_share_r5','shtoi_r10'],'E_opp_b2b':['opp_b2b'],'ALL':['opp_sa_pos_r20','opp_aa_r20','opp_thru','team_af_r20','opp_af_r20','pp_share_r5','shtoi_r10','opp_b2b']}
df=df[df.n_prior>=5]; tr2=df[df.season<2024]; vl=df[df.season==2024]; tr=df[df.season<2025]; te=df[df.season==2025]
P=dict(objective='poisson',learning_rate=0.03,num_leaves=15,min_data_in_leaf=200,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,verbose=-1,seed=1)
nll=lambda k,y,mu:-stats.nbinom.logpmf(y,k,k/(k+mu)).mean()
y=te.shots.values; out=[]; rng=np.random.default_rng(0); gid=te.gameId.values; preds={}
for name,add in G.items():
    F=base+add; m=lgb.train(P,lgb.Dataset(tr2[F],tr2.shots),2000,valid_sets=[lgb.Dataset(vl[F],vl.shots)],callbacks=[lgb.early_stopping(100,verbose=False)])
    m=lgb.train(P,lgb.Dataset(tr[F],tr.shots),m.best_iteration); mutr=m.predict(tr[F])
    k=optimize.minimize_scalar(lambda k:nll(k,tr.shots.values,mutr),bounds=(.5,200),method='bounded').x; mu=m.predict(te[F])
    ll=-stats.nbinom.logpmf(y,k,k/(k+mu)); preds[name]=ll
    p=1-stats.nbinom.cdf(2,k,k/(k+mu)); o=(y>2.5)
    out.append(dict(variant=name,nll=ll.mean(),mae=np.abs(mu-y).mean(),brier_2p5=((p-o)**2).mean(),gain=dict(zip(m.feature_name(),m.feature_importance('gain'))).get(add[0],0) if add else 0))
R=pd.DataFrame(out); b=preds['base']
ug,inv=np.unique(gid,return_inverse=True)
for i,n in enumerate(R.variant):
    dlt=np.bincount(inv,preds[n]-b); s=[dlt[rng.integers(0,len(ug),len(ug))].sum()/len(y) for _ in range(1000)]
    R.loc[i,'d_nll_x1000']=(preds[n]-b).mean()*1000; R.loc[i,'ci_lo']=np.percentile(s,2.5)*1000; R.loc[i,'ci_hi']=np.percentile(s,97.5)*1000
print(len(te),'test rows'); print(R.round(5).to_string(index=False)); R.to_csv('/workspace/feature-audit-nhl-20261102/ablation_2025_26.csv',index=False)
