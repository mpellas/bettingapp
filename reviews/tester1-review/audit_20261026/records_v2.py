"""v2 (Oct 26 9:15 PT): split sides.csv (graded from fresh box scores by audit_nhl_lists.py) into as-posted / final-card / skipped.
Card membership from raw files: picks/finalcall_done markers (Oct 25), bets.csv as card proxy for Oct 24 (final-call text not on disk),
room cards for Oct 17-20 (no final-call text on disk -> posted = card). Read-only over /workspace/nhl-sog."""
import pandas as pd, numpy as np, os
OUT=os.path.dirname(os.path.abspath(__file__)); R=pd.read_csv(f'{OUT}/sides.csv')
B=pd.read_csv('/workspace/props-finder/user_bets/bets.csv'); B=B[B.sport=='nhl']
skip={ # (date,player): reason
 ('20261024','Tom Wilson'):'huge price move (no-vig +23.2 pts toward side); not bet (user bet U1.5, a different line)',
 ('20261024','Mattias Samuelsson'):'not on final card/not bet (no Fliff market at post); final-call text not on disk',
 ('20261024','Darren Raddysh'):'Fliff -150 worse than -117 shop-at',
 ('20261024','Matt Coronato'):'2 of 7 agree',
 ('20261024','Vince Dunn'):'huge price move (+22.3 pts) and Fliff -205 worse than -159 shop-at',
 ('20261025','Roman Kantserov'):'NO BETS card 9:31 PT (Fliff not offered)',
 ('20261025','Roope Hintz'):'final call 12:18 PT: skip (Fliff -190 vs -157)',
 ('20261025','Miro Heiskanen'):'final call 12:18 PT: skip (Fliff +110 vs +145)',
 ('20261025','Roman Josi'):'huge move +140 -> -195; 1.5 not on Fliff',
 ('20261025','Sam Malinski'):'Fliff -115 worse than +109 shop-at; 3 of 7',
 ('20261025','Brayden Schenn'):'Fliff -110 never reached +109; room says NO BETS (marker lists it as conditional)'}
R['date']=R.date.astype(str); R['skip_reason']=[skip.get((d,p),'') for d,p in zip(R.date,R.player)]
R['record']=np.where(R.skip_reason!='','skipped','final-card')
R.to_csv(f'{OUT}/sides_v2.csv',index=False)
def s(r):
    c=r.dropna(subset=['clv_pts'])
    return dict(sides=len(r),WL=f'{int(r.hit.sum())}-{int(len(r)-r.hit.sum())}',u_shop=round(r.u_shop.sum(),2),u_dk=round(r.u_dk.sum(),2),
                close_n=len(c),close_mv=round(c.clv_pts.mean(),2) if len(c) else np.nan)
out=[]
for rec,sub in [('as-posted',R),('final-card',R[R.record=='final-card']),('skipped',R[R.record=='skipped'])]:
    for lbl,m in [('All Oct 17-25',sub.date>='0'),('Oct 18-24',(sub.date>='20261018')&(sub.date<='20261024')),
                  ('Post-floor',sub.list>='20261020_1513'),('Oct 17',sub.date=='20261017'),('Oct 25',sub.date=='20261025')]:
        out.append(dict(record=rec,slice=lbl,**s(sub[m])))
O=pd.DataFrame(out); O.to_csv(f'{OUT}/summary_v2.csv',index=False); print(O.to_string(index=False))
print(R[R.record=='skipped'][['list','player','side','line','hit','u_dk','skip_reason']].to_string())
