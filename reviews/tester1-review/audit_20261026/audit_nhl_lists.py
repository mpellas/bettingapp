"""Tester1 Oct 26 2026 audit: every NHL side posted on a list (picks/<date>[_HHMM]_post.txt 'Fliff check' lines) and on the
final room card (picks/<date>_HHMM_room.txt numbered entries), regraded from fresh NHL box scores (api-web.nhle.com).
Read-only over /workspace/nhl-sog. Units: flat 1u at the posted shop-at (worst acceptable Fliff) price and at the DK price
on the list. CLV: no-vig points for the side, list snapshot -> CLOSE.json, same line only; early_close/capture_gap games excluded."""
import re, glob, os, json, sys, time
import pandas as pd, numpy as np, requests
NS = '/workspace/nhl-sog'; OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, NS); os.chdir(NS)
import close_timing
PAT = re.compile(r'^Fliff check: (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]?\d+), Fliff at ([+-]?\d+) or better\)')
CARD = re.compile(r'^\d+\. (.+?), (.+?) \(.*?\), (OVER|UNDER) ([\d.]+) shots on goal')
dec = lambda a: 1 + (a / 100 if a > 0 else 100 / -a)
def stamp(pf):
    b = os.path.basename(pf).replace('_post.txt', '')
    return b if '_' in b else b + '_AM'
def dfile(st):
    d, hm = st.split('_'); f = f'picks/{d}_D_{hm}.csv'
    return f if os.path.exists(f) else f'picks/{d}_D.csv'
rows = []
for pf in sorted(glob.glob('picks/2026*_post.txt')):
    st = stamp(pf); d = st[:8]
    if d < '20261017': continue
    posted = [PAT.match(l) for l in open(pf)]; posted = [m for m in posted if m]
    rf = pf.replace('_post.txt', '_room.txt'); has_room = os.path.exists(rf)
    room = open(rf).read().splitlines() if has_room else []
    oncard = lambda pl, side, line: (any((pl in l and side in l and str(line) in l) or f'{pl.split()[-1]} {side[0]}{line}' in l for l in room) if has_room else True)  # no room file: the post was the card
    D = pd.read_csv(dfile(st))
    for m in posted:
        pl, side, line, dk, shop = m.group(1), m.group(2), float(m.group(3)), int(m.group(4)), int(m.group(5))
        x = D[(D.player == pl) & (D.line == line)]
        x = x.iloc[-1] if len(x) else None
        rows.append(dict(list=st, date=d, player=pl, side=side, line=line, dk=dk, shop_at=shop,
                         on_card=oncard(pl, side, line), card_source='room' if has_room else 'post',
                         nhl_id=None if x is None else int(x.nhl_id), gameId=None if x is None else int(x.gameId),
                         event=None if x is None else str(x.event), game=None if x is None else x.game,
                         nv_over_list=None if x is None else float(x.nv_over)))
R = pd.DataFrame(rows)
# box scores
BOX = {}
def box(gid):
    if gid in BOX: return BOX[gid]
    for i in range(3):
        try:
            j = requests.get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore', timeout=30).json(); break
        except Exception: time.sleep(2)
    else: BOX[gid] = None; return None
    s = {}
    for t in ('awayTeam', 'homeTeam'):
        pbg = j.get('playerByGameStats', {}).get(t, {})
        for grp in ('forwards', 'defense'):
            for p in pbg.get(grp, []): s[p['playerId']] = p.get('sog', p.get('shots'))
    BOX[gid] = dict(state=j.get('gameState'), sog=s); return BOX[gid]
# cross-check game IDs against /v1/score/<date> (US date of game)
SCORE = {}
for d in sorted(R.date.unique()):
    for dd in (d, (pd.Timestamp(d) + pd.Timedelta(days=1)).strftime('%Y%m%d')):
        iso = f'{dd[:4]}-{dd[4:6]}-{dd[6:]}'
        try:
            for g in requests.get(f'https://api-web.nhle.com/v1/score/{iso}', timeout=30).json().get('games', []): SCORE[g['id']] = g.get('gameState')
        except Exception: pass
