import pandas as pd, numpy as np
S=pd.read_pickle('board_season.pkl')
def summ(d,col='pl_dk'):
    d=d[d.hit.notna()&d[col].notna()]
    w=int(d.hit.astype(bool).sum())
    return f"n={len(d)} {w}-{len(d)-w} P/L {d[col].sum():+.2f}u ROI {100*d[col].sum()/max(len(d),1):+.1f}%"
C=S[S.cat=='CANDIDATE'].copy()
print('season cand dates',C.groupby('date').size().to_dict())
print('shop', summ(C,'pl_shop'))
print('lineup_age known',C.lineup_age_h.notna().sum())
print('stale>12', summ(C[C.lineup_age_h>12]), '| fresh<=12', summ(C[C.lineup_age_h<=12]))
print('agrees<=2', summ(C[C.agrees_n<=2]), '| >=3', summ(C[C.agrees_n>=3]), '| agrees NaN', C.agrees_n.isna().sum())
U=C[C.side=='UNDER']
print('under toi+', summ(U[U.sig_toi.astype(str)=='-']),'| under toi other',summ(U[U.sig_toi.astype(str)!='-']))
print(U.sig_toi.astype(str).value_counts().to_dict())
# what does sig_toi '-' mean? check evidence_summary sample
print(U[['sig_toi','evidence_summary']].head(4).to_string())
for s,g in C.groupby('side'): print(s, summ(g))
C['band']=(C.dk_price>=-150)&(C.dk_price<=110)
print('band', summ(C[C.band]), '| out', summ(C[~C.band]))
C['e']=C.edge*100
for lo,hi in [(0,5),(5,8),(8,12),(12,99)]: print('edge',lo,hi, summ(C[(C.e>=lo)&(C.e<hi)]))
# lineup age for week cands
W=C[C.date>='20261025']; print(W[['date','pass','player','lineup_age_h','team_dfo']].to_string())
