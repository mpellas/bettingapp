"""Shadow game-log cache (does NOT touch data/s*.pkl, which feed the frozen model).
Pulls 2026-27 regular-season skater game logs (shots, TOI) from the NHL stats API, Sep 1 -> today (season opened Sep 29; was Oct 1, fixed 2026-10-17),
into shadow/s2026_live.pkl. Free. Usage: python3 shadow/gamelog.py"""
import requests, pandas as pd, datetime as dt, os, time
B = 'https://api.nhle.com/stats/rest/en/skater/summary'
OUT = os.path.join(os.path.dirname(__file__), 's2026_live.pkl')
def pull(a, b):
    e = f'seasonId=20262027 and gameTypeId=2 and gameDate>="{a}" and gameDate<"{b}"'
    for t in range(4):
        try:
            return requests.get(B, params={'isAggregate': 'false', 'isGame': 'true', 'limit': -1, 'cayenneExp': e}, timeout=60).json()['data']
        except Exception:
            time.sleep(3)
    raise RuntimeError('NHL stats API failed')
def main():
    d0, end, rows = dt.date(2026, 9, 1), dt.date.today() + dt.timedelta(1), []
    while d0 < end:
        d1 = min(d0 + dt.timedelta(5), end); rows += pull(d0, d1); d0 = d1
    df = pd.DataFrame(rows)[['playerId', 'gameId', 'gameDate', 'shots', 'timeOnIcePerGame', 'positionCode', 'teamAbbrev', 'skaterFullName']]
    df = df.drop_duplicates(['playerId', 'gameId']); df.to_pickle(OUT)
    print(f'{len(df)} rows, {df.gameDate.min()} .. {df.gameDate.max()} -> {OUT}')
if __name__ == '__main__': main()
