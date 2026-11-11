"""Extra evidence tests (added 2026-11-09, room request). DISPLAY ONLY: never changes agrees_n, status, gates or ranking.
agrees_n stays 'N of 7' (evidence.py). This module adds sig_x_* columns plus agrees_all_n / tests_all_n
('N of M', M = 7 + number of extra tests) and evidence_all_summary. Each extra test is + / - / 0 (0 = neutral or no data).
Extra tests (owner in brackets; each is cross-checked by another agent):
  hit    [Yinzer]  player's hit rate at THIS line and side, this season (>= 5 games) AND last 10 games, vs DK no-vig P(side):
                   + if both are >= no-vig + 5 pts, - if both are <= no-vig - 5 pts, else 0.
  books  [Yinzer]  book agreement (fixed 2026-11-09 after Tester1 xcheck): raw two-sided Fliff pulls already on disk
                   (captures/fliff_<date>_<HHMM>_*.json, pulls at or before the pass only; no new credits). Same line: Fliff
                   NO-VIG P(side) vs DK no-vig, +/- at > 2 pts. Different line: + if Fliff's line is harder for the side, - if
                   easier. 0 if no Fliff pull before the pass (the usual case at sheet time).
                   PrizePicks blocks automated reads (403), so it is not used.
  rest   [Tester2] back-to-backs from the NHL schedule (api.nhle.com/stats/rest/en/game, one call per season, cached
                   per run). Player's team = the team in this game that also played his last logged game. Over: - if his
                   team played the day before and the opponent did not; + if the opponent did and his team did not;
                   0 if both or neither (under flips). 0 with a reason if the schedule or team can't be found.
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

def _norm(x):
    import unicodedata, re
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode().lower())

def _fliff(date, asof_hhmm):
    """2026-11-09 fix (Tester1 xcheck): read the raw two-sided Fliff pulls (captures/fliff_<date>_<HHMM>_*.json) made at or
    before the pass (HHMM PT <= asof_hhmm), newest first. Returns {(player_norm): {point: (over, under)}}."""
    import json
    fs = sorted(glob.glob(os.path.join(HERE, 'captures', f'fliff_{date}_*.json')))
    fs = [f for f in fs if os.path.basename(f).split('_')[2] <= asof_hhmm]
    out = {}
    for f in fs:  # oldest -> newest, later pulls overwrite
        try: d = json.load(open(f))
        except Exception: continue
        for bk in d.get('bookmakers', []):
            if bk.get('key') != 'fliff': continue
            for m in bk.get('markets', []):
                if m.get('key') != 'player_shots_on_goal': continue
                tmp = {}
                for o in m.get('outcomes', []):
                    tmp.setdefault((_norm(o.get('description')), float(o['point'])), {})[o['name'].lower()] = o['price']
                for (p, pt), v in tmp.items():
                    if 'over' in v and 'under' in v: out.setdefault(p, {})[pt] = (v['over'], v['under'])
    return out

def books(r, side, ctx):
    lines = ctx['fliff'].get(_norm(r['player']))
    if not lines: return 0, 'book agreement n/a (no Fliff pull before the pass)'
    ln = float(r['line']); o = side == 'over'
    if ln in lines:
        fo, fu = lines[ln]
        try: po, pu = _am2p(fo), _am2p(fu)
        except Exception: return 0, 'book agreement n/a (bad Fliff price)'
        nvf = po / (po + pu); nvf = nvf if o else 1 - nvf
        nvd = r['nv_over'] if o else 1 - r['nv_over']; d = nvf - nvd
        return (1 if d > 0.02 else (-1 if d < -0.02 else 0)), f'Fliff no-vig {nvf*100:.0f}% vs DK no-vig {nvd*100:.0f}% at {ln:g} ({d*100:+.1f} pts)'
    fl = min(lines, key=lambda x: abs(x - ln))
    lean = (fl > ln) if o else (fl < ln)   # a harder line for the side = Fliff expects the side more
    return (1 if lean else -1), f'Fliff line {fl:g} vs DK {ln:g} ' + ('leans toward' if lean else 'leans away from') + ' side'

_SCHED = {}

def _schedule(iso):
    y = int(iso[:4]); ss = f'{y}{y+1}' if int(iso[5:7]) >= 9 else f'{y-1}{y}'
    if ss not in _SCHED:
        import requests
        d = requests.get('https://api.nhle.com/stats/rest/en/game', params={'cayenneExp': f'gameType=2 and season={ss}'}, timeout=60).json()['data']
        G = pd.DataFrame(d)[['id', 'gameDate', 'homeTeamId', 'visitingTeamId']]
        played = {}
        for gd, h, v in zip(G.gameDate, G.homeTeamId, G.visitingTeamId):
            played.setdefault(gd, set()).update((h, v))
        _SCHED[ss] = ({int(i): (h, v) for i, h, v in zip(G.id, G.homeTeamId, G.visitingTeamId)}, played)
    return _SCHED[ss]

def rest(r, side, ctx):
    try: teams, played = _schedule(ctx['iso'])
    except Exception as e: return 0, f'rest n/a (schedule: {e})'
    gid = r.get('gameId'); g = teams.get(int(gid)) if pd.notna(gid) else None
    if g is None: return 0, 'rest n/a (game not in schedule)'
    L = ctx['logs']; last = L[(L.playerId == r['nhl_id']) & (L.gameDate < ctx['iso'])].sort_values('gameDate').tail(1)
    if last.empty or int(last.gameId.iloc[0]) not in teams: return 0, 'rest n/a (no prior game for team)'
    common = set(g) & set(teams[int(last.gameId.iloc[0])])
    if len(common) != 1: return 0, 'rest n/a (team unclear)'
    me = common.pop(); op = g[1] if g[0] == me else g[0]
    prev = (pd.Timestamp(ctx['iso']) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); y = played.get(prev, set())
    mb, ob = me in y, op in y
    v = -1 if (mb and not ob) else (1 if (ob and not mb) else 0)
    if side != 'over': v = -v
    why = ('both teams on a back-to-back' if mb and ob else 'his team on a back-to-back, opponent rested' if mb
           else 'opponent on a back-to-back, his team rested' if ob else 'no back-to-back')
    return v, f'rest: {why}'

EXTRA = {'hit': hit, 'books': books, 'rest': rest}
# 2026-11-09: Tester1 shot attempts + game total (cross-checked by Tester2), display only -> N of 12
try:
    import tester1_extra; EXTRA.update(tester1_extra.EXTRA_T1)
except Exception as _e:
    print(f'tester1 extra tests skipped: {_e}')


def annotate(picks, date, base=None, logs=None, asof_hhmm=None):
    """picks: D rows (nhl_id, line, nv_over, over, under, player). base: evidence.annotate output (for agrees_n).
    Returns one row per (nhl_id, line, side) with sig_x_*, agrees_all_n, tests_all_n, evidence_all_summary."""
    if logs is None:
        import shrink; logs = shrink.gamelogs()
    if asof_hhmm is None:  # leak guard: only pulls at or before the newest D capture in these picks
        t = pd.to_datetime(picks.get('captured_utc'), utc=True, errors='coerce').max() if 'captured_utc' in picks else pd.NaT
        asof_hhmm = (t).tz_convert('America/Los_Angeles').strftime('%H%M') if pd.notna(t) else '2359'
    ctx = dict(logs=logs, iso=f'{date[:4]}-{date[4:6]}-{date[6:]}', fliff=_fliff(date, asof_hhmm))
    b = {} if base is None else {(int(a), float(l), s): n for a, l, s, n in zip(base.nhl_id, base.line, base.side, base.agrees_n)}
    out = []
    for _, r in picks.iterrows():
        for side in ('over', 'under'):
            res = {k: f(r, side, ctx) for k, f in EXTRA.items()}
            n7 = b.get((int(r['nhl_id']), float(r['line']), side))
            pro = [w for s, w in res.values() if s > 0]; con = [w for s, w in res.values() if s < 0]
            na = [(w if 'schedule' in w else k) for k, (s, w) in res.items() if s == 0 and 'n/a' in str(w)]
            nx = len(pro); tot = 7 + len(EXTRA)
            out.append(dict(nhl_id=r['nhl_id'], line=r['line'], side=side,
                            **{f'sig_x_{k}': {1: '+', -1: '-', 0: '0'}[s] for k, (s, w) in res.items()},
                            agrees_all_n=(None if n7 is None or pd.isna(n7) else int(n7) + nx), tests_all_n=tot,
                            evidence_all_summary=(f'with new tests: agrees {"?" if n7 is None else int(n7) + nx} of {tot}'
                                                  + (f' (new: {"; ".join(pro)})' if pro else '')
                                                  + (f'; new against: {"; ".join(con)}' if con else '')
                                                  + (f'; n/a: {", ".join(na)}' if na else ''))))
    return pd.DataFrame(out)
