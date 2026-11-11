"""v5: v4 + Yinzer rulings: Nick Paul (Oct 19) back on card; Rust, McDavid (Oct 17), Ehlers (Oct 18), DeAngelo (Oct 20) -> 'unverified'."""
import pandas as pd, os
OUT=os.path.dirname(os.path.abspath(__file__)); R=pd.read_csv(f'{OUT}/sides_v4.csv',dtype={'date':str})
def setr(d,p,rec,why):
    m=(R.date==d)&(R.player==p); assert m.sum()==1,(d,p); R.loc[m,['record','bucket','skip_reason']]=[rec,rec,why]
setr('20261019','Nick Paul','final-card','')
for d,p in [('20261017','Bryan Rust'),('20261017','Connor McDavid'),('20261018','Nikolaj Ehlers'),('20261020','Tony DeAngelo')]:
    setr(d,p,'unverified','Yinzer ruling Oct 26: card status unverified')
R.to_csv(f'{OUT}/sides_v5.csv',index=False)
def s(r): return dict(sides=len(r),WL=f'{int(r.hit.sum())}-{int(len(r)-r.hit.sum())}',u_dk=round(r.u_dk.sum(),2),u_shop=round(r.u_shop.sum(),2))
out=[]
for rec,sub in [('final-card',R[R.record=='final-card']),('skipped',R[R.record=='skipped']),('unverified',R[R.record=='unverified']),('as-posted',R)]:
  for lbl,m in [('All Oct 17-25',sub.date>='0'),('Post-floor',sub.list>='20261020_1513')]:
    for x,ss in [('with',sub[m]),('excl 4 pre-noon',sub[m&~sub.pre_noon])]:
        out.append(dict(record=rec,slice=lbl,pre_noon=x,**s(ss)))
O=pd.DataFrame(out); O.to_csv(f'{OUT}/summary_v5.csv',index=False); print(O.to_string(index=False)); print(R.record.value_counts())
