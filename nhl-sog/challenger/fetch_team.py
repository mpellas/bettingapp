"""Team game logs (goals for/against, shots for/against) for score-effect / strength features. Free NHL stats API.
-> challenger/team_games.pkl (one row per team-game; teamAbbrev = the other row's opponentTeamAbbrev)."""
import requests, pandas as pd, datetime as dt, os
B = 'https://api.nhle.com/stats/rest/en/team/summary'
rows = []
for s in range(2021, 2027):
    e = f'seasonId={s}{s+1} and gameTypeId=2'
    if s == 2026: e += f' and gameDate<"{dt.date.today().isoformat()}"'
    d = requests.get(B, params={'isAggregate': 'false', 'isGame': 'true', 'limit': -1, 'cayenneExp': e}, timeout=90).json()['data']
    for r in d: r['season'] = s
    rows += d; print(s, len(d), flush=True)
df = pd.DataFrame(rows)[['gameId', 'gameDate', 'season', 'homeRoad', 'opponentTeamAbbrev', 'goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame']]
other = df[['gameId', 'opponentTeamAbbrev', 'homeRoad']].copy()
df = df.merge(other.rename(columns={'opponentTeamAbbrev': 'teamAbbrev', 'homeRoad': 'hr2'}), on='gameId')
df = df[df.hr2 != df.homeRoad].drop(columns='hr2').drop_duplicates(['gameId', 'teamAbbrev'])
df.to_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'team_games.pkl'))
print(len(df), df.gameDate.min(), df.gameDate.max())
