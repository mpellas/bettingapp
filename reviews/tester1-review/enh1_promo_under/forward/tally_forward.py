"""Forward nightly tally for enhancement test 1 (promo->UNDER veto dropped; paper only). Reads forward/slate_YYYYMMDD_HHMM.csv
written by ../shadow_no_promo_under.py, keeps the latest in-window pass per player-game (each slate = one window pass), grades
from NHL.com box scores, appends to tally.csv. Deciding list = makes_list True (would have been listed); all promo-vetoed unders logged.
Usage: python3 tally_forward.py YYYYMMDD"""
import sys, glob, os, re
import pandas as pd
sys.path.insert(0, '/workspace/nhl-sog/shadow/edge8_band'); import nhlbox as nb
HERE = os.path.dirname(os.path.abspath(__file__)); date = sys.argv[1]
fs = sorted(glob.glob(f'{HERE}/slate_{date}_*.csv'))
if fs:
    picks = {}
    a = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    ids = []
    for pid, pl, ln in zip(a.pass_id, a.player, a.line):
        hh = pid.split('_')[1]; k = (date, hh)
        if k not in picks: picks[k] = pd.read_csv(f'/workspace/nhl-sog/picks/{date}_D_{hh}.csv')
        r = picks[k][(picks[k].player == pl) & (picks[k].line == ln)].iloc[0]; ids.append((int(r.nhl_id), int(r.gameId)))
    a['nhl_id'], a['gameId'] = [i[0] for i in ids], [i[1] for i in ids]
    a = a[a.pass_id == a.groupby(['nhl_id', 'gameId']).pass_id.transform('max')].copy()
    a['side'] = 'under'; a['date'] = date
    keep = ['date', 'pass_id', 'game', 'player', 'nhl_id', 'gameId', 'side', 'line', 'dk_price', 'shop_at', 'edge_model_pts', 'tally', 'new_status', 'makes_list', 'blockers']
    nb.append_tally(f'{HERE}/tally.csv', nb.grade(a[keep], ('dk_price', 'shop_at')), ['date', 'nhl_id', 'gameId', 'line'])
T = pd.read_csv(f'{HERE}/tally.csv') if os.path.exists(f'{HERE}/tally.csv') else None
if T is not None:
    s = pd.DataFrame([dict(list='would list (deciding)', price='DK', **nb.summary(T, T.makes_list.astype(bool), 'u_dk_price')),
                      dict(list='would list (deciding)', price='shop-at', **nb.summary(T, T.makes_list.astype(bool), 'u_shop_at')),
                      dict(list='all promo-vetoed unders', price='DK', **nb.summary(T, T.makes_list.notna(), 'u_dk_price'))])
    s.to_csv(f'{HERE}/summary.csv', index=False); print(T[['date','player','line','dk_price','makes_list','actual','result']].to_string(index=False)); print(s.to_string(index=False))
