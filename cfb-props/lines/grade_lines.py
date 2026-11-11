"""Grade the free CFB DraftKings game-line track: spread, total, and CLV (open -> close). 0 credits.
For each FBS game on a date (from snapshots.csv):
  open  = first capture of the game (our timestamp); ESPN's own open fields are kept alongside as espn_open_*.
  close = last capture 0-30 min before kickoff; if none, last pre-kickoff capture with close_window_miss=True.
  result= final score from a fresh ESPN scoreboard pull (state=post only; others 'pending').
Outputs per game: home cover / push at open and close spread, over/under/push at open and close total,
  line moves (points, home perspective) and no-vig probability moves at an unchanged line,
  CLV of the open price for each side (no-vig close P of that side minus no-vig open P, only when the line is
  unchanged; otherwise reported in points).
If picks.csv exists (event_id, market[spread|total|ml], side[home|away|over|under], line, price, logged_utc),
each pick is graded W/L/P with units at its price and CLV vs close (points, and no-vig prob at an unchanged line).
Usage: python3 grade_lines.py 20261017   -> graded_<date>.csv (+ graded_picks_<date>.csv) and a summary."""
import sys, os, json, urllib.request
import pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); D = sys.argv[1]
URL = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates={d}&groups=80&limit=300'
def imp(a): return np.nan if a is None or pd.isna(a) else (100 / (a + 100) if a > 0 else -a / (-a + 100))
def nv(a, b): pa, pb = imp(a), imp(b); return pa / (pa + pb) if pa == pa and pb == pb else np.nan
S = pd.read_csv(f'{HERE}/snapshots.csv'); S = S[S.date_pt.astype(str) == D]
S = S[(S.state == 'pre') & (S.minutes_to_kickoff > 0) & S.spread_home_line.notna()].sort_values('captured_utc')
SBF = os.environ.get('CFB_SCOREBOARD_FILE')  # tests only: a saved scoreboard JSON instead of a live pull
sb = json.load(open(SBF)) if SBF else json.loads(urllib.request.urlopen(urllib.request.Request(URL.format(d=D), headers={'User-Agent': 'cfb-lines/0.1'}), timeout=30).read())
res = {}
for e in sb['events']:
    tm = {t['homeAway']: t for t in e['competitions'][0]['competitors']}
    res[str(e['id'])] = (e['status']['type']['state'], float(tm['home']['score'] or 0), float(tm['away']['score'] or 0))
out = []
for ev, g in S.groupby(S.event_id.astype(str)):
    o = g.iloc[0]; inw = g[(g.minutes_to_kickoff >= 0) & (g.minutes_to_kickoff <= 30)]
    c = inw.iloc[-1] if len(inw) else g.iloc[-1]
    st, hs, as_ = res.get(ev, ('missing', np.nan, np.nan)); fin = st == 'post'; margin = hs - as_; pts = hs + as_
    r = dict(event_id=ev, game=f'{o.away} @ {o.home}', kickoff_utc=o.kickoff_utc, state=st, home_score=hs if fin else None, away_score=as_ if fin else None,
             open_captured=o.captured_utc, open_min_to_kick=o.minutes_to_kickoff, close_captured=c.captured_utc, close_min_to_kick=c.minutes_to_kickoff,
             close_window_miss=len(inw) == 0, n_captures=len(g),
             spread_open=o.spread_home_line, spread_close=c.spread_home_line, espn_open_spread=o.open_spread_home_line,
             total_open=o.total, total_close=c.total, espn_open_total=o.open_total,
             spread_move_pts=c.spread_home_line - o.spread_home_line, total_move_pts=c.total - o.total,
             nv_home_spread_open=nv(o.spread_home_price, o.spread_away_price), nv_home_spread_close=nv(c.spread_home_price, c.spread_away_price),
             nv_over_open=nv(o.over_price, o.under_price), nv_over_close=nv(c.over_price, c.under_price),
             nv_home_ml_open=nv(o.ml_home, o.ml_away), nv_home_ml_close=nv(c.ml_home, c.ml_away))
    same_s, same_t = r['spread_move_pts'] == 0, r['total_move_pts'] == 0
    r['clv_home_spread_open_prob'] = r['nv_home_spread_close'] - r['nv_home_spread_open'] if same_s else np.nan
    r['clv_over_open_prob'] = r['nv_over_close'] - r['nv_over_open'] if same_t else np.nan
    r['clv_home_ml_prob'] = r['nv_home_ml_close'] - r['nv_home_ml_open']
    if fin:
        for lab, L in (('open', o.spread_home_line), ('close', c.spread_home_line)):
            v = margin + L; r[f'home_cover_{lab}'] = 'push' if v == 0 else ('home' if v > 0 else 'away')
        for lab, L in (('open', o.total), ('close', c.total)):
            r[f'total_result_{lab}'] = 'push' if pts == L else ('over' if pts > L else 'under')
    out.append(r)
