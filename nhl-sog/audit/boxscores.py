"""Official per-player boxscore rows (api-web.nhle.com gamecenter/<id>/boxscore; free) for every completed
regular-season game since 2021-22 -> audit/boxscores.pkl (playerId, gameId, gameDate, team, sog, toi_s, pos).
Incremental: games already cached are skipped. Usage: .venv/bin/python audit/boxscores.py [--since YYYY-MM-DD]"""
import requests, pandas as pd, os, sys, time, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'boxscores.pkl')
def schedule():
    d = requests.get('https://api.nhle.com/stats/rest/en/game', params={'cayenneExp': 'season>=20212022 and gameType=2'}, timeout=60).json()['data']
    return pd.DataFrame(d)
def box(gid):
    for t in range(5):
        try:
            r = requests.get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore', timeout=(10, 30))
            if r.status_code == 429: time.sleep(5 * (t + 1)); continue
            b = r.json(); break
        except Exception: time.sleep(2 * (t + 1))
    else: return gid, None, []
    rows = []
    for side in ('awayTeam', 'homeTeam'):
        ab = b[side]['abbrev']; opp = b['homeTeam' if side == 'awayTeam' else 'awayTeam']['abbrev']
        for grp in ('forwards', 'defense'):
            for p in b.get('playerByGameStats', {}).get(side, {}).get(grp, []):
                m, s = p['toi'].split(':')
                rows.append(dict(playerId=p['playerId'], gameId=gid, gameDate=b['gameDate'], team=ab, opp=opp, sog=p['sog'],
                                 toi_s=int(m) * 60 + int(s), pos=p['position'], name=p['name']['default']))
    return gid, b.get('gameState'), rows
if __name__ == '__main__':
    since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else '2000-01-01'
    g = schedule(); fin = g[g.gameStateId.isin([6, 7]) & (g.gameScheduleStateId == 1) & (g.gameDate >= since)]
    old = pd.read_pickle(OUT) if os.path.exists(OUT) else pd.DataFrame(columns=['gameId'])
    todo = sorted(set(fin.id) - set(old.gameId)); print(len(fin), 'final games;', len(todo), 'to fetch', flush=True)
    rows, bad = [], []
    with cf.ThreadPoolExecutor(8) as ex:
        for i, (gid, st, rr) in enumerate(ex.map(box, todo)):
            if st not in ('OFF', 'FINAL') or not rr: bad.append((gid, st))
            else: rows += rr
            if i % 500 == 0: print(i, flush=True)
    new = pd.concat([old, pd.DataFrame(rows)], ignore_index=True).drop_duplicates(['playerId', 'gameId'])
    new.to_pickle(OUT); print('saved', len(new), 'rows', new.gameId.nunique(), 'games; failed', bad)
