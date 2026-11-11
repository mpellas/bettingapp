"""Fetch PRE-GAME context for the NFL challenger (free sources, cached in sidecars/evidence/cache):
  open_lines.csv : ESPN core odds per game, first provider: OPENING spread (home favoured by) and total.
                   (ESPN keeps open/close for past NFL games; 'open' is what we use, never close/current.)
  wx_fc.csv      : Open-Meteo HISTORICAL-FORECAST archive (2022+) at the home stadium for the kickoff hour: wind, temp,
                   precipitation. This archive stitches each model run's first forecast hours, i.e. short-lead
                   forecasts known before kickoff (not observations); before 2022 it does not exist -> NaN.
  injuries/stats 2018-2023 nflverse files (2024-2026 already in the evidence cache).
Usage: .venv/bin/python sidecars/challenger/fetch_pregame.py [--seasons 2019-2026]"""
import os, sys, json, time, argparse, concurrent.futures as cf
import numpy as np, pandas as pd, requests
HERE = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.abspath(os.path.join(HERE, '..', 'evidence', 'cache'))
GH = 'https://github.com/nflverse/nflverse-data/releases/download'
ODDS = 'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{e}/competitions/{e}/odds'
# home stadium coordinates (approximate; weather only matters outdoors)
XY = {'ARI': (33.53, -112.26), 'ATL': (33.76, -84.40), 'BAL': (39.28, -76.62), 'BUF': (42.77, -78.79), 'CAR': (35.23, -80.85),
      'CHI': (41.86, -87.62), 'CIN': (39.10, -84.52), 'CLE': (41.51, -81.70), 'DAL': (32.75, -97.09), 'DEN': (39.74, -105.02),
      'DET': (42.34, -83.05), 'GB': (44.50, -88.06), 'HOU': (29.68, -95.41), 'IND': (39.76, -86.16), 'JAX': (30.32, -81.64),
      'KC': (39.05, -94.48), 'LV': (36.09, -115.18), 'OAK': (37.75, -122.20), 'LAC': (33.95, -118.34), 'LA': (33.95, -118.34),
      'MIA': (25.96, -80.24), 'MIN': (44.97, -93.26), 'NE': (42.09, -71.26), 'NO': (29.95, -90.08), 'NYG': (40.81, -74.07),
      'NYJ': (40.81, -74.07), 'PHI': (39.90, -75.17), 'PIT': (40.45, -80.02), 'SF': (37.40, -121.97), 'SEA': (47.60, -122.33),
      'TB': (27.98, -82.50), 'TEN': (36.17, -86.77), 'WAS': (38.91, -76.86)}
def num(x):
    try: return float(str(x).replace('+', ''))
    except Exception: return np.nan
def parse_odds(d):
    for it in d.get('items', []):
        if 'Live' in (it.get('provider') or {}).get('name', ''): continue
        ho = ((it.get('homeTeamOdds') or {}).get('open') or {}).get('pointSpread') or {}
        to = ((it.get('open') or {}).get('total') or {})
        sp, tot = num(ho.get('alternateDisplayValue', ho.get('american'))), num(to.get('alternateDisplayValue', to.get('american')))
        return dict(provider=it['provider']['name'], open_home_fav=-sp if sp == sp else np.nan, open_total=tot,
                    cur_home_fav=-num(it.get('spread')), cur_total=num(it.get('overUnder')))
    return {}
def get_odds(e):
    for i in range(3):
        try:
            r = requests.get(ODDS.format(e=e), timeout=20)
            if r.status_code == 200: return dict(espn=str(e), **parse_odds(r.json()))
            if r.status_code == 404: return dict(espn=str(e))
        except Exception: time.sleep(1 + i)
    return dict(espn=str(e))
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--seasons', default='2019-2026'); a = ap.parse_args()
    s0, s1 = map(int, a.seasons.split('-'))
    for s in range(2018, 2024):
        for u in (f'injuries/injuries_{s}.parquet', f'stats_player/stats_player_week_{s}.parquet', f'snap_counts/snap_counts_{s}.parquet'):
            p = os.path.join(CACHE, os.path.basename(u))
            if not os.path.exists(p):
                r = requests.get(f'{GH}/{u}', timeout=120); r.raise_for_status(); open(p, 'wb').write(r.content)
    g = pd.read_csv(os.path.join(CACHE, 'games.csv'))
    g = g[(g.season.between(s0, s1)) & (g.game_type == 'REG') & g.espn.notna() & (pd.to_datetime(g.gameday) <= pd.Timestamp.today() + pd.Timedelta(days=9))]
    P = os.path.join(CACHE, 'open_lines.csv'); have = pd.read_csv(P, dtype={'espn': str}) if os.path.exists(P) else pd.DataFrame(columns=['espn'])
    done = set(have.espn[have.get('open_total', pd.Series(dtype=float)).notna()]) if len(have) else set()
    todo = [str(int(e)) for e in g.espn if str(int(e)) not in done]
    with cf.ThreadPoolExecutor(8) as ex: rows = list(ex.map(get_odds, todo))
    O = pd.concat([have[have.espn.isin(done)], pd.DataFrame(rows)], ignore_index=True); O.to_csv(P, index=False)
    print(f'open lines: {O.open_total.notna().sum()} of {len(O)} games with an opening total')
    # weather: one historical-forecast request per home team per season (hourly, kickoff hour picked locally)
    W = os.path.join(CACHE, 'wx_fc.csv'); wrows = []
    gw = g[(g.season >= 2022) & (g.roof.isin(['outdoors', 'open'])) & (g.location != 'Neutral')]
    for (s, h), x in gw.groupby(['season', 'home_team']):
        if h not in XY: continue
        la, lo = XY[h]; st, en = x.gameday.min(), min(x.gameday.max(), str(pd.Timestamp.today().date()))
        if st > en: continue
        try:
            d = requests.get('https://historical-forecast-api.open-meteo.com/v1/forecast', params=dict(latitude=la, longitude=lo,
                start_date=st, end_date=en, hourly='wind_speed_10m,temperature_2m,precipitation', wind_speed_unit='mph',
                temperature_unit='fahrenheit', timezone='America/New_York'), timeout=60).json()['hourly']
        except Exception as e:
            print('wx fail', s, h, e); continue
        H = pd.DataFrame(d); H['time'] = pd.to_datetime(H.time)
        for r in x.itertuples():
            k = pd.Timestamp(f'{r.gameday} {r.gametime}').floor('h')   # nflverse gametime is US/Eastern
            m = H[H.time == k]
            if len(m): wrows.append(dict(game_id=r.game_id, wind_fc=m.wind_speed_10m.iloc[0], temp_fc=m.temperature_2m.iloc[0],
                                          precip_fc=H[(H.time >= k) & (H.time < k + pd.Timedelta(hours=3))].precipitation.sum()))
    pd.DataFrame(wrows).to_csv(W, index=False); print(f'weather forecasts: {len(wrows)} outdoor games (2022+)')
if __name__ == '__main__': main()
