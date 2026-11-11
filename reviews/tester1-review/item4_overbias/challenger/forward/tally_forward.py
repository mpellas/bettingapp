"""Forward nightly tally for the 50% shrink challenger (paper only). Reads forward/slate_YYYYMMDD_HHMM.csv written by
../shadow_shrink50.py slate, keeps the latest pass captured >= 150 min before NHL.com start per player-game, grades listed
sides (live list and challenger list) from NHL.com box scores, appends to tally.csv. Usage: python3 tally_forward.py YYYYMMDD"""
import sys, glob, os
import pandas as pd
sys.path.insert(0, '/workspace/nhl-sog/shadow/edge8_band'); import nhlbox as nb
HERE = os.path.dirname(os.path.abspath(__file__)); date = sys.argv[1]; out = []
for f in sorted(glob.glob(f'{HERE}/slate_{date}_*.csv')):
    hh = f.rsplit('_', 1)[1][:4]; r = pd.read_csv(f)
    pk = pd.read_csv(f'/workspace/nhl-sog/picks/{date}_D_{hh}.csv')[['player', 'line', 'nhl_id', 'gameId', 'captured_utc']].drop_duplicates(['player', 'line'])
    r = r.merge(pk, on=['player', 'line'], how='left'); r['pass'] = f'{date}_{hh}'; out.append(r)
if out:
    a = pd.concat(out, ignore_index=True); a['cap'] = pd.to_datetime(a.captured_utc, utc=True, format='mixed')
    st = {g: nb.start_utc(g) for g in a.gameId.unique()}
    a['mins_before'] = [(st[g] - c).total_seconds()/60 for g, c in zip(a.gameId, a.cap)]
    a = a[a.mins_before >= 150]; a = a[a.cap == a.groupby(['nhl_id', 'gameId']).cap.transform('max')]
    a = a[a.live_list | a.ch_list].drop(columns=['cap']); a['date'] = date
    if len(a): nb.append_tally(f'{HERE}/tally.csv', nb.grade(a, ('dk_price', 'live_shop_at', 'ch_shop_at')), ['date', 'nhl_id', 'gameId', 'side', 'line'])
T = pd.read_csv(f'{HERE}/tally.csv') if os.path.exists(f'{HERE}/tally.csv') else None
if T is not None:
    L, C = T.live_list.astype(bool), T.ch_list.astype(bool)
    s = pd.DataFrame([dict(list=n, **nb.summary(T, m, 'u_dk_price')) for n, m in
                      (('live', L), ('challenger', C), ('both', L & C), ('live_only', L & ~C), ('ch_only', C & ~L))])
    s.to_csv(f'{HERE}/summary.csv', index=False); print(T[['date','player','side','line','dk_price','live_list','ch_list','actual','result']].to_string(index=False)); print(s.to_string(index=False))
