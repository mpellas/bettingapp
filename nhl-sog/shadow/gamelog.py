"""Shadow game-log cache (does NOT touch data/s*.pkl, which feed the frozen model).
Pulls 2026-27 regular-season skater game logs (shots, TOI) from the NHL stats API, Sep 1 -> today (season opened Sep 29; was Oct 1, fixed 2026-10-17),
into shadow/s2026_live.pkl. Free. Usage: python3 shadow/gamelog.py"""
import requests, pandas as pd, datetime as dt, os, time
B = 'https://api.nhle.com/stats/rest/en/skater/summary'
OUT = os.path.join(os.path.dirname(__file__), 's2026_live.pkl')
def pull(a, b):
    e = f'seasonId=20262027 and gameTypeId=2 and gameDate>="{a}" and gameDate<"{b}"'
    d, start = [], 0
    while True:  # API caps at 100 rows per call and ignores limit=-1 (Nov 19, 2026); page with stable sort until total
        for t in range(4):
            try:
                j = requests.get(B, params={'isAggregate': 'false', 'isGame': 'true', 'start': start, 'limit': 100, 'sort': '[{"property":"gameId","direction":"ASC"},{"property":"playerId","direction":"ASC"}]', 'cayenneExp': e}, timeout=60).json(); break
            except Exception:
                if t == 3: raise RuntimeError('NHL stats API failed')
                time.sleep(3)
        d += j['data']; start += 100
        if not j['data'] or start >= j.get('total', 0): return d
def main():
    d0, end, rows = dt.date(2026, 9, 1), dt.date.today() + dt.timedelta(1), []
    while d0 < end:
        d1 = min(d0 + dt.timedelta(5), end); rows += pull(d0, d1); d0 = d1
    df = pd.DataFrame(rows)[['playerId', 'gameId', 'gameDate', 'shots', 'timeOnIcePerGame', 'positionCode', 'teamAbbrev', 'skaterFullName']]
    df = df.drop_duplicates(['playerId', 'gameId'])
    if os.path.exists(OUT) and len(df) < 0.95 * len(pd.read_pickle(OUT)): raise SystemExit(f'refusing to overwrite {OUT}: {len(df)} rows (truncated fetch?)')
    df.to_pickle(OUT)
    print(f'{len(df)} rows, {df.gameDate.min()} .. {df.gameDate.max()} -> {OUT}')
if __name__ == '__main__': main()
