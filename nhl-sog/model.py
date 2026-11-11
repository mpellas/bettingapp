from features import *
from scipy import stats,optimize
df=load()
df=feats(df)
F=[c for c in df if '_r' in c or c in ['shots_car','n_prior','rest','b2b','home','D']]
# leakage test: changing a game's own outcomes must not change that game's features
cut=df.date.sort_values().iloc[len(df)//2]; t=df.copy(); fut=t.date>=cut; t.loc[fut,['shots','toi','pptoi','att']]=999  # corrupt cutoff day and everything after
t=feats(t.drop(columns=[c for c in F if c not in ('home','D')])); key=['playerId','gameId']
a=df[df.date==cut].set_index(key)[F].sort_index(); b=t[t.date==cut].set_index(key)[F].sort_index()
bad=[c for c in F if not np.allclose(a[c].fillna(-1),b[c].fillna(-1))]; assert not bad,('LEAKAGE',bad); print('leakage test passed')
df=df[df.n_prior>=5]
def nb_p(mu,k): return k/(k+mu)
def nll(k,y,mu): return -stats.nbinom.logpmf(y,k,nb_p(mu,k)).mean()
def crps(y,mu,k,K=25):
    x=np.arange(K)[None,:]; F=stats.nbinom.cdf(x,k,nb_p(mu[:,None],k)); return (((F-(x>=y[:,None]))**2).sum(1)).mean()
res=[];cal=[]
P=dict(objective='poisson',learning_rate=0.03,num_leaves=15,min_data_in_leaf=200,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,verbose=-1)
for s in sorted(df.season.unique())[2:]:
    tr,te=df[df.season<s],df[df.season==s]
    if len(te)==0: continue
    vl=tr[tr.season==s-1]; tr2=tr[tr.season<s-1]
    m=lgb.train(P,lgb.Dataset(tr2[F],tr2.shots),2000,valid_sets=[lgb.Dataset(vl[F],vl.shots)],callbacks=[lgb.early_stopping(100,verbose=False)])
    m=lgb.train(P,lgb.Dataset(tr[F],tr.shots),m.best_iteration)
    trmu=m.predict(tr[F]); k=optimize.minimize_scalar(lambda k:nll(k,tr.shots.values,trmu),bounds=(0.5,200),method='bounded').x
    bmu_tr=tr.shots_r10.clip(lower=0.05).values; kb=optimize.minimize_scalar(lambda k:nll(k,tr.shots.values,bmu_tr),bounds=(0.5,200),method='bounded').x
    mu=m.predict(te[F]); bmu=te.shots_r10.clip(lower=0.05).values; y=te.shots.values
    res.append(dict(season=f'{s}-{s+1-2000}',rows=len(te),k_model=round(k,1),nll_model=nll(k,y,mu),nll_base=nll(kb,y,bmu),crps_model=crps(y,mu,k),crps_base=crps(y,bmu,kb)))
    for L in (1.5,2.5,3.5):
        p=1-stats.nbinom.cdf(int(L),k,nb_p(mu,k)); o=(y>L).astype(int)
        pb=1-stats.nbinom.cdf(int(L),kb,nb_p(bmu,kb))
        cal.append(pd.DataFrame(dict(season=s,line=L,p=p,pb=pb,o=o)))
r=pd.DataFrame(res); print(r.round(4).to_string(index=False))
c=pd.concat(cal); c['bin']=pd.cut(c.p,[0,.2,.35,.45,.55,.65,.8,1])
ct=c.groupby(['line','bin'],observed=True).agg(n=('o','size'),pred=('p','mean'),actual=('o','mean')).round(3)
print(ct.to_string())
bs=c.groupby('line').apply(lambda d:pd.Series(dict(brier_model=((d.p-d.o)**2).mean(),brier_base=((d.pb-d.o)**2).mean(),logloss_model=-np.mean(d.o*np.log(d.p.clip(1e-6))+(1-d.o)*np.log((1-d.p).clip(1e-6))),logloss_base=-np.mean(d.o*np.log(d.pb.clip(1e-6))+(1-d.o)*np.log((1-d.pb).clip(1e-6)))))).round(4)
print(bs.to_string())
open('results.md','w').write('# NHL SOG walk-forward\n\n'+r.round(4).to_markdown(index=False)+'\n\n## Calibration P(over)\n\n'+ct.to_markdown()+'\n\n'+bs.to_markdown()+'\n')
