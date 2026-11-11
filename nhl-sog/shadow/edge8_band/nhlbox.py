"""NHL.com box-score grader shared by the nightly shadow trackers (paper only). Free api-web.nhle.com, no Odds API."""
import os, json, urllib.request
import pandas as pd
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'box_cache')
def box(gid):
    gid = int(gid); f = os.path.join(CACHE, f'{gid}.json')
    if os.path.exists(f):
        d = json.load(open(f))
        if d.get('gameState') in ('OFF', 'FINAL'): return d
    d = json.load(urllib.request.urlopen(urllib.request.Request(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore', headers={'User-Agent': 'Mozilla/5.0'}), timeout=30))
    if d.get('gameState') in ('OFF', 'FINAL'): json.dump(d, open(f, 'w'))
    return d
def start_utc(gid): return pd.Timestamp(box(gid)['startTimeUTC'])
def sog(gid):
    """{nhl_id: shots} for a finished game, else None."""
    d = box(gid)
    if d.get('gameState') not in ('OFF', 'FINAL'): return None
    out = {}
    for t in ('awayTeam', 'homeTeam'):
        for grp in ('forwards', 'defense'):
            for p in d.get('playerByGameStats', {}).get(t, {}).get(grp, []): out[int(p['playerId'])] = float(p.get('sog', 0))
    return out
def dec(a): a = float(a); return 1 + a/100 if a > 0 else 1 + 100/-a
def grade(df, price_cols=('dk_price',)):
    """adds actual, result (W/L/P/DNP/PENDING) and u_<price col> (1u flat)."""
    df = df.copy(); acts = []
    for n, g in zip(df.nhl_id, df.gameId):
        s = sog(g); acts.append('PENDING' if s is None else s.get(int(n), 'DNP'))
    df['actual'] = acts; res = []
    for a, l, sd in zip(df.actual, df.line, df.side.str.lower()):
        if a in ('PENDING', 'DNP'): res.append(a); continue
        res.append('P' if a == l else ('W' if ((a > l) if sd == 'over' else (a < l)) else 'L'))
    df['result'] = res
    for c in price_cols:
        df['u_' + c] = [(dec(p) - 1) if r == 'W' else (-1.0 if r == 'L' else 0.0 if r == 'P' else float('nan')) for r, p in zip(df.result, df[c])]
    return df
def summary(df, mask, ucol):
    x = df[mask]; g = x[x.result.isin(['W', 'L', 'P'])]
    w, l = int((g.result == 'W').sum()), int((g.result == 'L').sum())
    return dict(sides=len(x), graded=len(g), W=w, L=l, units=round(g[ucol].sum(), 2),
                roi_pct=round(100*g[ucol].sum()/max(len(g), 1), 1), pending=int(x.result.isin(['PENDING', 'DNP']).sum()))
def append_tally(path, new, key):
    if os.path.exists(path):
        old = pd.read_csv(path)
        k = lambda d: d[key].astype(str).apply(lambda c: c.str.lower().str.replace(r'\.0$', '', regex=True)).agg('|'.join, axis=1)
        old = old[~k(old).isin(set(k(new)))]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(path, index=False); return new
