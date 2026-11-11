"""Train final model on all data available (as-of today), save models/model_<hash>.txt + meta. Hash = sha256 of model text[:10]."""
from features import *; import hashlib
from scipy import stats,optimize
df=feats(load()); F=FEATS(df); df=df[df.n_prior>=5]
P=dict(objective='poisson',learning_rate=0.03,num_leaves=15,min_data_in_leaf=200,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,verbose=-1,seed=7)
m=lgb.train(P,lgb.Dataset(df[F],df.shots),int(sys.argv[1]) if len(sys.argv)>1 else 600)
mu=m.predict(df[F]); y=df.shots.values
k=optimize.minimize_scalar(lambda k:-stats.nbinom.logpmf(y,k,k/(k+mu)).mean(),bounds=(0.5,200),method='bounded').x
txt=m.model_to_string(); h=hashlib.sha256(txt.encode()).hexdigest()[:10]
open(f'models/model_{h}.txt','w').write(txt)
json.dump({'hash':h,'k':k,'features':F,'trained_through':str(df.date.max().date()),'rows':len(df)},open(f'models/model_{h}.json','w'),indent=1)
open('models/CURRENT','w').write(h); print(h,round(k,2),len(df))