if not out: print(f'{D}: no pre-kickoff captures with DK lines (ESPN drops odds after games end; capture before kickoff)'); sys.exit(0)
G = pd.DataFrame(out); G.to_csv(f'{HERE}/graded_{D}.csv', index=False)
fin = G[G.state == 'post']
print(f'{D}: {len(G)} games with DK lines; final {len(fin)}; close-window misses {int(G.close_window_miss.sum())}')
if len(G):
    print(f'  spread moved in {int((G.spread_move_pts != 0).sum())} games (mean |move| {G.spread_move_pts.abs().mean():.2f} pts); total moved in {int((G.total_move_pts != 0).sum())} (mean |move| {G.total_move_pts.abs().mean():.2f})')
if len(fin):
    for lab in ('open', 'close'):
        hc = fin[f'home_cover_{lab}'].value_counts().to_dict(); tr = fin[f'total_result_{lab}'].value_counts().to_dict()
        print(f'  at {lab}: spread {hc}; total {tr}')
    m = fin.spread_move_pts.notna() & (fin.spread_move_pts != 0)
    if m.any():
        # did the side the line moved toward cover the CLOSE number more than half the time? (market-efficiency check)
        tow = np.where(fin.loc[m, 'spread_move_pts'] < 0, 'home', 'away')
        hit = (fin.loc[m, 'home_cover_open'] == tow).mean()
        print(f'  side the spread moved toward covered the OPEN number in {hit:.1%} of {int(m.sum())} moved games')
P = f'{HERE}/picks.csv'
if os.path.exists(P):
    pk = pd.read_csv(P); pk = pk[pk.event_id.astype(str).isin(G.event_id)]
    rows = []
    for _, p in pk.iterrows():
        r = G[G.event_id == str(p.event_id)].iloc[0]; row = dict(p)
        dec = 1 + (p.price / 100 if p.price > 0 else 100 / -p.price)
        if p.market == 'spread':
            Lc = r.spread_close if p.side == 'home' else -r.spread_close
            row['clv_pts'] = p.line - Lc  # + = got a better number than close
            ncl = r.nv_home_spread_close if p.side == 'home' else 1 - r.nv_home_spread_close
            if r.state == 'post':
                v = (r.home_score - r.away_score) * (1 if p.side == 'home' else -1) + p.line
                row['result'] = 'P' if v == 0 else ('W' if v > 0 else 'L')
        elif p.market == 'total':
            row['clv_pts'] = (r.total_close - p.line) * (1 if p.side == 'over' else -1)
            ncl = r.nv_over_close if p.side == 'over' else 1 - r.nv_over_close
            if r.state == 'post':
                t = r.home_score + r.away_score; row['result'] = 'P' if t == p.line else ('W' if (t > p.line) == (p.side == 'over') else 'L')
        else:
            row['clv_pts'] = 0; ncl = r.nv_home_ml_close if p.side == 'home' else 1 - r.nv_home_ml_close
            if r.state == 'post': row['result'] = 'W' if ((r.home_score > r.away_score) == (p.side == 'home')) else 'L'
        row['clv_prob_vs_price'] = (ncl - 1 / dec) if row['clv_pts'] == 0 else np.nan  # close no-vig P minus price's implied P
        row['units'] = {'W': dec - 1, 'L': -1, 'P': 0}.get(row.get('result'), np.nan)
        rows.append(row)
    if rows:
        PG = pd.DataFrame(rows)
        if 'track' not in PG: PG['track'] = 'main'
        PG['track'] = PG.track.fillna('main')
        PG.to_csv(f'{HERE}/graded_picks_{D}.csv', index=False)
        for tk, PGt in PG.groupby('track'):  # each track (e.g. cfb_offnum = off-number converted) is its own paper track
            print(f'  picks [{tk}]: {len(PGt)}; W-L-P {(PGt.result=="W").sum()}-{(PGt.result=="L").sum()}-{(PGt.result=="P").sum()}; units {PGt.units.sum():+.2f}; mean CLV pts {PGt.clv_pts.mean():+.2f}')
