import pandas as pd, numpy as np
S=pd.read_pickle('board_dedup.pkl')
def dec(a): a=float(a); return a/100 if a>0 else 100/abs(a)
def plf(h,p): return np.nan if (pd.isna(p) or pd.isna(h)) else (dec(p) if h else -1.0)
S['pl_dk']=[plf(h,p) for h,p in zip(S.hit,S.dk_price)]
S['pl_shop']=[plf(h,p) for h,p in zip(S.hit,S.fliff_shop_at)] if 'fliff_shop_at' in S else np.nan
print(S.columns.tolist()); print(S.sig_toi.value_counts(dropna=False).head(8).to_dict()); print(S.gstatus.value_counts(dropna=False).to_dict())
def summ(d,col='pl_dk'):
    d=d[d.hit.notna()&d[col].notna()]
    w=int(d.hit.astype(bool).sum())
    return f"n={len(d)} {w}-{len(d)-w} P/L {d[col].sum():+.2f}u ROI {100*d[col].sum()/max(len(d),1):+.1f}% won_forgone {d[d.hit.astype(bool)][col].sum():.2f} loss_avoided {len(d)-w}"
def cat(r):
    r=str(r)
    if 'model not above' in r: return 'model_not_above_novig'
    if r.startswith('model +') : return 'CANDIDATE'
    for k,v in [('recent form','recent_form_fail'),('milestone','not_milestone_side'),('role changed','role_or_lineup_veto'),('edge below 5','edge_below_5pt_floor'),('slot veto','slot_veto'),('thin edge','thin_edge_pre_floor'),('more than 12','over_12pts_from_novig'),('outside top 5','outside_top5'),('shop gate','shop_gate_failed')]:
        if k in r: return v
    return 'other:'+r
S['cat']=S.status_reason.apply(cat)
S.to_pickle('board_season.pkl')
for wk,lab in [(S.date>='20261025','WEEK'),(S.date>='20261017','SEASON')]:
    print('==',lab)
    for c,g in S[wk].groupby('cat'): print(f'{c:28s}', summ(g))
