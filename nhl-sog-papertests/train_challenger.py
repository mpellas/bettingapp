"""Train challenger A on prior seasons only (season<=2025, i.e. through 2025-26); early stopping on 2025 with fit on <2025 first."""
import os; from chal_common import *; import lightgbm as lgb; from scipy import stats,optimize
os.chdir('/workspace/nhl-sog'); df=add_pos(feats(load())); os.chdir('/workspace/nhl-sog-papertests')
df=df[(df.n_prior>=5)&(df.season<=2025)]
tr2,vl,tr=df[df.season<2025],df[df.season==2025],df
P=dict(objective='poisson',learning_rate=0.03,num_leaves=15,min_data_in_leaf=200,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,verbose=-1,seed=1)
m=lgb.train(P,lgb.Dataset(tr2[FEATS],tr2.shots),2000,valid_sets=[lgb.Dataset(vl[FEATS],vl.shots)],callbacks=[lgb.early_stopping(100,verbose=False)])
bi=m.best_iteration; m=lgb.train(P,lgb.Dataset(tr[FEATS],tr.shots),bi); mu=m.predict(tr[FEATS])
nll=lambda k:-stats.nbinom.logpmf(tr.shots.values,k,k/(k+mu)).mean()
k=optimize.minimize_scalar(nll,bounds=(.5,200),method='bounded').x
m.save_model('models/chal_A.txt'); json.dump(dict(k=k,features=FEATS,best_iter=bi,rows=len(tr),max_season=2025,max_date=str(tr.gameDate.max())),open('models/chal_A.json','w'),indent=1)
print('trained',bi,'iters k',k,len(tr),'rows through',tr.gameDate.max())
