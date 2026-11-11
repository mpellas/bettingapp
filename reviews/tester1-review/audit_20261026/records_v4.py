"""v4 (Oct 26 ~9:30 PT): v3 + 17 more skips verified against posted FINAL CALL cards (session transcripts in /workspace/agent-tools/*.txt;
picks/finalcall_done/*.txt are markers only) and /workspace/nhl-sog/crosscheck/tester3_calls.csv. Pre-noon = 4 NJD@WSH sides only (Aho stays)."""
import pandas as pd, numpy as np, os
OUT=os.path.dirname(os.path.abspath(__file__)); R=pd.read_csv(f'{OUT}/sides_v3.csv',dtype={'date':str})
new={('20261017','Bryan Rust'):'tester3_calls 16:19 skip',('20261017','Connor McDavid'):'tester3_calls 16:19 skip',
 ('20261018','Nikolaj Ehlers'):'tester3_calls 13:58 skip',
 ('20261019','Beckett Sennecke'):'FINAL CALL 12:47 skip',('20261019','Artturi Lehkonen'):'FINAL CALL 12:47 skip',
 ('20261019','Nick Paul'):'corrected FINAL CALL 1:19 (T2+T3 skip)',('20261019','Rickard Rakell'):'FINAL CALL 3:12 skip',
 ('20261020','Kirill Marchenko'):'FINAL CALL 1:03 skip',('20261020','Morgan Rielly'):'FINAL CALL 1:03 skip',('20261020','Jackson LaCombe'):'FINAL CALL 1:03 skip',
 ('20261020','Tony DeAngelo'):'FINAL CALL 1:03 on hold, lineup never confirmed',
 ('20261020','Charlie McAvoy'):'FINAL CALL 2:05 skip',('20261020','Wyatt Johnston'):'FINAL CALL 2:05 skip',('20261020','Jimmy Snuggerud'):'FINAL CALL 2:05 skip',
 ('20261020','Alex Formenton'):'FINAL CALL 3:08 skip',('20261020','Kirill Kaprizov'):'FINAL CALL 3:08 skip',('20261020','Vince Dunn'):'FINAL CALL 3:12 skip'}
for (d,p),r in new.items():
    m=(R.date==d)&(R.player==p); assert m.sum()==1,(d,p); R.loc[m,['skip_reason','record','bucket']]=[r,'skipped','tester-skipped']
R['pre_noon']=(R.list=='20261017_AM')&R.game.str.contains('New Jersey Devils at Washington')
R.to_csv(f'{OUT}/sides_v4.csv',index=False)
def s(r): return dict(sides=len(r),WL=f'{int(r.hit.sum())}-{int(len(r)-r.hit.sum())}',u_shop=round(r.u_shop.sum(),2),u_dk=round(r.u_dk.sum(),2))
out=[]
for rec,sub in [('as-posted',R),('final-card',R[R.record=='final-card']),('skipped',R[R.record=='skipped'])]:
  for x,ss in [('with pre-noon',sub),('excl 4 pre-noon',sub[~sub.pre_noon])]:
    for lbl,m in [('All',ss.date>='0'),('Oct 18-24',(ss.date>='20261018')&(ss.date<='20261024')),('Post-floor',ss.list>='20261020_1513'),('Oct 17',ss.date=='20261017')]:
        out.append(dict(record=rec,pre_noon=x,slice=lbl,**s(ss[m])))
out.append(dict(record='pre-noon excluded',pre_noon='',slice='4 NJD@WSH',**s(R[R.pre_noon])))
O=pd.DataFrame(out); O.to_csv(f'{OUT}/summary_v4.csv',index=False); print(O.to_string(index=False)); print(R.bucket.value_counts())
print(R[(R.record=='final-card')&(R.list>='20261020_1513')][['list','player','hit','u_dk','u_shop']])
