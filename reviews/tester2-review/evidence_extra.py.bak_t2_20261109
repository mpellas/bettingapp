"""Extra evidence tests (added 2026-11-09, room request). DISPLAY ONLY: never changes agrees_n, status, gates or ranking.
agrees_n stays 'N of 7' (evidence.py). This module adds sig_x_* columns plus agrees_all_n / tests_all_n
('N of M', M = 7 + number of extra tests) and evidence_all_summary. Each extra test is + / - / 0 (0 = neutral or no data).
Extra tests (owner in brackets; each is cross-checked by another agent):
  hit    [Yinzer]  player's hit rate at THIS line and side, this season (>= 5 games) AND last 10 games, vs DK no-vig P(side):
                   + if both are >= no-vig + 5 pts, - if both are <= no-vig - 5 pts, else 0.
  books  [Yinzer]  book agreement: Fliff price/line already pulled for this side (fliff_prices/<date>_*.csv; no new credits)
                   vs DK at D. + if Fliff's line or price leans toward the side (implied P(side) > DK's by > 2 pts at the same
                   line, or a line that is harder for the side), - if it leans away, 0 if no Fliff pull exists (usual case).
                   PrizePicks blocks automated reads (403), so it is not used.
Other owners add functions to EXTRA as f(r, side, ctx) -> (sign, why)."""
import os, glob
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
HIT_BAND, MIN_SEASON_G = 0.05, 5

def _am2p(a):
    a = float(a); return -a / (-a + 100) if a < 0 else 100 / (a + 100)

def _season_start(iso):
    return f'{iso[:4]}-09-01' if int(iso[5:7]) >= 9 else f'{int(iso[:4])-1}-09-01'

def hit(r, side, ctx):
    L = ctx['logs']; iso = ctx['iso']
    g = L[(L.playerId == r['nhl_id']) & (L.gameDate < iso)].sort_values('gameDate')
    cur = g[g.gameDate >= _season_start(iso)]
    if len(cur) < MIN_SEASON_G: return 0, f'hit rate n/a (< {MIN_SEASON_G} games this season)'
    o = side == 'over'; ln = float(r['line'])
    f = (lambda s: s > ln) if o else (lambda s: s < ln)
    hs = f(cur.shots).mean(); l10 = g.tail(10); h10 = f(l10.shots).mean()
    nv = r['nv_over'] if o else 1 - r['nv_over']
    why = (f'{side} {ln:g} hit {f(cur.shots).sum()} of {len(cur)} this season ({hs*100:.0f}%), '
           f'{f(l10.shots).sum()} of {len(l10)} last 10 ({h10*100:.0f}%) vs no-vig {nv*100:.0f}%')
    if hs >= nv + HIT_BAND and h10 >= nv + HIT_BAND: return 1, why
    if hs <= nv - HIT_BAND and h10 <= nv - HIT_BAND: return -1, why
    return 0, why

def _fliff(date):
    fs = sorted(glob.glob(os.path.join(HERE, 'fliff_prices', f'{date}_*.csv')))
    if not fs: return {}
    F = pd.concat([pd.read_csv(f) for f in fs]).sort_values('capture_time_pt')
    F = F[F.fliff_price.notna()]
    return {(int(a), str(s).lower()): (float(l), float(p)) for a, s, l, p in zip(F.nhl_id, F.side, F.fliff_line, F.fliff_price)}

def books(r, side, ctx):
    k = (int(r['nhl_id']), side); fl = ctx['fliff'].get(k)
    if fl is None: return 0, 'book agreement n/a (no Fliff pull for this side)'
    fline, fprice = fl; ln = float(r['line']); o = side == 'over'
    if fline != ln:
        lean = (fline > ln) if o else (fline < ln)   # a harder line for the side = Fliff expects the side more
        return (1 if lean else -1), f'Fliff line {fline:g} vs DK {ln:g} ' + ('leans toward' if lean else 'leans away from') + ' side'
    dk = r['over'] if o else r['under']
    try: d = _am2p(fprice) - _am2p(dk)
    except Exception: return 0, 'book agreement n/a (DK price missing)'
    why = f'Fliff {int(fprice):+d} vs DK {dk} at {ln:g} ({d*100:+.1f} pts)'
    return (1 if d > 0.02 else (-1 if d < -0.02 else 0)), why

EXTRA = {'hit': hit, 'books': books}

def annotate(picks, date, base=None, logs=None):
    """picks: D rows (nhl_id, line, nv_over, over, under, player). base: evidence.annotate output (for agrees_n).
    Returns one row per (nhl_id, line, side) with sig_x_*, agrees_all_n, tests_all_n, evidence_all_summary."""
    if logs is None:
        import shrink; logs = shrink.gamelogs()
    ctx = dict(logs=logs, iso=f'{date[:4]}-{date[4:6]}-{date[6:]}', fliff=_fliff(date))
    b = {} if base is None else {(int(a), float(l), s): n for a, l, s, n in zip(base.nhl_id, base.line, base.side, base.agrees_n)}
    out = []
    for _, r in picks.iterrows():
        for side in ('over', 'under'):
            res = {k: f(r, side, ctx) for k, f in EXTRA.items()}
            n7 = b.get((int(r['nhl_id']), float(r['line']), side))
            pro = [w for s, w in res.values() if s > 0]; con = [w for s, w in res.values() if s < 0]
            nx = len(pro); tot = 7 + len(EXTRA)
            out.append(dict(nhl_id=r['nhl_id'], line=r['line'], side=side,
                            **{f'sig_x_{k}': {1: '+', -1: '-', 0: '0'}[s] for k, (s, w) in res.items()},
                            agrees_all_n=(None if n7 is None or pd.isna(n7) else int(n7) + nx), tests_all_n=tot,
                            evidence_all_summary=(f'with new tests: agrees {"?" if n7 is None else int(n7) + nx} of {tot}'
                                                  + (f' (new: {"; ".join(pro)})' if pro else '')
                                                  + (f'; new against: {"; ".join(con)}' if con else ''))))
    return pd.DataFrame(out)
