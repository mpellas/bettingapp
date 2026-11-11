import pandas as pd
D=pd.read_csv('sides_graded.csv'); H=D[D.healthy&D.fair_excl.notna()]
print('EV_excl quantiles',H.ev_excl.describe().round(2).to_dict()); print('EV_all max',H.ev_all.max().round(2))
print(H.nlargest(5,'ev_excl')[['player','market','line','side','book','price','ev_excl','ev_all','sharps','model_p']].round(3).to_string())
print('void/ungraded:',D[D.model_ok&D.band&~D.result.isin(['win','loss','push'])][['game','player','market','result']].to_string())
L=pd.read_csv('/workspace/props-finder/analysis/shadow_modelled_ledger.csv')
print('ledger',len(L),L.result.value_counts().to_dict(),round(L.units.sum(),2))
k=['player','market','line','side','book']
m=L.merge(D[k+['price','result','units','actual']],on=k,how='left',suffixes=('_led','_me'))
m=m.drop_duplicates(subset=['file']+k)
print('unmatched',m.result_me.isna().sum())
mm=m[(m.result_led!=m.result_me)|((m.units_led-m.units_me).abs()>.01)]
print('mismatch rows',len(mm)); print(mm[['file','player','market','line','side','price_led','price_me','actual_led','actual_me','result_led','result_me']].to_string())
# best-book per side model set dedupe across pulls
R=D[D.model_ok&D.band&D.healthy].copy(); R['dec']=R.price.apply(lambda p:1+(100/abs(p) if p<0 else p/100))
B=R.sort_values('dec').groupby(['event_id','player','market','line','side']).tail(1)
w=(B.result=='win').sum();l=(B.result=='loss').sum(); print('best-book model set',len(B),f'{w}-{l}',round(B.units.sum(),2))
