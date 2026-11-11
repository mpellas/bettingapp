import pandas as pd, numpy as np
C=pd.read_pickle('cands.pkl'); S=pd.read_pickle('board_dedup.pkl')
def dec(a): a=float(a); return a/100 if a>0 else 100/abs(a)
def plf(hit,price): return np.nan if (pd.isna(price) or pd.isna(hit)) else (dec(price) if hit else -1.0)
def summ(d,col):
    d=d[d.hit.notna()]
    w=int(d.hit.astype(bool).sum()); l=len(d)-w
    pl=d[col].sum(); cost=d[d.hit.astype(bool)][col].sum(); saved=-d[~d.hit.astype(bool)][col].sum()
    return dict(n=len(d),W=w,L=l,pl=round(pl,2),roi=round(100*pl/len(d),1) if len(d) else np.nan,won_forgone=round(cost,2),loss_avoided=round(saved,2))
sk=C[C.decision=='skipped']
print('WEEK skipped @shop',summ(sk,'pl_shop_at')); print('@dk',summ(sk,'pl_dk')); print('@best',summ(sk,'pl_best_avail'))
print('card play', C[C.decision=='card_play'][['player','hit','pl_dk','pl_shop_at']].to_dict('records'))
print('all candidates @dk',summ(C,'pl_dk'))
print('in band DK',summ(sk[sk.in_band_dk],'pl_dk'), 'out band',summ(sk[~sk.in_band_dk],'pl_dk'))
for r in ['price_worse_than_shop_at','fliff_not_posted','toi_up_on_under','stale_lineup','gate_2_of_7','checker_missing_or_split','other']:
    d=sk[sk.reasons.apply(lambda x: r in x)]
    print(r, 'shop',summ(d,'pl_shop_at'),'| dk',summ(d,'pl_dk'), '| sole', (d.n_reasons==1).sum())
print('price only', summ(sk[sk.price_only],'pl_shop_at'), summ(sk[sk.price_only],'pl_dk'))
print('multi reasons', (sk.n_reasons>1).sum(), 'of', len(sk))
print('by day'); 
for d,g in sk.groupby('date'): print(d, summ(g,'pl_shop_at'), summ(g,'pl_dk'))
# over/under
for s,g in sk.groupby('side'): print(s, summ(g,'pl_dk'))