acts, states, inscore = [], [], []
for _, r in R.iterrows():
    if pd.isna(r.get('gameId')): acts.append(np.nan); states.append('no D row'); inscore.append(False); continue
    b = box(int(r.gameId)); inscore.append(int(r.gameId) in SCORE)
    if not b: acts.append(np.nan); states.append('box fetch failed'); continue
    states.append(b['state']); v = b['sog'].get(int(r.nhl_id)); acts.append(np.nan if v is None else v)
R['actual'] = acts; R['game_state'] = states; R['gid_in_score'] = inscore
R['hit'] = [np.nan if np.isnan(a) or s not in ('OFF', 'FINAL') else int(a > l if sd == 'OVER' else a < l) for a, s, l, sd in zip(R.actual, R.game_state, R.line, R.side)]
R['u_shop'] = [np.nan if np.isnan(h) else (dec(p) - 1 if h else -1.0) for h, p in zip(R.hit, R.shop_at)]
R['u_dk'] = [np.nan if np.isnan(h) else (dec(p) - 1 if h else -1.0) for h, p in zip(R.hit, R.dk)]
# old graded actual (for reconciliation)
def old_act(r):
    f = f'graded/{r.date}.csv'
    if not os.path.exists(f) or pd.isna(r.get('nhl_id')): return np.nan
    G = pd.read_csv(f); g = G[(G.nhl_id == r.nhl_id) & (G.line == r.line)].actual.dropna()
    return g.iloc[0] if len(g) else np.nan
R['graded_actual'] = [old_act(r) for _, r in R.iterrows()]
# closing line
T = close_timing.all_games()
CL = {}
for f in glob.glob('captures/*/*_CLOSE.json'):
    j = json.load(open(f))
    for l in j.get('closed', []):
        if l.get('market') == 'sog': CL[(str(j['event']), l['nhl_id'], float(l['line']))] = l['nv_over']
ct, clv = [], []
for _, r in R.iterrows():
    t = T.get(r.get('event'), {}).get('close_timing') if r.get('event') else None; ct.append(t)
    c = CL.get((r.get('event'), r.get('nhl_id'), r.line)) if r.get('event') else None
    if c is None or t in ('early_close', 'capture_gap', None) or pd.isna(r.get('nv_over_list')): clv.append(np.nan); continue
    s = 1 if r.side == 'OVER' else -1; clv.append(round(100 * s * (c - r.nv_over_list), 2))
R['close_timing'] = ct; R['clv_pts'] = clv
R['era'] = np.where(R.list >= '20261020_1513', 'post-floor', 'pre-floor')
R.to_csv(f'{OUT}/sides.csv', index=False)
def summ(lbl, r):
    g = r.dropna(subset=['hit']); c = r.dropna(subset=['clv_pts'])
    return dict(slice=lbl, sides=len(r), graded=len(g), WL=f'{int(g.hit.sum())}-{int(len(g)-g.hit.sum())}',
                u_shop=round(g.u_shop.sum(), 2), u_dk=round(g.u_dk.sum(), 2), clv_n=len(c), clv_mean=round(c.clv_pts.mean(), 2) if len(c) else np.nan)
S = [summ('all posted Oct 17-25', R), summ('prior-audit scope (lists Oct 18-24)', R[(R.date >= '20261018') & (R.date <= '20261024')]),
     summ('pre-floor (to 20261020_1508)', R[R.era == 'pre-floor']), summ('post-floor (20261020_1513 on)', R[R.era == 'post-floor']),
     summ('final cards only', R[R.on_card == True])]
for d, r in R.groupby('date'): S.append(summ(d, r))
pd.DataFrame(S).to_csv(f'{OUT}/summary.csv', index=False)
print(pd.DataFrame(S).to_string(index=False))
print(R[['list', 'player', 'side', 'line', 'dk', 'shop_at', 'on_card', 'game_state', 'actual', 'graded_actual', 'hit', 'close_timing', 'clv_pts']].to_string())
