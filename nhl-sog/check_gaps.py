"""Gap check for the NHL SOG game logs (added 2026-10-17: 'there should be no gaps in historic NHL data').
Every completed regular-season game (NHL schedule, api.nhle.com/stats/rest/en/game) in the window must have box-score rows
in data/s*.pkl: both teams present and >= 30 skater rows (normal 36; 34-35 happens when a team dresses fewer skaters).
--box also checks shots per player against the official boxscore (api-web.nhle.com gamecenter/<id>/boxscore).
Exit code 1 with a loud 'GAP CHECK FAILED' line on any gap/mismatch; 0 otherwise. Free; no Odds API.
Usage: .venv/bin/python check_gaps.py [--days N (default 14; 0 = all seasons in data/)] [--box]"""
import sys, glob, datetime as dt, requests, pandas as pd, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
days = int(sys.argv[sys.argv.index('--days') + 1]) if '--days' in sys.argv else 14
today = dt.date.today().isoformat(); start = (dt.date.today() - dt.timedelta(days)).isoformat() if days else '2021-09-01'
df = pd.concat([pd.read_pickle(f) for f in sorted(glob.glob('data/s*.pkl'))])
g = pd.DataFrame(requests.get('https://api.nhle.com/stats/rest/en/game', params={'cayenneExp': f'gameType=2 and gameDate>="{start}" and gameDate<"{today}"'}, timeout=60).json()['data'])
g = g[g.season >= 20212022] if len(g) else g
fin = g[g.gameStateId.isin([6, 7]) & (g.gameScheduleStateId == 1)] if len(g) else g
c = df.groupby('gameId').agg(n=('playerId', 'size'), teams=('teamAbbrev', 'nunique'))
problems = []
for r in fin.itertuples():
    if r.id not in c.index: problems.append(f'{r.gameDate} game {r.id}: NO box-score rows')
    elif c.loc[r.id, 'teams'] < 2 or c.loc[r.id, 'n'] < 30: problems.append(f'{r.gameDate} game {r.id}: only {c.loc[r.id, "n"]} rows / {c.loc[r.id, "teams"]} teams')
if len(g):
    notfin = g[~g.id.isin(fin.id) & (g.gameScheduleStateId == 1)]
    problems += [f'{r.gameDate} game {r.id}: not final on the NHL schedule (state {r.gameStateId})' for r in notfin.itertuples()]
nbox = 0
if '--box' in sys.argv:
    for gid in fin.id:
        if gid not in c.index: continue
        b = requests.get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore', timeout=30).json()['playerByGameStats']
        off = {p['playerId']: p['sog'] for s in ('awayTeam', 'homeTeam') for grp in ('forwards', 'defense') for p in b[s][grp] if p['toi'] != '00:00'}  # dressed with 0:00 TOI = did not play; the stats feed omits them (11 such rows 2021-26), not a gap
        ours = df[df.gameId == gid].set_index('playerId').shots.to_dict(); nbox += 1
        miss = set(off) - set(ours); bad = [p for p in set(off) & set(ours) if off[p] != ours[p]]
        if miss: problems.append(f'game {gid}: {len(miss)} boxscore skaters missing from our rows {sorted(miss)[:5]}')
        if bad: problems.append(f'game {gid}: shots differ from boxscore for {len(bad)} players {bad[:5]}')
print(f'gap check {start}..{today} (excl.): {len(fin)} completed games, {nbox} checked vs boxscore, {len(problems)} problems')
if problems:
    print('GAP CHECK FAILED:\n  ' + '\n  '.join(problems), file=sys.stderr); sys.exit(1)
print('gap check OK')
