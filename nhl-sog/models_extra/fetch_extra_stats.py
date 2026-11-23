"""Fetch free NHL stats for the paper points / saves / puckline models.

Writes only under models_extra/data/. Does not touch data/s20xx.pkl, fetch.py,
or challenger/team_games.pkl. Same public api.nhle.com stats API already used
by fetch.py / challenger/fetch_team.py (paged, 10-day chunks).
"""
import os, sys, time, datetime as dt
import requests, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'data')
os.makedirs(OUT, exist_ok=True)
os.chdir(ROOT)

YDAY = (dt.date.today() - dt.timedelta(1)).isoformat()
SEAS = {
    2021: ('2021-10-01', '2022-05-01'),
    2022: ('2022-10-01', '2023-04-20'),
    2023: ('2023-10-01', '2024-04-20'),
    2024: ('2024-10-01', '2025-04-20'),
    2025: ('2025-10-01', '2026-04-20'),
    2026: ('2026-09-01', YDAY),
}
SKATER_COLS = [
    'playerId', 'gameId', 'gameDate', 'skaterFullName', 'positionCode',
    'teamAbbrev', 'opponentTeamAbbrev', 'homeRoad',
    'goals', 'assists', 'points', 'shots', 'timeOnIcePerGame',
    'ppGoals', 'ppPoints', 'evPoints', 'plusMinus',
]
GOALIE_COLS = [
    'playerId', 'gameId', 'gameDate', 'goalieFullName',
    'teamAbbrev', 'opponentTeamAbbrev', 'homeRoad',
    'saves', 'shotsAgainst', 'goalsAgainst', 'timeOnIce',
    'gamesStarted', 'savePct', 'decision' if False else 'wins',
]
# wins is always present; we'll also try to keep gamesStarted
GOALIE_COLS = [
    'playerId', 'gameId', 'gameDate', 'goalieFullName',
    'teamAbbrev', 'opponentTeamAbbrev', 'homeRoad',
    'saves', 'shotsAgainst', 'goalsAgainst', 'timeOnIce',
    'gamesStarted', 'savePct', 'wins', 'losses', 'otLosses', 'shutouts',
]
TEAM_COLS = [
    'gameId', 'gameDate', 'teamAbbrev', 'teamFullName', 'teamId', 'opponentTeamAbbrev', 'homeRoad',
    'goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame',
    'wins', 'losses', 'otLosses', 'winsInRegulation', 'winsInShootout',
    'regulationAndOtWins',
]


def get(kind, rep, season, a, b):
    base = f'https://api.nhle.com/stats/rest/en/{kind}/{rep}'
    exp = f'seasonId={season}{season+1} and gameTypeId=2 and gameDate>="{a}" and gameDate<"{b}"'
    rows, start = [], 0
    while True:
        for t in range(4):
            try:
                j = requests.get(
                    base,
                    params={
                        'isAggregate': 'false', 'isGame': 'true',
                        'start': start, 'limit': 100,
                        'sort': '[{"property":"gameId","direction":"ASC"},{"property":"playerId","direction":"ASC"}]'
                                if kind != 'team' else
                                '[{"property":"gameId","direction":"ASC"}]',
                        'cayenneExp': exp,
                    },
                    timeout=60,
                ).json()
                break
            except Exception as x:
                if t == 3:
                    raise
                print(f'retry {t+1} {kind}/{rep} {a}: {x}', flush=True)
                time.sleep(3)
        data = j.get('data') or []
        rows += data
        start += 100
        if not data or start >= j.get('total', 0):
            break
    return rows


def pick(rows, cols):
    out = []
    for r in rows:
        out.append({k: r.get(k) for k in cols if k in r or True})
        # keep only requested keys (missing -> None)
        out[-1] = {k: r.get(k) for k in cols}
    return out


def fetch_season(kind, rep, cols, season, a, b, label):
    d0 = dt.date.fromisoformat(a)
    end = dt.date.fromisoformat(b) + dt.timedelta(1)
    parts = []
    while d0 < end:
        d1 = min(d0 + dt.timedelta(10), end)
        part = pick(get(kind, rep, season, d0, d1), cols)
        parts.extend(part)
        print(f'  {label} {season} {d0}..{d1} +{len(part)} (cum {len(parts)})', flush=True)
        d0 = d1
    df = pd.DataFrame(parts)
    if len(df):
        df = df.drop_duplicates([c for c in ['playerId', 'gameId'] if c in df.columns] or ['gameId', 'teamAbbrev'])
    df['season'] = season
    return df


