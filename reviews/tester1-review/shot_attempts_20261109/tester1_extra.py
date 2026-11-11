"""Tester1 extra evidence tests (2026-11-09, PAPER / DISPLAY ONLY). Rest/travel was dropped 8:15 AM PT (Tester2 owns it). Drop-in for nhl-sog/evidence_extra.py:
    import tester1_extra; EXTRA.update(tester1_extra.EXTRA_T1)    # -> sig_x_att, sig_x_total; 'N of 12' (current EXTRA is 10)
Each test is f(r, side, ctx) -> (sign, why), sign in {+1, 0, -1}. r = one D row (needs nhl_id, line, game, event).
ctx is evidence_extra's ctx (uses ctx['iso']); this module adds its own caches under ctx['t1'] (logs with attempts, game totals). Definitions and bands: README.md in this folder (fixed before results).
  att    shot attempts: last-10 attempts/60 vs base, and SOG-per-attempt regression; over + / under - (or reverse)
  total  DK game total (ESPN open): >= 6.5 over +, <= 5.5 over -, else 0; under reversed
UNAVAILABLE DATA: the interface only allows sign 0/+1/-1, so a test that cannot score returns (0, 'n/a (<reason>)').
The why text ALWAYS starts with 'n/a' in that case; status(fn, r, side, ctx) -> 'ok' | 'n/a' exposes it, and
NA_PREFIX lets the sheet show 'n/a' instead of '0'. Never a silent 0. Never writes anywhere. Totals come from TOTALS_CSV; a missing event is fetched live from ESPN (in memory only)
unless ctx['t1_no_fetch'] is True."""
import os, glob, json, time, urllib.request
import numpy as np, pandas as pd
T1_DIR = '/workspace/tester1-review/shot_attempts_20261109'   # absolute, so this one file can be copied into nhl-sog as is
NHL = '/workspace/nhl-sog'
TOTALS_CSV = os.path.join(T1_DIR, 'cache', 'espn_totals.csv')
import sys; sys.path.insert(0, T1_DIR)
from att_signal import compute, N_RECENT, N_BASE
TOT_HI, TOT_LO = 6.5, 5.5
NA_PREFIX = 'n/a'

def _logs():
    fs = sorted(glob.glob(f'{NHL}/data/s20*.pkl'))
    df = pd.concat([pd.read_pickle(f) for f in fs]).drop_duplicates(['playerId', 'gameId'])
    df = df[df.timeOnIcePerGame.fillna(0) > 0].copy()
    df['hrs'] = df.timeOnIcePerGame / 3600.0; df['att'] = df.totalShotAttempts.astype(float)
    return df.sort_values(['playerId', 'gameDate', 'gameId']).reset_index(drop=True)

def _t1(ctx):
    if 't1' in ctx: return ctx['t1']
    L = _logs()
    tot = {}
    if os.path.exists(TOTALS_CSV):
        T = pd.read_csv(TOTALS_CSV, dtype={'event': str})
        tot = {e: (o, c) for e, o, c in zip(T.event, T.open_total, T.close_total)}
    ctx['t1'] = dict(logs=L, by={k: v for k, v in L.groupby('playerId')}, tot=tot)
    return ctx['t1']

def att_numbers(r, ctx):
    t = _t1(ctx)
    if pd.isna(r.get('nhl_id')): return None
    g = t['by'].get(int(r['nhl_id']))
    if g is None: return compute(0, 0, 0, 0, 0, 0, 0, 0)
    g = g[g.gameDate < ctx['iso']]
    rr = g.iloc[-N_RECENT:]; b = g.iloc[-(N_RECENT + N_BASE):-N_RECENT] if len(g) > N_RECENT else g.iloc[0:0]
    return compute(rr.shots.sum(), rr.att.sum(), rr.hrs.sum(), b.shots.sum(), b.att.sum(), b.hrs.sum(), len(rr), len(b))

def att(r, side, ctx):
    try: f = att_numbers(r, ctx)
    except Exception as e: return 0, f'n/a (shot-attempt logs unavailable: {type(e).__name__})'
    if f is None: return 0, 'n/a (no NHL id)'
    if f['att_why'].startswith('n/a'): return 0, f"n/a (shot attempts: {f['n_recent']} recent / {f['n_base']} base games, {f['att_r10']:.0f} attempts; needs 10 / 30 / 15)"
    v = f['att_over'] if side == 'over' else -f['att_over']
    return v, 'shot attempts: ' + f['att_why']

def _fetch_total(ev):
    try:
        u = f'https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/{ev}/competitions/{ev}/odds'
        with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15) as h:
            d = json.load(h)
        time.sleep(0.5)
        for it in d.get('items', []):
            if str(it.get('provider', {}).get('id')) == '100':
                f = lambda x: float((x or {}).get('total', {}).get('american')) if (x or {}).get('total') else np.nan
                return f(it.get('open')), f(it.get('close'))
    except Exception: return np.nan, 'fetch_failed'
    return np.nan, np.nan

def total_value(r, ctx):
    t = _t1(ctx); ev = str(r.get('event'))
    if ev in ('', 'nan', 'None'): return np.nan, 'no ESPN event id on the row'
    if ev not in t['tot']:
        if ctx.get('t1_no_fetch'): return np.nan, 'not in totals cache, live fetch off'
        t['tot'][ev] = _fetch_total(ev)
    o, c = t['tot'].get(ev, (np.nan, np.nan))
    if pd.notna(o): return float(o), 'open'
    if isinstance(c, str): return np.nan, 'ESPN odds fetch failed'
    if pd.notna(c): return float(c), 'close'
    return np.nan, 'ESPN feed has no DraftKings total for this game'

def total(r, side, ctx):
    try: v, src = total_value(r, ctx)
    except Exception as e: return 0, f'n/a (game total unavailable: {type(e).__name__})'
    if pd.isna(v): return 0, f'n/a (game total: {src})'
    s = 1 if v >= TOT_HI else (-1 if v <= TOT_LO else 0)
    return (s if side == 'over' else -s), f'DK game total {v:g} ({src})'

EXTRA_T1 = {'att': att, 'total': total}

def status(fn, r, side, ctx):
    return 'n/a' if fn(r, side, ctx)[1].startswith(NA_PREFIX) else 'ok'

def display(fn, r, side, ctx):
    """'+', '-', '0' or 'n/a' for the sheet."""
    s, why = fn(r, side, ctx)
    return 'n/a' if why.startswith(NA_PREFIX) else {1: '+', -1: '-', 0: '0'}[s]
