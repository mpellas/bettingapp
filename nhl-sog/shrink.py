"""Gamma-Poisson shrunk recent form (shadow columns; approved 2026-10-16 as a challenger, not used for status).

Per player, strictly before the pick's game date (PT, from captured_utc):
  last 10 games  : S10 shots in T10 hours of TOI           (the raw rule's window)
  prior          : rate0 = shots/hour over the 30 games before those 10 (spans into 2025-26);
                   fallback = position league rate if < 5 such games
  prior strength : m = M_GAMES (15) games of TOI at the player's recent TOI/game (hours)
  posterior rate : Gamma(a = rate0*m + S10, b = m + T10)  ->  shrunk_mu = a/b * t, t = toi_r5 hours
  predictive     : X ~ NegBin(r=a, p=b/(b+t))  (gamma-Poisson mixture), so P(over) / P(under) are exact.
Game logs: data/s2021..2025.pkl (history) + shadow/s2026_live.pkl (fresh, from shadow/gamelog.py).
2026 logs: whichever of shadow/s2026_live.pkl and data/s2026.pkl is freshest (fetch.py fixed 2026-10-17).
Columns added: fresh_toi_r5, fresh_sog60_r10, fresh_recent_mu, p_fresh_over/under (raw rule on fresh logs),
               shrunk_rate0, shrunk_mu, p_shrunk_over/under, shrunk_pass_over/under.
"""
import os, glob, math
import numpy as np, pandas as pd
from scipy import stats
HERE = os.path.dirname(os.path.abspath(__file__))
M_GAMES = 15
_LOG = None
def gamelogs():
    global _LOG
    if _LOG is None:
        hist = [pd.read_pickle(f) for f in sorted(glob.glob(f'{HERE}/data/s202[1-5].pkl'))]
        live = os.path.join(HERE, 'shadow', 's2026_live.pkl')
        cands = [pd.read_pickle(f) for f in (live, f'{HERE}/data/s2026.pkl') if os.path.exists(f)]
        parts = hist + [max(cands, key=lambda c: (c.gameDate.max(), len(c)))]  # freshest 2026 log; ties -> more rows (2026-10-17)
        df = pd.concat([p[['playerId', 'gameId', 'gameDate', 'shots', 'timeOnIcePerGame', 'positionCode']] for p in parts])
        df = df.drop_duplicates(['playerId', 'gameId']).sort_values(['gameDate', 'gameId'])
        df['hrs'] = df.timeOnIcePerGame / 3600.0
        _LOG = df
    return _LOG
def pick_date(r):
    return pd.Timestamp(r.captured_utc).tz_convert('America/Los_Angeles').strftime('%Y-%m-%d')
def _pos_rate(log, pos, date):
    x = log[(log.gameDate < date) & (log.positionCode.eq('D') == (pos == 'D'))].tail(20000)
    return x.shots.sum() / x.hrs.sum()
def one(r, m_games=M_GAMES):
    log = gamelogs(); date = pick_date(r)
    g = log[(log.playerId == r.nhl_id) & (log.gameDate < date)]
    if len(g) == 0: return {}
    l10, prior = g.tail(10), g.iloc[-40:-10]
    S10, T10 = l10.shots.sum(), l10.hrs.sum()
    toi5 = g.tail(5).hrs.mean()
    pos = g.positionCode.iloc[-1]
    rate0 = prior.shots.sum() / prior.hrs.sum() if len(prior) >= 5 and prior.hrs.sum() > 0 else _pos_rate(log, pos, date)
    m = m_games * g.tail(30).hrs.mean()
    a, b, t, L = rate0 * m + S10, m + T10, toi5, float(r.line)
    p = b / (b + t)
    nb_over = 1 - stats.nbinom.cdf(math.floor(L), a, p); nb_under = stats.nbinom.cdf(math.ceil(L) - 1, a, p)
    fmu = S10 / T10 * toi5 if T10 > 0 else np.nan
    return dict(fresh_toi_r5=toi5 * 60, fresh_sog60_r10=S10 / T10 if T10 > 0 else np.nan, fresh_recent_mu=fmu,
                p_fresh_over=1 - stats.poisson.cdf(math.floor(L), fmu), p_fresh_under=stats.poisson.cdf(math.ceil(L) - 1, fmu),
                shrunk_rate0=rate0, shrunk_mu=a / b * t, p_shrunk_over=nb_over, p_shrunk_under=nb_under,
                shrunk_pass_over=nb_over > r.nv_over, shrunk_pass_under=nb_under > 1 - r.nv_over)
def annotate(df, m_games=M_GAMES):
    if not {'nhl_id', 'captured_utc', 'line', 'nv_over'} <= set(df.columns): return df
    extra = pd.DataFrame([one(r, m_games) for r in df.itertuples()], index=df.index)
    return pd.concat([df, extra], axis=1)
