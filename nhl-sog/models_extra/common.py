"""Shared helpers for the extra NHL paper models (points, puckline, saves)."""
import os, json, math
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, 'data')
MOD = os.path.join(HERE, 'models')
SHADOW = os.path.join(HERE, 'shadow')
os.makedirs(DATA, exist_ok=True)
os.makedirs(MOD, exist_ok=True)
os.makedirs(SHADOW, exist_ok=True)

# Price band: enforced only at the -150 end. -155 or worse is outside. Plus money is inside.
BAND_FLOOR = -150


def in_band(price):
    if price is None or (isinstance(price, float) and math.isnan(price)):
        return False
    return float(price) >= BAND_FLOOR


def am2p(a):
    a = float(a)
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def units(price, res):
    if price is None or (isinstance(price, float) and math.isnan(price)) or res not in ('win', 'loss', 'push'):
        return None
    a = float(price)
    return 0.0 if res == 'push' else -1.0 if res == 'loss' else (a / 100 if a > 0 else 100 / -a)


def eastern_date(utc_iso):
    """NHL gameDate is the local/ET calendar date of the start, not the UTC date folder."""
    ts = pd.to_datetime(utc_iso, utc=True)
    return ts.tz_convert('America/New_York').strftime('%Y-%m-%d')


def load_idmap():
    p = os.path.join(ROOT, 'captures', 'idmap.json')
    if not os.path.exists(p):
        return {}
    raw = json.load(open(p))
    return {str(k): (int(v) if v is not None else None) for k, v in raw.items()}


def summarize_bets(df, price_col='price_D', result_col='result', label=''):
    """W-L, units, ROI vs break-even at real prices. df must already be the taken sides."""
    d = df[df[price_col].notna() & df[result_col].isin(['win', 'loss', 'push'])].copy()
    if not len(d):
        return {'label': label, 'n': 0, 'wins': 0, 'losses': 0, 'pushes': 0,
                'hit_rate': None, 'units': None, 'roi': None, 'avg_breakeven': None, 'note': 'no priced graded sides'}
    d['u'] = [units(p, r) for p, r in zip(d[price_col], d[result_col])]
    w = int((d[result_col] == 'win').sum())
    l = int((d[result_col] == 'loss').sum())
    p = int((d[result_col] == 'push').sum())
    u = float(pd.Series(d['u']).sum())
    n_decided = w + l
    be = float(d[price_col].map(am2p).mean()) if len(d) else None
    return {
        'label': label, 'n': int(len(d)), 'wins': w, 'losses': l, 'pushes': p,
        'hit_rate': round(w / n_decided, 4) if n_decided else None,
        'units': round(u, 2), 'roi': round(u / len(d), 4) if len(d) else None,
        'avg_breakeven': round(be, 4) if be is not None else None,
    }


def leakage_check(df, feat_cols, date_col='date', outcome_cols=None, key=None):
    """Corrupt post-cutoff outcomes and assert features on the cutoff day are unchanged."""
    outcome_cols = outcome_cols or []
    key = key or ['playerId', 'gameId']
    cut = df[date_col].sort_values().iloc[len(df) // 2]
    t = df.copy()
    fut = t[date_col] >= cut
    for c in outcome_cols:
        if c in t.columns:
            t.loc[fut, c] = 999
    return cut, t, key, feat_cols
