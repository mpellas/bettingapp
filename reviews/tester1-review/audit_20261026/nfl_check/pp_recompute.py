import sys; sys.path.insert(0,'/workspace/props-finder'); import pandas as pd, pickem as P
pd.Timestamp.now=staticmethod(lambda tz=None: pd.Timestamp('2026-10-01',tz='UTC'))
Q={'20261018T1440':[('Ray Davis','rush_yds','Over',.5703),('Darren Waller','reception_yds','Under',.5646),('Tyler Higbee','reception_yds','Under',.5628),('Dak Prescott','rush_yds','Under',.5597),('Omarion Hampton','reception_yds','Under',.5569)],
   '20261025T1432':[('Darnell Mooney','reception_yds','Under',.5662),('J.J. McCarthy','rush_yds','Under',.5590)]}
BE={t:P.breakeven(t) for t in P.TYPES}; print({k:round(v,4) for k,v in BE.items()})
for raw,qs in Q.items():
    L=P.legs_from_raw(f'/workspace/props-finder/raw/{raw}','nfl')
    for pl,mk,sd,posted in qs:
        r=L[(L.player==pl)&(L.market==mk)&(L.side==sd)]
        for x in r.itertuples():
            bw=x.blend_win; types=[t for t in P.TYPES if bw>=P.breakeven(t,x.push)+0.01]
            print(raw,pl,mk,sd,x.pp_line,'blend',bw,'posted',posted,'diff',round(bw-posted,4),'model',x.model_p,'push',x.push,'clears+1pt:',types)
