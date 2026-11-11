"""2025-26 PROXY (no prices, synthetic lines; information test only, not profit).
Line = floor(recent_mu) + 0.5, recent_mu = sog60_r10 * toi_r5 / 60 (as-of, prior games only).
Reports over-hit rate and mean(actual - recent_mu) by over-side vote for att and total."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import att_signal as A, teams as TM
from backtest import wilson
L = A.load_logs()   # TOI>0 games, all seasons (history needed for base windows)
V = A.vectorized(L)
P = V[V.season == 2025].copy()
# att (same thresholds as att_signal.compute)
with np.errstate(divide='ignore', invalid='ignore'):
    a = (P.att_R / P.hrs_R) / (P.att_B / P.hrs_B) - 1
    b = (P.shots_B / P.att_B) / (P.shots_R / P.att_R) - 1
sg = lambda x: np.where(x >= A.BAND, 1, np.where(x <= -A.BAND, -1, 0))
ok = (P.n_R >= A.N_RECENT) & (P.n_B >= A.MIN_BASE) & (P.att_R >= A.MIN_ATT) & (P.hrs_R > 0) & (P.hrs_B > 0) & (P.att_B > 0)
P['att_v'] = np.where(ok, np.sign(sg(a.fillna(0)) + sg(np.where(P.shots_R > 0, b, np.inf))), 0)
# spot-check vectorized vs per-query
by = {k: v for k, v in L.groupby('playerId')}
for _, r in P[ok].sample(300, random_state=1).iterrows():
    f = A.features_for(by, r.playerId, r.gameDate)
    assert f['att_over'] == r.att_v, (r.playerId, r.gameDate, f, r.att_v)
# recent_mu, synthetic line
g = L.groupby('playerId', sort=False)
L['toi_m'] = L.timeOnIcePerGame / 60
toi5 = g.toi_m.transform(lambda s: s.shift(1).rolling(5, min_periods=5).mean())
P['toi_r5'] = toi5.loc[P.index]
P['recent_mu'] = (P.shots_R / P.hrs_R) * P.toi_r5 / 60
P = P[ok & P.recent_mu.notna()].copy()
P['line'] = np.floor(P.recent_mu) + 0.5
P['over_hit'] = P.shots > P.line; P['resid'] = P.shots - P.recent_mu
P['home'] = np.where(P.homeRoad == 'H', P.teamAbbrev, P.opponentTeamAbbrev)
# total: ESPN DK open total, matched by home team + local date (start_utc - 8h)
T = pd.read_csv(os.path.join(HERE, 'cache', 'espn_totals.csv'), dtype={'event': str})
T = T[T['mode'] == 's2025'].copy()
T['home'] = [TM.T.get(TM.home_of(x), (None,))[0] for x in T.game]
T['gameDate'] = (pd.to_datetime(T.start_utc, utc=True) - pd.Timedelta(hours=8)).dt.strftime('%Y-%m-%d')
T['tot'] = T.open_total.fillna(T.close_total)  # provider: DK else ESPN BET (see README); T['tot_src'] = np.where(T.open_total.notna(), 'open', np.where(T.close_total.notna(), 'close', 'n/a'))
P = P.merge(T[['home', 'gameDate', 'tot', 'tot_src']].drop_duplicates(['home', 'gameDate']), on=['home', 'gameDate'], how='left')
P['total_v'] = np.where(P.tot >= 6.5, 1, np.where(P.tot <= 5.5, -1, 0)); P.loc[P.tot.isna(), 'total_v'] = 0
out = []
for sig in ['att_v', 'total_v']:
    for v in (1, 0, -1):
        x = P[P[sig] == v]; n = len(x); k = int(x.over_hit.sum()); lo, hi = wilson(k, n)
        se = x.resid.std() / np.sqrt(n) if n else np.nan
        out.append(dict(signal=sig[:-2], over_vote={1: '+', 0: '0', -1: '-'}[v], rows=n, over_hit=k/n if n else np.nan, hit_lo=lo, hit_hi=hi,
                        mean_resid=x.resid.mean(), resid_lo=x.resid.mean() - 1.96*se, resid_hi=x.resid.mean() + 1.96*se))
S = pd.DataFrame(out); S.to_csv(os.path.join(HERE, 'out', 'backtest_proxy_summary.csv'), index=False)
pd.set_option('display.width', 200); print(S.round(3).to_string(index=False))
print('rows', len(P), 'games', P.gameId.nunique(), '| total matched rows', int(P.tot.notna().sum()), P.tot_src.value_counts(dropna=False).to_dict())
print('providers', T.provider.value_counts(dropna=False).to_dict() if 'provider' in T else 'n/a'); print('totals dist', P.drop_duplicates('gameId').tot.value_counts(dropna=False).to_dict())
