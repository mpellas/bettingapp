"""Shot attempts per skater-game from the free NHL play-by-play (api-web gamecenter/<id>/play-by-play):
attempts = goals + shots-on-goal + missed shots + blocked shots, by shootingPlayerId (shootout excluded, periodType SO).
The NHL stats 'realtime' report has totalShotAttempts = null for every 2021-22 game, so this fills that column.
Usage: .venv/bin/python audit/attempts_pbp.py SEASON [N_SAMPLE]  -> audit/attempts_<season>.pkl"""
import requests, pandas as pd, sys, os, time, collections, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
def pbp(gid):
    for t in range(5):
        try: b = requests.get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/play-by-play', timeout=(10, 30)).json(); break
        except Exception: time.sleep(2 * (t + 1))
    else: return gid, None
    c = collections.Counter()
    for p in b['plays']:
        if p['typeDescKey'] in ('goal', 'shot-on-goal', 'missed-shot', 'blocked-shot') and p.get('periodDescriptor', {}).get('periodType') != 'SO':
            sid = p['details'].get('shootingPlayerId') or p['details'].get('scoringPlayerId')
            if sid: c[sid] += 1
    return gid, c
if __name__ == '__main__':
    s = int(sys.argv[1]); d = pd.read_pickle(f'{ROOT}/data/s{s}.pkl'); gids = sorted(d.gameId.unique())
    if len(sys.argv) > 2: gids = gids[::max(1, len(gids) // int(sys.argv[2]))][:int(sys.argv[2])]
    rows, bad = [], []
    with cf.ThreadPoolExecutor(8) as ex:
        for gid, c in ex.map(pbp, gids):
            if c is None: bad.append(gid); continue
            rows += [dict(gameId=gid, playerId=k, att_pbp=v) for k, v in c.items()]
    out = pd.DataFrame(rows); out.to_pickle(f'{HERE}/attempts_{s}{"_sample" if len(sys.argv) > 2 else ""}.pkl')
    print(s, len(gids), 'games', len(out), 'rows; failed', bad)