def main():
    # Skater points
    sk_frames = []
    for s, (a, b) in SEAS.items():
        fp = os.path.join(OUT, f'skater_points_{s}.pkl')
        if os.path.exists(fp) and s != 2026:
            print(f'skip existing {fp}', flush=True)
            sk_frames.append(pd.read_pickle(fp))
            continue
        df = fetch_season('skater', 'summary', SKATER_COLS, s, a, b, 'skater')
        df.to_pickle(fp)
        print(f'wrote {fp} {len(df)}', flush=True)
        sk_frames.append(df)
    sk = pd.concat(sk_frames, ignore_index=True) if sk_frames else pd.DataFrame()
    sk.to_pickle(os.path.join(OUT, 'skater_points.pkl'))
    print('skater_points total', len(sk), flush=True)

    # Goalies
    g_frames = []
    for s, (a, b) in SEAS.items():
        fp = os.path.join(OUT, f'goalie_saves_{s}.pkl')
        if os.path.exists(fp) and s != 2026:
            print(f'skip existing {fp}', flush=True)
            g_frames.append(pd.read_pickle(fp))
            continue
        df = fetch_season('goalie', 'summary', GOALIE_COLS, s, a, b, 'goalie')
        df.to_pickle(fp)
        print(f'wrote {fp} {len(df)}', flush=True)
        g_frames.append(df)
    g = pd.concat(g_frames, ignore_index=True) if g_frames else pd.DataFrame()
    g.to_pickle(os.path.join(OUT, 'goalie_saves.pkl'))
    print('goalie_saves total', len(g), flush=True)

    # Team games: start from a copy of challenger/team_games.pkl if present, refresh 2026
    team_src = os.path.join(ROOT, 'challenger', 'team_games.pkl')
    frames = []
    if os.path.exists(team_src):
        t0 = pd.read_pickle(team_src)
        # keep 2021-2025 fully; 2026 will be refetched
        frames.append(t0[t0.season != 2026] if 'season' in t0.columns else t0)
        print(f'copied prior team games {len(frames[0])} from challenger (non-2026)', flush=True)
    s, (a, b) = 2026, SEAS[2026]
    df = fetch_season('team', 'summary', TEAM_COLS, s, a, b, 'team')
    df.to_pickle(os.path.join(OUT, 'team_games_2026.pkl'))
    frames.append(df)
    # if no prior copy, also fetch 2021-2025
    have_prior = os.path.exists(team_src)
    if not have_prior:
        for s, (a, b) in SEAS.items():
            if s == 2026:
                continue
            frames.append(fetch_season('team', 'summary', TEAM_COLS, s, a, b, 'team'))
    team = pd.concat(frames, ignore_index=True)
    # 2026+ API omits teamAbbrev; fill from teamFullName and, if needed, the other row's opponentTeamAbbrev.
    NAME = {
        'Anaheim Ducks':'ANA','Boston Bruins':'BOS','Buffalo Sabres':'BUF','Calgary Flames':'CGY',
        'Carolina Hurricanes':'CAR','Chicago Blackhawks':'CHI','Colorado Avalanche':'COL',
        'Columbus Blue Jackets':'CBJ','Dallas Stars':'DAL','Detroit Red Wings':'DET',
        'Edmonton Oilers':'EDM','Florida Panthers':'FLA','Los Angeles Kings':'LAK',
        'Minnesota Wild':'MIN','Montreal Canadiens':'MTL','Montréal Canadiens':'MTL',
        'Nashville Predators':'NSH','New Jersey Devils':'NJD','New York Islanders':'NYI',
        'New York Rangers':'NYR','Ottawa Senators':'OTT','Philadelphia Flyers':'PHI',
        'Pittsburgh Penguins':'PIT','San Jose Sharks':'SJS','Seattle Kraken':'SEA',
        'St. Louis Blues':'STL','Tampa Bay Lightning':'TBL','Toronto Maple Leafs':'TOR',
        'Utah Mammoth':'UTA','Utah Hockey Club':'UTA','Vancouver Canucks':'VAN',
        'Vegas Golden Knights':'VGK','Washington Capitals':'WSH','Winnipeg Jets':'WPG',
    }
    if 'teamFullName' in team.columns:
        miss = team.teamAbbrev.isna() if 'teamAbbrev' in team.columns else slice(None)
        team.loc[miss, 'teamAbbrev'] = team.loc[miss, 'teamFullName'].map(NAME)
    if team.teamAbbrev.isna().any():
        filled = []
        for gid, g in team.groupby('gameId'):
            g = g.copy()
            if len(g) == 2 and g.teamAbbrev.isna().any():
                idx = g.index.tolist()
                if pd.isna(g.loc[idx[0], 'teamAbbrev']):
                    g.loc[idx[0], 'teamAbbrev'] = g.loc[idx[1], 'opponentTeamAbbrev']
                if pd.isna(g.loc[idx[1], 'teamAbbrev']):
                    g.loc[idx[1], 'teamAbbrev'] = g.loc[idx[0], 'opponentTeamAbbrev']
            filled.append(g)
        team = pd.concat(filled, ignore_index=True)
    if len(team):
        team = team[team.teamAbbrev.notna()].drop_duplicates(['gameId', 'teamAbbrev'])
    team.to_pickle(os.path.join(OUT, 'team_games.pkl'))
    print('team_games total', len(team), 'dates', team.gameDate.min() if len(team) else None, team.gameDate.max() if len(team) else None, flush=True)


if __name__ == '__main__':
    main()
