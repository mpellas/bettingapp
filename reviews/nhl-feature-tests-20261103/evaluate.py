import pandas as pd,numpy as np
from scipy import stats
te=pd.read_pickle('preds_2025_26.pkl'); V=['base','a_venue','b_vsopp','c_oppD_nhl','c_oppD_mp']
y=te.shots.values; rng=np.random.default_rng(0); ug,inv=np.unique(te.gameId,return_inverse=True)
B=[rng.integers(0,len(ug),len(ug)) for _ in range(1000)]
def pov(v,L): k=te['k_'+v].iloc[0]; mu=te['mu_'+v].values; return 1-stats.nbinom.cdf(int(L),k,k/(k+mu))
def boot(d):
    s=np.bincount(inv,d); c=np.bincount(inv); return np.percentile([s[b].sum()/c[b].sum() for b in B],[2.5,97.5])
# proxy posted line: the half-line where BASE P(over) is closest to 50%
pb={L:pov('base',L) for L in (0.5,1.5,2.5,3.5,4.5)}
Ls=np.array([0.5,1.5,2.5,3.5,4.5]); idx=np.argmin(np.abs(np.stack([pb[L] for L in Ls])-0.5),axis=0); te['line']=Ls[idx]
rows=[];buck=[];cal=[]
llb=None
for v in V:
    k=te['k_'+v].iloc[0]; mu=te['mu_'+v].values; ll=-stats.nbinom.logpmf(y,k,k/(k+mu))
    if v=='base': llb=ll
    r=dict(variant=v,n=len(y),nll=ll.mean(),d_nll_x1000=(ll-llb).mean()*1000)
    lo,hi=boot(ll-llb); r['ci_lo']=lo*1000; r['ci_hi']=hi*1000
    for L in (1.5,2.5,3.5):
        p=pov(v,L); o=(y>L); r[f'logloss_{L}']=-(o*np.log(p)+(1-o)*np.log(1-p)).mean(); r[f'brier_{L}']=((p-o)**2).mean()
    rows.append(r)
    # picks at the proxy line: side = model's side, edge = |p-0.5| in points
    p=np.array([pov(v,L)[i] for i,L in []]) if False else np.choose(idx,[pov(v,L) for L in Ls])
    over=p>=.5; hit=np.where(over,y>te.line,y<te.line); e=np.abs(p-.5)*100
    for lo_,hi_ in [(0,3),(3,5),(5,8),(8,12),(12,100)]:
        m=(e>=lo_)&(e<hi_)
        buck.append(dict(variant=v,edge=f'{lo_}-{hi_}',n=int(m.sum()),hit=hit[m].mean() if m.sum() else np.nan,pred=(.5+e[m]/100).mean() if m.sum() else np.nan,over_share=over[m].mean() if m.sum() else np.nan))
    # top picks: top 2% by edge
    q=e>=np.percentile(e,98); buck.append(dict(variant=v,edge='top2%',n=int(q.sum()),hit=hit[q].mean(),pred=(.5+e[q]/100).mean(),over_share=over[q].mean()))
    # calibration at 2.5 line
    p25=pov(v,2.5); bins=np.clip((p25*10).astype(int),0,9)
    ece=sum(abs(p25[bins==b].mean()-(y[bins==b]>2.5).mean())*(bins==b).mean() for b in range(10) if (bins==b).any())
    rows[-1]['ece_2.5']=ece
R=pd.DataFrame(rows); Bk=pd.DataFrame(buck)
R.to_csv('metrics.csv',index=False); Bk.to_csv('edge_buckets.csv',index=False)
pd.set_option('display.width',250); print(R.round(5).to_string(index=False)); print(Bk.round(3).to_string(index=False))
print(te.line.value_counts())
# paired hit-rate diff in the 5+ bucket vs base on same rows? report sample
